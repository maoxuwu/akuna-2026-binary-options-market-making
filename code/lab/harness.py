"""本地 session 回测器：尽可能复刻评测端的市场机制。

    python3 harness.py

复刻的机制（依据题面 + 平台诊断日志观察）：
    - warm-up 历史 → warm_up()；
    - 每天：生成新期权、RFQ（最优价路由，可拆单；我方报价先插入、稳定
      排序 → 同价先成交我方，实验室约定非平台规则）、FOK（所有接受者按
      qty//n 平分，余数不分配，qty<n 时按列表顺序各 1 张——实验室约定，
      非平台规则，见 code/NOTE.md）、步进、到期结算、盘末破产检查；
    - 现金按最坏损失记账（买 q@p 占 q·p，卖占 q(1−p)，到期返还）；
    - 竞争对手仿真：常驻极端报价者（0.01/0.99 大量）、FixedWidth(w)
      （真值 ± w/2）——它们是 Akuna 的机器人，直接给真理论价。

流量模型【拍脑袋，方向校准自 平台诊断日志】：噪声流愿意付出大幅
过价（日志里 0.99 买 theo 0.11 的都有）；sharp 流能看到下一天的
标的（真逆向选择）。scenario 控制两者比例。

绝对数值无意义，用途：① 验证机制 ② 比较我们自己的参数变体。
"""

from __future__ import annotations

import math
import random
import statistics
from dataclasses import dataclass

from solution import (
    AJARAI_UNDERLYING_ID, FED_FUNDS_RATE_UNDERLYING_ID, THERIODIC_UNDERLYING_ID,
    BinaryOption, FokOrder, MarketHistory, MarketMaker, MarketParameters,
    OptionLeg, OrderType, Quote, Underlying, model_from_parameters,
    price_option_with_model,
)

WARMUP_DAYS = 250
SESSION_DAYS = 40
NEW_OPTIONS_PER_DAY = 3
RFQS_PER_DAY = 6
FOKS_PER_DAY = 4


# ---------------------------------------------------------------------------
# 对手做市商仿真（Akuna bots：直接知道真理论价）
# ---------------------------------------------------------------------------


class BotState:
    def __init__(self, name: str, cash: float):
        self.name = name
        self.cash = cash
        self.position: dict[int, int] = {}
        self.trades: dict[int, list[tuple[float, int]]] = {}
        self.bankrupt = False

    def book(self, option_id: int, price: float, qty: int) -> None:
        self.position[option_id] = self.position.get(option_id, 0) + qty
        self.trades.setdefault(option_id, []).append((price, qty))
        self.cash -= qty * price if qty > 0 else (-qty) * (1.0 - price)

    def settle(self, option: BinaryOption, payoff: float) -> None:
        for _, qty in self.trades.pop(option.option_id, []):
            self.cash += qty * payoff if qty > 0 else (-qty) * (1.0 - payoff)
        self.position.pop(option.option_id, None)


class StubQuoterBot:
    """0.01/0.99 大量报价；只接极端价 FOK。"""

    def __init__(self, cash: float):
        self.state = BotState("StubQuoter", cash)

    def quote(self, option, theo):
        return 0.01, 50, 0.99, 50

    def accept_fok(self, fok: FokOrder, theo: float) -> bool:
        if fok.order_type == OrderType.BUY:
            return fok.price >= 0.9
        return fok.price <= 0.1


class FixedWidthBot:
    """真值 ± w/2，固定数量；FOK 有正 edge 就接。"""

    def __init__(self, width: float, cash: float):
        self.width = width
        self.state = BotState(f"FixedWidth{width}", cash)

    def quote(self, option, theo):
        bid = max(math.floor((theo - self.width / 2) * 100) / 100, 0.0)
        offer = min(math.ceil((theo + self.width / 2) * 100) / 100, 1.0)
        if offer <= bid:
            offer = min(bid + 0.01, 1.0)
        if offer <= bid:
            bid = offer - 0.01
        return bid, 10, offer, 10

    def accept_fok(self, fok: FokOrder, theo: float) -> bool:
        if fok.order_type == OrderType.BUY:
            return fok.price - theo >= self.width / 2
        return theo - fok.price >= self.width / 2


# ---------------------------------------------------------------------------
# session 主循环
# ---------------------------------------------------------------------------


@dataclass
class SessionResult:
    ranking: list[tuple[str, float]]
    our_pnl: float
    our_rank: int
    bankrupt: bool
    fills: int
    fok_accepts: int
    fok_offers: int


def sample_parameters(rng: random.Random) -> MarketParameters:
    return MarketParameters(
        ajarai_drift=rng.uniform(-0.002, 0.003),
        ajarai_idio_std_dev=rng.uniform(0.008, 0.02),
        ajarai_rate_beta=rng.uniform(-0.04, 0.0),
        ajarai_sector_beta=rng.uniform(0.8, 1.2),
        rate_down_probability=rng.uniform(0.15, 0.3),
        rate_reversion_strength=rng.uniform(0.05, 0.15),
        rate_up_probability=rng.uniform(0.15, 0.3),
        sector_std_dev=rng.uniform(0.01, 0.03),
        theriodic_drift=rng.uniform(-0.002, 0.003),
        theriodic_idio_std_dev=rng.uniform(0.008, 0.02),
        theriodic_rate_beta=rng.uniform(-0.04, 0.0),
        theriodic_sector_beta=rng.uniform(0.8, 1.2),
    )


def run_session(seed: int, capital: float = 20.0,
                sharp_fraction: float = 0.2,
                noise_max_overpay: float = 0.5) -> SessionResult:
    rng = random.Random(seed)
    random.seed(seed * 7 + 1)  # 环境类内部用全局 random

    params = sample_parameters(rng)
    values = {FED_FUNDS_RATE_UNDERLYING_ID: 2.0,
              AJARAI_UNDERLYING_ID: rng.uniform(400, 1500),
              THERIODIC_UNDERLYING_ID: rng.uniform(400, 1500)}
    true_model = model_from_parameters(params)

    rows = {uid: [v] for uid, v in values.items()}
    for _ in range(WARMUP_DAYS - 1):
        values = params.advance_step(values)
        for uid, v in values.items():
            rows[uid].append(v)
    history = MarketHistory(values_by_underlying_id={
        uid: tuple(vs) for uid, vs in rows.items()})

    def underlyings() -> list[Underlying]:
        return [Underlying("FED", FED_FUNDS_RATE_UNDERLYING_ID,
                           values[FED_FUNDS_RATE_UNDERLYING_ID]),
                Underlying("AJR", AJARAI_UNDERLYING_ID, values[AJARAI_UNDERLYING_ID]),
                Underlying("THR", THERIODIC_UNDERLYING_ID, values[THERIODIC_UNDERLYING_ID])]

    option_id_counter = [0]
    active: list[BinaryOption] = []

    def spawn_option(days_left: int) -> BinaryOption | None:
        option_id_counter[0] += 1
        oid = option_id_counter[0]
        expiry = rng.randint(1, min(8, max(days_left, 1)))
        kind = rng.random()
        if kind < 0.3:
            grid = round(values[FED_FUNDS_RATE_UNDERLYING_ID] * 4) / 4
            strike = grid + 0.25 * rng.randint(-3, 3)
            return BinaryOption((OptionLeg(FED_FUNDS_RATE_UNDERLYING_ID, 1.0),),
                                oid, expiry, max(strike, 0.25))
        if kind < 0.85:
            uid = rng.choice([AJARAI_UNDERLYING_ID, THERIODIC_UNDERLYING_ID])
            strike = round(values[uid] * (1 + rng.uniform(-0.06, 0.06)), 2)
            return BinaryOption((OptionLeg(uid, 1.0),), oid, expiry, strike)
        legs = (OptionLeg(AJARAI_UNDERLYING_ID, 1.0),
                OptionLeg(THERIODIC_UNDERLYING_ID, -1.0))
        if rng.random() < 0.5:
            legs = (OptionLeg(AJARAI_UNDERLYING_ID, -1.0),
                    OptionLeg(THERIODIC_UNDERLYING_ID, 1.0))
        return BinaryOption(legs, oid, expiry, 0.0)

    mm = MarketMaker(underlyings(), [], capital)
    mm.warm_up(history)
    bots = [StubQuoterBot(capital), FixedWidthBot(0.1, capital), FixedWidthBot(0.05, capital)]
    our = BotState("Maoxu", capital)  # 影子账本（评测端视角）

    # 对手方池：固定 ID + 固定画像（平台诊断日志显示同一 ID 反复出现，
    # 这是对手方分型机制能起作用的前提）
    counterparties = [(rng.randint(100000, 999999), rng.random() < sharp_fraction)
                      for _ in range(8)]

    fills = fok_accepts = fok_offers = 0

    def theo(option: BinaryOption) -> float:
        return price_option_with_model(true_model, values, option)

    def next_day_theo(option: BinaryOption, next_values) -> float:
        return price_option_with_model(true_model, next_values, option.advance_step())

    for day in range(SESSION_DAYS):
        for _ in range(NEW_OPTIONS_PER_DAY):
            option = spawn_option(SESSION_DAYS - day)
            if option:
                active.append(option)
        # KNOWN SEAM (left as run, see code/NOTE.md): contracts spawned on
        # day >= 1 are traded before the end-of-day announce below reaches the
        # bot; one-day contracts spawned after day 0 are never announced.
        mm.on_step_advance(underlyings(), list(active)) if day == 0 else None

        # 预先抽出明天的市场（sharp 流看得到）
        next_values = params.advance_step(dict(values))

        # ---------------- RFQ ----------------
        for _ in range(RFQS_PER_DAY):
            if not active:
                break
            option = rng.choice(active)
            t = theo(option)
            is_buy = rng.random() < 0.5
            qty = rng.randint(1, 10)
            cp_id, sharp = rng.choice(counterparties)
            if sharp:
                t_next = next_day_theo(option, next_values)
                limit = t_next  # 只按明天的真值占便宜
            else:
                limit = t + rng.uniform(0, noise_max_overpay) * (1 if is_buy else -1)
            limit = min(max(limit, 0.0), 1.0)

            books: list[tuple[float, int, object]] = []
            if not our.bankrupt:
                q = mm.quote(option, cp_id)
                books.append((q.offer_price, q.offer_quantity, "us")
                             if is_buy else (q.bid_price, q.bid_quantity, "us"))
            for bot in bots:
                if bot.state.bankrupt:
                    continue
                bid, bq, offer, oq = bot.quote(option, t)
                books.append((offer, oq, bot) if is_buy else (bid, bq, bot))

            books.sort(key=lambda x: x[0], reverse=not is_buy)
            remaining = qty
            for price, avail, who in books:
                if remaining <= 0:
                    break
                if is_buy and price > limit:
                    break
                if not is_buy and price < limit:
                    break
                take = min(remaining, avail)
                remaining -= take
                signed = -take if is_buy else take  # 对手买 → 做市商卖出
                if who == "us":
                    mm.on_trade(option, price, signed, cp_id)
                    our.book(option.option_id, price, signed)
                    fills += 1
                else:
                    who.state.book(option.option_id, price, signed)

        # ---------------- FOK ----------------
        for _ in range(FOKS_PER_DAY):
            if not active:
                break
            option = rng.choice(active)
            t = theo(option)
            is_buy = rng.random() < 0.5
            qty = rng.randint(2, 30)
            cp_id, sharp = rng.choice(counterparties)
            if sharp:
                t_next = next_day_theo(option, next_values)
                price = t_next - 0.02 if is_buy else t_next + 0.02
            else:
                off = rng.uniform(0.05, noise_max_overpay)
                price = t + off if is_buy else t - off
            price = round(min(max(price, 0.0), 0.99), 2)
            fok = FokOrder(cp_id, option.option_id,
                           OrderType.BUY if is_buy else OrderType.SELL, price, qty)

            accepters = []
            if not our.bankrupt:
                fok_offers += 1
                if mm.respond_to_fok(option, fok):
                    accepters.append("us")
                    fok_accepts += 1
            for bot in bots:
                if not bot.state.bankrupt and bot.accept_fok(fok, t):
                    accepters.append(bot)
            if accepters:
                # 实验室约定：floor 分单，余数不分配；qty<n 时按列表顺序各 1 张
                # （lab convention, not an observed platform rule — see code/NOTE.md）
                share = max(qty // len(accepters), 1)
                left = qty
                for who in accepters:
                    take = min(share, left)
                    if take <= 0:
                        break
                    left -= take
                    signed = -take if is_buy else take
                    if who == "us":
                        mm.on_trade(option, price, signed, cp_id)
                        our.book(option.option_id, price, signed)
                        fills += 1
                    else:
                        who.state.book(option.option_id, price, signed)

        # ---------------- 步进 + 到期 + 破产 ----------------
        values = next_values
        advanced = []
        for option in active:
            nxt = option.advance_step()
            if option.steps_until_expiry <= 1:  # 步进后到 0 → 结算
                payoff = nxt.expiry_valuation(values)
                our.settle(nxt, payoff)
                for bot in bots:
                    bot.state.settle(nxt, payoff)
            else:
                advanced.append(nxt)
        active = advanced

        if not our.bankrupt:
            mm.on_step_advance(underlyings(), list(active))
        for state in [our] + [b.state for b in bots]:
            if not state.bankrupt and state.cash < 0:
                state.bankrupt = True

    ranking = sorted(
        [(our.name, round(our.cash - capital, 2))]
        + [(b.state.name, round(b.state.cash - capital, 2)) for b in bots],
        key=lambda x: x[1], reverse=True)
    our_rank = [n for n, _ in ranking].index("Maoxu") + 1
    return SessionResult(ranking, round(our.cash - capital, 2), our_rank,
                         our.bankrupt, fills, fok_accepts, fok_offers)


SCENARIOS = {
    "calm_dumb": dict(sharp_fraction=0.1, noise_max_overpay=0.5),
    "mixed": dict(sharp_fraction=0.25, noise_max_overpay=0.3),
    "toxic": dict(sharp_fraction=0.55, noise_max_overpay=0.15),
}


def main() -> None:
    for name, kw in SCENARIOS.items():
        results = [run_session(seed, capital=random.Random(seed).choice([10.0, 20.0, 40.0]), **kw)
                   for seed in range(12)]
        pnls = [r.our_pnl for r in results]
        ranks = [r.our_rank for r in results]
        wins = sum(1 for r in ranks if r == 1)
        se = statistics.stdev(pnls) / math.sqrt(len(pnls)) if len(pnls) > 1 else 0
        print(f"{name:10s} pnl={statistics.mean(pnls):7.2f} ±{se:5.2f} "
              f"rank_avg={statistics.mean(ranks):.2f} wins={wins}/12 "
              f"bankrupt={sum(r.bankrupt for r in results)} "
              f"fills={statistics.mean([r.fills for r in results]):5.1f} "
              f"fok={statistics.mean([r.fok_accepts for r in results]):4.1f}"
              f"/{statistics.mean([r.fok_offers for r in results]):.1f}")


if __name__ == "__main__":
    main()

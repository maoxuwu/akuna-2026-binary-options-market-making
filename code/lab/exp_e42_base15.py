"""E42 粗筛：base_quote_size 10 vs 15 的 harness 配对 A/B。

    python3 exp_e42_base15.py

背景（菜单 ②）：cap-40 场 per_quote 预算 0.16×24 ≈ 3.84，价 0.3 时
qty = 12.8 > 10 → base_quote_size 10 是绑定约束；15 解绑。
但 harness 的 RFQ 客户单量是 1-10 张 → 成交 = min(客户量, 我们挂量)，
挂 10 与 15 应当逐位恒等（预测：qty_max=10 的所有 Δ = 0）。
真实平台客户单量 ≤30（E40 结论），所以再跑一版 RFQ 单量 1-30 的
变体——那才是这个旋钮真正暴露的世界。

判定（双关纪律第二关）：qty30 版三场景配对非劣（尤其 toxic 不能
显著变差）才允许上真集。
"""

import math
import random
import statistics

from harness import (
    FixedWidthBot, StubQuoterBot, WARMUP_DAYS, SESSION_DAYS,
    NEW_OPTIONS_PER_DAY, RFQS_PER_DAY, FOKS_PER_DAY, sample_parameters,
    BotState,
)
from solution import (
    AJARAI_UNDERLYING_ID, FED_FUNDS_RATE_UNDERLYING_ID, THERIODIC_UNDERLYING_ID,
    BinaryOption, CFG, FokOrder, MarketHistory, MarketMaker, OptionLeg,
    OrderType, Underlying, model_from_parameters, price_option_with_model,
)

SCENARIOS = {
    "calm_dumb": dict(sharp_fraction=0.1, noise_max_overpay=0.5),
    "mixed": dict(sharp_fraction=0.25, noise_max_overpay=0.3),
    "toxic": dict(sharp_fraction=0.55, noise_max_overpay=0.15),
}


def run_session(seed: int, capital: float, sharp_fraction: float,
                noise_max_overpay: float, rfq_qty_max: int):
    rng = random.Random(seed)
    random.seed(seed * 7 + 1)

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

    def underlyings():
        return [Underlying("FED", FED_FUNDS_RATE_UNDERLYING_ID,
                           values[FED_FUNDS_RATE_UNDERLYING_ID]),
                Underlying("AJR", AJARAI_UNDERLYING_ID, values[AJARAI_UNDERLYING_ID]),
                Underlying("THR", THERIODIC_UNDERLYING_ID, values[THERIODIC_UNDERLYING_ID])]

    option_id_counter = [0]
    active: list[BinaryOption] = []

    def spawn_option(days_left: int):
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
    our = BotState("Maoxu", capital)

    counterparties = [(rng.randint(100000, 999999), rng.random() < sharp_fraction)
                      for _ in range(8)]

    def theo(option):
        return price_option_with_model(true_model, values, option)

    def next_day_theo(option, next_values):
        return price_option_with_model(true_model, next_values, option.advance_step())

    for day in range(SESSION_DAYS):
        for _ in range(NEW_OPTIONS_PER_DAY):
            option = spawn_option(SESSION_DAYS - day)
            if option:
                active.append(option)
        # KNOWN SEAM (left as run, see code/NOTE.md): same announcement-timing
        # seam as harness.py; also inherited by exp_ablation.py via import.
        mm.on_step_advance(underlyings(), list(active)) if day == 0 else None

        next_values = params.advance_step(dict(values))

        for _ in range(RFQS_PER_DAY):
            if not active:
                break
            option = rng.choice(active)
            t = theo(option)
            is_buy = rng.random() < 0.5
            qty = rng.randint(1, rfq_qty_max)
            cp_id, sharp = rng.choice(counterparties)
            if sharp:
                limit = next_day_theo(option, next_values)
            else:
                limit = t + rng.uniform(0, noise_max_overpay) * (1 if is_buy else -1)
            limit = min(max(limit, 0.0), 1.0)

            books = []
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
                signed = -take if is_buy else take
                if who == "us":
                    mm.on_trade(option, price, signed, cp_id)
                    our.book(option.option_id, price, signed)
                else:
                    who.state.book(option.option_id, price, signed)

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
            if not our.bankrupt and mm.respond_to_fok(option, fok):
                accepters.append("us")
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
                    else:
                        who.state.book(option.option_id, price, signed)

        values = next_values
        advanced = []
        for option in active:
            nxt = option.advance_step()
            if option.steps_until_expiry <= 1:
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

    names = [(our.cash - capital, "us")] + \
        [(b.state.cash - capital, b.state.name) for b in bots]
    names.sort(reverse=True)
    rank = [n for _, n in names].index("us") + 1
    return dict(pnl=round(our.cash - capital, 2), rank=rank, bankrupt=our.bankrupt)


def main():
    for qty_max in (10, 30):
        print(f"\n========== RFQ 客户单量 1-{qty_max} ==========")
        for scen, kw in SCENARIOS.items():
            deltas, rank_moves = [], 0
            bank10 = bank15 = 0
            for seed in range(20):
                capital = random.Random(seed).choice([10.0, 20.0, 40.0])
                CFG["base_quote_size"] = 10
                a = run_session(seed, capital, rfq_qty_max=qty_max, **kw)
                CFG["base_quote_size"] = 15
                b = run_session(seed, capital, rfq_qty_max=qty_max, **kw)
                CFG["base_quote_size"] = 10
                deltas.append(b["pnl"] - a["pnl"])
                rank_moves += (a["rank"] - b["rank"])  # 正 = 15 排名更好
                bank10 += a["bankrupt"]
                bank15 += b["bankrupt"]
            n = len(deltas)
            se = statistics.stdev(deltas) / math.sqrt(n) if n > 1 else 0.0
            nz = sum(1 for d in deltas if abs(d) > 1e-9)
            print(f"{scen:10s} Δpnl(15−10)={statistics.mean(deltas):+7.2f} ±{se:5.2f} "
                  f"min={min(deltas):+7.2f} max={max(deltas):+7.2f} "
                  f"非零Δ={nz}/{n} 排名净移动={rank_moves:+d} "
                  f"破产 10挡={bank10} 15挡={bank15}")


if __name__ == "__main__":
    main()

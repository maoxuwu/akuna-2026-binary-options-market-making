"""场中毒性翻转实验：补上 ramp 认证的保留意见（harness 无翻转场景）。

    python3 exp_toxicity_flip.py

设计：
  - 复用 harness 的世界生成与撮合循环，但第 flip_day 天流量制度切换
    （calm→toxic 或反向）。对手方 **ID 不变、sharp 身份重抽**——
    这是对我们机制最恶意的构造：前半场攒出"清白豁免"（正 markout
    历史）的对手，后半场变成狙击手，恰好钻 E18 反转默认的空子；
    同时 ramp 在前半场盈利后加大了预算。
  - 配对变体：v11 原样 vs size_ramp_mult=0（关 ramp）。同种子 =
    同世界（环境生成与我们行为无关，rng 消耗数逐日恒定），
    差值完全归因于 ramp。
  - 读数：终盘 PnL 配对差、翻转后半场 PnL 配对差（"先赚后跌回吐"
    恐惧模式的直接测量）、破产数、最差单场差。

判定标准（与 E29-E31 认证同口径）：ramp 配对均值非劣（Δ ≥ −SE 量级）
且零破产、无灾难尾部（min Δ 不深于单场正常噪声）。
"""

import math
import random
import statistics

from harness import (
    FixedWidthBot, StubQuoterBot, WARMUP_DAYS, SESSION_DAYS,
    NEW_OPTIONS_PER_DAY, RFQS_PER_DAY, FOKS_PER_DAY, sample_parameters,
)
from solution import (
    AJARAI_UNDERLYING_ID, FED_FUNDS_RATE_UNDERLYING_ID, THERIODIC_UNDERLYING_ID,
    BinaryOption, CFG, FokOrder, MarketHistory, MarketMaker, OptionLeg,
    OrderType, Underlying, model_from_parameters, price_option_with_model,
)
from harness import BotState

FLIP_DAY = 20

REGIMES = {
    "calm": dict(sharp_fraction=0.1, noise_max_overpay=0.5),
    "toxic": dict(sharp_fraction=0.55, noise_max_overpay=0.15),
}


def run_flip_session(seed: int, capital: float, regime_a: str, regime_b: str):
    """与 harness.run_session 同构，仅流量制度在 FLIP_DAY 切换。"""
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

    frac_a = REGIMES[regime_a]["sharp_fraction"]
    counterparties = [[rng.randint(100000, 999999), rng.random() < frac_a]
                      for _ in range(8)]

    pnl_at_flip = 0.0

    def theo(option):
        return price_option_with_model(true_model, values, option)

    def next_day_theo(option, next_values):
        return price_option_with_model(true_model, next_values, option.advance_step())

    for day in range(SESSION_DAYS):
        regime = regime_a if day < FLIP_DAY else regime_b
        overpay = REGIMES[regime]["noise_max_overpay"]
        if day == FLIP_DAY:
            # ID 不变、身份重抽：前半场的"清白"对手可能变狙击手
            frac_b = REGIMES[regime_b]["sharp_fraction"]
            for cp in counterparties:
                cp[1] = rng.random() < frac_b
            pnl_at_flip = our.cash - capital  # 已实现口径（在途持仓不计）

        for _ in range(NEW_OPTIONS_PER_DAY):
            option = spawn_option(SESSION_DAYS - day)
            if option:
                active.append(option)
        # KNOWN SEAM (left as run, see code/NOTE.md): same announcement-timing
        # seam as harness.py.
        mm.on_step_advance(underlyings(), list(active)) if day == 0 else None

        next_values = params.advance_step(dict(values))

        for _ in range(RFQS_PER_DAY):
            if not active:
                break
            option = rng.choice(active)
            t = theo(option)
            is_buy = rng.random() < 0.5
            qty = rng.randint(1, 10)
            cp_id, sharp = rng.choice(counterparties)
            if sharp:
                limit = next_day_theo(option, next_values)
            else:
                limit = t + rng.uniform(0, overpay) * (1 if is_buy else -1)
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
                off = rng.uniform(0.05, overpay)
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

    return dict(pnl=round(our.cash - capital, 2),
                pnl_at_flip=round(pnl_at_flip, 2),
                bankrupt=our.bankrupt)


def paired_run(direction: tuple[str, str], seeds: range) -> None:
    a, b = direction
    deltas, post_deltas, rows = [], [], []
    bank_on = bank_off = 0
    original_mult = CFG["size_ramp_mult"]
    for seed in seeds:
        capital = random.Random(seed).choice([10.0, 20.0, 40.0])
        CFG["size_ramp_mult"] = original_mult
        on = run_flip_session(seed, capital, a, b)
        CFG["size_ramp_mult"] = 0.0
        off = run_flip_session(seed, capital, a, b)
        CFG["size_ramp_mult"] = original_mult
        d = on["pnl"] - off["pnl"]
        dp = (on["pnl"] - on["pnl_at_flip"]) - (off["pnl"] - off["pnl_at_flip"])
        deltas.append(d)
        post_deltas.append(dp)
        bank_on += on["bankrupt"]
        bank_off += off["bankrupt"]
        rows.append((seed, capital, on["pnl"], off["pnl"], d, dp))
    n = len(deltas)
    se = statistics.stdev(deltas) / math.sqrt(n) if n > 1 else 0.0
    se_p = statistics.stdev(post_deltas) / math.sqrt(n) if n > 1 else 0.0
    print(f"\n=== {a} → {b}（flip@{FLIP_DAY}）, {n} 配对种子 ===")
    print(f"Δ终盘 PnL (ramp−noramp): {statistics.mean(deltas):+.2f} ± {se:.2f}"
          f"   min={min(deltas):+.2f}  max={max(deltas):+.2f}")
    print(f"Δ翻转后半场 PnL:        {statistics.mean(post_deltas):+.2f} ± {se_p:.2f}"
          f"   min={min(post_deltas):+.2f}")
    print(f"破产: ramp={bank_on}  noramp={bank_off}")
    neg_on = sum(1 for r in rows if r[2] < 0)
    neg_off = sum(1 for r in rows if r[3] < 0)
    flips = [(s, c, pon, poff) for s, c, pon, poff, _, _ in rows
             if poff >= 0 > pon]
    print(f"亏损场: ramp={neg_on}  noramp={neg_off}  "
          f"赢→亏符号翻转: {len(flips)} {flips if flips else ''}")
    print(f"绝对 PnL 均值: ramp={statistics.mean([r[2] for r in rows]):+.2f}  "
          f"noramp={statistics.mean([r[3] for r in rows]):+.2f}")
    worst = sorted(rows, key=lambda r: r[4])[:3]
    for seed, cap, pon, poff, d, dp in worst:
        print(f"  最差种子 {seed} (cap {cap:.0f}): on={pon:+.2f} off={poff:+.2f}"
              f" Δ={d:+.2f} Δ后半场={dp:+.2f}")


if __name__ == "__main__":
    paired_run(("calm", "toxic"), range(30))
    paired_run(("toxic", "calm"), range(30))

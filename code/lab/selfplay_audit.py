# NOTE (publication): parameter values in this file are arbitrary plausible stand-ins, not the competition values.
"""对抗审计（第二轮备战）：feed-then-snipe 攻击我们的 FOK 通道。

    python3 selfplay_audit.py

攻击者假设：第二轮对手可以以对手方身份发 FOK（规则未知，按保守
假设审计），带次日信息，会最优化下单量与价格（逐步加价直到我们
接受——测试剂量天花板能否被硬钱压穿）。

剧本 A（裸狙击）：直接在 1d ATM（theo 日波动最大的 kill zone）
用价格阶梯探我们的门槛，最大量 FOK。
剧本 B（喂食后狙击）：先送 3+ 笔对我们有利的小单攒正 markout
（清白状态 → vol 溢价归零），再狙击。

量化：狙击手总利润（≈我们的损失）、被接受笔数、防线首拒日、
markout 样本数（确认防线真的看到了数据）。
"""
import random
import statistics
import sys
from dataclasses import replace

sys.path.insert(0, "<WORKDIR>/akuna2026")

from solution import (
    AJARAI_UNDERLYING_ID, FED_FUNDS_RATE_UNDERLYING_ID, THERIODIC_UNDERLYING_ID,
    BinaryOption, FokOrder, MarketHistory, MarketMaker, MarketParameters,
    OptionLeg, OrderType, Underlying, model_from_parameters,
    price_option_with_model,
)

PARAMS = MarketParameters(
    ajarai_drift=0.0008, ajarai_idio_std_dev=0.012, ajarai_rate_beta=-0.017,
    ajarai_sector_beta=1.0, rate_down_probability=0.21,
    rate_reversion_strength=0.09, rate_up_probability=0.24,
    sector_std_dev=0.024, theriodic_drift=0.0011, theriodic_idio_std_dev=0.015,
    theriodic_rate_beta=-0.011, theriodic_sector_beta=1.0)
TRUE_MODEL = model_from_parameters(PARAMS)
SNIPER = 666001
MARGINS = (0.021, 0.05, 0.08, 0.12, 0.16, 0.25, 0.37, 0.45)


def underlyings(values):
    return [Underlying("FED", FED_FUNDS_RATE_UNDERLYING_ID,
                       values[FED_FUNDS_RATE_UNDERLYING_ID]),
            Underlying("AJR", AJARAI_UNDERLYING_ID, values[AJARAI_UNDERLYING_ID]),
            Underlying("THR", THERIODIC_UNDERLYING_ID, values[THERIODIC_UNDERLYING_ID])]


def run_attack(seed, capital=40.0, feed_days=0, snipe_days=12, max_qty=30):
    random.seed(seed * 13 + 7)
    values = {FED_FUNDS_RATE_UNDERLYING_ID: 2.0,
              AJARAI_UNDERLYING_ID: 1000.0, THERIODIC_UNDERLYING_ID: 900.0}
    rows = {uid: [v] for uid, v in values.items()}
    for _ in range(299):
        values = PARAMS.advance_step(values)
        for uid, v in values.items():
            rows[uid].append(v)

    mm = MarketMaker(underlyings(values), [], capital)
    mm.warm_up(MarketHistory(values_by_underlying_id={
        uid: tuple(vs) for uid, vs in rows.items()}))

    spawned = []   # (option_at_spawn, spawn_day)
    oid = [0]

    def current_options(day):
        out = []
        for opt, d0 in spawned:
            left = opt.steps_until_expiry - (day - d0)
            if left > 0:
                out.append(replace(opt, steps_until_expiry=left))
        return out

    sniper_profit = 0.0
    accepted = 0
    first_reject = None
    total_days = feed_days + snipe_days

    for day in range(total_days):
        next_values = PARAMS.advance_step(dict(values))
        oid[0] += 1

        if day < feed_days:
            strike = round(values[AJARAI_UNDERLYING_ID] * 1.05, 2)
            option = BinaryOption((OptionLeg(AJARAI_UNDERLYING_ID, 1.0),),
                                  oid[0], 6, strike)
            spawned.append((option, day))
            mm.on_step_advance(underlyings(values), current_options(day))
            theo = price_option_with_model(TRUE_MODEL, values, option)
            theo_next = price_option_with_model(
                TRUE_MODEL, next_values, option.advance_step())
            if theo_next >= theo:   # 次日 theo 涨 → 卖给我们攒正 markout
                fok = FokOrder(SNIPER, oid[0], OrderType.SELL,
                               round(max(theo - 0.10, 0.01), 2), 1)
                if mm.respond_to_fok(option, fok):
                    mm.on_trade(option, fok.price, 1, SNIPER)
                    sniper_profit -= (theo - fok.price)
        else:
            strike = round(values[AJARAI_UNDERLYING_ID], 2)
            option = BinaryOption((OptionLeg(AJARAI_UNDERLYING_ID, 1.0),),
                                  oid[0], 1, strike)
            spawned.append((option, day))
            mm.on_step_advance(underlyings(values), current_options(day))
            theo = price_option_with_model(TRUE_MODEL, values, option)
            payoff = option.advance_step().expiry_valuation(next_values)
            hit = False
            for qty in (max_qty, 20, 10, 5, 2, 1):
                for margin in MARGINS:
                    if payoff >= 0.5:
                        price = round(min(theo + margin, 0.99), 2)
                        fok = FokOrder(SNIPER, oid[0], OrderType.BUY, price, qty)
                        if mm.respond_to_fok(option, fok):
                            mm.on_trade(option, price, -qty, SNIPER)
                            sniper_profit += (1.0 - price) * qty
                            hit = True
                    else:
                        price = round(max(theo - margin, 0.01), 2)
                        fok = FokOrder(SNIPER, oid[0], OrderType.SELL, price, qty)
                        if mm.respond_to_fok(option, fok):
                            mm.on_trade(option, price, qty, SNIPER)
                            sniper_profit += price * qty
                            hit = True
                    if hit:
                        break
                if hit:
                    break
            if hit:
                accepted += 1
            elif first_reject is None:
                first_reject = day - feed_days
        values = next_values

    # 推进一天让最后的到期结算
    mm.on_step_advance(underlyings(values), [])
    return (sniper_profit, accepted, first_reject,
            len(mm._fok_markouts), round(mm._mirror_cash - capital, 2))


for label, feed in (("裸狙击(A)", 0), ("喂食后狙击(B)", 6)):
    profits, snipes, rejects, pnls = [], [], [], []
    for seed in range(10):
        p, n, fr, nmark, mmpnl = run_attack(seed, feed_days=feed)
        profits.append(p)
        snipes.append(n)
        rejects.append(fr if fr is not None else 99)
        pnls.append(mmpnl)
    print(f"{label}: 狙击手均利={statistics.mean(profits):7.2f} "
          f"最大={max(profits):7.2f} 接受笔数均={statistics.mean(snipes):.1f} "
          f"首拒日中位={statistics.median(rejects):.0f} "
          f"我方镜像pnl均={statistics.mean(pnls):7.2f} markout_n={nmark}")

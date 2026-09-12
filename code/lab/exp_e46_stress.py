# NOTE (publication): parameter values in this file are arbitrary plausible stand-ins, not the competition values.
"""E46/E47：结构化最坏环境扫雷 + 超时免疫定量基准。

    python3 exp_e46_stress.py

fuzz_solution 是随机操作序列；这里补**结构化**对抗环境（隐藏用例
最可能的藏身处）：参数取值边界（无回归/概率贴边/冻结利率/零相关/
巨漂移/巨波动/远离目标的起点）、资本边界（1/5/500）、session 形状
（5 天短场 / 100 天长场 / 期权洪峰 50 只/天）。
硬断言：① 不崩；② 不破产；③ 影子账本与镜像现金一致（<1e-6，
在全部结算后）；④ 报价永远合法（Quote 构造器自证）。
E47 基准：洪峰负载下逐环节计时，给 README「超时免疫」一个实测数。
"""
import math
import random
import statistics
import sys
import time

BASE = "<WORKDIR>/akuna2026"
sys.path.insert(0, BASE)

from solution import (
    AJARAI_UNDERLYING_ID as AJR, FED_FUNDS_RATE_UNDERLYING_ID as FED,
    THERIODIC_UNDERLYING_ID as THR, BinaryOption, FokOrder, MarketHistory,
    MarketMaker, MarketParameters, OptionLeg, OrderType, Underlying,
)

BOUNDARY_PARAMS = {
    "no_reversion": dict(rate_reversion_strength=0.0),
    "prob_edge": dict(rate_up_probability=0.49, rate_down_probability=0.5,
                      rate_reversion_strength=0.01),
    "frozen_rate": dict(rate_up_probability=0.01, rate_down_probability=0.01),
    "zero_sector": dict(sector_std_dev=0.0),
    "huge_drift": dict(ajarai_drift=0.05, theriodic_drift=-0.05),
    "huge_vol": dict(ajarai_idio_std_dev=0.2, theriodic_idio_std_dev=0.2,
                     sector_std_dev=0.1),
    "far_from_target": dict(rate_reversion_strength=0.5),
}

BASE_PARAMS = dict(
    ajarai_drift=0.0008, ajarai_idio_std_dev=0.015, ajarai_rate_beta=-0.017,
    ajarai_sector_beta=1.0, rate_down_probability=0.21,
    rate_reversion_strength=0.09, rate_up_probability=0.24,
    sector_std_dev=0.024, theriodic_drift=0.0011, theriodic_idio_std_dev=0.015,
    theriodic_rate_beta=-0.011, theriodic_sector_beta=1.0)


def underlyings(values):
    return [Underlying("FED", FED, values[FED]),
            Underlying("AJR", AJR, values[AJR]),
            Underlying("THR", THR, values[THR])]


def run_stress(name, overrides, seed, capital=20.0, days=40, warmup=250,
               opts_per_day=3, r0=2.0):
    rng = random.Random(seed)
    random.seed(seed * 101 + 9)
    params = MarketParameters(**{**BASE_PARAMS, **overrides})
    values = {FED: r0, AJR: rng.uniform(50, 3000), THR: rng.uniform(50, 3000)}
    rows = {uid: [v] for uid, v in values.items()}
    for _ in range(warmup - 1):
        values = params.advance_step(values)
        for uid, v in values.items():
            rows[uid].append(v)
    # 巨漂移下公司价可能被四舍五入到 0.0——这本身就是要测的退化输入
    mm = MarketMaker(underlyings(values), [], capital)
    mm.warm_up(MarketHistory(values_by_underlying_id={
        uid: tuple(vs) for uid, vs in rows.items()}))

    shadow_cash = capital
    trades = {}
    specs = []
    oid = [0]

    def spawn():
        oid[0] += 1
        kind = rng.random()
        expiry = rng.randint(1, 8)
        if kind < 0.3:
            strike = max(round(values[FED] * 4) / 4 + 0.25 * rng.randint(-3, 3), 0.25)
            legs = (OptionLeg(FED, 1.0),)
        elif kind < 0.85:
            uid = rng.choice([AJR, THR])
            base = values[uid] if values[uid] > 0 else 1.0
            strike = round(base * (1 + rng.uniform(-0.1, 0.1)), 2)
            legs = (OptionLeg(uid, 1.0),)
        else:
            legs = ((OptionLeg(AJR, 1.0), OptionLeg(THR, -1.0))
                    if rng.random() < 0.5
                    else (OptionLeg(AJR, -1.0), OptionLeg(THR, 1.0)))
            strike = 0.0
        return [oid[0], legs, expiry, strike]

    def book(o, price, signed):
        trades.setdefault(o, []).append((price, signed))
        nonlocal shadow_cash
        shadow_cash -= signed * price if signed > 0 else -signed * (1.0 - price)

    for day in range(days):
        for _ in range(opts_per_day):
            specs.append(spawn())
        live = [s for s in specs if s[2] > 0]
        mm.on_step_advance(underlyings(values), [
            BinaryOption(s[1], s[0], s[2], s[3]) for s in live])
        for _ in range(6):
            if not live:
                break
            s = rng.choice(live)
            opt = BinaryOption(s[1], s[0], s[2], s[3])
            q = mm.quote(opt, rng.randint(1, 8))          # 构造器自证合法
            if rng.random() < 0.4:                        # 随机成交其一侧
                if rng.random() < 0.5:
                    take = min(rng.randint(1, 10), q.bid_quantity)
                    mm.on_trade(opt, q.bid_price, take, 77)
                    book(s[0], q.bid_price, take)
                else:
                    take = min(rng.randint(1, 10), q.offer_quantity)
                    mm.on_trade(opt, q.offer_price, -take, 77)
                    book(s[0], q.offer_price, -take)
        for _ in range(4):
            if not live:
                break
            s = rng.choice(live)
            opt = BinaryOption(s[1], s[0], s[2], s[3])
            price = round(rng.uniform(0.01, 0.99), 2)
            side = rng.choice([OrderType.BUY, OrderType.SELL])
            fok = FokOrder(rng.randint(1, 8), s[0], side, price, rng.randint(1, 30))
            if mm.respond_to_fok(opt, fok):
                signed = -fok.quantity if side == OrderType.BUY else fok.quantity
                mm.on_trade(opt, price, signed, fok.counterparty_id)
                book(s[0], price, signed)

        values = params.advance_step(values)
        for s in specs:
            if s[2] > 0:
                s[2] -= 1
                if s[2] == 0:
                    obs = sum(w.weight * values[w.underlying_id] for w in s[1])
                    payoff = 1.0 if obs >= s[3] else 0.0
                    for price, signed in trades.pop(s[0], []):
                        shadow_cash += (signed * payoff if signed > 0
                                        else -signed * (1.0 - payoff))
        assert shadow_cash >= 0, f"{name} seed {seed}: 破产 cash={shadow_cash:.4f}"

    # 主循环最后一天的到期要先在当前行情下 announce 给 mm（否则清场
    # 循环先推进行情，mm 会用晚一天的标的值结算这批期权 → 账本分叉）
    mm.on_step_advance(underlyings(values), [
        BinaryOption(s[1], s[0], s[2], s[3]) for s in specs if s[2] > 0])
    # 清场结算
    for _ in range(10):
        values = params.advance_step(values)
        for s in specs:
            if s[2] > 0:
                s[2] -= 1
                if s[2] == 0:
                    obs = sum(w.weight * values[w.underlying_id] for w in s[1])
                    payoff = 1.0 if obs >= s[3] else 0.0
                    for price, signed in trades.pop(s[0], []):
                        shadow_cash += (signed * payoff if signed > 0
                                        else -signed * (1.0 - payoff))
        mm.on_step_advance(underlyings(values), [
            BinaryOption(s[1], s[0], s[2], s[3]) for s in specs if s[2] > 0])

    drift = (mm._mirror_cash - capital) - (shadow_cash - capital)
    assert abs(drift) < 1e-6, f"{name} seed {seed}: 镜像漂移 {drift}"
    return shadow_cash - capital, mm._error_count


def stress_battery():
    print("== E46 结构化对抗环境（每配置 3 种子）==")
    rows = []
    for name, ov in BOUNDARY_PARAMS.items():
        kw = dict(r0=8.0) if name == "far_from_target" else {}
        for seed in range(3):
            pnl, errs = run_stress(name, ov, seed, **kw)
            rows.append((name, seed, pnl, errs))
    for cap in (1.0, 5.0, 500.0):
        for seed in range(3):
            pnl, errs = run_stress(f"capital_{cap:g}", {}, seed, capital=cap)
            rows.append((f"capital_{cap:g}", seed, pnl, errs))
    for days, warm in ((5, 2), (100, 400)):
        for seed in range(3):
            pnl, errs = run_stress(f"days_{days}_warm_{warm}", {}, seed,
                                   days=days, warmup=warm)
            rows.append((f"days_{days}", seed, pnl, errs))
    for seed in range(3):
        pnl, errs = run_stress("option_flood_50pd", {}, seed, opts_per_day=50)
        rows.append(("flood_50pd", seed, pnl, errs))
    by = {}
    for name, seed, pnl, errs in rows:
        by.setdefault(name, []).append((pnl, errs))
    for name, xs in by.items():
        pnls = [p for p, _ in xs]
        errs = max(e for _, e in xs)
        print(f"  {name:18s} pnl=[{min(pnls):+9.2f}, {max(pnls):+9.2f}] "
              f"max_error_count={errs}  破产=0 镜像漂移<1e-6 ✓")
    print(f"  合计 {len(rows)} 场全过（不崩/不破产/账本守恒/报价合法）")


def latency_bench():
    print("\n== E47 超时基准（洪峰负载）==")
    rng = random.Random(0)
    random.seed(11)
    params = MarketParameters(**BASE_PARAMS)
    values = {FED: 2.0, AJR: 800.0, THR: 900.0}
    rows = {uid: [v] for uid, v in values.items()}
    for _ in range(399):
        values = params.advance_step(values)
        for uid, v in values.items():
            rows[uid].append(v)
    mm = MarketMaker(underlyings(values), [], 40.0)
    t0 = time.perf_counter()
    mm.warm_up(MarketHistory(values_by_underlying_id={
        uid: tuple(vs) for uid, vs in rows.items()}))
    t_warm = time.perf_counter() - t0

    # 200 只在场期权（远超真实 ~3/天×8天≈24 的量级）
    opts = []
    for i in range(200):
        kind = i % 3
        d = 1 + i % 10
        if kind == 0:
            opts.append(BinaryOption((OptionLeg(FED, 1.0),), i + 1, d,
                                     max(0.25, 2.0 + 0.25 * (i % 7 - 3))))
        elif kind == 1:
            uid = AJR if i % 2 else THR
            opts.append(BinaryOption((OptionLeg(uid, 1.0),), i + 1, d,
                                     round(values[uid] * (1 + (i % 13 - 6) / 100), 2)))
        else:
            opts.append(BinaryOption(
                (OptionLeg(AJR, 1.0), OptionLeg(THR, -1.0)), i + 1, d, 0.0))
    mm.on_step_advance(underlyings(values), opts)

    t0 = time.perf_counter()
    for o in opts:
        mm.quote(o, 5)
    t_quote = time.perf_counter() - t0
    t0 = time.perf_counter()
    for o in opts:
        mm.respond_to_fok(o, FokOrder(5, o.option_id, OrderType.BUY, 0.6, 5))
    t_fok = time.perf_counter() - t0
    # 制造 200 笔 pending markout 后步进（最重的回调路径）
    for o in opts[:200]:
        mm.on_trade(o, 0.5, 1, 5)
    t0 = time.perf_counter()
    mm.on_step_advance(underlyings(values), [o.advance_step() for o in opts])
    t_adv = time.perf_counter() - t0

    # MC 兜底：三腿奇异合约 10d（唯一非解析路径）冷/热
    exotic = BinaryOption((OptionLeg(FED, 50.0), OptionLeg(AJR, 1.0),
                           OptionLeg(THR, 1.0)), 9999, 10, 1500.0)
    t0 = time.perf_counter()
    mm.price_option(exotic)
    t_mc_cold = time.perf_counter() - t0
    t0 = time.perf_counter()
    mm.price_option(exotic)
    t_mc_hot = time.perf_counter() - t0

    day_cost = t_quote + t_fok + t_adv
    print(f"  warm_up(400d)           {t_warm*1000:8.1f} ms")
    print(f"  quote ×200 期权         {t_quote*1000:8.1f} ms ({t_quote*5:.2f} ms/次)")
    print(f"  respond_to_fok ×200     {t_fok*1000:8.1f} ms")
    print(f"  on_step_advance(200仓)  {t_adv*1000:8.1f} ms")
    print(f"  MC 兜底 冷/热           {t_mc_cold*1000:8.1f} / {t_mc_hot*1000:.3f} ms")
    print(f"  → 洪峰日成本 ≈ {day_cost*1000:.0f} ms；100 天洪峰 session "
          f"≈ {day_cost*100 + t_warm:.1f} s（对任何评测时限都有量级裕度）")


if __name__ == "__main__":
    stress_battery()
    latency_bench()

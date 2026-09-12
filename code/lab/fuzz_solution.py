# NOTE (publication): parameter values in this file are arbitrary plausible stand-ins, not the competition values.
"""随机操作序列不变量测试（提交前最后防线）。

    python3 fuzz_solution.py

四根支柱分别验证过，但机制交互组合空间没有被系统扫过。三条硬不变量：
  ① quote() 永远返回合法 Quote（评测端 __post_init__ 不炸）；
  ② 镜像现金守恒：全部结算后 mirror − initial ≡ Σ_cp_realized
     （买 q(pay−p)、卖同式，任何记账 bug 都会打破这条恒等式）；
  ③ 合法输入下 _error_count == 0（无静默异常在吞错）。
"""
import random
import sys
from dataclasses import replace

sys.path.insert(0, "<WORKDIR>/akuna2026")

from solution import (
    AJARAI_UNDERLYING_ID, FED_FUNDS_RATE_UNDERLYING_ID, THERIODIC_UNDERLYING_ID,
    BinaryOption, FokOrder, MarketHistory, MarketMaker, MarketParameters,
    OptionLeg, OrderType, Quote, Underlying,
)

PARAMS = MarketParameters(
    ajarai_drift=0.0008, ajarai_idio_std_dev=0.015, ajarai_rate_beta=-0.017,
    ajarai_sector_beta=1.0, rate_down_probability=0.21,
    rate_reversion_strength=0.09, rate_up_probability=0.24,
    sector_std_dev=0.024, theriodic_drift=0.0011, theriodic_idio_std_dev=0.015,
    theriodic_rate_beta=-0.011, theriodic_sector_beta=1.0)
UIDS = (FED_FUNDS_RATE_UNDERLYING_ID, AJARAI_UNDERLYING_ID, THERIODIC_UNDERLYING_ID)


def underlyings(values):
    return [Underlying("FED", FED_FUNDS_RATE_UNDERLYING_ID,
                       values[FED_FUNDS_RATE_UNDERLYING_ID]),
            Underlying("AJR", AJARAI_UNDERLYING_ID, values[AJARAI_UNDERLYING_ID]),
            Underlying("THR", THERIODIC_UNDERLYING_ID, values[THERIODIC_UNDERLYING_ID])]


def random_option(rng, oid, values):
    kind = rng.random()
    expiry = rng.randint(1, 10)
    if kind < 0.25:
        strike = round(rng.uniform(0.25, 6.0) * 4) / 4
        legs = (OptionLeg(FED_FUNDS_RATE_UNDERLYING_ID, rng.choice([1.0, -1.0, 2.0])),)
    elif kind < 0.6:
        uid = rng.choice([AJARAI_UNDERLYING_ID, THERIODIC_UNDERLYING_ID])
        strike = round(values[uid] * rng.uniform(0.7, 1.3), 2)
        legs = (OptionLeg(uid, rng.choice([1.0, -1.0, 0.5, 2.5])),)
    elif kind < 0.85:
        w = rng.choice([(1.0, -1.0), (-1.0, 1.0), (1.0, 1.0), (2.0, -0.5)])
        legs = (OptionLeg(AJARAI_UNDERLYING_ID, w[0]),
                OptionLeg(THERIODIC_UNDERLYING_ID, w[1]))
        strike = 0.0 if rng.random() < 0.5 else round(rng.uniform(-200, 400), 2)
    else:
        legs = (OptionLeg(FED_FUNDS_RATE_UNDERLYING_ID, rng.uniform(10, 100)),
                OptionLeg(AJARAI_UNDERLYING_ID, 1.0),
                OptionLeg(THERIODIC_UNDERLYING_ID, rng.choice([1.0, -1.0])))
        strike = round(rng.uniform(0, 2000), 2)
    return BinaryOption(legs, oid, expiry, strike)


def run_fuzz(seed, n_ops=2500):
    rng = random.Random(seed)
    random.seed(seed * 17 + 5)
    values = {FED_FUNDS_RATE_UNDERLYING_ID: 2.0,
              AJARAI_UNDERLYING_ID: rng.uniform(300, 2000),
              THERIODIC_UNDERLYING_ID: rng.uniform(300, 2000)}
    n_hist = rng.choice([2, 5, 60, 300])   # 含退化 warm-up
    rows = {uid: [v] for uid, v in values.items()}
    for _ in range(n_hist - 1):
        values = PARAMS.advance_step(values)
        for uid, v in values.items():
            rows[uid].append(v)

    capital = rng.choice([10.0, 20.0, 40.0, 200.0])
    mm = MarketMaker(underlyings(values), [], capital)
    mm.warm_up(MarketHistory(values_by_underlying_id={
        uid: tuple(vs) for uid, vs in rows.items()}))

    live = {}      # oid -> (option_at_spawn, day_spawned)
    day = [0]
    oid = [0]

    def cur(o, d0):
        left = o.steps_until_expiry - (day[0] - d0)
        return replace(o, steps_until_expiry=max(left, 0))

    def advance():
        nonlocal values
        values = PARAMS.advance_step(values)
        day[0] += 1
        still = [cur(o, d0) for o, d0 in live.values()
                 if o.steps_until_expiry - (day[0] - d0) > 0]
        mm.on_step_advance(underlyings(values), still)
        for k in [k for k, (o, d0) in live.items()
                  if o.steps_until_expiry - (day[0] - d0) <= 0]:
            del live[k]

    mm.on_step_advance(underlyings(values), [])
    for _ in range(n_ops):
        r = rng.random()
        if r < 0.15 or not live:
            oid[0] += 1
            o = random_option(rng, oid[0], values)
            live[oid[0]] = (o, day[0])
            mm.on_step_advance(underlyings(values),
                               [cur(x, d0) for x, d0 in live.values()])
        elif r < 0.55:
            o, d0 = rng.choice(list(live.values()))
            q = mm.quote(cur(o, d0), rng.randint(1, 30))
            assert isinstance(q, Quote)
        elif r < 0.75:
            o, d0 = rng.choice(list(live.values()))
            side = rng.choice([OrderType.BUY, OrderType.SELL])
            fok = FokOrder(rng.randint(1, 30), o.option_id, side,
                           round(rng.uniform(0.01, 0.99), 2), rng.randint(1, 60))
            assert mm.respond_to_fok(cur(o, d0), fok) in (True, False)
        elif r < 0.9:
            o, d0 = rng.choice(list(live.values()))
            price = round(rng.uniform(0.01, 0.99), 2)
            qty = rng.randint(1, 40) * rng.choice([1, -1])
            mm.on_trade(cur(o, d0), price, qty, rng.randint(1, 30))
        else:
            advance()

    for _ in range(12):    # 清场：让所有持仓到期结算
        advance()

    drift = mm._mirror_cash - capital - sum(mm._cp_realized.values())
    assert abs(drift) < 1e-6, f"镜像守恒破裂：drift={drift}"
    assert mm._error_count == 0, f"静默异常 {mm._error_count} 次"
    return mm._mirror_cash - capital


if __name__ == "__main__":
    for seed in range(8):
        pnl = run_fuzz(seed)
        print(f"seed {seed}: OK (期末镜像 pnl={pnl:+.2f})")
    print("全部不变量通过")

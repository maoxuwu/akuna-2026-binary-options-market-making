# NOTE (publication): parameter values in this file are arbitrary plausible stand-ins, not the competition values.
"""D5 probe 3: price_option (estimated model) robustness on the same option matrix.

Cases: (a) normal 30d warm-up generated from the reference process; (b) no warm_up at all;
(c) MarketHistory({}); (d) constant (zero-change) history; (e) 2-day history.
Asserts finite float in [0,1], no exception, <1s per call. Also reports max
|price_option - price_option_from_parameters(STANDIN)| after the normal warm-up (info).
"""
import math
import random
import sys
import time

sys.path.insert(0, '<WORKDIR>')
from template import (
    MarketMaker, MarketHistory, MarketParameters, BinaryOption, OptionLeg, Underlying,
    FED_FUNDS_RATE_UNDERLYING_ID as FID,
    AJARAI_UNDERLYING_ID as AID,
    THERIODIC_UNDERLYING_ID as TID,
)

STANDIN = MarketParameters(
    ajarai_drift=0.0008, theriodic_drift=0.0011,
    ajarai_idio_std_dev=0.012, theriodic_idio_std_dev=0.015,
    ajarai_rate_beta=-0.017, theriodic_rate_beta=-0.011,
    ajarai_sector_beta=1.0, theriodic_sector_beta=1.0,
    sector_std_dev=0.024,
    rate_up_probability=0.24, rate_down_probability=0.21,
    rate_reversion_strength=0.09, rate_step=0.25, rate_target=2.0,
)

def gen_history(days, seed=7, start=None):
    random.seed(seed)
    state = dict(start or {FID: 3.0, AID: 500.0, TID: 600.0})
    rows = {FID: [state[FID]], AID: [state[AID]], TID: [state[TID]]}
    for _ in range(days - 1):
        state = STANDIN.advance_step(state)
        for k in rows:
            rows[k].append(state[k])
    return MarketHistory({k: tuple(v) for k, v in rows.items()}), state

def opt_matrix():
    oid = [0]
    def mk(legs, e, k):
        oid[0] += 1
        return BinaryOption(legs=tuple(OptionLeg(u, w) for u, w in legs),
                            option_id=oid[0], steps_until_expiry=e, strike=k)
    out = []
    for e in (0, 1, 10, 60, 365):
        for k in (0.0, 3.0, 100.0, -0.25):
            out.append(mk([(FID, 1.0)], e, k))
        out.append(mk([(FID, -2.0)], e, -6.0))
        for k in (1e-9, 500.0, 1e9, -5.0):
            out.append(mk([(AID, 1.0)], e, k))
        out.append(mk([(AID, -2.0)], e, -900.0))
        for k in (1e-9, 600.0, 1e9):
            out.append(mk([(TID, 1.0)], e, k))
        for k in (0.0, 50.0, -50.0, 1e-9, 1e9):
            out.append(mk([(TID, 1.0), (AID, -1.0)], e, k))
        out.append(mk([(TID, 0.5), (AID, -2.0)], e, -700.0))
        out.append(mk([(AID, 1.0), (TID, 1.0)], e, 1000.0))
        out.append(mk([(FID, 1.0), (AID, 1.0), (TID, 1.0)], e, 1100.0))
        out.append(mk([(FID, -2.0), (AID, 0.5), (TID, -1.0)], e, -400.0))
    return out

def check(mm, label):
    violations, slowest, n = [], (0.0, None), 0
    for o in opt_matrix():
        n += 1
        t0 = time.perf_counter()
        try:
            v = mm.price_option(o)
            dt = time.perf_counter() - t0
            if not (isinstance(v, float) and math.isfinite(v) and 0.0 <= v <= 1.0):
                violations.append((label, str(o), f"BAD VALUE {v!r}"))
        except Exception as exc:
            dt = time.perf_counter() - t0
            violations.append((label, str(o), f"RAISED {type(exc).__name__}: {exc}"))
        if dt > slowest[0]:
            slowest = (dt, str(o))
        if dt > 1.0:
            violations.append((label, str(o), f"SLOW {dt:.2f}s"))
    print(f"  [{label}] calls={n} violations={len(violations)} "
          f"slowest={slowest[0]*1000:.1f}ms ({slowest[1]})")
    for v in violations:
        print("    VIOLATION:", v)
    return violations

unds = lambda s: [Underlying("FED", FID, s[FID]), Underlying("AJR", AID, s[AID]),
                  Underlying("THR", TID, s[TID])]
all_v = []

# (a) normal 30-day warm-up (31 values -> 30 observations), cash=20 (no classifier gate)
hist, end = gen_history(31)
mm = MarketMaker(unds(end), [], 20.0)
t0 = time.perf_counter()
mm.warm_up(hist)
print(f"warm_up(30d) took {1e3*(time.perf_counter()-t0):.1f}ms; "
      f"defensive={mm._is_defensive_environment} test19={mm._is_test_nineteen_environment}")
all_v += check(mm, "30d warm-up")
diffs = [(abs(mm.price_option(o) - mm.price_option_from_parameters(STANDIN, o)), str(o))
         for o in opt_matrix() if o.steps_until_expiry in (1, 10, 60)]
mx = max(diffs)
print(f"  info: max |estimated - true-param| over 1/10/60d options = {mx[0]:.4f} on {mx[1]}")

# (b) no warm_up at all (default priors)
mm_b = MarketMaker(unds(end), [], 20.0)
all_v += check(mm_b, "no warm-up")

# (c) empty history dict
mm_c = MarketMaker(unds(end), [], 20.0)
mm_c.warm_up(MarketHistory({}))
all_v += check(mm_c, "warm_up(MarketHistory({}))")

# (d) constant history (rate never moves, companies frozen)
const = MarketHistory({FID: (3.0,) * 31, AID: (500.0,) * 31, TID: (600.0,) * 31})
mm_d = MarketMaker(unds({FID: 3.0, AID: 500.0, TID: 600.0}), [], 20.0)
mm_d.warm_up(const)
all_v += check(mm_d, "constant 31d history")

# (e) 2-day history (1 observation)
h2, e2 = gen_history(2, seed=11)
mm_e = MarketMaker(unds(e2), [], 20.0)
mm_e.warm_up(h2)
all_v += check(mm_e, "2-day history")

print(f"\nTOTAL violations: {len(all_v)}")

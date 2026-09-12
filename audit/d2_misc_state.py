# NOTE (publication): parameter values in this file are arbitrary plausible stand-ins, not the competition values.
"""D2 misc: latent-state and lifecycle checks.
1) warm_up called twice: flags from the first call survive an early-return second
   call (documented; platform calls warm_up exactly once -> not deliverable).
2) quote()/respond_to_fok() BEFORE warm_up: must work on constructor defaults.
3) warm_up timing for 45-day (real max) and 400-day (hypothetical) histories.
"""
import sys, math, time, traceback, random
sys.path.insert(0, '<WORKDIR>')
from template import (MarketMaker, MarketHistory, MarketParameters, BinaryOption,
                      OptionLeg, FokOrder, OrderType, Underlying,
                      FED_FUNDS_RATE_UNDERLYING_ID as FID,
                      AJARAI_UNDERLYING_ID as AID,
                      THERIODIC_UNDERLYING_ID as TID)

def geo(v0, r, n):
    out = [v0]
    for _ in range(n - 1):
        out.append(out[-1] * math.exp(r))
    return tuple(out)

failures = []
unds = [Underlying("FED", FID, 1.5), Underlying("AJR", AID, 500.0), Underlying("THR", TID, 600.0)]
opt = BinaryOption(legs=(OptionLeg(AID, 1.0),), option_id=1, steps_until_expiry=3, strike=500.0)

# 1) warm_up twice: gate flag stickiness across an early-return second call
mm = MarketMaker(list(unds), [opt], 10.0)
gate_hist = MarketHistory({FID: tuple([1.5] * 20), AID: geo(500.0, -0.0051, 20), TID: geo(600.0, 0.0031, 20)})
mm.warm_up(gate_hist)
first = mm._is_defensive_environment
mm.warm_up(MarketHistory({}))            # early return: does NOT recompute/reset flags
second = mm._is_defensive_environment
print(f"warm_up twice: after gate hist={first}, after empty re-warm_up={second} "
      f"(flag {'STICKS across early-return re-warm_up' if second else 'was reset'})")
# and a full non-gate second history DOES recompute:
mm.warm_up(MarketHistory({FID: tuple([1.5] * 30), AID: geo(500.0, 0.001, 30), TID: geo(600.0, 0.001, 30)}))
print(f"full second warm_up recomputes: defensive={mm._is_defensive_environment} (expect False)")

# 2) methods before warm_up
mm2 = MarketMaker(list(unds), [opt], 10.0)
try:
    q = mm2.quote(opt, 1)
    r = mm2.respond_to_fok(opt, FokOrder(1, 1, OrderType.SELL, 0.30, 2))
    p = mm2.price_option(opt)
    print(f"pre-warm_up: quote={q} fok={r} price={p:.4f}  (defaults, no exception)")
except Exception:
    failures.append(("pre-warm_up", traceback.format_exc()))

# 3) warm_up timing
STANDIN_PARAMS = MarketParameters(
    ajarai_drift=0.0008, ajarai_idio_std_dev=0.012, ajarai_rate_beta=-0.017,
    ajarai_sector_beta=1.0, rate_down_probability=0.21, rate_reversion_strength=0.09,
    rate_up_probability=0.24, sector_std_dev=0.024, theriodic_drift=0.0011,
    theriodic_idio_std_dev=0.015, theriodic_rate_beta=-0.011, theriodic_sector_beta=1.0)
for days in (45, 400):
    random.seed(days)
    vals = {FID: 2.0, AID: 800.0, TID: 1100.0}
    rows = [dict(vals)]
    for _ in range(days - 1):
        vals = STANDIN_PARAMS.advance_step(vals)
        rows.append(dict(vals))
    hist = MarketHistory({FID: tuple(r[FID] for r in rows),
                          AID: tuple(r[AID] for r in rows),
                          TID: tuple(r[TID] for r in rows)})
    mm3 = MarketMaker(list(unds), [opt], 40.0)
    t0 = time.perf_counter()
    mm3.warm_up(hist)
    dt = (time.perf_counter() - t0) * 1000
    print(f"warm_up({days}d) = {dt:.1f} ms, flags=({mm3._is_defensive_environment},{mm3._is_test_nineteen_environment})")
    if dt > 5000:
        failures.append((f"warm_up {days}d", f"{dt:.0f} ms"))

print()
if failures:
    for l, m in failures:
        print("---", l, "---"); print(m)
    sys.exit(1)
print("MISC STATE CHECKS DONE")

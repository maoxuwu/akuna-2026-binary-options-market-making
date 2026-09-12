# NOTE (publication): parameter values in this file are arbitrary plausible stand-ins, not the competition values.
"""D5 probe 2: non-finite MarketParameters pass __post_init__ (all comparisons False).

Checks (a) whether NaN/inf fields slip through validation, (b) whether pricing survives,
(c) the _rate_distribution state-explosion when rate_step is NaN (hash(nan) is
identity-based on Python >=3.10, so every round(nan+..) makes a NEW dict key ->
3^steps states -> timeout/OOM for realistic expiries).
"""
import math
import sys
import time

sys.path.insert(0, '<WORKDIR>')
from template import (
    MarketMaker, MarketParameters, BinaryOption, OptionLeg, Underlying,
    FED_FUNDS_RATE_UNDERLYING_ID as FID,
    AJARAI_UNDERLYING_ID as AID,
    THERIODIC_UNDERLYING_ID as TID,
)

STANDIN = dict(
    ajarai_drift=0.0008, theriodic_drift=0.0011,
    ajarai_idio_std_dev=0.012, theriodic_idio_std_dev=0.015,
    ajarai_rate_beta=-0.017, theriodic_rate_beta=-0.011,
    ajarai_sector_beta=1.0, theriodic_sector_beta=1.0,
    sector_std_dev=0.024,
    rate_up_probability=0.24, rate_down_probability=0.21,
    rate_reversion_strength=0.09, rate_step=0.25, rate_target=2.0,
)

def P(**over):
    d = dict(STANDIN); d.update(over)
    return MarketParameters(**d)

NAN, INF = float('nan'), float('inf')
unds = [Underlying("FED", FID, 3.0), Underlying("AJR", AID, 500.0),
        Underlying("THR", TID, 600.0)]
mm = MarketMaker(unds, [], 20.0)
fed = lambda e: BinaryOption(legs=(OptionLeg(FID, 1.0),), option_id=900 + e,
                             steps_until_expiry=e, strike=3.0)
ajr = lambda e: BinaryOption(legs=(OptionLeg(AID, 1.0),), option_id=800 + e,
                             steps_until_expiry=e, strike=500.0)

print("== 1. Which non-finite params pass MarketParameters validation? ==")
for label, over in [
    ("rate_step=NaN", dict(rate_step=NAN)),
    ("rate_step=inf", dict(rate_step=INF)),
    ("p_up=NaN", dict(rate_up_probability=NAN)),
    ("reversion=NaN", dict(rate_reversion_strength=NAN)),
    ("target=NaN", dict(rate_target=NAN)),
    ("target=inf", dict(rate_target=INF)),
    ("drift=NaN", dict(ajarai_drift=NAN)),
    ("drift=inf", dict(ajarai_drift=INF)),
    ("idio=NaN", dict(ajarai_idio_std_dev=NAN)),
    ("beta=inf", dict(ajarai_rate_beta=INF)),
]:
    try:
        P(**over)
        print(f"  {label}: PASSES validation")
    except ValueError as e:
        print(f"  {label}: rejected ({e})")

print("\n== 2. Do the passing ones crash / hang pricing? (short expiry first) ==")
for label, params in [
    ("p_up=NaN", P(rate_up_probability=NAN)),
    ("target=NaN", P(rate_target=NAN)),
    ("target=inf", P(rate_target=INF)),
    ("drift=NaN", P(ajarai_drift=NAN)),
    ("drift=inf", P(ajarai_drift=INF)),
    ("idio=NaN", P(ajarai_idio_std_dev=NAN)),
    ("beta=inf", P(ajarai_rate_beta=INF)),
]:
    for o in (fed(10), ajr(10)):
        t0 = time.perf_counter()
        try:
            v = mm.price_option_from_parameters(params, o)
            ok = isinstance(v, float) and math.isfinite(v) and 0.0 <= v <= 1.0
            print(f"  {label:12s} {'FED' if o.legs[0].underlying_id == FID else 'AJR'}"
                  f" 10d -> {v!r}  ok={ok}  {1e3*(time.perf_counter()-t0):.1f}ms")
        except Exception as exc:
            print(f"  {label:12s} -> RAISED {type(exc).__name__}: {exc}")

print("\n== 3. rate_step=NaN state explosion: dict keys grow 3x per expiry step ==")
print("   (hash(float('nan')) is id-based on this Python:",
      hash(float('nan')) != hash(float('nan')), ")")
nan_params = P(rate_step=NAN)
prev = None
for e in (6, 7, 8, 9, 10, 11):
    t0 = time.perf_counter()
    dist = mm._rate_distribution(3.0, e, nan_params)
    dt = time.perf_counter() - t0
    ratio = f"  x{len(dist)/prev:.2f} vs e-1" if prev else ""
    print(f"  expiry={e:3d}: states={len(dist):>8d}  build={dt*1000:8.1f}ms{ratio}")
    prev = len(dist)

print("\n  full price_option_from_parameters at expiry=11 (FED option):")
t0 = time.perf_counter()
v = mm.price_option_from_parameters(nan_params, fed(11))
print(f"  -> {v!r} in {time.perf_counter()-t0:.2f}s "
      f"(3^n growth => expiry 20 ~ 3.5e9 states = OOM/timeout; expiry 60/365 hopeless)")

print("\n== 4. rate_step=inf: inf-inf=NaN keys on later steps -> same explosion? ==")
inf_params = P(rate_step=INF)
prev = None
for e in (6, 8, 10, 11):
    t0 = time.perf_counter()
    dist = mm._rate_distribution(3.0, e, inf_params)
    dt = time.perf_counter() - t0
    print(f"  expiry={e:3d}: states={len(dist):>8d}  build={dt*1000:8.1f}ms")

# NOTE (publication): parameter values in this file are arbitrary plausible stand-ins, not the competition values.
"""D5 probe 1: price_option_from_parameters matrix — true + edge params x option grid.

Asserts: finite float in [0,1], no exception, each call < 1s (runtime outliers flagged).
READ-ONLY on template.py.
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

PARAM_SETS = {
    "STANDIN": P(),
    "EDGE_rev_max_pnear1_zerovol": P(rate_reversion_strength=1.0,
                                     rate_up_probability=0.5, rate_down_probability=0.4999,
                                     sector_std_dev=0.0, ajarai_idio_std_dev=0.0,
                                     theriodic_idio_std_dev=0.0, rate_step=1e-9),
    "EDGE_bigstep_fartarget_bigvol": P(rate_step=100.0, rate_target=1000.0,
                                       rate_reversion_strength=1.0,
                                       rate_up_probability=0.01, rate_down_probability=0.01,
                                       sector_std_dev=0.5, ajarai_idio_std_dev=0.3,
                                       theriodic_idio_std_dev=0.4),
    "EDGE_psum_exactly_1": P(rate_up_probability=0.5, rate_down_probability=0.5,
                             rate_reversion_strength=0.0),
    "EDGE_tiny_vols": P(sector_std_dev=1e-12, ajarai_idio_std_dev=1e-12,
                        theriodic_idio_std_dev=1e-12),
    "EDGE_neg_beta_big": P(ajarai_rate_beta=-5.0, theriodic_rate_beta=4.0),
}

def opts():
    oid = [0]
    def mk(legs, expiry, strike):
        oid[0] += 1
        return BinaryOption(legs=tuple(OptionLeg(u, w) for u, w in legs),
                            option_id=oid[0], steps_until_expiry=expiry, strike=strike)
    out = []
    EXP = (0, 1, 10, 60, 365)
    for e in EXP:
        # FED singles
        for k in (0.0, 3.0, 100.0, -0.25):
            out.append(mk([(FID, 1.0)], e, k))
        out.append(mk([(FID, 0.5)], e, 1.5))
        out.append(mk([(FID, -2.0)], e, -6.0))
        # company singles
        for k in (1e-9, 500.0, 1e9, -5.0):
            out.append(mk([(AID, 1.0)], e, k))
        out.append(mk([(AID, 0.5)], e, 250.0))
        out.append(mk([(AID, -2.0)], e, -900.0))
        for k in (1e-9, 600.0, 1e9):
            out.append(mk([(TID, 1.0)], e, k))
        # spreads (THR - AJR), strike 0 (log-ratio shortcut) and nonzero (512-pt quadrature)
        for k in (0.0, 50.0, -50.0, 1e-9, 1e9, -1e9):
            out.append(mk([(TID, 1.0), (AID, -1.0)], e, k))
        out.append(mk([(TID, 0.5), (AID, -2.0)], e, 0.0))
        out.append(mk([(TID, 0.5), (AID, -2.0)], e, -700.0))
        out.append(mk([(AID, -1.0), (TID, 1.0)], e, 0.0))   # leg order swapped
        # same-sign spreads
        out.append(mk([(AID, 1.0), (TID, 1.0)], e, 1000.0))
        out.append(mk([(AID, 1.0), (TID, 1.0)], e, 0.0))
        out.append(mk([(AID, -1.0), (TID, -1.0)], e, -3000.0))
        # 3-leg
        out.append(mk([(FID, 1.0), (AID, 1.0), (TID, 1.0)], e, 1100.0))
        out.append(mk([(FID, -2.0), (AID, 0.5), (TID, -1.0)], e, -400.0))
        out.append(mk([(FID, 1.0), (AID, 1.0), (TID, -1.0)], e, 100.0))
    return out

def run(fed0=3.0, label=""):
    unds = [Underlying("FED", FID, fed0), Underlying("AJR", AID, 500.0),
            Underlying("THR", TID, 600.0)]
    violations, outliers = [], []
    n = 0
    slowest = (0.0, None, None)
    for pname, params in PARAM_SETS.items():
        mm = MarketMaker(unds, [], 20.0)  # fresh mm; THEO channel needs no warm_up
        for o in opts():
            n += 1
            t0 = time.perf_counter()
            try:
                v = mm.price_option_from_parameters(params, o)
                dt = time.perf_counter() - t0
                if not (isinstance(v, float) and math.isfinite(v) and 0.0 <= v <= 1.0):
                    violations.append((label, pname, str(o), f"BAD VALUE {v!r}"))
            except Exception as exc:
                dt = time.perf_counter() - t0
                violations.append((label, pname, str(o), f"RAISED {type(exc).__name__}: {exc}"))
            if dt > slowest[0]:
                slowest = (dt, pname, str(o))
            if dt > 1.0:
                outliers.append((label, pname, str(o), f"{dt:.2f}s"))
    return n, violations, outliers, slowest

total_t0 = time.perf_counter()
n1, v1, o1, s1 = run(3.0, "fed3.0")
# floor case: rate pinned at 0 with strong downward tilt
FLOOR = P(rate_up_probability=0.05, rate_down_probability=0.7,
          rate_reversion_strength=1.0, rate_target=0.0)
PARAM_SETS_SAVE = dict(PARAM_SETS)
PARAM_SETS.clear(); PARAM_SETS["FLOOR_down_tilt"] = FLOOR
n2, v2, o2, s2 = run(0.0, "fed0.0_floor")
PARAM_SETS.update(PARAM_SETS_SAVE)

print(f"calls={n1 + n2}  wall={time.perf_counter() - total_t0:.1f}s")
print(f"violations={len(v1) + len(v2)}")
for v in (v1 + v2):
    print("  VIOLATION:", v)
print(f"runtime outliers >1s: {len(o1) + len(o2)}")
for o in (o1 + o2):
    print("  OUTLIER:", o)
print(f"slowest call main: {s1[0]*1000:.1f}ms  params={s1[1]}  opt={s1[2]}")
print(f"slowest call floor: {s2[0]*1000:.1f}ms  params={s2[1]}  opt={s2[2]}")

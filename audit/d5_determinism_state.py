# NOTE (publication): parameter values in this file are arbitrary plausible stand-ins, not the competition values.
"""D5 probe 4: determinism, global-RNG isolation, degenerate underlying_state values."""
import math
import random
import sys

sys.path.insert(0, '<WORKDIR>')
from template import (
    MarketMaker, MarketParameters, BinaryOption, OptionLeg, Underlying,
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
spread = BinaryOption(legs=(OptionLeg(TID, 1.0), OptionLeg(AID, -1.0)),
                      option_id=1, steps_until_expiry=10, strike=50.0)  # quadrature path

# determinism + RNG isolation
u = [Underlying("FED", FID, 3.0), Underlying("AJR", AID, 500.0), Underlying("THR", TID, 600.0)]
mm = MarketMaker(u, [], 20.0)
random.seed(123); baseline = random.random()
random.seed(123)
v1 = mm.price_option_from_parameters(STANDIN, spread)
v2 = mm.price_option_from_parameters(STANDIN, spread)
after = random.random()
print(f"deterministic: {v1 == v2} ({v1!r})")
print(f"global RNG untouched by pricing: {after == baseline}")

# degenerate underlying_state values (not grader-deliverable: companies always positive)
fails = []
for label, vals in [
    ("AJR=0", (3.0, 0.0, 600.0)),
    ("AJR=-5", (3.0, -5.0, 600.0)),
    ("both companies 0", (3.0, 0.0, 0.0)),
    ("huge values", (3.0, 1e300, 1e300)),
    ("FED huge", (1e9, 500.0, 600.0)),
]:
    uu = [Underlying("FED", FID, vals[0]), Underlying("AJR", AID, vals[1]),
          Underlying("THR", TID, vals[2])]
    m = MarketMaker(uu, [], 20.0)
    for o in (spread,
              BinaryOption(legs=(OptionLeg(AID, 1.0),), option_id=2,
                           steps_until_expiry=10, strike=500.0),
              BinaryOption(legs=(OptionLeg(TID, 1.0), OptionLeg(AID, -1.0)),
                           option_id=3, steps_until_expiry=10, strike=0.0)):
        try:
            v = m.price_option_from_parameters(STANDIN, o)
            ok = isinstance(v, float) and math.isfinite(v) and 0.0 <= v <= 1.0
            if not ok:
                fails.append((label, str(o), v))
            print(f"  {label:20s} {str(o):40s} -> {v:.4f} ok={ok}")
        except Exception as exc:
            fails.append((label, str(o), f"RAISED {type(exc).__name__}: {exc}"))
            print(f"  {label:20s} {str(o):40s} -> RAISED {type(exc).__name__}: {exc}")
print(f"failures: {len(fails)}")

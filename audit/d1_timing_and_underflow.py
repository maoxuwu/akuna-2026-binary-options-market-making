"""DIMENSION 1 auxiliary probes.

1) warm_up wall-time on the worst realistic and worst degenerate histories
   (rate-MLE coordinate search cost scales with distinct transition pairs).
2) Adjacent numeric probe: log-underflow in _one_lognormal_probability via an
   extreme-weight option (out of dimension-1 proper; deliverability noted).
"""
import math
import random
import sys
import time
import traceback

sys.path.insert(0, '<WORKDIR>')
from template import (
    MarketMaker, MarketHistory, BinaryOption, OptionLeg, Underlying,
    FED_FUNDS_RATE_UNDERLYING_ID as FID,
    AJARAI_UNDERLYING_ID as AID,
    THERIODIC_UNDERLYING_ID as TID,
)


def unds():
    return [Underlying("FED", FID, 3.0), Underlying("AJR", AID, 500.0), Underlying("THR", TID, 600.0)]


print("========== warm_up timing ==========")
rng = random.Random(1)

# (1) 400-day on-grid realistic walk
fed = [3.0]
for _ in range(399):
    fed.append(max(round(fed[-1] + rng.choice((-0.25, 0.0, 0.25)), 2), 0.0))
ajr = [500.0]
thr = [600.0]
for _ in range(399):
    ajr.append(round(ajr[-1] * math.exp(rng.gauss(0.001, 0.022)), 2))
    thr.append(round(thr[-1] * math.exp(rng.gauss(0.001, 0.022)), 2))
h1 = {FID: tuple(fed), AID: tuple(ajr), TID: tuple(thr)}

# (2) 400-day FED completely off-grid (every transition pair distinct -> max MLE state count)
fed2 = tuple(round(3.0 + rng.uniform(-1.0, 1.0), 6) for _ in range(400))
h2 = {FID: fed2, AID: tuple(ajr), TID: tuple(thr)}

# (3) 2000-day on-grid (beyond spec, stress)
fed3 = [3.0]
for _ in range(1999):
    fed3.append(max(round(fed3[-1] + rng.choice((-0.25, 0.0, 0.25)), 2), 0.0))
ajr3 = [500.0]
thr3 = [600.0]
for _ in range(1999):
    ajr3.append(round(ajr3[-1] * math.exp(rng.gauss(0.001, 0.022)), 2))
    thr3.append(round(thr3[-1] * math.exp(rng.gauss(0.001, 0.022)), 2))
h3 = {FID: tuple(fed3), AID: tuple(ajr3), TID: tuple(thr3)}

for tag, h in (("400d on-grid", h1), ("400d off-grid FED", h2), ("2000d on-grid", h3)):
    mm = MarketMaker(unds(), [], 40.0)
    t0 = time.perf_counter()
    mm.warm_up(MarketHistory(h))
    dt = time.perf_counter() - t0
    print(f"{tag}: warm_up took {dt*1000:.1f} ms (n={mm._history_observations})")

print()
print("========== adjacent probe: log-underflow via extreme option weight ==========")
mm = MarketMaker(unds(), [], 10.0)
mm.warm_up(MarketHistory({FID: (3.0,) * 30, AID: tuple(500.0 * math.exp(0.001 * i) for i in range(30)),
                          TID: tuple(600.0 * math.exp(-0.001 * i) for i in range(30))}))
weird = BinaryOption(legs=(OptionLeg(AID, 1e308),), option_id=50, steps_until_expiry=3, strike=1e-300)
try:
    p = mm.price_option(weird)
    print(f"price_option(weight=1e308, strike=1e-300) = {p!r}  (no exception)")
except Exception:
    print("price_option RAISED:")
    print(traceback.format_exc())
try:
    q = mm.quote(weird, 1)
    print(f"quote -> bid {q.bid_price}x{q.bid_quantity} offer {q.offer_price}x{q.offer_quantity} (no exception)")
except Exception:
    print("quote RAISED:")
    print(traceback.format_exc())

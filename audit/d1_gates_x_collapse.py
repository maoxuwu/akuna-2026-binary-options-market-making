"""DIMENSION 1: classifier gates firing on a degenerate (zero-variance) warm-up.

Craft histories that satisfy the defensive gate (cash 10, n=19, FED0<=1.5,
AJR drift<-0.005, THR drift>0.003) and the test19 gate (cash 40, n=39,
1.25<=FED0<=1.75, AJR drift>0.005, THR drift<-0.005) using geometric constant
returns, which also drive residual variance to exactly 0.  Run the battery on
the gated quote()/respond_to_fok() branches.
"""
import math
import sys
import traceback

sys.path.insert(0, '<WORKDIR>')
from template import (
    MarketMaker, MarketHistory, BinaryOption, OptionLeg, FokOrder, OrderType, Underlying, Quote,
    FED_FUNDS_RATE_UNDERLYING_ID as FID,
    AJARAI_UNDERLYING_ID as AID,
    THERIODIC_UNDERLYING_ID as TID,
)

FAILURES = []


def geo(v0, rate, n):
    return tuple(round(v0 * math.exp(rate * i), 6) for i in range(n))


def battery(tag, mm):
    opts = [
        BinaryOption(legs=(OptionLeg(FID, 1.0),), option_id=1, steps_until_expiry=3, strike=1.5),
        BinaryOption(legs=(OptionLeg(AID, 1.0),), option_id=2, steps_until_expiry=5, strike=500.0),
        BinaryOption(legs=(OptionLeg(TID, 1.0),), option_id=3, steps_until_expiry=5, strike=600.0),
        BinaryOption(legs=(OptionLeg(TID, 1.0),), option_id=4, steps_until_expiry=1, strike=550.0),
        BinaryOption(legs=(OptionLeg(TID, 1.0), OptionLeg(AID, -1.0)), option_id=5, steps_until_expiry=2, strike=0.0),
        BinaryOption(legs=(OptionLeg(TID, 1.0), OptionLeg(AID, -1.0)), option_id=6, steps_until_expiry=4, strike=80.0),
    ]
    for o in opts:
        try:
            p = mm.price_option(o)
            assert math.isfinite(p) and 0.0 <= p <= 1.0, f"price {p!r}"
        except Exception:
            FAILURES.append((tag, f"price_option(opt{o.option_id}) RAISED:\n{traceback.format_exc()}"))
        for cp in (1, 44):
            try:
                q = mm.quote(o, cp)
                assert isinstance(q, Quote)
            except Exception:
                FAILURES.append((tag, f"quote(opt{o.option_id},cp{cp}) RAISED:\n{traceback.format_exc()}"))
        for ot in (OrderType.BUY, OrderType.SELL):
            for price in (0.0, 0.01, 0.5, 0.99, 1.0):
                for qty in (2, 40, 1000):
                    try:
                        mm.respond_to_fok(o, FokOrder(7, o.option_id, ot, price, qty))
                    except Exception:
                        FAILURES.append((tag, f"fok(opt{o.option_id},{ot},{price},{qty}) RAISED:\n{traceback.format_exc()}"))


# --- defensive gate + variance collapse (cash 10, 20-day history, n=19)
unds_d = [Underlying("FED", FID, 1.25), Underlying("AJR", AID, 500.0), Underlying("THR", TID, 600.0)]
hist_d = {FID: (1.25,) * 20, AID: geo(500.0, -0.006, 20), TID: geo(600.0, 0.004, 20)}
mm_d = MarketMaker(unds_d, [], 10.0)
mm_d.warm_up(MarketHistory(hist_d))
print(f"defensive gate fired: {mm_d._is_defensive_environment}  n={mm_d._history_observations} "
      f"var={dict(mm_d._estimated_variance_by_id)} drift={ {k: round(v,5) for k,v in mm_d._estimated_drift_by_id.items()} }")
battery("defensive-x-collapse", mm_d)
q = mm_d.quote(BinaryOption(legs=(OptionLeg(AID, 1.0),), option_id=90, steps_until_expiry=5, strike=500.0), 1)
print(f"  sample defensive quote (AJR ATM 5d, theo pinned): bid {q.bid_price}x{q.bid_quantity} offer {q.offer_price}x{q.offer_quantity}")

# --- test19 gate + variance collapse (cash 40, 40-day history, n=39)
unds_t = [Underlying("FED", FID, 1.5), Underlying("AJR", AID, 500.0), Underlying("THR", TID, 600.0)]
hist_t = {FID: (1.5,) * 40, AID: geo(500.0, 0.006, 40), TID: geo(600.0, -0.006, 40)}
mm_t = MarketMaker(unds_t, [], 40.0)
mm_t.warm_up(MarketHistory(hist_t))
print(f"test19 gate fired: {mm_t._is_test_nineteen_environment}  n={mm_t._history_observations} "
      f"var={dict(mm_t._estimated_variance_by_id)} drift={ {k: round(v,5) for k,v in mm_t._estimated_drift_by_id.items()} }")
battery("test19-x-collapse", mm_t)
q = mm_t.quote(BinaryOption(legs=(OptionLeg(TID, 1.0),), option_id=91, steps_until_expiry=5, strike=600.0), 1)
print(f"  sample test19 quote (THR ATM 5d): bid {q.bid_price}x{q.bid_quantity} offer {q.offer_price}x{q.offer_quantity}")

print()
print(f"FAILURES: {len(FAILURES)}")
for tag, msg in FAILURES:
    print(f"--- [{tag}] {msg}")

"""Completeness-critic probes: chains no dimension exercised end-to-end.

GAP-A: non-finite / huge FOK price -> accept -> grader follow-up on_trade -> next quote()
       (d4 probed respond_to_fok on inf/NaN but never the on_trade follow-through)
GAP-B: warm-up with a single-day company ratio that overflows to inf in log-return space
       (d1/d2 went to 1e12 swings and separate 1e-200/1e170 monotone paths; never an
        inf log-return in ONE consecutive pair)
GAP-C: MarketHistory carrying an extra unknown underlying id key
GAP-D: second FULL (non-early-return) warm_up mid-session re-firing gates
"""
import sys, math, traceback
sys.path.insert(0, '<WORKDIR>')
from template import (MarketMaker, MarketHistory, BinaryOption, OptionLeg, FokOrder,
                      OrderType, Underlying, Quote,
                      FED_FUNDS_RATE_UNDERLYING_ID as FID,
                      AJARAI_UNDERLYING_ID as AID,
                      THERIODIC_UNDERLYING_ID as TID)

def unds(f=3.0, a=500.0, t=600.0):
    return [Underlying("FED", FID, f), Underlying("AJR", AID, a), Underlying("THR", TID, t)]

def fresh(cash=20.0):
    opt = BinaryOption(legs=(OptionLeg(AID, 1.0),), option_id=1, steps_until_expiry=3, strike=500.0)
    return MarketMaker(unds(), [opt], cash), opt

def battery(mm, opt, label):
    errs = []
    for fn, desc in [
        (lambda: mm.price_option(opt), "price_option"),
        (lambda: mm.quote(opt, 7), "quote"),
        (lambda: mm.respond_to_fok(opt, FokOrder(7, opt.option_id, OrderType.SELL, 0.30, 2)), "fok"),
    ]:
        try:
            v = fn()
            if desc == "quote":
                assert isinstance(v, Quote)
            elif desc == "price_option":
                assert math.isfinite(v) and 0.0 <= v <= 1.0, f"price out of range: {v}"
        except Exception as e:
            errs.append((desc, type(e).__name__, str(e)[:100]))
    print(f"  [{label}] battery errors: {errs if errs else 'NONE'}")
    return errs

print("=== GAP-A: non-finite/huge on_trade price follow-through ===")
for price, qty, tag in [(float('inf'), -5, "inf sell-side"), (float('nan'), 5, "nan buy-side"), (1e308, -5, "1e308 sell-side")]:
    mm, opt = fresh()
    # step 1: grader-shaped FOK first (dataclass admits any price >= 0; nan<0 is False so nan passes)
    try:
        fok = FokOrder(7, 1, OrderType.BUY, price, 5)
        acc = mm.respond_to_fok(opt, fok)
    except Exception as e:
        acc = f"fok-raise:{type(e).__name__}"
    # step 2: grader follow-up trade at that price (we sold -> negative qty)
    try:
        mm.on_trade(opt, price, qty, 7)
        cash = mm._available_cash
    except Exception as e:
        cash = f"on_trade-raise:{type(e).__name__}"
    # step 3: next quote request
    try:
        q = mm.quote(opt, 8)
        out = f"quote OK {q}"
    except Exception as e:
        out = f"QUOTE RAISED {type(e).__name__}: {e}"
    print(f"  [{tag}] fok_accept={acc} cash_after={cash} -> {out}")

print("\n=== GAP-B: single-pair inf log-return in warm_up ===")
n = 20
fed = tuple(1.5 for _ in range(n))
ajr = (1e-300,) + tuple(1e300 for _ in range(n - 1))   # one-day ratio 1e600 -> inf log-return
thr = tuple(600.0 * (1.001 ** i) for i in range(n))
try:
    mm, opt = fresh(10.0)
    mm.warm_up(MarketHistory({FID: fed, AID: ajr, TID: thr}))
    print(f"  drift={mm._estimated_drift_by_id} var={mm._estimated_variance_by_id} "
          f"cov={mm._estimated_company_covariance} shrunk={mm._shrunk_drift_by_id} "
          f"gates=({mm._is_defensive_environment},{mm._is_test_nineteen_environment})")
    battery(mm, opt, "inf-log-return")
    spread = BinaryOption(legs=(OptionLeg(TID, 1.0), OptionLeg(AID, -1.0)), option_id=9, steps_until_expiry=2, strike=0.0)
    battery(mm, spread, "inf-log-return spread")
    spread2 = BinaryOption(legs=(OptionLeg(TID, 1.0), OptionLeg(AID, -1.0)), option_id=10, steps_until_expiry=2, strike=50.0)
    battery(mm, spread2, "inf-log-return spreadK (quadrature)")
except Exception:
    print("  WARM_UP RAISED:"); traceback.print_exc()

print("\n=== GAP-C: extra unknown key in MarketHistory ===")
try:
    mm, opt = fresh()
    vals = tuple(500.0 + i for i in range(21))
    mm.warm_up(MarketHistory({FID: tuple(1.5 for _ in range(21)), AID: vals, TID: vals, 99: vals}))
    battery(mm, opt, "extra-key")
except Exception:
    print("  RAISED:"); traceback.print_exc()

print("\n=== GAP-D: second FULL warm_up mid-session (gate re-fire) ===")
try:
    mm, opt = fresh(10.0)
    # generic first warm-up
    base = tuple(500.0 * (1.0005 ** i) for i in range(25))
    mm.warm_up(MarketHistory({FID: tuple(1.5 for _ in range(25)), AID: base, TID: base}))
    g1 = (mm._is_defensive_environment, mm._is_test_nineteen_environment)
    # trade, then a second warm-up crafted to fire the defensive gate (20d, cash10, FED<=1.5, drifts -/+)
    mm.on_trade(opt, 0.40, 3, 5)
    a2 = tuple(500.0 * math.exp(-0.007 * i) for i in range(20))
    t2 = tuple(600.0 * math.exp(+0.005 * i) for i in range(20))
    mm.warm_up(MarketHistory({FID: tuple(1.25 for _ in range(20)), AID: a2, TID: t2}))
    g2 = (mm._is_defensive_environment, mm._is_test_nineteen_environment)
    print(f"  gates first={g1} second={g2}  (True in second = gates CAN re-fire mid-session)")
    battery(mm, opt, "post-second-warmup")
except Exception:
    print("  RAISED:"); traceback.print_exc()

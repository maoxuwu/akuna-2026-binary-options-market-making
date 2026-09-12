"""DIMENSION 1 focused probe: variance collapse on ultra-short / constant warm-up.

V46 has NO variance floor.  With n=1 sample (2-day history) or n=2 samples
(3-day history, 2-parameter OLS fits perfectly) the residual variance is
exactly 0, so company-option theo becomes a deterministic 0/1 indicator.
This probe quantifies the resulting quoting behaviour and the worst-case
capital path, and verifies whether the mirror ledger can go negative.
"""
import math
import sys

sys.path.insert(0, '<WORKDIR>')
from template import (
    MarketMaker, MarketHistory, BinaryOption, OptionLeg, FokOrder, OrderType, Underlying,
    FED_FUNDS_RATE_UNDERLYING_ID as FID,
    AJARAI_UNDERLYING_ID as AID,
    THERIODIC_UNDERLYING_ID as TID,
)


def unds(fed=3.0, ajr=500.0, thr=600.0):
    return [Underlying("FED", FID, fed), Underlying("AJR", AID, ajr), Underlying("THR", TID, thr)]


def show(tag, hist, cash=10.0):
    mm = MarketMaker(unds(), [], cash)
    mm.warm_up(MarketHistory(hist))
    print(f"--- {tag}: n={mm._history_observations} "
          f"var={dict(mm._estimated_variance_by_id)} drift={ {k: round(v,5) for k,v in mm._estimated_drift_by_id.items()} }")
    # ATM AJR 5-day: true prob ~0.5ish under any sane model
    atm = BinaryOption(legs=(OptionLeg(AID, 1.0),), option_id=1, steps_until_expiry=5, strike=500.0)
    up = BinaryOption(legs=(OptionLeg(AID, 1.0),), option_id=2, steps_until_expiry=5, strike=490.0)
    for o, name in ((atm, "AJR>=500 5d"), (up, "AJR>=490 5d")):
        theo = mm.price_option(o)
        q = mm.quote(o, 1)
        print(f"    {name}: theo={theo!r}  quote bid {q.bid_price}x{q.bid_quantity} / offer {q.offer_price}x{q.offer_quantity}")
    return mm


print("========== exact variance collapse cases ==========")
# 2-day history, AJR fell slightly -> negative drift -> theo(ATM)=0 exactly
show("2-day (n=1)", {FID: (3.0, 3.0), AID: (500.0, 495.0), TID: (600.0, 606.0)})
# 2-day history, AJR rose slightly -> positive drift -> theo(ATM)=1 exactly
mm = show("2-day rising (n=1)", {FID: (3.0, 3.0), AID: (495.0, 500.0), TID: (606.0, 600.0)})
# 3-day (n=2): OLS with 2 params fits 2 points exactly
show("3-day (n=2)", {FID: (3.0, 3.25, 3.25), AID: (500.0, 502.0, 505.0), TID: (600.0, 599.0, 597.0)})
# constant 20-day
show("const 20-day (n=19)", {FID: (3.0,) * 20, AID: (500.0,) * 20, TID: (600.0,) * 20})

print()
print("========== worst-case capital path on pinned theo=1 ==========")
# rising 2-day history: theo(ATM)=1 -> mm bids ~0.97 with all deployable cash.
mm2 = MarketMaker(unds(), [], 10.0)
mm2.warm_up(MarketHistory({FID: (3.0, 3.0), AID: (495.0, 500.0), TID: (606.0, 600.0)}))
atm = BinaryOption(legs=(OptionLeg(AID, 1.0),), option_id=10, steps_until_expiry=1, strike=500.0)
q = mm2.quote(atm, 3)
print(f"quote on 1d ATM AJR: bid {q.bid_price}x{q.bid_quantity} offer {q.offer_price}x{q.offer_quantity}")
print(f"cash before: {mm2._available_cash:.4f}")
# grader lifts our whole bid
mm2.on_trade(atm, q.bid_price, q.bid_quantity, 3)
print(f"cash after full bid fill: {mm2._available_cash:.4f}  (collateral committed = {q.bid_price * q.bid_quantity:.4f})")
# option settles worthless (AJR drops below 500)
mm2.on_step_advance(unds(3.0, 480.0, 610.0), [])
print(f"cash after worthless settlement: {mm2._available_cash:.4f}  -> capital loss = {10.0 - mm2._available_cash:.4f} of 10.0")
print(f"mirror ledger negative? {mm2._available_cash < 0}")

print()
print("========== FOK behaviour under pinned theo ==========")
# theo=1 exactly -> counterparty SELL at 0.99 accepted with big qty? edge = 1-0.99 = 0.01 < required 0.0174? check
mm3 = MarketMaker(unds(), [], 40.0)
mm3.warm_up(MarketHistory({FID: (3.0, 3.0), AID: (495.0, 500.0), TID: (606.0, 600.0)}))
o = BinaryOption(legs=(OptionLeg(AID, 1.0),), option_id=20, steps_until_expiry=3, strike=500.0)
print(f"theo={mm3.price_option(o)}  margin={mm3._trading_margin(9):.4f}")
for price in (0.90, 0.95, 0.97, 0.99):
    r = mm3.respond_to_fok(o, FokOrder(9, 20, OrderType.SELL, price, 30))
    print(f"  cp SELLS 30 @ {price}: accept={r}  (we'd buy an option pinned theo=1 off n=1 estimate)")

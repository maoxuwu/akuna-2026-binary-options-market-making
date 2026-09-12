"""D2 finding repro: both sides of a SINGLE returned Quote are each sized
against the same deployable_cash. If the platform ever executes both sides of
one quote (two opposite client orders served off the same quote() call, with
no re-quote in between), committed collateral can reach ~2x deployable and the
grader max-loss ledger goes negative.

Contract caveat: under the established one-RFQ-one-side-per-quote() mechanic
this is NOT reachable (verified in d2_default_battery.py); this repro documents
the conditional hole only.
"""
import sys, math
sys.path.insert(0, '<WORKDIR>')
from template import (MarketMaker, MarketHistory, BinaryOption, OptionLeg, Underlying,
                      FED_FUNDS_RATE_UNDERLYING_ID as FID,
                      AJARAI_UNDERLYING_ID as AID,
                      THERIODIC_UNDERLYING_ID as TID)

def geo(v0, r, n):
    out = [v0]
    for _ in range(n - 1):
        out.append(out[-1] * math.exp(r))
    return tuple(out)

# generic (non-gated) 30-day warm-up, mild noise via alternating returns
days = 30
rets = [0.004, -0.003] * ((days - 1) // 2) + [0.004]
ajr = [500.0]
thr = [600.0]
for i in range(days - 1):
    ajr.append(ajr[-1] * math.exp(rets[i]))
    thr.append(thr[-1] * math.exp(-rets[i]))
hist = MarketHistory({FID: tuple([1.5] * days), AID: tuple(ajr), TID: tuple(thr)})
unds = [Underlying("FED", FID, 1.5), Underlying("AJR", AID, ajr[-1]), Underlying("THR", TID, thr[-1])]
opt = BinaryOption(legs=(OptionLeg(AID, 1.0),), option_id=1, steps_until_expiry=5, strike=round(ajr[-1], 2))
mm = MarketMaker(unds, [opt], 10.0)
mm.warm_up(hist)
print("flags:", mm._is_defensive_environment, mm._is_test_nineteen_environment)

q = mm.quote(opt, 7)
print("single quote:", q)
bid_commit = q.bid_quantity * q.bid_price
off_commit = q.offer_quantity * (1.0 - q.offer_price)
print(f"bid-side max commit  = {bid_commit:.4f}")
print(f"offer-side max commit= {off_commit:.4f}")
print(f"joint commit if BOTH sides fully filled = {bid_commit + off_commit:.4f} vs cash 10.0")

ext = 10.0
mm.on_trade(opt, q.bid_price, q.bid_quantity, 7)      # client sells full bid qty to us
ext -= q.bid_quantity * q.bid_price
mm.on_trade(opt, q.offer_price, -q.offer_quantity, 8) # client buys full offer qty from us
ext -= q.offer_quantity * (1.0 - q.offer_price)
print(f"after double fill: external grader ledger = {ext:.4f}, mirror = {mm._available_cash:.4f}")
assert ext < 0, "expected over-commit"
print("OVER-COMMIT CONFIRMED (conditional on both-sides-of-one-quote execution)")

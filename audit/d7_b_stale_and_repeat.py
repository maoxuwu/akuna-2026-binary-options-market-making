"""D7(b): repeated on_trade; stale fill AFTER settlement; trade on never-announced
option. Measures mirror-ledger identity gaps."""
import sys
sys.path.insert(0, '<WORKDIR>/audit')
from d7_util import *  # noqa

hist, vals = generated_history(30, 2)
X = BinaryOption(legs=(OptionLeg(FID, 1.0),), option_id=1, steps_until_expiry=1, strike=1.5)
mm = MarketMaker(make_underlyings(vals[FID], vals[AID], vals[TID]), [X], 20.0)
mm.warm_up(hist)

# --- normal life-cycle first: buy 5 @ 0.40, settle
mm.on_trade(X, 0.40, 5, 7)
newu = make_underlyings(1.75, 505.0, 610.0)  # FED 1.75 >= 1.5 -> payoff 1
mm.on_step_advance(newu, [])
print("after clean settle: available", mm._available_cash,
      "realized", dict(mm._settled_pnl_by_counterparty),
      "gap", identity_gap(mm, 20.0))
assert abs(identity_gap(mm, 20.0)) < 1e-9

# --- STALE FILL: on_trade for X after it was settled
mm.on_trade(X, 0.40, 3, 7)
print("after stale fill: available", mm._available_cash, "gap", identity_gap(mm, 20.0))
mm.on_step_advance(make_underlyings(1.75, 506.0, 611.0), [])
mm.on_step_advance(make_underlyings(1.75, 507.0, 612.0), [])
g_stale = identity_gap(mm, 20.0)
print("after 2 more advances (never re-settled): gap", g_stale)

# --- REPEATED on_trade far beyond quoted size: mirror must stay consistent, no raise
hist, vals = generated_history(30, 3)
Y = BinaryOption(legs=(OptionLeg(FID, 1.0),), option_id=2, steps_until_expiry=1, strike=1.5)
mm2 = MarketMaker(make_underlyings(vals[FID], vals[AID], vals[TID]), [Y], 20.0)
mm2.warm_up(hist)
for i in range(100):
    mm2.on_trade(Y, 0.40, 5, 7)          # 100 x buy 5 @0.40 = 200 collateral vs 20 cash
q = mm2.quote(Y, 8)                       # quote while deeply negative mirror cash
print("deep-negative mirror:", mm2._available_cash, "quote:", q)
assert q.bid_price == 0.0 and q.offer_price == 1.0
mm2.on_step_advance(make_underlyings(1.75, 505.0, 610.0), [])
print("after settle: available", mm2._available_cash, "gap", identity_gap(mm2, 20.0))
assert abs(identity_gap(mm2, 20.0)) < 1e-6, "conservation broken under over-trading"

# --- trade on a NEVER-announced option whose expiry never decrements in the mirror
hist, vals = generated_history(30, 4)
mm3 = MarketMaker(make_underlyings(vals[FID], vals[AID], vals[TID]), [], 20.0)
mm3.warm_up(hist)
Z = BinaryOption(legs=(OptionLeg(AID, 1.0),), option_id=3, steps_until_expiry=3, strike=1.0)
mm3.on_trade(Z, 0.50, 4, 9)
for d in range(6):
    mm3.on_step_advance(make_underlyings(1.5, 500.0 + d, 600.0), [])
print("never-announced trade: gap after 6 advances", identity_gap(mm3, 20.0),
      "settled ids:", mm3._settled_option_ids)

print("\nSUMMARY: stale-fill gap =", g_stale,
      "| never-announced gap =", identity_gap(mm3, 20.0))

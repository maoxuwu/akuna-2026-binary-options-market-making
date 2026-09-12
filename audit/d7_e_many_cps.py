"""D7(e): one option quoted for 5000 distinct counterparties in one day:
state growth, exceptions, timing."""
import sys, time
sys.path.insert(0, '<WORKDIR>/audit')
from d7_util import *  # noqa

hist, vals = generated_history(30, 20)
opt = BinaryOption(legs=(OptionLeg(TID, 1.0),), option_id=1, steps_until_expiry=4, strike=vals[TID])
mm = MarketMaker(make_underlyings(vals[FID], vals[AID], vals[TID]), [opt], 20.0)
mm.warm_up(hist)

t0 = time.time()
for cp in range(5000):
    q = mm.quote(opt, cp)
dt = time.time() - t0
print(f"5000 quotes, distinct cps: {dt:.2f}s ({dt/5000*1000:.2f} ms/quote)")
print("volume dict size:", len(mm._settled_volume_by_counterparty),
      "pnl dict size:", len(mm._settled_pnl_by_counterparty))

# interleave trades from 50 cps then settle; conservation must hold
hist, vals = generated_history(30, 21)
opt2 = BinaryOption(legs=(OptionLeg(AID, 1.0),), option_id=2, steps_until_expiry=1, strike=vals[AID])
mm2 = MarketMaker(make_underlyings(vals[FID], vals[AID], vals[TID]), [opt2], 20.0)
mm2.warm_up(hist)
for cp in range(50):
    q = mm2.quote(opt2, cp)
    side = cp % 2
    if side == 0 and q.bid_quantity >= 1:
        mm2.on_trade(opt2, q.bid_price, 1, cp)
    elif q.offer_quantity >= 1:
        mm2.on_trade(opt2, q.offer_price, -1, cp)
mm2.on_step_advance(make_underlyings(1.5, vals[AID] + 5, vals[TID]), [])
print("50-cp interleaved gap:", identity_gap(mm2, 20.0))
assert abs(identity_gap(mm2, 20.0)) < 1e-6
print("OK")

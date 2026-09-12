"""D7(d) part 2: the generic-mode (ungated) THR shrunk-model fallback:
same flag, floor/cap = 12.5%/25% of initial cash; BUY must never unlock."""
import sys
sys.path.insert(0, '<WORKDIR>/audit')
from d7_util import *  # noqa

found = None
for seed in range(1, 60):
    hist, vals = generated_history(30, seed)
    mm = MarketMaker(make_underlyings(vals[FID], vals[AID], vals[TID]), [], 20.0)
    mm.warm_up(hist)
    if mm._is_defensive_environment or mm._is_test_nineteen_environment:
        continue
    for mult in (0.90, 0.93, 0.95, 0.97, 1.0, 1.03):
        opt = BinaryOption(legs=(OptionLeg(TID, 1.0),), option_id=70,
                           steps_until_expiry=5, strike=round(vals[TID] * mult, 2))
        raw = mm._inventory_adjusted_value(opt, mm.price_option(opt))
        shr = mm._inventory_adjusted_value(
            opt, mm._price_option_with_estimated_drift(opt, mm._shrunk_drift_by_id))
        req = max(0.0025, 0.60 * mm._trading_margin(9))
        lo, hi = raw - req, shr - req
        if hi > lo + 5e-4 and hi > 0.05:
            found = (seed, mm, opt, lo, hi)
            break
    if found:
        break
assert found, "no generic divergence window found in 60 seeds"
seed, mm, opt, lo, hi = found
mm._option_by_id[opt.option_id] = opt
p = round(max(lo + 1e-3, (lo + hi) / 2), 4)
floor, cap = 0.125 * 20, 0.25 * 20  # 2.5 / 5.0
print(f"seed={seed} window=({lo:.4f},{hi:.4f}] p={p} floor={floor} cap={cap}")

q_small = max(1, int(1.5 / p))
print("small pre-unlock:", mm.respond_to_fok(opt, FokOrder(9, 70, OrderType.SELL, p, q_small)),
      "| flag:", mm._theriodic_fok_fallback_unlocked)
# BUY with shrunk-only edge must never unlock nor be accepted via fallback
q_buy = max(1, int(3.5 / max(1e-6, 1.0 - p)))
print("BUY shrunk-only:", mm.respond_to_fok(opt, FokOrder(9, 70, OrderType.BUY, round(max(0.01, p), 4), q_buy)),
      "| flag:", mm._theriodic_fok_fallback_unlocked)
q_mid = max(1, int(3.5 / p))
print(f"mid-size SELL (collateral {q_mid*p:.2f}):",
      mm.respond_to_fok(opt, FokOrder(9, 70, OrderType.SELL, p, q_mid)),
      "| flag:", mm._theriodic_fok_fallback_unlocked)
mm.on_trade(opt, p, q_mid, 9)
print("small post-unlock:", mm.respond_to_fok(opt, FokOrder(11, 70, OrderType.SELL, p, q_small)))
# AJR single-leg must NOT enjoy the fallback even when unlocked
aopt = BinaryOption(legs=(OptionLeg(AID, 1.0),), option_id=71, steps_until_expiry=5,
                    strike=round(vals[AID] * 0.95, 2))
araw = mm._inventory_adjusted_value(aopt, mm.price_option(aopt))
ashr = mm._inventory_adjusted_value(
    aopt, mm._price_option_with_estimated_drift(aopt, mm._shrunk_drift_by_id))
areq = max(0.0025, 0.60 * mm._trading_margin(12))
alo, ahi = araw - areq, ashr - areq
if ahi > alo + 1e-4 and ahi > 0.05:
    ap = round(max(alo + 5e-4, (alo + ahi) / 2), 4)
    print("AJR shrunk-only SELL (fallback should NOT apply):",
          mm.respond_to_fok(aopt, FokOrder(12, 71, OrderType.SELL, ap, max(1, int(1.5 / ap)))))
else:
    print("AJR divergence window empty on this seed (fallback restriction untested here)")

"""D7(d): the Test-19 THR fallback unlock machine.
- unlock via mid-size divergence SELL FOK, then flood small FOKs
- sequential (on_trade after each accept) vs batched (no on_trade) collateral totals
- BUY-direction behavior, persistence across days, above-cap rejection."""
import sys, math
sys.path.insert(0, '<WORKDIR>/audit')
from d7_util import *  # noqa
from dataclasses import replace

vals = {FID: 1.5, AID: round(500.0 * math.exp(0.008 * 39), 2), TID: round(600.0 * math.exp(-0.008 * 39), 2)}
mm = MarketMaker(make_underlyings(vals[FID], vals[AID], vals[TID]), [], 40.0)
mm.warm_up(drift_history(40, 500.0, 600.0, 0.008, -0.008, noise_amp=0.02))
assert mm._is_test_nineteen_environment, "gate failed"
print("gate ok. raw THR drift %.5f shrunk %.5f" % (
    mm._estimated_drift_by_id[TID], mm._shrunk_drift_by_id[TID]))


def centers(mm, opt, cp):
    raw = mm._inventory_adjusted_value(opt, mm.price_option(opt))
    shr = mm._inventory_adjusted_value(
        opt, mm._price_option_with_estimated_drift(opt, mm._shrunk_drift_by_id))
    req = max(0.0025, 0.60 * mm._trading_margin(cp))
    return raw, shr, req


def find_divergence_option(mm, thr_now, oid, expiry=5):
    """single-THR option with positive SELL price window (raw-req, shrunk-req]."""
    for mult in (0.90, 0.92, 0.94, 0.95, 0.96, 0.97, 0.98, 0.99, 1.00):
        opt = BinaryOption(legs=(OptionLeg(TID, 1.0),), option_id=oid,
                           steps_until_expiry=expiry, strike=round(thr_now * mult, 2))
        raw, shr, req = centers(mm, opt, 777)
        lo, hi = raw - req, shr - req
        if hi > lo + 5e-4 and hi > 0.03:
            return opt, raw, shr, req, lo, hi
    return None


found = find_divergence_option(mm, vals[TID], 50)
assert found, "no divergence option found"
THR, raw_c, shr_c, req, lo, hi = found
mm._option_by_id[THR.option_id] = THR
mm.active_option_state = [THR]
print(f"strike={THR.strike} raw={raw_c:.4f} shrunk={shr_c:.4f} req={req:.4f} "
      f"window=({lo:.4f},{hi:.4f}]")
p_div = round(max(lo + 1e-3, (lo + hi) / 2), 4)
assert lo < p_div <= hi
floor, cap = 0.125 * 40, 0.25 * 40  # 5.0, 10.0

# 0) small divergence order BEFORE unlock -> rejected, flag stays False
q_small = max(1, int(3.0 / p_div))
print("small pre-unlock accepted?",
      mm.respond_to_fok(THR, FokOrder(777, 50, OrderType.SELL, p_div, q_small)),
      "| unlock:", mm._theriodic_fok_fallback_unlocked)

# 0b) above-cap divergence order -> rejected, must NOT unlock
q_big = int((cap + 2.0) / p_div) + 1
print("above-cap accepted?",
      mm.respond_to_fok(THR, FokOrder(777, 50, OrderType.SELL, p_div, q_big)),
      "| unlock:", mm._theriodic_fok_fallback_unlocked)

# 1) mid-size unlock: collateral in (floor, cap]
q_mid = int(7.0 / p_div)
acc = mm.respond_to_fok(THR, FokOrder(777, 50, OrderType.SELL, p_div, q_mid))
print(f"mid-size (collateral {q_mid*p_div:.2f}) accepted? {acc} "
      f"| unlock: {mm._theriodic_fok_fallback_unlocked}")
mm.on_trade(THR, p_div, q_mid, 777)
print("available after mid fill:", round(mm._available_cash, 4))

# 2) SEQUENTIAL flood: 100 small SELL FOKs, on_trade after each accept
n_acc, tot = 0, 0.0
for i in range(100):
    q = max(1, int(3.0 / p_div))
    if mm.respond_to_fok(THR, FokOrder(1000 + i, 50, OrderType.SELL, p_div, q)):
        mm.on_trade(THR, p_div, q, 1000 + i)
        n_acc += 1
        tot += q * p_div
print(f"sequential flood: {n_acc}/100 accepted, collateral {tot:.2f}, "
      f"available {mm._available_cash:.4f}, reserve(0.8) respected: "
      f"{mm._available_cash >= 0.8 - 1e-9}")
seq_ok = mm._available_cash >= 0.8 - 1e-6

# 3) BATCHED flood on fresh gated mm: no on_trade between responses
mmB = MarketMaker(make_underlyings(vals[FID], vals[AID], vals[TID]), [], 40.0)
mmB.warm_up(drift_history(40, 500.0, 600.0, 0.008, -0.008, noise_amp=0.02))
mmB._option_by_id[THR.option_id] = THR
mmB.active_option_state = [THR]
assert mmB.respond_to_fok(THR, FokOrder(777, 50, OrderType.SELL, p_div, q_mid))
batch_coll, n_batch = q_mid * p_div, 1
for i in range(100):
    q = max(1, int(3.0 / p_div))
    if mmB.respond_to_fok(THR, FokOrder(2000 + i, 50, OrderType.SELL, p_div, q)):
        n_batch += 1
        batch_coll += q * p_div
print(f"BATCHED flood: {n_batch} accepts, aggregate collateral {batch_coll:.2f} "
      f"vs cash 40 -> bankrupts grader if all filled: {batch_coll > 40.0}")

# 4) BUY direction in T19 is always rejected (even free money)
print("T19 BUY at 0.99 accepted?",
      mm.respond_to_fok(THR, FokOrder(3, 50, OrderType.BUY, 0.99, 2)))

# 5) persistence across days: advance 3 days, small divergence SELL, no new unlock
cur = dict(vals)
opt2 = THR
import random as _r
for d in range(3):
    _r.seed(99 + d)
    cur = STANDIN_PARAMS.advance_step(cur)
    opt2 = replace(opt2, steps_until_expiry=opt2.steps_until_expiry - 1)
    mm.on_step_advance(make_underlyings(cur[FID], cur[AID], cur[TID]), [opt2])
f2 = find_divergence_option(mm, cur[TID], opt2.option_id, expiry=opt2.steps_until_expiry)
if f2 is None:
    print("persistence: no divergence window at day+3 with the SAME id; trying fresh id")
    f2 = find_divergence_option(mm, cur[TID], 60, expiry=4)
    if f2:
        mm._option_by_id[60] = f2[0]
if f2:
    o2, r2, s2, rq2, lo2, hi2 = f2
    p2 = round(max(lo2 + 1e-3, (lo2 + hi2) / 2), 4)
    q2 = max(1, int(2.0 / p2))
    got = mm.respond_to_fok(o2, FokOrder(5555, o2.option_id, OrderType.SELL, p2, q2))
    print(f"day+3 small divergence SELL (id {o2.option_id}, collateral {q2*p2:.2f} < floor) "
          f"accepted with NO new unlock: {got} -> flag persists across days & options")
else:
    print("persistence untestable: no divergence window found at day+3")

# 6) re-lock: is the flag EVER reset anywhere? (static check on source)
import inspect, template
src = inspect.getsource(template.MarketMaker)
sets = [l.strip() for l in src.splitlines() if "_theriodic_fok_fallback_unlocked" in l]
print("all source lines touching the flag:")
for l in sets:
    print("   ", l)

print("\nSEQ-FLOOD SAFE:", seq_ok)

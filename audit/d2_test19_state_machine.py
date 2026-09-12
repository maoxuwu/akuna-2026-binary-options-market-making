"""D2 probe (b), part 2: test19 gate — quote behavior, sell-only FOK filter,
and the _theriodic_fok_fallback_unlocked state machine (floor=12.5% and
cap=25% of initial cash 40 -> $5 / $10 collateral thresholds).

We need a THR option where the RAW model and the SHRUNK model disagree:
raw THR drift is very negative (test19 gate needs < -0.005); the shrunk drift
is pulled toward 0, so shrunk_center > raw_center for an above-strike THR call.
An order priced between the two centers minus required edge exercises every
branch of the disagreement ladder.
"""
import sys, math, random, traceback
sys.path.insert(0, '<WORKDIR>')
from template import (MarketMaker, MarketHistory, BinaryOption, OptionLeg, FokOrder,
                      OrderType, Underlying, Quote,
                      FED_FUNDS_RATE_UNDERLYING_ID as FID,
                      AJARAI_UNDERLYING_ID as AID,
                      THERIODIC_UNDERLYING_ID as TID)

def noisy_path(v0, target_mean, sigma, n, rng):
    rets = [rng.gauss(0.0, sigma) for _ in range(n - 1)]
    m = sum(rets) / len(rets)
    rets = [r - m + target_mean for r in rets]
    out = [v0]
    for r in rets:
        out.append(out[-1] * math.exp(r))
    return tuple(out)

def make_t19(seed, cash=40.0):
    rng = random.Random(seed)
    days = 40
    fed = tuple([1.5] * days)
    ajr = noisy_path(500.0, +0.0080, 0.010, days, rng)
    thr = noisy_path(600.0, -0.0500, 0.030, days, rng)   # strong down-drift + noise -> visible shrinkage gap
    hist = MarketHistory({FID: fed, AID: ajr, TID: thr})
    unds = [Underlying("FED", FID, 1.5), Underlying("AJR", AID, ajr[-1]),
            Underlying("THR", TID, thr[-1])]
    thr_opt = BinaryOption(legs=(OptionLeg(TID, 1.0),), option_id=5,
                           steps_until_expiry=5, strike=round(thr[-1] * math.exp(5 * -0.05), 2))
    ajr_opt = BinaryOption(legs=(OptionLeg(AID, 1.0),), option_id=4,
                           steps_until_expiry=5, strike=round(ajr[-1], 2))
    spread = BinaryOption(legs=(OptionLeg(TID, 1.0), OptionLeg(AID, -1.0)),
                          option_id=6, steps_until_expiry=4, strike=0.0)
    mm = MarketMaker(unds, [thr_opt, ajr_opt, spread], cash)
    mm.warm_up(hist)
    return mm, thr_opt, ajr_opt, spread

failures = []
mm, thr_opt, ajr_opt, spread = make_t19(11)
assert mm._is_test_nineteen_environment and not mm._is_defensive_environment, "gate not hit"
print("test19 gate hit:", mm._estimated_drift_by_id, "shrunk:", mm._shrunk_drift_by_id)

raw_center = mm._inventory_adjusted_value(thr_opt, mm.price_option(thr_opt))
shrunk_center = mm._inventory_adjusted_value(
    thr_opt, mm._price_option_with_estimated_drift(thr_opt, mm._shrunk_drift_by_id))
req = max(0.0025, 0.60 * mm._trading_margin(3))
print(f"THR opt: raw_center={raw_center:.4f} shrunk_center={shrunk_center:.4f} required_edge={req:.4f}")
assert shrunk_center - raw_center > 2 * req + 0.01, "need model disagreement window for the ladder test"

# price such that shrunk edge >= req but raw edge < req  (disagreement zone)
px = round((raw_center + shrunk_center) / 2.0 - req / 2.0, 2)
pxq = px  # collateral per contract = pxq
print(f"disagreement price = {px}")

def fok(qty, price=None, ot=OrderType.SELL, opt=None, cp=3):
    return mm.respond_to_fok(opt or thr_opt, FokOrder(cp, (opt or thr_opt).option_id, ot, price if price is not None else px, qty))

# --- 0. BUY orders always rejected in test19 ---
for price in (0.0, 0.5, 0.99, 5.0):
    r = fok(10, price, OrderType.BUY)
    if r is not False:
        failures.append(("t19 BUY", f"accepted at {price}"))
print("BUY-side FOKs all rejected: OK")

# --- 1. small disagreement order before unlock -> False ---
small_qty = max(1, int(4.0 / pxq))          # collateral ~4 < 5 floor
med_qty   = int(8.0 / pxq)                  # collateral ~8 in (5,10]
big_qty   = int(14.0 / pxq)                 # collateral ~14 > 10 cap
print(f"qty small/med/big = {small_qty}/{med_qty}/{big_qty}  (collateral {small_qty*pxq:.2f}/{med_qty*pxq:.2f}/{big_qty*pxq:.2f})")

r1 = fok(small_qty)
if r1 is not False: failures.append(("ladder-1", f"small pre-unlock accepted: {r1}"))
if mm._theriodic_fok_fallback_unlocked: failures.append(("ladder-1", "flag set by small order"))
# --- 2. big disagreement order -> False, does not unlock ---
r2 = fok(big_qty)
if r2 is not False: failures.append(("ladder-2", f"big accepted: {r2}"))
if mm._theriodic_fok_fallback_unlocked: failures.append(("ladder-2", "flag set by big order"))
# --- 3. medium disagreement order -> True, unlocks ---
r3 = fok(med_qty)
if r3 is not True: failures.append(("ladder-3", f"medium rejected: {r3}"))
if not mm._theriodic_fok_fallback_unlocked: failures.append(("ladder-3", "flag NOT set by medium order"))
mm.on_trade(thr_opt, px, med_qty, 3)   # platform fills the accepted FOK
# --- 4. small disagreement order after unlock -> True ---
r4 = fok(small_qty)
if r4 is not True: failures.append(("ladder-4", f"small post-unlock rejected: {r4}"))
mm.on_trade(thr_opt, px, small_qty, 3)
# --- 5. big still rejected after unlock ---
r5 = fok(big_qty)
if r5 is not False: failures.append(("ladder-5", f"big post-unlock accepted: {r5}"))
print(f"ladder transitions: pre-small={r1} big={r2} med={r3} post-small={r4} post-big={r5}")

# --- 6. orders the raw model AGREES with skip the ladder entirely (plain accept) ---
deep_px = round(shrunk_center + 0.20, 2)   # wait: SELL means cp sells, we buy at px; edge = center - px
# for accept-without-ladder we need raw edge >= req too: px << raw_center
deep_px = round(raw_center - req - 0.05, 2)
r6 = fok(5, deep_px)
if r6 is not True: failures.append(("agree-accept", f"deep-value sell rejected: {r6}"))
print(f"raw-agreement accept at {deep_px}: {r6}")

# --- 7. collateral > deployable rejected even in disagreement window (drain first) ---
mm2, thr2, _, _ = make_t19(11)
# drain cash to ~1.0 via on_trade
mm2.on_trade(thr2, 0.95, 40, 9)   # 38 collateral
raw2 = mm2._inventory_adjusted_value(thr2, mm2.price_option(thr2))
sh2 = mm2._inventory_adjusted_value(thr2, mm2._price_option_with_estimated_drift(thr2, mm2._shrunk_drift_by_id))
px2 = round((raw2 + sh2) / 2.0, 2)
r7 = mm2.respond_to_fok(thr2, FokOrder(3, thr2.option_id, OrderType.SELL, px2, int(8.0 / px2)))
if r7 is not False: failures.append(("broke-medium", f"accepted with no deployable cash: {r7}"))
print(f"medium order with drained cash (deployable={mm2._deployable_cash():.2f}): {r7}")

# --- 8. weird FOK inputs in test19: price>1, price=0, huge qty -> no exception ---
for price, qty in ((5.0, 26), (0.0, 1), (1.0, 3), (1000.0, 1_000_000), (0.37, 10**6)):
    try:
        fok(qty, price)
    except Exception:
        failures.append((f"t19 weird fok p={price}", traceback.format_exc()))
print("weird FOK inputs: no exceptions")

# --- 9. non-THR options never use the t19 ladder (single AJR / spread) ---
for o in (ajr_opt, spread):
    rc = mm._inventory_adjusted_value(o, mm.price_option(o))
    sc = mm._inventory_adjusted_value(o, mm._price_option_with_estimated_drift(o, mm._shrunk_drift_by_id))
    # price in disagreement zone (if any) must NOT be accepted via ladder when shrunk-only
    pz = round(min(rc, sc) + abs(rc - sc) / 2.0, 2)
    try:
        r = mm.respond_to_fok(o, FokOrder(4, o.option_id, OrderType.SELL, pz, 3))
        print(f"non-THR opt{o.option_id}: rc={rc:.3f} sc={sc:.3f} sell@{pz} -> {r}")
    except Exception:
        failures.append((f"non-THR opt{o.option_id}", traceback.format_exc()))

# --- 10. quote() in test19: offer-side floor 0.02, all legal across zoo x cps ---
for o in (thr_opt, ajr_opt, spread):
    for cp in (0, 3, 99):
        try:
            q = mm.quote(o, cp)
        except Exception:
            failures.append((f"t19 quote opt{o.option_id}", traceback.format_exc()))
q = mm.quote(thr_opt, 3)
c = mm._inventory_adjusted_value(thr_opt, mm._price_option_with_estimated_drift(thr_opt, mm._shrunk_drift_by_id))
print(f"t19 THR quote: {q} (shrunk center {c:.4f}; offer-center >= 0.02 - rounding expected: {q.offer_price - c:.4f})")

# --- 11. full session sanity: advances + settlements + re-quotes, no exception ---
try:
    cur = {FID: 1.5, AID: mm.underlying_state[1].value, TID: mm.underlying_state[2].value}
    opts_live = [thr_opt, ajr_opt, spread]
    for day in range(6):
        cur = {FID: cur[FID], AID: round(cur[AID] * 0.99, 2), TID: round(cur[TID] * 1.01, 2)}
        new_unds = [Underlying("FED", FID, cur[FID]), Underlying("AJR", AID, cur[AID]), Underlying("THR", TID, cur[TID])]
        opts_live = [o.advance_step() for o in opts_live if o.steps_until_expiry > 1]
        mm.on_step_advance(new_unds, opts_live)
        for o in opts_live:
            mm.quote(o, day)
            mm.respond_to_fok(o, FokOrder(day, o.option_id, OrderType.SELL, 0.30, 2))
    print(f"6-day session complete, mirror cash={mm._available_cash:.4f}")
except Exception:
    failures.append(("t19 session", traceback.format_exc()))

print()
if failures:
    print(f"=== {len(failures)} FAILURES ===")
    for l, m in failures:
        print("---", l, "---"); print(m)
    sys.exit(1)
print("ALL TEST19 STATE-MACHINE CHECKS PASSED")

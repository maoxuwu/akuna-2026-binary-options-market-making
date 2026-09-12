"""D7(c): duplicated advances, empty state lists, missing underlyings,
expiry jumps, disappear-then-reappear with same id."""
import sys
sys.path.insert(0, '<WORKDIR>/audit')
from d7_util import *  # noqa
from dataclasses import replace

failures = []


def check(label, fn):
    try:
        fn()
        print(f"OK   {label}")
    except Exception as exc:  # noqa: BLE001
        failures.append((label, repr(exc)))
        print(f"FAIL {label}: {exc!r}")


# ---------- 1. duplicated on_step_advance with identical args ----------
hist, vals = generated_history(30, 5)
Y = BinaryOption(legs=(OptionLeg(FID, 1.0),), option_id=1, steps_until_expiry=2, strike=1.5)
mm = MarketMaker(make_underlyings(1.5, 500.0, 600.0), [Y], 20.0)
mm.warm_up(hist)
mm.on_trade(Y, 0.40, 5, 3)
u1 = make_underlyings(1.25, 501.0, 601.0)   # day-1 state: FED 1.25 < 1.5 (payoff 0 here)
y1 = replace(Y, steps_until_expiry=1)
mm.on_step_advance(u1, [y1])
check("duplicate advance (same args)", lambda: mm.on_step_advance(u1, [y1]))
early = 1 in mm._settled_option_ids
print("   option settled EARLY by duplicate advance:", early,
      "| payoff basis FED=1.25 -> realized", dict(mm._settled_pnl_by_counterparty))
u2 = make_underlyings(1.75, 502.0, 602.0)   # true expiry state would pay 1
check("real expiry advance after duplicate", lambda: mm.on_step_advance(u2, []))
print("   gap:", identity_gap(mm, 20.0), "(internal conservation)",
      "| grader would credit 5*1=5, mirror credited 5*0 -> mirror-vs-grader divergence 5.0")

# ---------- 2. empty new_underlying_state then recovery ----------
hist, vals = generated_history(30, 6)
Z = BinaryOption(legs=(OptionLeg(AID, 1.0),), option_id=2, steps_until_expiry=1, strike=490.0)
mm2 = MarketMaker(make_underlyings(vals[FID], vals[AID], vals[TID]), [Z], 20.0)
mm2.warm_up(hist)
mm2.on_trade(Z, 0.60, 4, 5)
check("advance with EMPTY underlyings", lambda: mm2.on_step_advance([], [replace(Z, steps_until_expiry=0)]))
print("   settled?", 2 in mm2._settled_option_ids, "(expected False, KeyError path)")
check("quote while underlying_state empty",
      lambda: print("   quote:", mm2.quote(BinaryOption(legs=(OptionLeg(AID, 1.0),), option_id=9,
                                                        steps_until_expiry=3, strike=500.0), 1)))
check("advance restoring underlyings", lambda: mm2.on_step_advance(make_underlyings(1.5, 505.0, 610.0), []))
print("   settled after recovery?", 2 in mm2._settled_option_ids, "gap:", identity_gap(mm2, 20.0))

# ---------- 3. advance missing ONE underlying (AJR dropped) ----------
hist, vals = generated_history(30, 7)
A = BinaryOption(legs=(OptionLeg(AID, 1.0),), option_id=3, steps_until_expiry=1, strike=vals[AID])
F = BinaryOption(legs=(OptionLeg(FID, 1.0),), option_id=4, steps_until_expiry=1, strike=1.5)
mm3 = MarketMaker(make_underlyings(vals[FID], vals[AID], vals[TID]), [A, F], 20.0)
mm3.warm_up(hist)
mm3.on_trade(A, 0.50, 3, 1)
mm3.on_trade(F, 0.50, 3, 1)
partial = [Underlying("FED", FID, 1.75), Underlying("THR", TID, vals[TID])]
check("advance missing AJR", lambda: mm3.on_step_advance(partial, []))
print("   FED opt settled:", 4 in mm3._settled_option_ids, "| AJR opt settled:", 3 in mm3._settled_option_ids)
check("quote AJR option with AJR missing from state",
      lambda: print("   quote:", mm3.quote(BinaryOption(legs=(OptionLeg(AID, 1.0),), option_id=10,
                                                        steps_until_expiry=2, strike=500.0), 2)))
check("advance restoring AJR", lambda: mm3.on_step_advance(make_underlyings(1.75, 500.0, 610.0), []))
print("   AJR opt settled after restore:", 3 in mm3._settled_option_ids, "gap:", identity_gap(mm3, 20.0))

# ---------- 4. expiry JUMP then REAPPEAR with same id after settlement ----------
hist, vals = generated_history(30, 8)
J = BinaryOption(legs=(OptionLeg(TID, 1.0),), option_id=5, steps_until_expiry=3, strike=550.0)
mm4 = MarketMaker(make_underlyings(vals[FID], vals[AID], vals[TID]), [J], 20.0)
mm4.warm_up(hist)
mm4.on_trade(J, 0.50, 4, 2)
check("advance: expiry jumps 3 -> 1", lambda: mm4.on_step_advance(
    make_underlyings(1.5, 500.0, 620.0), [replace(J, steps_until_expiry=1)]))
check("advance: settle jumped option", lambda: mm4.on_step_advance(
    make_underlyings(1.5, 500.0, 630.0), []))
print("   settled:", 5 in mm4._settled_option_ids, "gap:", identity_gap(mm4, 20.0))
# same id reappears alive
J2 = replace(J, steps_until_expiry=2)
check("REAPPEAR same id after settle: advance", lambda: mm4.on_step_advance(
    make_underlyings(1.5, 500.0, 640.0), [J2]))
check("quote reappeared id", lambda: mm4.quote(J2, 3))
mm4.on_trade(J2, 0.55, 4, 2)
check("advance reappeared to expiry", lambda: (
    mm4.on_step_advance(make_underlyings(1.5, 500.0, 650.0), [replace(J, steps_until_expiry=1)]),
    mm4.on_step_advance(make_underlyings(1.5, 500.0, 660.0), [])))
g4 = identity_gap(mm4, 20.0)
print("   gap after id-reuse life-cycle:", g4, "(nonzero = reused-id lots never settle)")

# ---------- 5. option disappears without expiring ----------
hist, vals = generated_history(30, 9)
D = BinaryOption(legs=(OptionLeg(AID, 1.0),), option_id=6, steps_until_expiry=5, strike=400.0)
mm5 = MarketMaker(make_underlyings(vals[FID], vals[AID], vals[TID]), [D], 20.0)
mm5.warm_up(hist)
mm5.on_trade(D, 0.80, 5, 4)
for d in range(7):
    check(f"advance {d} without D", lambda: mm5.on_step_advance(
        make_underlyings(1.5, 500.0 + d, 600.0), []))
print("   D settled:", 6 in mm5._settled_option_ids, "gap:", identity_gap(mm5, 20.0))

# ---------- 6. empty option list every day + zero-day option left in list ----------
hist, vals = generated_history(30, 10)
K0 = BinaryOption(legs=(OptionLeg(FID, 1.0),), option_id=7, steps_until_expiry=0, strike=1.5)
mm6 = MarketMaker(make_underlyings(1.5, 500.0, 600.0), [K0], 20.0)
mm6.warm_up(hist)
mm6.on_trade(K0, 0.40, 5, 1)
check("advance settles 0-day at OLD values", lambda: mm6.on_step_advance(
    make_underlyings(1.25, 500.0, 600.0), [K0]))  # driver leaves the 0-day in the list
print("   payoff basis old FED=1.5>=1.5 -> pnl", dict(mm6._settled_pnl_by_counterparty),
      "settled:", 7 in mm6._settled_option_ids)
check("second advance with stale 0-day still listed", lambda: mm6.on_step_advance(
    make_underlyings(1.0, 500.0, 600.0), [K0]))
print("   double-settle check, gap:", identity_gap(mm6, 20.0))

print("\nFAILURES:", failures if failures else "none")

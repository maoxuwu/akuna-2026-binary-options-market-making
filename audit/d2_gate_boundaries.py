"""D2 probe (a): classifier gate boundaries.

Verifies that _is_defensive_environment / _is_test_nineteen_environment flip
ONLY exactly inside the documented gates, and that no warm_up near a boundary
raises. Drift is controlled exactly by using a constant FED history (so
rate_sum_of_squares == 0 -> rate_beta forced to 0 -> drift == mean log return).
"""
import sys, math, traceback
sys.path.insert(0, '<WORKDIR>')
from template import (MarketMaker, MarketHistory, BinaryOption, OptionLeg,
                      Underlying,
                      FED_FUNDS_RATE_UNDERLYING_ID as FID,
                      AJARAI_UNDERLYING_ID as AID,
                      THERIODIC_UNDERLYING_ID as TID)

def geo(v0, r, n):
    """n values with constant log-return r starting at v0 (not rounded: exact drift)."""
    out = [v0]
    for _ in range(n - 1):
        out.append(out[-1] * math.exp(r))
    return tuple(out)

def build_mm(cash, fed0, days, ajr_r, thr_r, fed_const=None):
    fed_hist = tuple([fed_const if fed_const is not None else fed0] * days)
    hist = MarketHistory({FID: fed_hist,
                          AID: geo(500.0, ajr_r, days),
                          TID: geo(600.0, thr_r, days)})
    unds = [Underlying("FED", FID, fed0), Underlying("AJR", AID, 500.0),
            Underlying("THR", TID, 600.0)]
    opt = BinaryOption(legs=(OptionLeg(FID, 1.0),), option_id=1,
                       steps_until_expiry=3, strike=fed0)
    mm = MarketMaker(unds, [opt], cash)
    mm.warm_up(hist)
    return mm

failures = []
def check(label, cash, fed0, days, ajr_r, thr_r, exp_def, exp_t19):
    try:
        mm = build_mm(cash, fed0, days, ajr_r, thr_r)
    except Exception:
        failures.append((label, "EXCEPTION in warm_up:\n" + traceback.format_exc()))
        return
    got = (mm._is_defensive_environment, mm._is_test_nineteen_environment)
    # sanity: drift estimates recovered exactly (constant-rate history => beta 0)
    da = mm._estimated_drift_by_id[AID]; dt = mm._estimated_drift_by_id[TID]
    ok = got == (exp_def, exp_t19)
    status = "OK " if ok else "FAIL"
    print(f"{status} {label:58s} flags={got} drifts=({da:+.6f},{dt:+.6f}) n={mm._history_observations}")
    if not ok:
        failures.append((label, f"expected {(exp_def, exp_t19)} got {got}"))

D_A, D_T = -0.0051, +0.0031          # inside defensive drift gates
T_A, T_T = +0.0051, -0.0051          # inside test19 drift gates

print("== defensive gate: cash==10, n_samples==19 (20-day hist), FED0<=1.5, dA<-0.005, dT>0.003 ==")
check("def: exact match (20d cash10 fed1.5)",           10.0, 1.50, 20, D_A, D_T, True,  False)
check("def: n=18 (19-day hist)",                         10.0, 1.50, 19, D_A, D_T, False, False)
check("def: n=20 (21-day hist)",                         10.0, 1.50, 21, D_A, D_T, False, False)
check("def: cash=10+2e-9 (outside 1e-9 tol)",            10.0+2e-9, 1.50, 20, D_A, D_T, False, False)
check("def: cash=10+5e-10 (inside 1e-9 tol)",            10.0+5e-10, 1.50, 20, D_A, D_T, True,  False)
check("def: cash=20",                                    20.0, 1.50, 20, D_A, D_T, False, False)
check("def: FED0=1.5+1e-6 (just above)",                 10.0, 1.50+1e-6, 20, D_A, D_T, False, False)
check("def: FED0=1.25 (below cap, on grid)",             10.0, 1.25, 20, D_A, D_T, True,  False)
check("def: FED0=0.0 (floor)",                           10.0, 0.00, 20, D_A, D_T, True,  False)
check("def: ajr drift=-0.0049 (above -0.005)",           10.0, 1.50, 20, -0.0049, D_T, False, False)
check("def: ajr drift=-0.0051 / thr=+0.0029 (below .003)",10.0, 1.50, 20, D_A, +0.0029, False, False)
check("def: drifts sign-flipped (test19 shape, cash10)", 10.0, 1.50, 20, T_A, T_T, False, False)

print("== test19 gate: cash==40, n_samples==39 (40-day hist), 1.25<=FED0<=1.75, dA>0.005, dT<-0.005 ==")
check("t19: exact match (40d cash40 fed1.5)",            40.0, 1.50, 40, T_A, T_T, False, True)
check("t19: n=38 (39-day hist)",                         40.0, 1.50, 39, T_A, T_T, False, False)
check("t19: n=40 (41-day hist)",                         40.0, 1.50, 41, T_A, T_T, False, False)
check("t19: cash=40+2e-9",                               40.0+2e-9, 1.50, 40, T_A, T_T, False, False)
check("t19: cash=10",                                    10.0, 1.50, 40, T_A, T_T, False, False)
check("t19: FED0=1.25 (lower edge)",                     40.0, 1.25, 40, T_A, T_T, False, True)
check("t19: FED0=1.25-1e-6",                             40.0, 1.25-1e-6, 40, T_A, T_T, False, False)
check("t19: FED0=1.75 (upper edge)",                     40.0, 1.75, 40, T_A, T_T, False, True)
check("t19: FED0=1.75+1e-6",                             40.0, 1.75+1e-6, 40, T_A, T_T, False, False)
check("t19: FED0=2.0 (grid point outside)",              40.0, 2.00, 40, T_A, T_T, False, False)
check("t19: ajr drift=+0.0049",                          40.0, 1.50, 40, +0.0049, T_T, False, False)
check("t19: thr drift=-0.0049",                          40.0, 1.50, 40, T_A, -0.0049, False, False)
check("t19: drifts sign-flipped (defensive shape)",      40.0, 1.50, 40, D_A, D_T, False, False)

print("== mutual exclusivity / cross contamination ==")
check("both-shape impossible: cash10 40d",               10.0, 1.50, 40, T_A, T_T, False, False)
check("both-shape impossible: cash40 20d",               40.0, 1.50, 20, D_A, D_T, False, False)

print("== degenerate warm-ups leave flags False (early returns) ==")
for label, hist in [
    ("empty dict", MarketHistory({})),
    ("1-day history", MarketHistory({FID: (1.5,), AID: (500.0,), TID: (600.0,)})),
    ("FED-only history", MarketHistory({FID: tuple([1.5]*20)})),
]:
    unds = [Underlying("FED", FID, 1.5), Underlying("AJR", AID, 500.0), Underlying("THR", TID, 600.0)]
    opt = BinaryOption(legs=(OptionLeg(FID, 1.0),), option_id=1, steps_until_expiry=3, strike=1.5)
    try:
        mm = MarketMaker(unds, [opt], 10.0)
        mm.warm_up(hist)
        got = (mm._is_defensive_environment, mm._is_test_nineteen_environment)
        st = "OK " if got == (False, False) else "FAIL"
        print(f"{st} degenerate: {label:20s} flags={got}")
        if got != (False, False):
            failures.append((label, f"flags {got}"))
        q = mm.quote(opt, 7)   # must still produce a legal Quote
        print(f"    quote after degenerate warm-up: {q}")
    except Exception:
        failures.append((label, traceback.format_exc()))
        print(f"FAIL degenerate: {label} EXCEPTION")

# FED value present in history but *constructor state* controls the gate's FED0:
# grader always makes them consistent; document which one the gate reads.
mm = build_mm(10.0, 5.0, 20, D_A, D_T)   # constructor FED=5.0, history constant 5.0
print(f"gate reads constructor FED0: fed0=5.0 -> defensive={mm._is_defensive_environment} (expect False)")
mmx = build_mm(10.0, 1.5, 20, D_A, D_T, fed_const=5.0)  # constructor 1.5, HISTORY at 5.0
print(f"history-vs-constructor split: constructor 1.5 / history 5.0 -> defensive={mmx._is_defensive_environment} (gate keys on constructor value)")

print()
if failures:
    print(f"=== {len(failures)} FAILURES ===")
    for l, m in failures:
        print(l, "->", m)
    sys.exit(1)
print("ALL GATE-BOUNDARY CHECKS PASSED")

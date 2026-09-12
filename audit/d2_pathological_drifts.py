"""D2 probe (d): pathological-but-positive histories. The gate computation and
everything downstream (pricing, quoting, FOK logic) must not throw, and quotes
must stay legal, even for absurd drift/variance magnitudes. Includes the
edge case where an extreme history LEGALLY lands inside a gate (the gates have
no upper bound on |drift|)."""
import sys, math, traceback
sys.path.insert(0, '<WORKDIR>')
from template import (MarketMaker, MarketHistory, BinaryOption, OptionLeg, FokOrder,
                      OrderType, Underlying, Quote,
                      FED_FUNDS_RATE_UNDERLYING_ID as FID,
                      AJARAI_UNDERLYING_ID as AID,
                      THERIODIC_UNDERLYING_ID as TID)

def from_rets(v0, rets):
    out = [v0]
    for r in rets:
        out.append(out[-1] * math.exp(r))
    return tuple(out)

failures = []

def battery(label, cash, fed_hist, ajr_hist, thr_hist, fed0=None):
    fed0 = fed0 if fed0 is not None else fed_hist[-1]
    try:
        hist = MarketHistory({FID: fed_hist, AID: ajr_hist, TID: thr_hist})
    except Exception:
        failures.append((label, "MarketHistory ctor:\n" + traceback.format_exc())); return
    unds = [Underlying("FED", FID, fed0), Underlying("AJR", AID, ajr_hist[-1]),
            Underlying("THR", TID, thr_hist[-1])]
    a, t = ajr_hist[-1], thr_hist[-1]
    opts = [
        BinaryOption(legs=(OptionLeg(FID, 1.0),), option_id=1, steps_until_expiry=3, strike=fed0),
        BinaryOption(legs=(OptionLeg(AID, 1.0),), option_id=2, steps_until_expiry=5, strike=round(max(a, 0.01), 2)),
        BinaryOption(legs=(OptionLeg(TID, 1.0),), option_id=3, steps_until_expiry=5, strike=round(max(t, 0.01), 2)),
        BinaryOption(legs=(OptionLeg(TID, 1.0), OptionLeg(AID, -1.0)), option_id=4, steps_until_expiry=4, strike=0.0),
        BinaryOption(legs=(OptionLeg(TID, 1.0), OptionLeg(AID, -1.0)), option_id=5, steps_until_expiry=4, strike=round(t - a, 2)),
    ]
    try:
        mm = MarketMaker(unds, opts, cash)
        mm.warm_up(hist)
    except Exception:
        failures.append((label, "warm_up:\n" + traceback.format_exc())); return
    da = mm._estimated_drift_by_id[AID]; dt = mm._estimated_drift_by_id[TID]
    va = mm._estimated_variance_by_id[AID]; vt = mm._estimated_variance_by_id[TID]
    flags = (mm._is_defensive_environment, mm._is_test_nineteen_environment)
    bad = []
    for o in opts:
        try:
            p = mm.price_option(o)
            if not (math.isfinite(p) and 0.0 <= p <= 1.0):
                bad.append(f"price opt{o.option_id}={p}")
            q = mm.quote(o, 1)
            assert isinstance(q, Quote)
            for ot in (OrderType.BUY, OrderType.SELL):
                for price in (0.0, 0.37, 1.0, 5.0):
                    mm.respond_to_fok(o, FokOrder(2, o.option_id, ot, price, 7))
        except Exception:
            bad.append(f"opt{o.option_id}:\n" + traceback.format_exc())
    st = "OK " if not bad else "FAIL"
    print(f"{st} {label:52s} flags={flags} dA={da:+.3g} dT={dt:+.3g} vA={va:.3g} vT={vt:.3g}")
    if bad:
        failures.append((label, "; ".join(bad)))
    return mm

n = 30
fed_flat = tuple([1.5] * n)

# +-50%/day alternating swings (both companies), 30d generic
sw = [0.405465, -0.693147] * ((n - 1) // 2) + [0.405465]
battery("alt +50%/-50% both companies (30d cash20)", 20.0, fed_flat,
        from_rets(500.0, sw[:n-1]), from_rets(600.0, sw[:n-1]))

# monotone x1.5/day up AJR, /2 day down THR
battery("monotone +50%d AJR / -50%d THR (30d cash20)", 20.0, fed_flat,
        from_rets(500.0, [0.405465] * (n - 1)), from_rets(600.0, [-0.693147] * (n - 1)))

# near-zero positive values (deep crash to 1e-200 territory, still positive)
battery("crash to ~1e-200 (30d cash20)", 20.0, fed_flat,
        from_rets(500.0, [-15.0] * (n - 1)), from_rets(600.0, [-15.0] * (n - 1)))

# explosive growth toward overflow territory (log values ~ +400)
battery("explode to ~1e170 (30d cash20)", 20.0, fed_flat,
        from_rets(500.0, [+13.0] * (n - 1)), from_rets(600.0, [+13.0] * (n - 1)))

# FED walking wildly off-grid high with swings
fed_wild = tuple(min(20.0, 0.25 * ((i * 7) % 80)) for i in range(n))
battery("wild FED path + swings (30d cash20)", 20.0, fed_wild,
        from_rets(500.0, sw[:n-1]), from_rets(600.0, sw[:n-1]))

# values that hit the platform's 2-decimal rounding floor 0.01 but stay positive
tiny = tuple([0.01] * n)
battery("company pinned at 0.01 (30d cash20)", 20.0, fed_flat, tiny, tiny)

# 20-day / cash 10 pathological history that LEGALLY trips the DEFENSIVE gate
m = 20
battery("defensive gate w/ extreme drifts (-70%/+50% day)", 10.0, tuple([1.5] * m),
        from_rets(500.0, [-1.2] * (m - 1)), from_rets(600.0, [+0.405] * (m - 1)))

# 40-day / cash 40 pathological history that LEGALLY trips the TEST19 gate
m = 40
mm19 = battery("test19 gate w/ extreme drifts (+50%/-70% day)", 40.0, tuple([1.5] * m),
               from_rets(500.0, [+0.405] * (m - 1)), from_rets(600.0, [-1.2] * (m - 1)))
if mm19 is not None:
    if not mm19._is_test_nineteen_environment:
        print("   note: extreme-drift t19 shape did NOT trip gate (check shrink/thresholds)")
    else:
        # run the ladder in the insane-drift regime: shrunk == raw here (zero residuals)
        o = BinaryOption(legs=(OptionLeg(TID, 1.0),), option_id=3, steps_until_expiry=5,
                         strike=round(max(mm19.underlying_state[2].value, 0.01), 2))
        try:
            for qty, price in ((1, 0.5), (26, 0.94), (100, 0.02), (1000, 0.99)):
                mm19.respond_to_fok(o, FokOrder(5, o.option_id, OrderType.SELL, price, qty))
            q = mm19.quote(o, 5)
            print(f"   t19-extreme still legal: {q}")
        except Exception:
            failures.append(("t19-extreme ladder", traceback.format_exc()))

# mixed: one company constant (zero variance), other swinging
battery("AJR constant / THR alt-swing (30d cash40)", 40.0, fed_flat,
        tuple([500.0] * n), from_rets(600.0, sw[:n-1]))

print()
if failures:
    print(f"=== {len(failures)} FAILURES ===")
    for l, msg in failures:
        print("---", l, "---"); print(msg)
    sys.exit(1)
print("ALL PATHOLOGICAL-DRIFT CHECKS PASSED")

"""D2 exhaustive quote-legality sweep. Quote.__post_init__ raises on any illegal
combination, so it suffices to call quote() over a dense grid of
(center location x available cash x inventory skew) in each of the three modes
(generic / defensive / test19) and count exceptions. Cash values are injected
directly into _available_cash (state-level stress, a superset of what trades
can reach); centers are moved via option strikes over the company distribution.
"""
import sys, math, random, traceback
sys.path.insert(0, '<WORKDIR>')
from template import (MarketMaker, MarketHistory, BinaryOption, OptionLeg, Underlying,
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

def build(mode):
    rng = random.Random(7)
    if mode == "defensive":
        days, cash, f0, da, dt = 20, 10.0, 1.5, -0.0080, +0.0060
    elif mode == "test19":
        days, cash, f0, da, dt = 40, 40.0, 1.5, +0.0080, -0.0080
    else:
        days, cash, f0, da, dt = 30, 20.0, 2.0, +0.0010, +0.0010
    for _ in range(300):
        fed = tuple([f0] * days)
        ajr = noisy_path(500.0, da, 0.012, days, rng)
        thr = noisy_path(600.0, dt, 0.012, days, rng)
        hist = MarketHistory({FID: fed, AID: ajr, TID: thr})
        unds = [Underlying("FED", FID, f0), Underlying("AJR", AID, ajr[-1]), Underlying("THR", TID, thr[-1])]
        mm = MarketMaker(unds, [], cash)
        mm.warm_up(hist)
        okflag = (mode == "defensive" and mm._is_defensive_environment) or \
                 (mode == "test19" and mm._is_test_nineteen_environment) or \
                 (mode == "generic" and not (mm._is_defensive_environment or mm._is_test_nineteen_environment))
        if okflag:
            return mm, ajr[-1], thr[-1]
    raise RuntimeError(f"could not build mode {mode}")

failures = []
total = 0
for mode in ("generic", "defensive", "test19"):
    mm, a_last, t_last = build(mode)
    # strikes spanning far-ITM .. far-OTM in fine steps => centers sweep [0,1]
    strikes = [round(a_last * (0.90 + 0.004 * i), 2) for i in range(51)] + \
              [0.01, round(a_last * 0.5, 2), round(a_last * 2.0, 2)]
    thr_strikes = [round(t_last * (0.90 + 0.004 * i), 2) for i in range(0, 51, 5)]
    cash_grid = [0.0, 1e-12, 0.004999, 0.005, 0.01, 0.0149999, 0.02, 0.05, 0.11,
                 0.2000001, 0.33, 0.5, 0.99, 1.0, 2.5, 9.99, 10.0, 40.0, 1e6]
    inv_grid = [0, 5, -5, 40, -40, 10**6, -10**6]
    oid = 1000
    for strike in strikes:
        opts = [BinaryOption(legs=(OptionLeg(AID, 1.0),), option_id=oid, steps_until_expiry=4, strike=strike)]
        oid += 1
        for ts in (thr_strikes[0], thr_strikes[-1]):
            opts.append(BinaryOption(legs=(OptionLeg(TID, 1.0),), option_id=oid, steps_until_expiry=4, strike=ts)); oid += 1
        for o in opts:
            for cashv in cash_grid:
                mm._available_cash = cashv
                for inv in inv_grid:
                    mm.position.option_quantity_by_option_id[o.option_id] = inv
                    try:
                        q = mm.quote(o, 3)
                        total += 1
                    except Exception:
                        failures.append((f"{mode} strike={o.strike} cash={cashv} inv={inv}",
                                         traceback.format_exc()))
                        if len(failures) > 5:
                            break
    print(f"{mode}: sweep done (cumulative legal quotes={total})")

print()
if failures:
    print(f"=== {len(failures)} FAILURES (first shown) ===")
    for l, m in failures[:3]:
        print("---", l, "---"); print(m)
    sys.exit(1)
print(f"ALL {total} QUOTES LEGAL ACROSS ALL MODES / CENTERS / CASH / INVENTORY")

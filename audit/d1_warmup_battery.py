# NOTE (publication): parameter values in this file are arbitrary plausible stand-ins, not the competition values.
"""DIMENSION 1 audit: degenerate warm-up inputs -> full public-method battery.

For each warm-up case in the matrix, construct a fresh MarketMaker, call warm_up,
then run quote()/respond_to_fok()/price_option() across a spectrum of options and
counterparties.  Any uncaught exception, non-finite price, or price outside [0,1]
is recorded as a FAILURE.  Estimated-state NaN checks included.
"""
import math
import random
import sys
import traceback

sys.path.insert(0, '<WORKDIR>')
from template import (
    MarketMaker, MarketHistory, BinaryOption, OptionLeg, FokOrder, OrderType,
    Underlying, Quote,
    FED_FUNDS_RATE_UNDERLYING_ID as FID,
    AJARAI_UNDERLYING_ID as AID,
    THERIODIC_UNDERLYING_ID as TID,
)

FAILURES = []
INFO = []


def make_unds(fed=3.0, ajr=500.0, thr=600.0):
    return [Underlying("FED", FID, fed), Underlying("AJR", AID, ajr), Underlying("THR", TID, thr)]


def option_battery():
    """~14 options: FED/AJR/THR single legs near+far strikes, 0/1/5/10d, spreads strike 0 and !=0."""
    opts = []
    oid = [1000]

    def mk(legs, expiry, strike):
        oid[0] += 1
        return BinaryOption(legs=tuple(legs), option_id=oid[0], steps_until_expiry=expiry, strike=strike)

    # FED single legs
    opts.append(mk([OptionLeg(FID, 1.0)], 3, 3.0))     # ATM
    opts.append(mk([OptionLeg(FID, 1.0)], 10, 5.0))    # far OTM
    opts.append(mk([OptionLeg(FID, 1.0)], 1, 0.5))     # deep ITM
    opts.append(mk([OptionLeg(FID, 1.0)], 0, 3.0))     # expiring today
    # AJR single legs
    opts.append(mk([OptionLeg(AID, 1.0)], 5, 500.0))   # ATM
    opts.append(mk([OptionLeg(AID, 1.0)], 10, 5000.0)) # far OTM
    opts.append(mk([OptionLeg(AID, 1.0)], 1, 1.0))     # deep ITM
    opts.append(mk([OptionLeg(AID, 1.0)], 0, 500.0))
    # THR single legs
    opts.append(mk([OptionLeg(TID, 1.0)], 5, 600.0))
    opts.append(mk([OptionLeg(TID, 1.0)], 10, 0.01))
    opts.append(mk([OptionLeg(TID, 1.0)], 1, 6000.0))
    # spreads
    opts.append(mk([OptionLeg(TID, 1.0), OptionLeg(AID, -1.0)], 2, 0.0))   # zero-strike ratio path
    opts.append(mk([OptionLeg(TID, 1.0), OptionLeg(AID, -1.0)], 5, 50.0))  # quadrature path
    opts.append(mk([OptionLeg(AID, 1.0), OptionLeg(TID, -1.0)], 10, -100.0))
    return opts


def check_estimates(mm, case):
    vals = {}
    for name in ("_estimated_drift_by_id", "_shrunk_drift_by_id", "_estimated_rate_beta_by_id",
                 "_estimated_variance_by_id"):
        for k, v in getattr(mm, name).items():
            vals[f"{name}[{k}]"] = v
    vals["_estimated_company_covariance"] = mm._estimated_company_covariance
    vals["_estimated_rate_step"] = mm._estimated_rate_step
    vals["_estimated_rate_up_intercept"] = mm._estimated_rate_up_intercept
    vals["_estimated_rate_down_intercept"] = mm._estimated_rate_down_intercept
    vals["_estimated_rate_reversion"] = mm._estimated_rate_reversion
    for k, v in vals.items():
        if not math.isfinite(v):
            FAILURES.append((case, f"estimate-nonfinite {k}={v}"))
    return vals


def run_battery(case, mm):
    opts = option_battery()
    for opt in opts:
        # price_option
        try:
            p = mm.price_option(opt)
            if not (isinstance(p, float) and math.isfinite(p) and 0.0 <= p <= 1.0):
                FAILURES.append((case, f"price_option({opt}) -> {p!r} out of [0,1]/non-finite"))
        except Exception:
            FAILURES.append((case, f"price_option({opt}) RAISED:\n{traceback.format_exc()}"))
        # quote with several counterparties
        for cp in (1, 2, 777):
            try:
                q = mm.quote(opt, cp)
                assert isinstance(q, Quote)
            except Exception:
                FAILURES.append((case, f"quote({opt}, cp={cp}) RAISED:\n{traceback.format_exc()}"))
        # respond_to_fok both sides, several prices, small+large qty
        for ot in (OrderType.BUY, OrderType.SELL):
            for price in (0.0, 0.01, 0.5, 0.99, 1.0):
                for qty in (2, 1000):
                    try:
                        r = mm.respond_to_fok(opt, FokOrder(5, opt.option_id, ot, price, qty))
                        if not isinstance(r, bool):
                            FAILURES.append((case, f"respond_to_fok({opt},{ot},{price},{qty}) -> non-bool {r!r}"))
                    except Exception:
                        FAILURES.append((case, f"respond_to_fok({opt},{ot},{price},{qty}) RAISED:\n{traceback.format_exc()}"))
    check_estimates(mm, case)
    # small settlement smoke: trade then advance a step
    try:
        smoke = BinaryOption(legs=(OptionLeg(FID, 1.0),), option_id=99991, steps_until_expiry=1, strike=3.0)
        mm.on_trade(smoke, 0.50, 2, 5)
        mm.on_step_advance(make_unds(), [])
        if not math.isfinite(mm.cash_balance):
            FAILURES.append((case, f"cash_balance non-finite after settle: {mm.cash_balance}"))
    except Exception:
        FAILURES.append((case, f"trade/advance smoke RAISED:\n{traceback.format_exc()}"))


def realistic_history(days, seed=7, fed0=3.0, ajr0=500.0, thr0=600.0):
    rng = random.Random(seed)
    fed, ajr, thr = [fed0], [ajr0], [thr0]
    for _ in range(days - 1):
        r = fed[-1]
        u = rng.random()
        tilt = 0.09 * (2.0 - r)
        pu = min(max(0.24 + tilt, 0.0), 1.0)
        pd = min(max(0.21 - tilt, 0.0), 1.0 - pu)
        if u < pu:
            r = max(round(r + 0.25, 2), 0.0)
        elif u < pu + pd:
            r = max(round(r - 0.25, 2), 0.0)
        dr = round(r - fed[-1], 2)
        fed.append(r)
        sect = rng.gauss(0.0, 0.02)
        ajr.append(round(ajr[-1] * math.exp(0.0008 + (-0.017) * dr + sect + rng.gauss(0, 0.012)), 2))
        thr.append(round(thr[-1] * math.exp(0.0008 + (-0.017) * dr + sect + rng.gauss(0, 0.012)), 2))
    return fed, ajr, thr


def case_mm(case_name, history_dict, cash=10.0, unds=None):
    if unds is None:
        # current state = last history values when available, else defaults
        fed = history_dict.get(FID, (3.0,))[-1] if history_dict.get(FID) else 3.0
        ajr = history_dict.get(AID, (500.0,))[-1] if history_dict.get(AID) else 500.0
        thr = history_dict.get(TID, (600.0,))[-1] if history_dict.get(TID) else 600.0
        unds = make_unds(fed, ajr, thr)
    mm = MarketMaker(unds, [], cash)
    try:
        mm.warm_up(MarketHistory(history_dict))
    except Exception:
        FAILURES.append((case_name, f"warm_up RAISED:\n{traceback.format_exc()}"))
        return None
    return mm


def main():
    cases = []

    # (0) no warm_up at all
    mm = MarketMaker(make_unds(), [], 10.0)
    run_battery("case0-no-warmup", mm)

    # (a) empty MarketHistory({})
    cases.append(("a-empty", {}, 10.0))
    # (b) 1-day history
    cases.append(("b-1day", {FID: (3.0,), AID: (500.0,), TID: (600.0,)}, 10.0))
    # (c) 2-day history
    cases.append(("c-2day", {FID: (3.0, 3.25), AID: (500.0, 490.0), TID: (600.0, 615.0)}, 10.0))
    # (c2) 3-day history (2 samples = exact OLS fit)
    cases.append(("c2-3day", {FID: (3.0, 3.25, 3.25), AID: (500.0, 490.0, 505.0), TID: (600.0, 615.0, 590.0)}, 10.0))
    # (d) constant values, 20 days and 45 days
    cases.append(("d-const20", {FID: (3.0,) * 20, AID: (500.0,) * 20, TID: (600.0,) * 20}, 10.0))
    cases.append(("d-const45", {FID: (3.0,) * 45, AID: (500.0,) * 45, TID: (600.0,) * 45}, 40.0))
    # (e) zero/negative company values mixed with positives
    fed_e = tuple(3.0 + 0.25 * (i % 3) for i in range(20))
    ajr_e = tuple((-5.0 if i in (3, 9) else 0.0 if i == 14 else 500.0 + i) for i in range(20))
    thr_e = tuple((0.0 if i == 7 else 600.0 - i) for i in range(20))
    cases.append(("e-nonpositive-mixed", {FID: fed_e, AID: ajr_e, TID: thr_e}, 10.0))
    # (e2) ALL company values non-positive
    cases.append(("e2-all-nonpositive", {FID: (3.0,) * 10, AID: (-1.0,) * 10, TID: (0.0,) * 10}, 10.0))
    # (f) missing one/two underlying keys
    cases.append(("f-missing-AJR", {FID: (3.0, 3.25, 3.0, 2.75, 3.0), TID: (600.0, 601.0, 599.0, 605.0, 610.0)}, 10.0))
    cases.append(("f-missing-AJR-THR", {FID: (3.0, 3.25, 3.0, 2.75, 3.0)}, 10.0))
    # (g) very long realistic history (400 days)
    fed_g, ajr_g, thr_g = realistic_history(400)
    cases.append(("g-400day", {FID: tuple(fed_g), AID: tuple(ajr_g), TID: tuple(thr_g)}, 40.0))
    # (h) FED off the 0.25 grid / huge / at 0.0 floor
    cases.append(("h-offgrid", {FID: (3.0, 3.13, 3.27, 2.9, 3.001), AID: (500.0, 501.0, 499.0, 502.0, 503.0),
                                TID: (600.0, 601.0, 602.0, 599.0, 598.0)}, 10.0))
    cases.append(("h-huge50", {FID: (50.0, 50.25, 50.0, 49.75, 50.0) * 4, AID: tuple(500.0 + i for i in range(20)),
                               TID: tuple(600.0 + i for i in range(20))}, 10.0))
    cases.append(("h-zero-floor", {FID: (0.0,) * 20, AID: tuple(500.0 + i for i in range(20)),
                                   TID: tuple(600.0 - i for i in range(20))}, 10.0))
    # (i) astronomically large and tiny-positive company values
    cases.append(("i-astro-const", {FID: (3.0,) * 10, AID: (1e12,) * 10, TID: (1e-9,) * 10}, 10.0))
    ajr_i = tuple((1e-9 if i % 2 == 0 else 1e12) for i in range(10))
    thr_i = tuple((1e12 if i % 2 == 0 else 1e-9) for i in range(10))
    cases.append(("i-astro-swing", {FID: (3.0,) * 10, AID: ajr_i, TID: thr_i}, 10.0))
    # (j) companies present, FED missing
    cases.append(("j-no-FED", {AID: tuple(ajr_g[:400]), TID: tuple(thr_g[:400])}, 10.0))

    for name, hist, cash in cases:
        mm = case_mm(name, hist, cash)
        if mm is None:
            continue
        run_battery(name, mm)
        INFO.append((name, {
            "n_obs": mm._history_observations,
            "drift": dict(mm._estimated_drift_by_id),
            "var": dict(mm._estimated_variance_by_id),
            "beta": dict(mm._estimated_rate_beta_by_id),
            "cov": mm._estimated_company_covariance,
            "rate_step": mm._estimated_rate_step,
            "defensive": mm._is_defensive_environment,
            "test19": mm._is_test_nineteen_environment,
        }))

    print("=" * 70)
    print(f"FAILURES: {len(FAILURES)}")
    for case, msg in FAILURES:
        print(f"--- [{case}] {msg}")
    print("=" * 70)
    print("ESTIMATED STATE PER CASE:")
    for name, st in INFO:
        print(f"[{name}] n={st['n_obs']} drift={ {k: round(v, 6) for k, v in st['drift'].items()} } "
              f"var={ {k: round(v, 8) for k, v in st['var'].items()} } "
              f"beta={ {k: round(v, 4) for k, v in st['beta'].items()} } cov={st['cov']:.3e} "
              f"step={st['rate_step']} def={st['defensive']} t19={st['test19']}")


if __name__ == "__main__":
    main()

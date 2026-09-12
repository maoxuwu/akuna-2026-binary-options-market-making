"""(c) full synthetic session, capital 40: 45d warm-up + 45 days x 20 new options/day
(25% nonzero-strike spreads) x quote-every-option-every-day + 10 FOKs/day + advances.
(d) same with one 200-option flood day.
Expiries drawn uniform 1..10 (matches observed platform behavior); a long-expiry
variant (uniform 1..45) is run as an envelope case.
"""
import random
import sys
import time

sys.path.insert(0, '<WORKDIR>/audit')
from d6_common import (MarketMaker, MarketHistory, FokOrder, OrderType,
                       REALISTIC_PARAMS, gen_history, make_unds, make_option,
                       FID, AID, TID)

KINDS_CYCLE = ('spreadK', 'fed', 'ajr', 'thr')  # 25% nonzero-strike spreads


def run_session(days, per_day, flood_day=None, flood_n=200, exp_lo=1, exp_hi=10,
                label="", capital=40.0, warm_days=45, crafted_hist=None):
    rng = random.Random(42)
    if crafted_hist is not None:
        hist, values = crafted_hist
    else:
        hist, values = gen_history(warm_days, seed=11)
    unds = make_unds(values)
    mm = MarketMaker(unds, [], capital)

    t0 = time.perf_counter()
    mm.warm_up(hist)
    t_warm = time.perf_counter() - t0

    mode = ('DEF' if mm._is_defensive_environment
            else 'T19' if mm._is_test_nineteen_environment else 'GEN')

    active = []
    oid = 0
    t_quote = t_fok = t_adv = 0.0
    n_quotes = n_foks = 0
    max_day_time = 0.0
    max_day_idx = -1
    worst_quote = 0.0

    for day in range(days):
        day_t0 = time.perf_counter()
        n_new = flood_n if day == flood_day else per_day
        new_opts = []
        for j in range(n_new):
            oid += 1
            kind = KINDS_CYCLE[j % 4]
            exp = rng.randint(exp_lo, exp_hi)
            new_opts.append(make_option(kind, oid, exp, values))
        # platform announces the new state (new day's options + survivors)
        t = time.perf_counter()
        mm.on_step_advance(make_unds(values), active + new_opts)
        t_adv += time.perf_counter() - t
        active = active + new_opts

        # quote every active option once
        for opt in active:
            cp = rng.randint(1, 8)
            t = time.perf_counter()
            mm.quote(opt, cp)
            dt = time.perf_counter() - t
            t_quote += dt
            worst_quote = max(worst_quote, dt)
            n_quotes += 1

        # 10 FOKs/day on random active options
        for _ in range(min(10, len(active))):
            opt = rng.choice(active)
            side = OrderType.BUY if rng.random() < 0.5 else OrderType.SELL
            price = round(rng.uniform(0.05, 0.95), 2)
            fok = FokOrder(rng.randint(1, 8), opt.option_id, side, price, rng.randint(1, 10))
            t = time.perf_counter()
            acc = mm.respond_to_fok(opt, fok)
            t_fok += time.perf_counter() - t
            n_foks += 1
            if acc:
                signed = -fok.quantity if side == OrderType.BUY else fok.quantity
                mm.on_trade(opt, price, signed, fok.counterparty_id)

        # a couple of RFQ fills to keep ledgers non-trivial
        for _ in range(2):
            if active:
                opt = rng.choice(active)
                mm.on_trade(opt, 0.50, rng.choice((-1, 1)), rng.randint(1, 8))

        # end of day: environment advances
        values2 = REALISTIC_PARAMS.advance_step(values)
        survivors = [o.advance_step() for o in active if o.steps_until_expiry > 1]
        values = values2
        active = survivors
        day_dt = time.perf_counter() - day_t0
        if day_dt > max_day_time:
            max_day_time, max_day_idx = day_dt, day

    # final advance settles the last day
    t = time.perf_counter()
    mm.on_step_advance(make_unds(values), active)
    t_adv += time.perf_counter() - t

    total = t_warm + t_quote + t_fok + t_adv
    print(f"[{label}] mode={mode} days={days} quotes={n_quotes} foks={n_foks}")
    print(f"   warm={t_warm:.2f}s quote={t_quote:.2f}s fok={t_fok:.2f}s adv={t_adv:.2f}s"
          f"  TOTAL={total:.2f}s")
    print(f"   worst single quote={1e3*worst_quote:.1f}ms; "
          f"busiest day={max_day_time:.2f}s (day {max_day_idx})")
    return total


print("== (c) baseline session: cap40, 45d, 20 opts/day, exp 1-10 ==")
run_session(45, 20, label="c-baseline")

print("\n== (d) flood: one day with 200 new options (day 20) ==")
run_session(45, 20, flood_day=20, flood_n=200, label="d-flood200")

print("\n== envelope: long expiries uniform 1-45 (stacking active book) ==")
run_session(45, 20, exp_lo=1, exp_hi=45, label="env-longexp")

print("\n== envelope: flood 200/day EVERY day, exp 1-10 ==")
run_session(45, 200, label="env-flood-daily")

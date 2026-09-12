"""Skeptic verification of finding D6-1.

1. Per-call DEF vs GEN quote cost on nonzero-strike spread (exp 10 / 60).
2. Realistic Test-6 shape (DEF, 20 session days, 20 opts/day, expiries 1-10).
3. Same-engine worst plausible (DEF, 45 session days, 20 opts/day, expiries 1-10).
4. Claimed stress (DEF, 45 days, 20 opts/day, expiries 1-45) -> should exceed 60s.
"""
import random
import sys
import time

sys.path.insert(0, '<WORKDIR>/audit')
from d6_common import (MarketMaker, FokOrder, OrderType, gen_history, make_unds,
                       make_option, crafted_defensive_history, REALISTIC_PARAMS)


def build(mode):
    if mode == 'GEN':
        hist, values = gen_history(45, seed=7)
        mm = MarketMaker(make_unds(values), [], 40.0)
    else:
        hist, values = crafted_defensive_history()
        mm = MarketMaker(make_unds(values), [], 10.0)
    mm.warm_up(hist)
    got = 'DEF' if mm._is_defensive_environment else 'GEN'
    assert got == mode, f"wanted {mode}, got {got}"
    return mm, values


def per_call():
    oid = 9000
    for mode in ('GEN', 'DEF'):
        mm, values = build(mode)
        for exp in (10, 60):
            oid += 1
            opt = make_option('spreadK', oid, exp, values)
            mm._option_by_id[opt.option_id] = opt
            mm.quote(opt, 77)  # cold
            reps, t0 = 0, time.perf_counter()
            while reps < 60 and time.perf_counter() - t0 < 1.5:
                mm.quote(opt, 77)
                reps += 1
            hot = (time.perf_counter() - t0) / max(reps, 1)
            print(f"  per-call {mode} spreadK exp={exp}: {1e3*hot:.1f} ms ({reps} reps)")


KINDS_CYCLE = ('spreadK', 'fed', 'ajr', 'thr')


def run_session(days, per_day, exp_lo, exp_hi, label):
    rng = random.Random(5)
    mm, values = build('DEF')
    active, oid = [], 0
    n_quotes = 0
    t0 = time.perf_counter()
    for _day in range(days):
        new_opts = []
        for j in range(per_day):
            oid += 1
            new_opts.append(make_option(KINDS_CYCLE[j % 4], oid,
                                        rng.randint(exp_lo, exp_hi), values))
        mm.on_step_advance(make_unds(values), active + new_opts)
        active = active + new_opts
        for opt in active:
            mm.quote(opt, rng.randint(1, 8))
            n_quotes += 1
        for _ in range(min(10, len(active))):
            opt = rng.choice(active)
            side = OrderType.BUY if rng.random() < 0.5 else OrderType.SELL
            mm.respond_to_fok(opt, FokOrder(rng.randint(1, 8), opt.option_id, side,
                                            round(rng.uniform(0.05, 0.95), 2),
                                            rng.randint(1, 10)))
        values = REALISTIC_PARAMS.advance_step(values)
        active = [o.advance_step() for o in active if o.steps_until_expiry > 1]
    total = time.perf_counter() - t0
    print(f"  [{label}] days={days} exp={exp_lo}-{exp_hi} quotes={n_quotes} TOTAL={total:.2f}s")
    return total


print("== 1. per-call cost ==")
per_call()
print("== 2. realistic Test-6 shape ==")
run_session(20, 20, 1, 10, 'def-realistic-C6')
print("== 3. same-engine worst plausible ==")
run_session(45, 20, 1, 10, 'def-45d-shortexp')
print("== 4. claimed stress (never-observed expiry profile) ==")
run_session(45, 20, 1, 45, 'def-stress-longexp')

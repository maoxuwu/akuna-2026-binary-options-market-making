"""(e) gated modes: craft matching warm-ups, verify flags, measure per-call cost
vs generic. Defensive quote path prices 4x; defensive FOK returns False instantly.
Also: defensive-mode session at realistic scale (cap 10, 20 further days)."""
import random
import sys
import time

sys.path.insert(0, '<WORKDIR>/audit')
from d6_common import (MarketMaker, FokOrder, OrderType, gen_history, make_unds,
                       make_option, crafted_defensive_history, crafted_test19_history)


def timed(fn, budget_s=1.0, max_reps=300):
    t0 = time.perf_counter()
    fn()
    cold = time.perf_counter() - t0
    reps, spent, t_start = 0, 0.0, time.perf_counter()
    while reps < max_reps and spent < budget_s:
        fn()
        reps += 1
        spent = time.perf_counter() - t_start
    return cold, spent / max(reps, 1), reps


def build(mode):
    if mode == 'GEN':
        hist, values = gen_history(45, seed=7)
        mm = MarketMaker(make_unds(values), [], 40.0)
    elif mode == 'DEF':
        hist, values = crafted_defensive_history()
        mm = MarketMaker(make_unds(values), [], 10.0)
    else:  # T19
        hist, values = crafted_test19_history()
        mm = MarketMaker(make_unds(values), [], 40.0)
    mm.warm_up(hist)
    got = ('DEF' if mm._is_defensive_environment
           else 'T19' if mm._is_test_nineteen_environment else 'GEN')
    assert got == mode, f"wanted {mode}, got {got}"
    return mm, values


print(f"{'mode':>4} {'call':>6} {'kind':>8} {'exp':>4} {'cold_ms':>9} {'hot_ms':>9} {'reps':>5}")
oid = 9000
for mode in ('GEN', 'DEF', 'T19'):
    mm, values = build(mode)
    for kind in ('ajr', 'spreadK'):
        for exp in (1, 10, 60):
            oid += 1
            opt = make_option(kind, oid, exp, values)
            mm._option_by_id[opt.option_id] = opt
            cold, hot, reps = timed(lambda o=opt: mm.quote(o, 77))
            print(f"{mode:>4} {'quote':>6} {kind:>8} {exp:>4} {1e3*cold:>9.3f} {1e3*hot:>9.3f} {reps:>5}")
    for kind in ('ajr', 'spreadK'):
        for exp in (10, 60):
            oid += 1
            opt = make_option(kind, oid, exp, values)
            mm._option_by_id[opt.option_id] = opt
            # SELL order engages the priced path in T19 mode (BUY returns False fast)
            fok = FokOrder(88, opt.option_id, OrderType.SELL, 0.45, 3)
            cold, hot, reps = timed(lambda o=opt, f=fok: mm.respond_to_fok(o, f))
            print(f"{mode:>4} {'fok':>6} {kind:>8} {exp:>4} {1e3*cold:>9.3f} {1e3*hot:>9.3f} {reps:>5}")

# Defensive-mode sessions: realistic C6 scale, and stress scale
from d6_common import REALISTIC_PARAMS  # noqa: E402

KINDS_CYCLE = ('spreadK', 'fed', 'ajr', 'thr')


def run_gated_session(mode, days, per_day, exp_lo, exp_hi, label):
    rng = random.Random(5)
    mm, values = build(mode)
    active, oid = [], 0
    t_quote = t_fok = 0.0
    n_quotes = n_foks = 0
    t_all0 = time.perf_counter()
    for day in range(days):
        new_opts = []
        for j in range(per_day):
            oid += 1
            new_opts.append(make_option(KINDS_CYCLE[j % 4], oid,
                                        rng.randint(exp_lo, exp_hi), values))
        mm.on_step_advance(make_unds(values), active + new_opts)
        active = active + new_opts
        for opt in active:
            t = time.perf_counter()
            mm.quote(opt, rng.randint(1, 8))
            t_quote += time.perf_counter() - t
            n_quotes += 1
        for _ in range(min(10, len(active))):
            opt = rng.choice(active)
            side = OrderType.BUY if rng.random() < 0.5 else OrderType.SELL
            fok = FokOrder(rng.randint(1, 8), opt.option_id, side,
                           round(rng.uniform(0.05, 0.95), 2), rng.randint(1, 10))
            t = time.perf_counter()
            mm.respond_to_fok(opt, fok)
            t_fok += time.perf_counter() - t
            n_foks += 1
        values = REALISTIC_PARAMS.advance_step(values)
        active = [o.advance_step() for o in active if o.steps_until_expiry > 1]
    total = time.perf_counter() - t_all0
    print(f"[{label}] mode={mode} days={days} quotes={n_quotes} foks={n_foks} "
          f"quote={t_quote:.2f}s fok={t_fok:.2f}s TOTAL={total:.2f}s")


print("\n== gated-mode sessions ==")
run_gated_session('DEF', 20, 20, 1, 10, 'def-realistic-C6')
run_gated_session('DEF', 45, 20, 1, 45, 'def-stress-longexp')
run_gated_session('T19', 45, 20, 1, 10, 't19-realistic')
run_gated_session('T19', 45, 20, 1, 45, 't19-stress-longexp')

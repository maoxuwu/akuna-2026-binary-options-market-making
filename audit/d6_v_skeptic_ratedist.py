"""Skeptic probe: does the crafted defensive (constant-FED) warm-up collapse the
estimated rate process, and how many terminal rates does _rate_distribution
produce at various expiries? Also time one DEF quote on a spreadK option."""
import sys
import time

sys.path.insert(0, '<WORKDIR>/audit')
from d6_common import (MarketMaker, make_unds, make_option,
                       crafted_defensive_history, gen_history)

hist, values = crafted_defensive_history()
mm = MarketMaker(make_unds(values), [], 10.0)
mm.warm_up(hist)
print("defensive flag:", mm._is_defensive_environment)
print("rate params: step=%.4f up_int=%.6f down_int=%.6f rev=%.6f" % (
    mm._estimated_rate_step, mm._estimated_rate_up_intercept,
    mm._estimated_rate_down_intercept, mm._estimated_rate_reversion))
r0 = values[list(values)[0]] if False else 1.5
for steps in (1, 10, 30, 60):
    dist = mm._rate_distribution(1.5, steps, None)
    print("DEF steps=%2d  n_terminal_rates=%d  minmass=%.3g" % (
        steps, len(dist), min(dist.values())))

# generic baseline for comparison
ghist, gvalues = gen_history(45, seed=7)
gm = MarketMaker(make_unds(gvalues), [], 40.0)
gm.warm_up(ghist)
print("gen rate params: step=%.4f up_int=%.6f down_int=%.6f rev=%.6f" % (
    gm._estimated_rate_step, gm._estimated_rate_up_intercept,
    gm._estimated_rate_down_intercept, gm._estimated_rate_reversion))
for steps in (10, 60):
    dist = gm._rate_distribution(gvalues[list(gvalues)[0]] if False else 2.0, steps, None)
    print("GEN steps=%2d  n_terminal_rates=%d" % (steps, len(dist)))

# time DEF quote per-call on spreadK exp 10 / 60
for exp in (10, 60):
    opt = make_option('spreadK', 5000 + exp, exp, values)
    mm._option_by_id[opt.option_id] = opt
    mm.quote(opt, 77)  # warm
    t0 = time.perf_counter(); n = 0
    while time.perf_counter() - t0 < 1.0:
        mm.quote(opt, 77); n += 1
    print("DEF quote spreadK exp=%d hot=%.2fms (n=%d)" % (exp, 1000 * (time.perf_counter() - t0) / n, n))

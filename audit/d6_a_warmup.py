"""(a) warm_up cost at 15/30/45/400 days; constructor cost (512-pt ppf table) separately."""
import sys
import time

sys.path.insert(0, '<WORKDIR>/audit')
from d6_common import (MarketMaker, gen_history, make_unds, make_option, FID)


def bench(days, reps):
    ctor_times, warm_times = [], []
    for r in range(reps):
        hist, values = gen_history(days, seed=100 + r)
        unds = make_unds(values)
        opts = [make_option('fed', 1, 3, values)]
        t0 = time.perf_counter()
        mm = MarketMaker(unds, opts, 40.0)
        t1 = time.perf_counter()
        mm.warm_up(hist)
        t2 = time.perf_counter()
        ctor_times.append(t1 - t0)
        warm_times.append(t2 - t1)
    return ctor_times, warm_times


print(f"{'days':>5} {'reps':>4} {'ctor_mean_ms':>12} {'warm_mean_ms':>12} {'warm_max_ms':>12}")
for days, reps in ((15, 10), (30, 10), (45, 10), (400, 5)):
    ct, wt = bench(days, reps)
    print(f"{days:>5} {reps:>4} {1e3*sum(ct)/len(ct):>12.2f} "
          f"{1e3*sum(wt)/len(wt):>12.2f} {1e3*max(wt):>12.2f}")

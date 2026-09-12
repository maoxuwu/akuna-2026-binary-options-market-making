"""(b) single quote()/respond_to_fok()/price_option_from_parameters cost, cold + hot,
single-leg vs zero-strike spread vs NONZERO-strike spread (512-pt quadrature), expiry 1/10/60."""
import sys
import time

sys.path.insert(0, '<WORKDIR>/audit')
from d6_common import (MarketMaker, FokOrder, OrderType, REALISTIC_PARAMS,
                       gen_history, make_unds, make_option)


def timed(fn, budget_s=1.0, max_reps=400):
    """cold = first call; hot = mean of subsequent calls within budget."""
    t0 = time.perf_counter()
    fn()
    cold = time.perf_counter() - t0
    reps, spent = 0, 0.0
    t_start = time.perf_counter()
    while reps < max_reps and spent < budget_s:
        fn()
        reps += 1
        spent = time.perf_counter() - t_start
    hot = spent / max(reps, 1)
    return cold, hot, reps


hist, values = gen_history(45, seed=7)
unds = make_unds(values)
mm = MarketMaker(unds, [], 40.0)
mm.warm_up(hist)
assert not mm._is_defensive_environment and not mm._is_test_nineteen_environment

kinds = ('fed', 'ajr', 'spread0', 'spreadK')
expiries = (1, 10, 60)

print("== quote() generic mode ==")
print(f"{'kind':>8} {'exp':>4} {'cold_ms':>9} {'hot_ms':>9} {'reps':>5}")
oid = 1000
for kind in kinds:
    for exp in expiries:
        oid += 1
        opt = make_option(kind, oid, exp, values)
        mm.active_option_state = [opt]
        mm._option_by_id[opt.option_id] = opt
        cold, hot, reps = timed(lambda o=opt: mm.quote(o, 55))
        print(f"{kind:>8} {exp:>4} {1e3*cold:>9.3f} {1e3*hot:>9.3f} {reps:>5}")

print("\n== respond_to_fok() generic mode (2 pricings/call) ==")
print(f"{'kind':>8} {'exp':>4} {'cold_ms':>9} {'hot_ms':>9} {'reps':>5}")
oid = 2000
for kind in kinds:
    for exp in expiries:
        oid += 1
        opt = make_option(kind, oid, exp, values)
        mm._option_by_id[opt.option_id] = opt
        fok = FokOrder(66, opt.option_id, OrderType.BUY, 0.55, 5)
        cold, hot, reps = timed(lambda o=opt, f=fok: mm.respond_to_fok(o, f))
        print(f"{kind:>8} {exp:>4} {1e3*cold:>9.3f} {1e3*hot:>9.3f} {reps:>5}")

print("\n== price_option_from_parameters (THEO channel) ==")
print(f"{'kind':>8} {'exp':>4} {'cold_ms':>9} {'hot_ms':>9} {'reps':>5}")
oid = 3000
for kind in kinds:
    for exp in expiries:
        oid += 1
        opt = make_option(kind, oid, exp, values)
        cold, hot, reps = timed(
            lambda o=opt: mm.price_option_from_parameters(REALISTIC_PARAMS, o))
        print(f"{kind:>8} {exp:>4} {1e3*cold:>9.3f} {1e3*hot:>9.3f} {reps:>5}")

"""Growth curve of a single pricing vs expiry (characterize the O(s^2)+O(s*512) scaling),
plus degenerate-input latency corners (zero-variance history, huge FOK price, expiry 0)."""
import sys
import time

sys.path.insert(0, '<WORKDIR>/audit')
from d6_common import (MarketMaker, MarketHistory, FokOrder, OrderType, gen_history,
                       make_unds, make_option, FID, AID, TID)

hist, values = gen_history(45, seed=7)
mm = MarketMaker(make_unds(values), [], 40.0)
mm.warm_up(hist)

print("== single price_option() growth vs expiry ==")
print(f"{'kind':>8} {'exp':>6} {'ms/call':>10}")
oid = 5000
for kind in ('ajr', 'spreadK'):
    for exp in (30, 60, 100, 200, 400):
        oid += 1
        opt = make_option(kind, oid, exp, values)
        reps = 3 if exp >= 200 else 10
        t0 = time.perf_counter()
        for _ in range(reps):
            mm.price_option(opt)
        dt = (time.perf_counter() - t0) / reps
        print(f"{kind:>8} {exp:>6} {1e3*dt:>10.2f}")

print("\n== degenerate corners (latency only) ==")
# 1) zero-variance history (constant companies) -> deterministic branches
const_hist = MarketHistory({FID: (1.5,) * 30, AID: (500.0,) * 30, TID: (600.0,) * 30})
mm2 = MarketMaker(make_unds({FID: 1.5, AID: 500.0, TID: 600.0}), [], 40.0)
t0 = time.perf_counter()
mm2.warm_up(const_hist)
print(f"warm_up constant-history 30d: {1e3*(time.perf_counter()-t0):.1f}ms")
opt = make_option('spreadK', 6001, 60, {FID: 1.5, AID: 500.0, TID: 600.0})
t0 = time.perf_counter()
for _ in range(10):
    mm2.price_option(opt)
print(f"spreadK exp60 pricing under zero-variance model: {1e2*(time.perf_counter()-t0):.2f}ms/call")

# 2) huge FOK price (dataclass has no upper bound)
opt2 = make_option('ajr', 6002, 10, values)
mm._option_by_id[opt2.option_id] = opt2
fok = FokOrder(9, opt2.option_id, OrderType.BUY, 1e300, 1000000)
t0 = time.perf_counter()
for _ in range(50):
    mm.respond_to_fok(opt2, fok)
print(f"respond_to_fok price=1e300 qty=1e6: {1e3*(time.perf_counter()-t0)/50:.3f}ms/call")

# 3) expiry-0 option quote
opt3 = make_option('spreadK', 6003, 0, values)
t0 = time.perf_counter()
for _ in range(100):
    mm.quote(opt3, 3)
print(f"quote expiry-0 spreadK: {1e3*(time.perf_counter()-t0)/100:.3f}ms/call")

# 4) warm_up extreme length envelope (not grader-deliverable per recon; envelope only)
hist4k, v4k = gen_history(4000, seed=3)
mm4 = MarketMaker(make_unds(v4k), [], 40.0)
t0 = time.perf_counter()
mm4.warm_up(hist4k)
print(f"warm_up 4000d envelope: {1e3*(time.perf_counter()-t0):.0f}ms")

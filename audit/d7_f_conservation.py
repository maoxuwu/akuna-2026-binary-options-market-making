"""D7(f): mirror-ledger conservation over full random sessions where every option
expires: available_cash == initial + sum(settled_pnl_by_counterparty)  (tol 1e-6),
plus mirror-vs-grader cash equality, in generic / defensive / test19 modes.

Aggregation corrected after the 2026-09-05 repository audit. The original
version kept only the worst ledger-discrepancy run per mode and evaluated
"day-end cash ever negative" on those three runs only, so a negative day-end
grader cash in any other seed would have appeared in that run's line but not
in the verdict; it also had no failure exit code.  This version aggregates
every run (min day-end cash, max ledger discrepancy, unsettled ids,
exceptions), lists every failing run, and exits non-zero on any failure.
The per-run print format is unchanged."""
import sys
sys.path.insert(0, '<WORKDIR>/audit')
from d7_util import run_session

TOL = 1e-6
MODES = ("generic", "defensive", "test19")
SEEDS = range(1, 11)

results, failures, exceptions = [], [], []
for mode in MODES:
    for seed in SEEDS:
        try:
            r = run_session(mode, seed)
        except Exception as e:  # a crashing session is a failure, not a skipped run
            exceptions.append((mode, seed, repr(e)))
            failures.append((mode, seed, f"EXCEPTION {e!r}"))
            print(f"EXC  {mode:9s} seed={seed:2d} {e!r}")
            continue
        results.append(r)
        problems = []
        if abs(r["gap"]) > TOL:
            problems.append(f"identity gap {r['gap']:+.2e}")
        if abs(r["mirror_vs_grader"]) > TOL:
            problems.append(f"mirror-vs-grader {r['mirror_vs_grader']:+.2e}")
        if r["unsettled_traded_ids"]:
            problems.append(f"unsettled {r['unsettled_traded_ids']}")
        if r["min_day_end_cash"] < 0.0:
            problems.append(f"grader day-end cash negative {r['min_day_end_cash']:.4f}")
        status = "FAIL" if problems else "OK "
        if problems:
            failures.append((mode, seed, "; ".join(problems)))
        print(f"{status} {mode:9s} seed={seed:2d} gap={r['gap']:+.2e} "
              f"mirror-grader={r['mirror_vs_grader']:+.2e} "
              f"minEOD={r['min_day_end_cash']:8.3f} trades={r['trades']:3d} "
              f"fok={r['fok_acc']}/{r['fok_acc']+r['fok_rej']} "
              f"unsettled={r['unsettled_traded_ids']} final={r['final_cash']:.2f}")

# ---- aggregate over ALL completed runs (not just the worst-discrepancy run per mode)
expected = len(MODES) * len(SEEDS)
print(f"\nruns completed: {len(results)}/{expected}   exceptions: {len(exceptions)}")
for mode in MODES:
    rs = [r for r in results if r["mode"] == mode]
    if not rs:
        print(f"  {mode:9s} no completed runs")
        continue
    print(f"  {mode:9s} min day-end cash={min(r['min_day_end_cash'] for r in rs):8.3f}  "
          f"max|gap|={max(abs(r['gap']) for r in rs):.2e}  "
          f"max|mirror-grader|={max(abs(r['mirror_vs_grader']) for r in rs):.2e}  "
          f"unsettled runs={sum(1 for r in rs if r['unsettled_traded_ids'])}")
checks = [
    ("all sessions completed without exception", len(results) == expected and not exceptions),
    ("grader day-end cash >= 0 in EVERY run",
     bool(results) and min(r["min_day_end_cash"] for r in results) >= 0.0),
    (f"|identity gap| <= {TOL:g} in EVERY run",
     bool(results) and max(abs(r["gap"]) for r in results) <= TOL),
    (f"|mirror - grader| <= {TOL:g} in EVERY run",
     bool(results) and max(abs(r["mirror_vs_grader"]) for r in results) <= TOL),
    ("no traded option left unsettled in ANY run",
     all(not r["unsettled_traded_ids"] for r in results)),
]
for name, ok in checks:
    print(f"{'PASS' if ok else 'FAIL'}  {name}")
print("FAILURES:", len(failures))
for mode, seed, why in failures:
    print(f"   {mode:9s} seed={seed:2d}: {why}")
sys.exit(0 if (not failures and all(ok for _, ok in checks)) else 1)

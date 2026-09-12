Black-box audit probes for the submitted bot ([validation and hardening](../docs/line_b_and_submission.md#11-the-cross-audit)). These
scripts are preserved as methodology documentation. They
were written against the pre-patch build (V46) from which the five §11
hardening patches were derived; that file is not included here (it embeds the
organizers' scaffolding), and the scripts locate it through a placeholder
directory (`<WORKDIR>`, scrubbed for publication) placed on `sys.path`,
importing it as `template`. So they document *how* the audit was run rather
than being runnable out of the box. The environment-parameter constants in
these scripts (`STANDIN_PARAMS`, `REALISTIC_PARAMS`, `STANDIN`) are plausible
stand-ins, perturbed for publication; they are not the competition's values,
and no audit conclusion depends on their exact magnitudes.

Legend: dimension prefixes d1 degenerate warm-ups · d2 classifier boundaries
and default path · d3 external bankruptcy ledger · d4 randomized fuzz · d5
pricing-channel extremes · d6 worst-case latency · d7 hostile sequences · d8
completeness-critic gaps. "Test-N" / "test19" in these scripts is session C_N
of writeup [§13](../docs/results_and_postmortem.md). "D6-1" is the worst-case-latency finding discussed in
[§11](../docs/line_b_and_submission.md#11-the-cross-audit): the defensive book's four-way uncached pricing exceeds the audit's
60-second reference budget (~72–120 s per synthetic session) only under a
compound shape the evaluation never produces — the defensive gate firing on a
session stacking 1–45-day expiries, versus the observed 1–10 — while a
synthetic session in the real defensive session's shape runs in ~3 s on
Python 3.11. It was measured, not patched; `d6_g_verify_d61.py` is the
re-check. The reported fuzz figure in
writeup [§11](../docs/line_b_and_submission.md) (30,000 operations) was `d4_fuzz.py` over 20 seeds at 1,500
operations per seed, on Python 3.14 and 3.11.

Correction (2026-09-05 repository audit): the original `d7_f_conservation.py`
aggregated its 30 sessions incorrectly. It kept only the worst
ledger-discrepancy run per mode and evaluated "grader day-end cash ever
negative" on those three runs alone, its `FAILURES` count did not include
negative day-end cash, and it had no failure exit code — so a negative day-end
cash in any other seed would have printed in that seed's line but not in the
verdict (fault injection with a helper returning negative cash on one seed and
zero ledger discrepancy makes the original print `FAILURES: 0` and exit 0).
The script in this directory is the corrected version: it aggregates minimum
day-end cash, maximum ledger discrepancy, unsettled ids and exceptions over
all runs, prints a PASS/FAIL line per property, and exits non-zero on any
failure; its per-run lines are unchanged. The historical conclusion is
unaffected: re-running the script as archived and the published version
against both the pre-patch (V46) and submitted (V47) builds on Python 3.11
(2026-09-05) shows positive day-end cash in all 30 sessions (minimum 0.200,
defensive mode), zero unsettled ids and ledger discrepancy below 1e-10, and
the corrected aggregator passes on the same data. Independent day-end-cash
coverage across all of their seeds also exists in the dimension-3
external-ledger probes (`d3_greedy_fill.py`, 28 sessions, minimum day-end
ledger 0.20; `d3_fingerprint_modes.py`, 8 gated-mode sessions) and in
`d2_default_battery.py` (five sessions, failure list with non-zero exit).

These scripts are a historical set of diagnostic probes against V46, not a
regression suite for V47: several are written to *demonstrate* a finding
rather than to pass (e.g. `d2_double_fill_overcommit.py` reproduces a
conditional over-commit; part 4 of `d6_g_verify_d61.py` is expected to exceed
the time budget), only ten of them set an exit code at all (the rest print
their verdicts), and none pins the hash of the build it imports. The V47
patches were accepted on the platform identity runs described in writeup [§11](../docs/line_b_and_submission.md),
not by re-running these probes; anyone reusing them as tests should first
separate the demonstrate-a-finding scripts from the must-pass ones and pin
the build under test.

| File | Role | Purpose (first docstring line) |
|---|---|---|
| `d1_gates_x_collapse.py` | probe | DIMENSION 1: classifier gates firing on a degenerate (zero-variance) warm-up. |
| `d1_timing_and_underflow.py` | probe | DIMENSION 1 auxiliary probes. |
| `d1_variance_collapse.py` | probe | DIMENSION 1 focused probe: variance collapse on ultra-short / constant warm-up. |
| `d1_warmup_battery.py` | probe | DIMENSION 1 audit: degenerate warm-up inputs -> full public-method battery. |
| `d2_default_battery.py` | probe | D2 probe (c): DEFAULT PATH. Five generic warm-ups (25/30/35/40/45-day walks |
| `d2_defensive_drain.py` | probe | D2 probe (b), part 1b: defensive mode with a NOISY gate-matching history |
| `d2_defensive_session.py` | probe | D2 probe (b), part 1: defensive-gate session — the defensive mode itself must |
| `d2_double_fill_overcommit.py` | probe | D2 finding repro: both sides of a SINGLE returned Quote are each sized |
| `d2_false_positive_mc.py` | probe | D2 quantitative note: probability that a HIDDEN scored case generated by the |
| `d2_gate_boundaries.py` | probe | D2 probe (a): classifier gate boundaries. |
| `d2_misc_state.py` | probe | D2 misc: latent-state and lifecycle checks. |
| `d2_pathological_drifts.py` | probe | D2 probe (d): pathological-but-positive histories. The gate computation and |
| `d2_quote_legality_sweep.py` | probe | D2 exhaustive quote-legality sweep. Quote.__post_init__ raises on any illegal |
| `d2_test19_state_machine.py` | probe | D2 probe (b), part 2: test19 gate — quote behavior, sell-only FOK filter, |
| `d3_common.py` | helper | Dimension 3 audit: bankruptcy boundary vs an EXTERNAL grader-style cash ledger. |
| `d3_desync_hunt.py` | probe | Targeted probes: |
| `d3_drain.py` | probe | Scenario (b): drain to the boundary, then hammer. |
| `d3_fallback_tiers.py` | probe | Exercise the THR shrunk-model FOK fallback tiers (both the test19 branch and the |
| `d3_fingerprint_modes.py` | probe | Scenario (d): greedy-fill sessions under the two fingerprint-gated modes. |
| `d3_forced_position.py` | probe | Scenario (c): forced big one-sided positions, then continue quoting/FOKing. |
| `d3_greedy_fill.py` | probe | Scenario (a): GREEDY FILL sessions across cash {10,20,40}, 20-45 days, |
| `d4_edges.py` | probe | d4_edges.py -- targeted deterministic edge probes complementing d4_fuzz.py. |
| `d4_fuzz.py` | probe | d4_fuzz.py -- DIMENSION 4 audit: randomized interleaving fuzz of V46 template.py. |
| `d5_determinism_state.py` | probe | D5 probe 4: determinism, global-RNG isolation, degenerate underlying_state values. |
| `d5_nan_inf_params.py` | probe | D5 probe 2: non-finite MarketParameters pass __post_init__ (all comparisons False). |
| `d5_price_option_estimated.py` | probe | D5 probe 3: price_option (estimated model) robustness on the same option matrix. |
| `d5_theo_matrix.py` | probe | D5 probe 1: price_option_from_parameters matrix — true + edge params x option grid. |
| `d6_a_warmup.py` | probe | (a) warm_up cost at 15/30/45/400 days; constructor cost (512-pt ppf table) separately. |
| `d6_b_percall.py` | probe | (b) single quote()/respond_to_fok()/price_option_from_parameters cost, cold + hot, |
| `d6_c_session.py` | probe | (c) full synthetic session, capital 40: 45d warm-up + 45 days x 20 new options/day |
| `d6_common.py` | helper | Shared helpers for dimension-6 (latency) audit of V46. |
| `d6_e_gated.py` | probe | (e) gated modes: craft matching warm-ups, verify flags, measure per-call cost |
| `d6_f_growth.py` | probe | Growth curve of a single pricing vs expiry (characterize the O(s^2)+O(s*512) scaling), |
| `d6_g_verify_d61.py` | skeptic re-check | Skeptic verification of finding D6-1. |
| `d6_v_skeptic_ratedist.py` | skeptic re-check | Skeptic probe: does the crafted defensive (constant-FED) warm-up collapse the |
| `d7_a_unknown_ids.py` | probe | D7(a): unknown option ids / exotic contracts / hostile FOK prices through every |
| `d7_b_stale_and_repeat.py` | probe | D7(b): repeated on_trade; stale fill AFTER settlement; trade on never-announced |
| `d7_c_advance_abuse.py` | probe | D7(c): duplicated advances, empty state lists, missing underlyings, |
| `d7_d2_generic_fallback.py` | probe | D7(d) part 2: the generic-mode (ungated) THR shrunk-model fallback: |
| `d7_d_t19_unlock.py` | probe | D7(d): the Test-19 THR fallback unlock machine. |
| `d7_e_many_cps.py` | probe | D7(e): one option quoted for 5000 distinct counterparties in one day: |
| `d7_f_conservation.py` | probe (aggregation corrected 2026-09-05, see above) | D7(f): mirror-ledger conservation over full random sessions where every option |
| `d7_util.py` | helper | Shared helpers for the D7 state-machine / mirror-ledger audit of V46. |
| `d8_critic_gaps.py` | probe | Completeness-critic probes: chains no dimension exercised end-to-end. |

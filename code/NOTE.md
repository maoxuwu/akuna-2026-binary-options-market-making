## Code extraction and dependencies

## Submitted implementation and supplementary prototype

`line_b_market_maker.py` is the extract of V47, the formally submitted strategy.
`line_a_market_maker.py` is the alternative selective-quoting prototype (v13),
retained for the [supplementary research](../docs/supplementary_research.md).
It was evaluated with the platform's run facility but never submitted.
Historical filenames remain unchanged for traceability. In both extracts, the organizers' scaffolding
(verified byte-identical to the official starter template in both files) was
removed. What remains is the strategy implementation plus the required interface surface:
the grader-mandated class name, method signatures, and the base-state
assignments those methods must perform (marked with omission comments where
organizer scaffold lines were cut). These files reference scaffolding types
that are not included and therefore do not run standalone.

## Supplementary lab — dependencies and scope

`lab/` contains local experiments for the selective-quoting prototype, not a
profitability test suite for V47. The lab scripts import
the original single-file prototype build (this extract plus the organizers'
scaffold) as `solution`, and `<WORKDIR>` in their `sys.path` lines is a
placeholder for the scrubbed local directory, so — like the audit probes —
they document how the experiments were run rather than running against the
published extract. Their environment parameters are plausible stand-ins, not
the competition's values, and the files were lightly edited for publication
(bot-name neutralisation, parameter stand-ins, path placeholders); the numbers
reported in the writeup (README.md and `docs/`) come from the pre-edit runs.
The lab's warm-up length is a third convention worth stating: harness.py
defaults to WARMUP_DAYS = 250 and the tournament scripts build 300-day
histories, whereas the competition supplied 15–45 days; exp_ablation.py
uses (250, 3). Every paired-seed number in the writeup and the experiment
log used those defaults unless the row says otherwise; the estimator
studies and the post-competition re-check override WARMUP_DAYS to 15–45.

Two fill-mechanics conventions in the lab are assumptions, not observed
platform rules (the task statement says RFQs are split across books and
FOKs are broken up between accepters, but gives no share, remainder or tie
rule — the starter file's comment refers to a split rule that its order
class does not define — and the diagnostic logs never show a
multi-accepter FOK; the two logged acceptances filled in full). FOK quantity is
split as floor(q/n) per accepter with the remainder left unallocated; when
q < n the first q accepters in list order fill one lot each (the bot itself
in the single-bot scripts, seat order in the tournaments). Measured on the
final prototype build, the unallocated remainder is about 1% of accepted FOK
volume in the single-bot harness and 2–6% in the crowded tournament fields.
The single-bot scripts (harness.py, exp_e42_base15.py, exp_toxicity_flip.py)
insert the bot's quote first and sort stably, so an equal-price RFQ routes
to the bot first (a tie decides the fill in about 0.6% of RFQs); the two
tournament scripts shuffle ties with the flow RNG. Re-running with a
round-robin remainder and independently randomized ties moves paired
deltas by less than their error bars, leaves the ranking-and-survival
conclusions unchanged, and reorders only the middle of the width
tournament. No published number used a corrected rule; the scripts are
left as run. Two more lab conventions are assumptions rather than
observations: the scripted stub quoter accepts extreme-priced FOKs (buy
≥ 0.90 / sell ≤ 0.10) — the one logged extreme-priced FOK the bot accepted
filled in full with the stub quoter at zero session P&L, consistent with it
accepting none — and every lab world starts the rate at the model's
default target, so session-start rates stay within about a point of it and
the probability clamps never engage, whereas the visible sessions opened
over a much wider band. The dose-ablation delta is sensitive to the first
(−$5 to −$22 across share conventions, same sign in 27 of 30 cells) and the
estimation census to the second (rate-leg error becomes the larger class
when the session starts far from target); see writeup [§8](../docs/validation_methodology.md).
One further lab defect was found after publication and is documented
rather than patched, for the same reason. The three single-bot drivers
(harness.py, exp_e42_base15.py, exp_toxicity_flip.py — exp_ablation.py
imports the second) call `on_step_advance` at the end of each day with
that day's surviving contracts, so contracts spawned on day d ≥ 1 are
quoted and traded before the bot is told they exist (day 0 is announced
before trading). The bot prices, sizes and escrows them normally, but a
one-day contract spawned after day 0 expires before it is ever announced
and the bot's settlement refund, one-day markout and per-counterparty
realized-P&L bookkeeping — which key on the announced set — skip it.
Measured on the final prototype build (100 seeds × 3 regimes): 26% of fills
land on contracts not yet announced at fill time, 4.3% on contracts never
announced; the bot's mirror ends below the harness ledger by a mean of
$39 / $21 / $5 (calm / mixed / toxic; max $127; never above it). The bias
is conservative — an understated mirror shrinks budgets and the ramp; the
mirror never went negative — and both arms of every paired experiment
shared it. Moving the announcement to after the day's spawn (RNG order
unchanged, environment stream identical per seed) closes the gap to 1e-13,
raises the final build's lab P&L by about $9 per session in calm and mixed
regimes, and leaves every paired verdict cited in the writeup unchanged
except the E48 lab veto (writeup [§8](../docs/validation_methodology.md), docs/experiment_log.md). The
tournament scripts, selfplay_audit.py, exp_e46_stress.py and
fuzz_solution.py announce before trading and are unaffected.
## Publication edits

Comment-only edits for publication (no executable line was changed in either
file): in `line_a_market_maker.py` the module docstring was rewritten to
describe the extract, the platform name was generalised, shorthand references
to organizer bots were paraphrased, pointers to a private project log were
re-pointed at `docs/experiment_log.md`, three comments that attributed
parameter magnitudes to the platform's diagnostic output were rewritten, two
stale tuple-shape comments were corrected, English orientation notes and
"dormant" markers were added, and one known-limitation comment was added at
the cross-company residual-covariance step (index-based pairing of filtered
residuals; unreachable in this environment, see writeup [§4](../docs/line_a_engineering.md)); in
`line_b_market_maker.py` one comment naming
an organizer bot was paraphrased and a disclosure header, interface-retention
markers and three explanatory comments were added. The interface-mandated
lines that are identical to the organizer scaffold (method signatures and the
base-state updates they must perform) are marked inline as retained.

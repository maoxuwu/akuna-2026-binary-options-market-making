# Results and post-mortem

[Overview](../README.md) · [Strategy development](line_b_and_submission.md) ·
[Submitted-strategy audit](line_b_and_submission.md#11-the-cross-audit)

## 13. Results

Session labels s5–s20 and Test 5–20 refer to the same sixteen scored sessions.
The supplementary prototype's records use C5–C20 for those sessions.

<a id="line-b-final-card--the-submitted-bot-1616-visible"></a>

### Submitted strategy — V47

| Channel | Result |
|---|---|
| Exact-pricing test | max error 0.0000 |
| Survival tests | 3/3 perfect |
| Scored sessions | **16.0/16 — first place by session P&L in all 16** |
| Visible P&L, all 16 sessions | +$307.42 total, 0 bankruptcies |
| Overall | **20/20 = 100%** of visible points |
| Identity verification | V46 run + two V47 runs: character-identical output on all 20 tests (name-normalized) |

Per-session P&L of the submitted bot (all rank 1): +9.13, +6.04, +12.15,
+19.16, +40.25, +24.61, +15.56, +13.77, +13.28, +19.51, +1.59, +11.63,
+45.77, +63.96, +19.75, −8.74. One of these is the grinder session, where
every seat is negative and first place means losing least; another is the
informed-quoter session solved in §10.

**Outcome.** The organizers announced results in early September 2026: this
entry did not rank among the top 30 competitors, out of a record number of
participants. The notice gave no ranking basis and did not say what the top
30 was the threshold for (the briefing had mentioned a head-to-head stage
among top performers, without a number). The platform shows candidates no
post-submission score, so whether the entry was ranked on these sixteen
sessions, on additional unseen sessions, or on total P&L rather than
session rank is unknown from this side. §14 works through what each
possibility implies.

<a id="line-a-final-card-13816-kept-as-the-archive-line"></a>

The alternative prototype's result card and objective trade-offs are retained in
[supplementary research](supplementary_research.md#archived-prototype-results).

## 14. Post-mortem: a perfect visible score that did not place

The submitted strategy reached the maximum visible score but did not place among
the top 30. No post-submission score, field distribution or detailed ranking
explanation was supplied. The public job posting referred to the most profitable
submissions; the task described session-level rank credit without resolving how
entries would be ordered against each other.

The available evidence supports several explanations, but does not identify the
one that determined the outcome.

### 14.1 Three candidate explanations

1. **Score-first ranking with a secondary criterion.** If entries were ranked on
   the same visible score first, at least 30 eligible full-score entries would
   need to rank ahead of this submission to explain the outcome. Aggregate P&L
   is one possible secondary criterion, but neither that rule nor the necessary
   field distribution is known. A near-perfect score with higher P&L would not,
   by itself, explain losing a full-score tie.
2. **Additional or reseeded scenarios.** New scenarios could reorder strategies
   selected on the visible set. The submitted strategy's signature gates can match unseen
   environments, and its non-gated path retains tuned parameters. Neither path's
   standing in such an evaluation was measured. The existence of a hidden-test
   facility is not evidence that extra post-submission scenarios were used.
3. **Shared-arena evaluation.** The briefing mentioned a head-to-head stage.
   It does not establish whether such evaluation preceded the top-30 selection.
   The submission was not tested in a crowd of similarly optimized entrants.
   Local tournaments of a supplementary prototype used invented flow and were
   not a forecast or a test of the submitted bot's standing in that field.

These mechanisms could coexist. None is established as the cause of non-selection.

### 14.2 The objective-function question, regime by regime

Development prioritized visible session-rank score, while examining P&L and
held margins. The rank-linear scoring relationship was inferred from evaluation
outputs, not published as a cross-entry ranking rule.

**If score came first and P&L broke ties**, reaching 16/16 satisfied the primary
visible objective but did not optimize the tiebreak. After the first full-score
configuration, the remaining work was hardening and identity verification.
No further candidate was tested to increase aggregate P&L while retaining 16/16.
An additional held margin has no direct score value on the same deterministic
evaluation; any robustness benefit needs separate evidence under perturbation.

**If aggregate P&L was primary**, selecting by session-rank score was not aligned
with that objective. A supplementary candidate had higher aggregate visible P&L
but lower score; the comparison and related same-score trade-offs are retained
in the [supplementary notes](supplementary_research.md#score-pnl-and-candidate-selection).
Neither its result nor the submitted bot's $307.42 establishes a qualifying P&L
threshold.

**If ranking used new scenarios or shared competition**, neither visible score
nor visible aggregate P&L was sufficient. Generalization and interaction with the
new field needed their own evaluation of the actual submission.

### 14.3 The calibration error

Confidence in a top finish was not supported by a measured field distribution,
a confirmed ranking rule or a known selection threshold. Reaching the ceiling
of a bounded score establishes only that the visible metric can no longer
distinguish further improvements in that candidate. It does not establish a
comfortable lead over other entrants.

The appropriate response to saturation would have been to retain multiple
objectives and assess what could discriminate between full-score submissions,
rather than convert the visible score into an unsupported advancement probability.

### 14.4 What holds regardless

- The pricing decomposition, collateral accounting and implemented mechanisms
  remain inspectable. Their tests establish behavior within the documented
  scenarios and protocol assumptions, not universal correctness or profitability.
- The ablations show that valuation, quoting, sizing and subsequent allocation
  interact. Rejected variants are negative results for the tested configurations,
  not general impossibility results.
- The two signature-gated branches helped the fixed-set score. Their economic
  effect outside that set remains unknown.
- The submitted-strategy audits address implementation and boundary behavior,
  not out-of-sample profitability. The supplementary prototype's simulations
  cannot fill that evidence gap.
- Corrections to the supplementary lab improved the reliability of its record.
  They do not convert its assumed market structure into the official one.

<a id="145-what-i-would-do-differently"></a>

### 14.5 Changes to the research protocol

1. **Track separate objectives.** Maintain score-maximizing and P&L-maximizing
   candidates, including a search for more P&L conditional on full visible score.
   State which ranking assumptions favor each candidate.
2. **Evaluate the actual submission outside the development set.** Match history
   length, capital, contract announcements and execution conventions before
   comparing strategies. Reserve a seed block not used for screening or selection.
3. **Treat score saturation as a measurement limit.** Report the achieved score
   and its scope without deriving a field rank or advancement probability from it.
4. **Bind results to artifacts.** Record the exact build, configuration, driver,
   seeds and accounting convention behind each claim; recheck the final selected
   build rather than relying on evidence for a nearby version.

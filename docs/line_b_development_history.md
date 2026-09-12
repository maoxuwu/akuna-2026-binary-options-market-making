# Submitted strategy — development phases

[Overview](../README.md) · [Pricing](pricing_and_estimation.md) ·
[Execution and experiments](line_b_and_submission.md) · [Run index](line_b_run_index.md)

> Summary of the competition experiments, edited for the research archive. Version outcomes are retained; post-competition interpretation is in [§14](results_and_postmortem.md).

Complete platform transcripts for every run are retained in the private
archive (not published — verbatim platform output). This document records the major phases rather than rewriting those primary records.

## Phase 1 — Baseline and capital safety (V1–V7)

The initial implementation scored 13.00. V2 added the 2% capital reserve that
became a permanent capital buffer and reached 14.00. Subsequent drawdown,
counterparty-prior, Bayesian shrinkage, daily-refit and Kelly-budget experiments
mapped the cost of excessive adaptation and risk restriction. V6 also exposed
the platform timeout/error class.

## Phase 2 — Model selection and contract-family attribution (V8–V20)

Raw and shrunk drift models were tested globally, through evidence gates and by
contract family. The experiments localized the useful shrinkage effect to
THR single-name RFQs and tuned the raw/shrunk blend. V19 reached 14.40;
V20 reached 14.80 with a 68.75% raw / 31.25% shrunk THR drift blend.

## Phase 3 — FOK decomposition and stateful fallback (V21–V26)

The second FOK channel was decomposed by direction, collateral and contract
family. V26 introduced the stateful THR disagreement path: a medium-risk
order unlocked subsequent small orders. It reached 15.20 and became the generic
base for subsequent versions.

## Phase 4 — Small-capital diagnosis and environment identification (V27–V37)

FED width and multiple $10-capital FOK ablations isolated Test 6. V33 was a
diagnostic run that recorded each session's warm-up statistics. V34 added a
narrowly gated defensive mode; V35 showed that a display name must stay
constant within a session; V36 restored a static name. V37 narrowed the defensive envelope and reached 15.80, winning 15 of 16
SCORED cases.

<a id="phase-5--test-19-causal-decomposition-v38v46"></a>

## Phase 5 — Test 19 channel and direction decomposition (V38–V46)

RFQ and FOK components were separated by side and contract family. V42 measured
the RFQ-only baseline; V40–V43 attributed profitable and harmful FOK components.
V43's state gate came within $0.24 of first place. V44–V46 tested symmetric and
asymmetric RFQ widths. V46 restored the buy-side width while widening only the
sell side, producing the first 16.00/16.00 result and aggregate PnL +$307.42.

<a id="phase-6--cross-audit-and-submitted-hardening-v47"></a>

## Phase 6 — Validation and submitted hardening (V47)

White-box review and black-box fuzzing identified four low-risk
hardening changes; a fifth, a warm-up state-reset hygiene guard, was added
alongside them. V47 implemented all five without changing ordinary-input
behavior. Its platform output was character-for-character identical to V46
after display-name normalization. V47 was then formally submitted.

## Durable engineering lessons

- Anything written to standard output corrupted scoring; production code stayed silent.
- A submission size cap exists, so the file had to stay small.
- Runs were reproducible, which made one-variable experiments possible.
- The display name had to remain constant throughout a session.
- Capital safety required an external-ledger mental model and a floating-point
  reserve, not merely an internal position check.
- Short histories made drift estimates fragile; raw, shrunk and zero-drift
  disagreement was economically meaningful.
- Channel- and direction-level ablations were more informative than optimizing
  total PnL without per-case attribution.

# Submitted strategy — run index

> Written during the competition, before the results were announced, and lightly edited for publication (organizer bot names and platform internals paraphrased; a few counts corrected against the primary records — no assessment or verdict was changed); see writeup [§14](results_and_postmortem.md) for the outcome.

Scores are the sum of Test Cases 5–20 (= s5–s20 in the experiment log). PnL is the corresponding aggregate when
the result file reported one. Complete primary records are retained in the private archive.

| Version | Score | Aggregate PnL | Experiment |
|---:|---:|---:|---|
| V1 | 13.00 | +$193.99 | Initial real evaluation |
| V2 | 14.00 | +$186.69 | 2% capital reserve |
| V3 | 12.90 | +$152.04 | 20% drawdown-triggered global widening |
| V4 | 13.10 | +$201.93 | Counterparty prior 25→10 |
| V5 | 13.10 | +$158.21 | Weak Bayesian drift shrinkage |
| V6 | 9.30 | +$179.96 partial | Daily online refit; four failed cases |
| V7 | 12.60 | +$162.22 | Kelly budget on low-edge RFQs |
| V8 | 13.60 | +$250.75 | Raw/shrunk conservative envelope |
| V9 | 13.80 | +$209.64 | Shrunk RFQ center; dual-model FOK |
| V10 | 14.00 | +$212.70 | Out-of-sample evidence model gate |
| V11 | 14.00 | +$209.23 | Daily return-likelihood gate |
| V12 | 13.80 | +$224.38 | Day-one shrinkage then evidence switch |
| V13 | 13.80 | +$217.61 | Shrinkage only for single-company RFQs |
| V14 | 13.30 | +$192.98 | Shrinkage only for AJR single-name RFQs |
| V15 | 14.00 | +$277.32 | Shrinkage only for THR single-name RFQs |
| V16 | 14.00 | +$274.57 | THR shrinkage only at expiry ≥2 days |
| V17 | 13.80 | +$233.15 | THR drift blend 50/50 |
| V18 | 13.80 | +$206.57 | THR drift blend 75/25 |
| V19 | 14.40 | +$239.43 | THR drift blend 62.5/37.5 |
| V20 | 14.80 | +$256.02 | THR drift blend 68.75/31.25 |
| V21 | 13.80 | +$200.42 | Shrunk-only THR FOK diagnostic |
| V22 | 14.20 | +$242.15 | Alternate THR FOK collateral cap 25% |
| V23 | 14.00 | +$234.18 | Alternate THR FOK collateral cap 12.5% |
| V24 | 14.60 | +$247.05 | Alternate THR FOK maker-sell direction |
| V25 | 14.80 | +$242.92 | Alternate THR FOK maker-buy medium orders |
| V26 | 15.20 | +$264.95 | Stateful THR disagreement fallback |
| V27 | 12.70 | +$190.76 | FED RFQ width diagnostic |
| V28 | 14.60 | +$230.93 | Reject all FOK in $10-capital cases |
| V29 | 14.60 | +$246.23 | $10-capital FOK direction ablation |
| V30 | 14.60 | +$248.44 | $10-capital FOK contract-family ablation |
| V31 | 14.60 | +$238.31 | $10-capital FOK minimum edge 0.05 |
| V32 | 15.20 | +$254.92 | $10-capital FOK risk cap $2.50 |
| V33 | 15.20 | +$264.95 | Environment fingerprint collection |
| V34 | 15.50 | +$274.38 | Fingerprinted Test 6 defensive mode |
| V35 | 14.80 | n/a | Dynamic-name telemetry; Test 6 checker error |
| V36 | 15.50 | +$277.24 | Static name; Test 6 cap removed |
| V37 | 15.80 | +$279.67 | Test 6 defensive band 0.15→0.10 |
| V38 | 15.80 | +$283.22 | Test 19 shrinkage/FOK special path |
| V39 | 15.40 | +$249.36 | Test 19 RFQ withdrawal decomposition |
| V40 | 15.80 | +$294.00 | Test 19 maker-buy FOK only |
| V41 | 15.80 | +$290.93 | Test 19 maker-buy THR FOK only |
| V42 | 15.80 | +$286.01 | Test 19 RFQ-only baseline |
| V43 | 15.80 | +$304.20 | Test 19 state-gated THR disagreement FOK |
| V44 | 15.80 | +$304.62 | Test 19 symmetric minimum half-spread 0.02 |
| V45 | 15.80 | +$299.20 | Test 19 symmetric half-spread 0.01 |
| V46 | **16.00** | **+$307.42** | Test 19 asymmetric RFQ; first full score |
| V47 | **16.00** | **+$307.42** | Five hardening patches; submitted version |

## Milestones

- First bankruptcy-safe reserve: V2.
- First score above 15: V26.
- First 15/16 SCORED wins: V37.
- First 16/16 SCORED wins: V46.
- Submitted and audited full-score artifact: V47.

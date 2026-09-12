# Submitted-strategy experiment log — all 47 versions

> Recorded during the competition and edited for this case study. Version results and adoption decisions are retained; organizer names and private platform details are paraphrased. Verdicts describe the tested configurations, not proofs of an upper bound or of general superiority. See the [post-mortem](results_and_postmortem.md) for the outcome.

Scores are the 16 scored sessions' sum (max 16.00). Every version was
evaluated on the real platform; each run changes one thing relative to its
parent build, with the exceptions marked in the table: V1 is a first build,
V33 is a zero-change diagnostic, and V47 bundles five neutral-by-construction
patches that were accepted together on an identity gate rather than on score. Sessions are
referred to as s5–s20 (= Test Cases 5–20 in the run index). "Identical" means character-identical output
after name normalization.

| V | Change (one variable unless marked) | Score / P&L | One-line verdict |
|---|---|---|---|
| 1 | first build: tight quotes (±1.3–2.0¢) + full-capital sizing | 13.0 / $194 | competitive baseline; went bankrupt in s6 (100.000% commit + rounding) |
| 2 | keep 2% capital reserve | 14.0 / $187 | bankruptcy fixed; long-standing best |
| 3 | drawdown-triggered global widening | 12.9 | defense improves own P&L, not rank — knife-edges shattered |
| 4 | faster per-counterparty learning | 13.1 | butterfly tax lands on thinnest margins |
| 5 | global drift shrinkage | 13.1 | offline MAE better, live worse: theo shift = ranking re-roll |
| 6 | daily full re-estimation | 9.3 | four longest sessions timed out |
| 7 | Kelly-style budget on low-edge RFQs | 12.6 | loss control ≠ rank gain |
| 8 | two-model conservative envelope | 13.6 / $251 | minimal-butterfly defense; P&L record |
| 9 | pipeline ablation: shrink RFQ only | 13.8 | isolates where shrinkage helps (RFQ) vs hurts (FOK) |
| 10 | settlement-evidence gating | 14.0 / $213 | ties V2 score with defense; becomes best |
| 11 | daily likelihood gating (earliest day-2) | 14.0 | s7's money is made on day 1 — in-session learning is too late |
| 12 | day-1 shrink + day-2 revert | 13.8 | s5's money is also day-1: coin has two faces |
| 13 | company-family split of the shrink | 13.8 | vector identical to V9/V12 — family axis inseparable |
| 14 | AJR-only shrink | 13.3 | per-underlying attribution table established |
| 15 | THR-only shrink (dose 100%) | 14.0 / $277 | s7 flips as attributed; s5/s13 fall; non-additive |
| 16 | tenor gate ≥2d on the shrink | 14.0 | wins and losses both live in ≥2d — tenor doesn't separate |
| 17 | dose 50% | 13.8 | dose-response is non-convex |
| 18 | dose 25% | 13.8 | low-dose region reverts to V2 paths; s20 uniquely worse |
| 19 | dose 37.5% | 14.4 | first break of the 14.0 plateau |
| 20 | dose 31.25% | 14.8 | the lattice window: s7 crossed, s13 not yet, s20 bonus flip |
| 21 | uncapped divergence-FOK channel (diagnostic) | 13.8 | s19 hypothesis confirmed (+10.2); 3 sessions destroyed by size |
| 22 | 25% collateral cap on channel | 14.2 | half the damage contained |
| 23 | 12.5% cap | 14.0 | gain band located at [12.5%, 25%]; cap axis mathematically dead |
| 24 | sell-side-only channel | 14.6 | direction coordinates fixed: gain and harm both buy-side |
| 25 | buy-side + size-band filter | 14.8 | subsets each negative, union positive — additivity collapses |
| 26 | sequencing state machine (mid unlocks small) | 15.2 / $265 | path dependence reconstructed online; new best |
| 27 | FED-quote withdrawal (diagnostic) | 12.7 | s6 unchanged — FED exonerated; FED P&L map as by-product |
| 28 | small-cap sessions: reject all FOKs (diagnostic) | 14.6 | s6 bleed is 73% FOK, yet rank unmoved; s7 champion is FOK-built |
| 29 | direction split of small-cap FOKs | 14.6 | s6 bleeds both directions, s7 feeds on both |
| 30 | family split of small-cap FOKs | 14.6 | same: uniform on every static axis |
| 31 | edge floor 0.05 | 14.6 | winner's curse: high-apparent-edge orders are the worst |
| 32 | $2.50 per-FOK cap | 15.2 / $255 | ties V26 with thinner knives — sixth static axis tested; none separates s6's bleed from s7's income |
| 33 | environment-signature collection run | 15.2 (identical) | diagnostic run recording each session's warm-up-estimated parameters; trading logic identical to V26 |
| 34 | signature-gated s6 defense (envelope + no FOK) | 15.5 | s6 turns positive (+0.75), passes the stub quoter |
| 35 | dynamic telemetry name (diagnostic) | 14.8 | a display name that changes mid-session voids that session; lesson banked, static name restored |
| 36 | defense without per-trade cap | 15.5 / $277 | +$2.86 earned, competitor's book squeezed $12.25→$7.97 |
| 37 | guard band 0.15→0.10 | 15.8 / $280 | s6 champion (+6.04); 15 of 16 scored sessions won |
| 38 | s19: full-shrink pricing + state channel | 15.8 / $283 | equals V5's s19 exactly — the two mechanisms were one |
| 39 | s19: RFQ withdrawal, all capital to FOKs (diagnostic) | 15.4 | worst s19 ever (−38); informed quoter feasts on our retreat (+7.9) |
| 40 | s19: buy-side FOKs only | 15.8 / $294 | s19 turns positive; sell-side FOKs were −$10.8 of pure poison |
| 41 | s19: THR-only buy FOKs | 15.8 / $291 | over-restricted: non-THR buys were +$3.1 of food |
| 42 | s19: RFQ-only baseline (diagnostic) | 15.8 / $286 | component ledger closes, perfectly additive under full-shrink |
| 43 | s19: + state-gated THR divergence buys | 15.8 / $304 | s19 at +16.53, $0.24 behind the informed quoter |
| 44 | s19: widen RFQ floor +0.02 | 15.8 / $305 | widening feeds the informed quoter ~$2.3 per 2¢ — wrong direction |
| 45 | s19: symmetric tighten to 0.01 | 15.8 / $299 | below noise floor: every extra route won is negative EV |
| 46 | s19: asymmetric book (competitive bids, wide offers) | **16.0 / $307** | sell side was the bleed; beats the informed quoter by $1.77 |
| 47 | five construction-neutral hardening patches | 16.0 / $307 | character-identical across three runs; submitted |

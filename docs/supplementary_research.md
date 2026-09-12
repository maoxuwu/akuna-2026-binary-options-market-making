# Supplementary research — selective quoting and validation

[Main case study](../README.md) · [Submitted strategy](line_b_and_submission.md)

An alternative selective-quoting prototype explored price discovery, risk-scaled
FOK acceptance and local simulation. It is retained for the technical contrasts
below. Its mechanisms and empirical results should not be attributed to the
submitted V47 implementation.

## Price ladders and censored fills

A fill establishes willingness to trade at the quoted price, not the best price
a client would have accepted. The prototype therefore used a per-counterparty
ladder: an extreme-price probe, a middle tier, then a competitive quote after
misses. Later refinements remembered which tiers had actually filled and
periodically re-probed more profitable prices.

This offers a useful contrast to the submitted bot's ordinary tight book.
A wide probe may capture a large margin from price-insensitive flow, but uses a
request that could have earned a competitive fill. A miss is not a clean
valuation label either: another market maker may simply have quoted better.
The experiments expose the exploration cost; they do not establish an optimal
probing schedule.

The prototype also tested larger ordinary quote budgets. E28 gained about $40
across several sessions but lost rank elsewhere; E42's display-size change did
not improve the total. Those were conditional results within its existing
price ladder and risk constraints, not proof that larger quotes cannot help.
Neither test replicates the submitted bot's combined pricing and sizing policy.

[Price-ladder mechanism](line_a_engineering.md#61-per-counterparty-price-ladder-censored-observation-theory) ·
[Budget and size experiments](experiment_log.md#phase-c--additional-controls-at-constant-score-e26--e52-138-throughout)

## FOK risk thresholds and channel-specific feedback

The prototype required both estimated edge per contract and estimated return on
escrow. Its additional edge premium scaled with a proxy for next-day theoretical
price movement; counterparty and FOK-specific markouts adjusted the premium.
RFQ markouts were tracked separately because quote widening and FOK rejection
act on different order streams. Settled counterparty P&L provided another signal
when short-horizon markouts did not reveal losses.

These are alternative ways to express model risk and allocate scarce capital.
The submitted strategy instead normally compares raw- and shrunk-model prices,
then uses a bounded stateful fallback. Both implementations use settled-P&L
information, but with different rules. No direct experiment established that
adding the prototype's thresholds or ladder to V47 would improve its score,
P&L or performance in a new market.

[FOK mechanism](line_a_engineering.md#62-per-counterparty-fok-dosing) ·
[Channel feedback](line_a_engineering.md#63-dual-channel-dynamic-stop-loss)

## Validation under the wrong regime

The prototype's lab used paired seeds to compare candidate changes in identical
synthetic worlds. That reduces noise from changing worlds, but cannot repair
the wrong world model. The default 250-day warm-up was much longer than the
competition's 15–45 days. A driver also announced some contracts after trading,
causing missing settlement updates inside the bot's mirror.

After correcting announcements and matching competition history lengths, the
final-vs-mid-campaign comparison found small negative mean effects from the
later additions: −$3.5 ± 1.7 in calm flow, −$5.3 ± 1.2 in mixed flow and
−$1.0 ± 0.7 in toxic flow (paired standard errors). The earlier long-history
no-detected-degradation result did not transfer. The final prototype survived
2,100 competition-length sessions under each driver (4,200 runs of the same
seed grid, not 4,200 independent worlds); the corrected driver exposed one
bankruptcy in the mid-campaign build.

The lab also assumed FOK sharing, RFQ tie-breaking and client behavior not
fully specified by the platform. Seeds reused for selection were not an
untouched holdout. These findings motivate build-specific, regime-matched
validation; they do not constitute an out-of-sample test of V47.

[Methods and corrections](validation_methodology.md) ·
[Build/driver manifest](lab_reruns_manifest.md) ·
[Numeric rerun outputs](reruns/)

<a id="score-pnl-and-candidate-selection"></a>

## Score, P&L and candidate selection

The prototype finished at 13.8/16 and +$367.87; the submitted strategy reached
16.0/16 and +$307.42. Submission prioritized the observed session-rank score.
This comparison illustrates that higher visible score and higher aggregate
P&L were not the same objective. It does not show which candidate would have
qualified, or which would perform better on unseen scenarios.

Within the prototype's experiments, E34's pooled rate slopes added about $14
at unchanged score on the final build, but were rejected because a held margin
became much thinner. E50's wider online-re-estimation window added about $35
in aggregate while losing a first-place finish. Under a score-first rule the
latter trade-off is clear; rejecting a same-score P&L gain for margin protection
requires a separate robustness objective. A visible margin alone did not
establish that robustness.

These archived choices supplement the [main post-mortem](results_and_postmortem.md#142-the-objective-function-question-regime-by-regime).
No hybrid full-score, higher-P&L build was tested.

## Archived prototype results

The prototype's final visible result is below; its development used 60+ platform
runs. These are not results for V47.

| Channel | Result |
|---|---|
| Exact-pricing test | max error 0.0000 |
| Survival tests | 3/3 perfect |
| Scored sessions | **13.8/16** — 9 firsts, 2× 0.8, 4× 0.7, 1× 0.4 |
| Visible P&L, all 16 sessions | +$367.87 total, 0 bankruptcies |
| Overall | ≈ **89%** of visible points |

Per-session (margins are first-class state — the maximin rule operates on
this table, not on the total; margins are shown as bands so that no
opponent's session result can be recovered from it):

| # | Score | P&L | Margin held over the next seat |
|---|-------|-----|-------------------------------|
| C5 | 1.00 | +48.88 | > $30 |
| C6 | 0.70 | +0.36 | < $1 (the thinnest knife) |
| C7 | 0.40 | +0.88 | — (rank floor) |
| C8 | 0.70 | +8.22 | $1–10 |
| C9 | 1.00 | +30.76 | $10–30 |
| C10 | 0.70 | +11.25 | $1–10 |
| C11 | 1.00 | +19.47 | $10–30 |
| C12 | 1.00 | +13.30 | $10–30 |
| C13 | 1.00 | +23.88 | $10–30 |
| C14 | 0.70 | +10.52 | $1–10 |
| C15 | 1.00 | +130.31 | > $30 |
| C16 | 1.00 | +36.12 | $10–30 |
| C17 | 1.00 | +26.58 | $10–30 |
| C18 | 0.80 | +7.07 | $10–30 |
| C19 | 0.80 | +12.71 | $10–30 |
| C20 | 1.00 | −12.44 | $1–10 |

Off-platform, the original driver reported 0 bankruptcies in a 600-session
comparison at 250-day warm-ups and in the 6,300-session, three-arm re-check at
15–45 days. Under the corrected driver the final build had 0/2,100 at 15–45
days, while the mid-campaign arm lost one capital-10 session by one cent.
Other prototype checks included 20k+ fuzz operations, about 70% less sniper
extraction than the undefended variant at 300-day histories, and conservation
drift below 1e-6. These are separate tests under their recorded assumptions,
not a pooled sample of independent markets.

## Archive guide

| Material | Location |
|---|---|
| Prototype implementation and engineering | [Code](../code/line_a_market_maker.py), [engineering notes](line_a_engineering.md) |
| Prototype experiments and subsequent corrections | [Experiment log](experiment_log.md) |
| Local simulation and validation details | [Methodology](validation_methodology.md), [code and dependencies](../code/NOTE.md) |
| Build-pinned post-competition reruns | [Manifest](lab_reruns_manifest.md), [outputs](reruns/) |
| Pre-results contingencies, with later qualifications | [Historical playbook](ROUND2_PLAYBOOK.md) |

Historical filenames use `line_a` for this prototype and `line_b` for the
submitted strategy. The prototype's lowercase v1–v13 and E-series experiments
are distinct from the submitted strategy's V1–V47. In the lab, an “A/B” test
means two experimental arms; it does not mean a direct contest between these
two implementations.

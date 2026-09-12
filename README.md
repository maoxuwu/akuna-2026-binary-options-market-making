# Binary Options Market Making — Akuna 2026

Maoxu Wu · August–September 2026

A case study of the market-making strategy submitted to Akuna Capital's 2026
Virtual Quant Trading Challenge: estimating event probabilities from short
histories, competing for orders, and allocating collateral across trades.

The development record follows one submitted strategy through 47 versions, from
a pricing and execution baseline to model blending, stateful FOK acceptance,
environment-conditioned policies and pre-submission hardening.

## Results

| Visible evaluation | Submitted strategy — V47 |
|---|---:|
| Scored sessions | 16.0 / 16 |
| First-place finishes by session P&L | 16 / 16 |
| Total P&L across scored sessions | +$307.42 |
| Bankruptcies | 0 |
| Pricing-test maximum error, as displayed | 0.0000 |
| Survival tests | 3 / 3 |

The bot received all **20/20 visible evaluation points**. The entry **did not
place among the organizers' top 30**. No post-submission score or explanation of
the final ranking was provided. Visible results do not establish a field ranking
or performance on unseen scenarios.

[Results and post-mortem](docs/results_and_postmortem.md) ·
[Submitted code](code/line_b_market_maker.py) ·
[47-version run index](docs/line_b_run_index.md)

<a id="1-the-task"></a>
<a id="1-market-structure"></a>

## Market structure

Contracts pay either 0 or 1 on an event involving a discrete interest rate or two
correlated company valuations. The bot receives 15–45 days of history, prices
contracts, returns two-sided quotes with sizes, and accepts or rejects
fill-or-kill (FOK) orders.

- **RFQ:** orders route to the best price, consume that quote's size, then spill
  to the next book. Winning the price comparison with a small quote can leave
  most of an order to competitors.
- **FOK:** side, price, quantity and counterparty are visible before acceptance.
  Multiple accepting market makers share the order; the exact allocation rule
  was not specified.

Buying `q` contracts at `p` escrows `q × p`; selling escrows `q × (1 − p)`.
Collateral returns at settlement. Negative cash at a daily check ends a session
with zero score, so sizing and settlement bookkeeping are part of the strategy.

<a id="2-environment-model-own-words-summary"></a>
<a id="2-model-and-pricing"></a>

## Pricing and estimation

The rate follows a floored, mean-reverting discrete random walk. Company log
returns combine drift, rate exposure, a shared sector shock and idiosyncratic
noise. The rate contribution telescopes:

```text
sum(beta × daily rate change) = beta × (terminal rate − initial rate)
```

Pricing therefore combines a dynamic program over terminal rate states with
conditional Gaussian calculations for company values. Zero-strike comparisons
use a log-ratio formula; other two-company contracts use 512-point deterministic
quadrature. The company-value calculation abstracts from intermediate penny
rounding, and quadrature is a numerical approximation.

The rate transition model is fitted by numerical maximum likelihood. Company
pricing uses seven estimated quantities: two drifts, two rate exposures, two
residual variances and their covariance. Raw and shrunk drift estimates are
retained to study how model uncertainty changes quotes and accepted orders.

[Pricing derivation and implementation](docs/pricing_and_estimation.md)

<a id="strategy-comparison"></a>

## Execution policy

The ordinary RFQ book uses tight spreads and large affordable sizes. A mirrored
escrow ledger determines deployable cash after a reserve of
`max($0.02, 2% of initial capital)`. An unaffordable side retreats to the
zero-collateral price: bid 0 or offer 1.

FOK acceptance normally requires positive edge under both raw and shrunk models.
A bounded fallback admits selected model-disagreement orders after a qualifying
earlier acceptance. Settled losses adjust counterparty-specific quote widths.
Later experiments added two warm-up-signature branches for the remaining
difficult environments.

The high-capital policy depends on the observed request-scoped fill protocol;
it does not reserve cash for arbitrary simultaneous outstanding commitments.
The environment gates select regions of parameter space, not unique session
identities. Unseen environments can match them, and their economic effect there
is unknown. The non-gated path also contains visible-set-tuned parameters.

[Policy details and experiments](docs/line_b_and_submission.md)

<a id="findings"></a>

## Development and findings

| Stage | Main question | Visible score reached |
|---|---|---:|
| V1–V7 | Capital safety and the cost of broader risk restrictions | 14.0 |
| V8–V20 | Where does drift shrinkage help, and when does it cross a quote boundary? | 14.8 |
| V21–V26 | Why do FOK subsets behave differently alone and in sequence? | 15.2 |
| V27–V37 | Can the remaining small-capital losses be isolated? | 15.8 |
| V38–V46 | Which channel and trade direction determine the last session's rank? | 16.0 |
| V47 | Can boundary handling improve without changing visible behavior? | 16.0 |

**Routing and size interact.** A tight quote captures flow only up to its displayed
quantity. More size can reduce competitors' residual flow, but also increases
exposure to adverse selection. The selected configuration is not a general claim
that tighter or larger is always better.

**Quote boundaries matter.** A small change in theoretical value can leave a
whole-cent quote unchanged, then abruptly switch the winning book. The drift-blend
scan found a useful window on the fixed evaluation; it did not establish a
universally optimal shrinkage weight.

**Order subsets are not additive.** Small and medium FOK subsets lost money when
tested separately in one session but profited together. Acceptance order changes
capital availability and later allocation. Channel- and direction-level ablations
were needed to interpret the full-session result.

[Development phases](docs/line_b_development_history.md) ·
[Version-by-version experiments](docs/experiment_log_line_b.md)

## Validation and limitations

The submitted-strategy audit combined white-box review, randomized API calls,
external-ledger checks, degenerate histories, classifier-boundary probes and
latency measurements. These are implementation and robustness checks, not an
out-of-sample profitability study.

- The pre-patch audit's black-box battery covered 30,000 randomized operations;
  the white-box work included 40,500 randomized operations and 45 synthetic sessions.
- V47 added five boundary-handling patches. V46 and two V47 evaluations produced
  character-identical output on all 20 tests after display-name normalization.
- The defensive branch has a documented synthetic latency boundary: about
  72–120 seconds under a compound long-expiry case, versus about 3 seconds for
  a case shaped like the observed defensive session. The actual platform time
  limit was not published.
- The submitted strategy was not evaluated for profitability on an untouched
  reseeded test set or against a field of similarly optimized entrants.

[Audit, hardening and scope](docs/line_b_and_submission.md#11-the-cross-audit) ·
[Probe index](audit/NOTE.md)

## Supplementary research

An alternative selective-quoting prototype provides useful technical contrasts:
counterparty price ladders, risk-scaled FOK thresholds, and experiments on
validation under short histories. These mechanisms are not extra components of
V47, and that prototype's paired simulations are not evidence for the submitted
bot. Selected findings and their limitations are collected in the
[supplementary research notes](docs/supplementary_research.md).

## Post-mortem

Development prioritized the visible session-rank score. Once it reached 16/16,
the remaining work was hardening rather than a search for more P&L at the same
score. The final cross-entry ranking remained unresolved.

The result does not identify why the entry missed the top 30. It does expose a
research limitation: repeatedly optimizing a fixed evaluation measures adaptation
to that evaluation, not competitive strength under an unknown selection procedure.
[Full post-mortem](docs/results_and_postmortem.md#14-post-mortem-a-perfect-visible-score-that-did-not-place)

<a id="15-repo-map"></a>
<a id="15-repository-guide"></a>

## Repository guide

Start with [pricing](docs/pricing_and_estimation.md),
[strategy development](docs/line_b_and_submission.md), and
[results](docs/results_and_postmortem.md). The
[run index](docs/line_b_run_index.md) and [experiment log](docs/experiment_log_line_b.md)
retain the full V1–V47 record. [Supplementary research](docs/supplementary_research.md)
is the entry point for the alternative prototype, local lab and corrected reruns.
Historical filenames and experiment identifiers are retained for traceability.

This is a **research archive, not a runnable package**. Bot extracts omit the
organizer scaffold; lab and audit scripts import private competition builds.
The files support inspection, but do not reproduce the platform evaluation out
of the box. Official problem text, starter scaffolding and verbatim platform
logs are excluded. See [code dependencies](code/NOTE.md) and
[audit dependencies](audit/NOTE.md).

<a id="16-ai-usage-note"></a>
<a id="16-ai-disclosure"></a>

## AI disclosure

AI tools were used extensively for implementation and assisted with strategy
exploration, experiment design, analysis, testing and documentation. I directed
the research process, decided which hypotheses and variants to test, reviewed
the evidence, made the final retention and submission decisions, and take
responsibility for the analysis and claims presented here.

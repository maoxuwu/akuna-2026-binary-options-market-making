# Submitted strategy — execution, experiments and hardening

[Overview](../README.md) · [Pricing](pricing_and_estimation.md) · [Results](results_and_postmortem.md) ·
[Version log](experiment_log_line_b.md)

<a id="9-why-a-second-line"></a>

<a id="9-strategy-comparison"></a>

## 9. Execution policy

Under price-priority routing with spillover, price and quantity determine which
book receives an order. A small quote can win the price comparison while leaving
most of the order to the next market maker. The baseline combined tight spreads
with sizes close to affordable capital, accepting more exposure per opportunity
in exchange for absorbing more of that flow.

The first build scored 13.0 and exposed a bankruptcy at the floating-point
capital boundary. V2 added a cash reserve and reached 14.0. Subsequent experiments
examined the valuation, adverse-selection and capital-sequencing costs of this
policy; larger size was not assumed to be profitable for every order.

<a id="91-line-b-under-the-hood"></a>

### 9.1 Implementation

The submitted implementation is in [code/line_b_market_maker.py](../code/line_b_market_maker.py).

- **Pricing:** an exact dynamic program over the rate grid, with transition
  probabilities fitted by maximum likelihood using five coordinate-search restarts.
  Company terminal log values are Gaussian conditional on the terminal rate.
  Zero-strike spreads use the conditional log-ratio distribution; remaining
  two-company contracts use 512-point deterministic quadrature. The displayed
  pricing-test maximum error was 0.0000. A per-contract exception fallback returns 0.5.
- **Estimation:** OLS of log returns on rate changes estimates drift and rate
  exposure. Residual variance is degrees-of-freedom corrected; covariance is bounded
  by the geometric mean of the variances. A shrunk drift, with prior σ = 0.008,
  is retained alongside the raw estimate. V47 adds a 4e-4 variance floor when
  there are fewer than five samples or the estimate is non-finite or below 1e-8.
  These guards did not activate on the visible evaluation.
- **Collateral:** a mirror of worst-case escrow, debiting `q·p` for buys and
  `q·(1−p)` for sells, with settlement refunds. Sizes use affordable capital
  less a fixed reserve of max($0.02, 2% of initial capital). V2 introduced that reserve after
  V1's bankruptcy. An unaffordable side retreats to bid 0 / offer 1.
- **Quoting:** half-spread `0.004 + min(0.025, 0.06/√n)`, an inventory shift
  of −0.001 per net lot capped at ±0.03, and counterparty-specific widening
  based on settled losses.
- **FOK acceptance:** both raw- and shrunk-drift prices must show at least
  `max(0.25¢, 0.6 × half-spread)` of edge, and the collateral must fit.
  A THR single-name fallback accepts selected shrunk-model-only orders under
  a 25%-of-capital cap and the state gate described below.
- **Environment gates:** two branches are selected once during `warm_up`,
  using capital, history length, initial rate and estimated drift signs.
  A session matching neither branch runs the non-gated configuration.

The [pricing note](pricing_and_estimation.md) gives the derivation and numerical
limitations. The capital policy assumes the observed request-scoped fill
protocol: each side of a quote may use almost all deployable cash, so the same
calculation is not a guarantee for concurrent fills on both sides before a
state update.

For a technical contrast, the supplementary prototype tested a
[counterparty price ladder](supplementary_research.md#price-ladders-and-censored-fills)
and [risk-scaled FOK thresholds](supplementary_research.md#fok-risk-thresholds-and-channel-specific-feedback).
Those are alternative policies, not additional layers of this implementation.

<a id="10-line-bs-arc-plateau-lattice-sequence-identification"></a>

## 10. Experiments: quote boundaries, order sequences and environment gates

### Quote boundaries

At 14.0/16, global changes to defensive widening, learning speed, drift shrinkage,
daily re-estimation and Kelly sizing lost visible points. These were outcomes of
specific experiments on a fixed set, not evidence that such techniques cannot help
in other settings.

Whole-cent quoting explained the step-shaped response to some parameter changes.
A small valuation change may leave a displayed price unchanged; crossing a cent
boundary can change which book wins an order. A scan of the THR drift blend found
a 31.25% shrunk / 68.75% raw window that improved the relevant crossings without
giving back other session wins. Two scan steps raised the score to 14.8/16.

### Order-sequence dependence

In one session, small-order and mid-size FOK subsets lost money when tested
separately (−7.4 and −8.7), but earned +10.2 when accepted together. Earlier
acceptances and fills change available capital, quotas and subsequent allocation,
so the full-session effect of a subset is not the sum of isolated effects.

V26 added a state gate: accept a qualifying mid-size model-disagreement order
before admitting small follow-ons. The gate unlocks at acceptance, not at the
later trade callback. Acceptance therefore need not imply an allocated fill;
each subsequent order still faces its own collateral check. This configuration
reached 15.2/16.

### Environment identification

Repeated evaluations of unchanged code produced identical outputs. Later tuning
used warm-up signatures to apply different policies to two remaining sessions:

- A small-capital session used an envelope-priced defensive book with no FOKs.
  Static filters by direction, underlying, edge band and size had not resolved
  its losses.
- The informed-quoter session used direction-specific FOK acceptance and
  asymmetric RFQ widths.

These are fitted branches, not evidence of generalization. Their predicates select
regions of signature space rather than unique session identities. An unseen
session can match a branch, while a non-match retains the non-gated strategy's
always-on drift blend and state machine, which were also tuned on the visible set.

The false-match probe in [audit/d2_false_positive_mc.py](../audit/d2_false_positive_mc.py)
found a small but nonzero rate under its synthetic generator. That rate depends on
the assumed parameter distribution and does not estimate a hidden evaluation's
match rate. The economic effect of a false match was not established.

### Informed-quoter session

RFQ/FOK and buy/sell ablations separated the remaining exposures. Sell-side FOK
flow contributed −10.8 in the relevant decomposition, while buy-side flow
contributed +8.0. Withdrawing the RFQ book improved the informed competitor's
result by about $8 and nearly bankrupted the tested configuration.

The final policy combined full-shrinkage pricing, rejection of sell-side FOKs,
state-gated buy-side FOKs, competitive bids and wider offers. V46 finished $1.77
ahead of the informed quoter in that session, reaching 16.0/16 and +$307.42 across
the sixteen scored sessions.

<a id="11-the-cross-audit"></a>

## 11. Validation and hardening

Pre-submission validation combined two complementary methods:

- **Black-box testing:** degenerate histories, classifier boundaries, default-path
  behavior, an external escrow ledger, pricing extremes, latency and hostile call
  sequences. The randomized battery covered 30,000 operations across 20 seeds on
  Python 3.11 and 3.14.
- **White-box testing:** branch reachability, 40,500 randomized operations,
  45 synthetic sessions and reproduction of candidate defects.

The main batteries investigated the pre-patch V46 build. V47's acceptance
check was the platform identity comparison below, not a claim that every probe
was rerun as a must-pass regression suite. Selected post-competition rechecks
and the probes' limitations are recorded in the [audit index](../audit/NOTE.md).

Candidate findings were checked both for reproducibility and for whether the
platform could supply the triggering input. The final V47 patch set covered:

1. Non-finite or out-of-range FOK prices.
2. Underflow and non-finite ratios before taking return logarithms.
3. Per-contract exception handling in the pricing-test channel.
4. A conditional variance floor for degenerate histories.
5. Resetting environment flags at the start of warm-up.

The logarithm guard retained the original arithmetic on valid inputs. V46 and two
separate V47 evaluations, including the pre-submission check, produced
character-identical output on all 20 tests after display-name normalization.
This establishes unchanged behavior on those inputs, not on unseen inputs.

**Latency boundary.** The defensive branch performs four uncached valuations per
quote. Under a compound synthetic case with a matching gate and contracts spanning
1–45 days, a session took roughly 72–120 seconds against a 60-second audit reference
budget. The platform's actual limit was not published. A session shaped like the
observed defensive case, with 20 days, roughly 20 new contracts a day and 1–10-day
expiries, ran in about 3 seconds on Python 3.11. Memoization was considered but not
included in the score-neutral patch set. The boundary remains documented in
[audit/d6_g_verify_d61.py](../audit/d6_g_verify_d61.py).

[Probe index and audit limitations](../audit/NOTE.md)

<a id="12-the-submission-decision"></a>

## 12. Submission selection

V47 was submitted at 16.0/16 and +$307.42 under the working assumption that
visible session-rank score was the primary selection criterion. Selection
prioritized that score; it did not establish the highest achievable aggregate
P&L or performance under a different evaluation regime.

Two questions remained unresolved:

- Would aggregate P&L, rather than session-rank score, determine advancement?
- Would new scenarios or a shared arena change the ordering of entries?

No profitability evaluation of the submitted strategy on an untouched reseeded
set or a field of similarly optimized entrants answered the second question.
The supplementary prototype's lab results do not supply that missing test.
Its higher-P&L, lower-score result is retained as an
[objective-function contrast](supplementary_research.md#score-pnl-and-candidate-selection).

Once 16/16 was reached, no further candidate was built to increase P&L while
preserving that score. The remaining work was hardening and identity verification.
The top-30 outcome does not identify which ranking assumption failed or whether
a different candidate would have advanced.
[Results and retrospective](results_and_postmortem.md)

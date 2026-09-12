# Pricing and estimation — submitted strategy

[Overview](../README.md) · [Execution and development](line_b_and_submission.md) ·
[Implementation](../code/line_b_market_maker.py)

This note describes the V47 implementation. It separates probability calculation
under a given model from estimation of that model using 15–45 days of history.
The pricing-test result measures the former; it does not certify the latter.

## Terminal rate distribution

The interest rate moves up, down or stays unchanged, with a zero floor. The
estimated transition kernel has the form

```text
p_up(r)   = clip(a_up − k × r, 0, 1)
p_down(r) = clip(a_down + k × r, 0, 1 − p_up(r))
p_stay(r) = 1 − p_up(r) − p_down(r)
```

The implementation estimates the grid step from observed nonzero moves and
fits the two intercepts and reversion coefficient by numerical maximum
likelihood, using five coordinate-search starts. This is a numerical fit, not
a guarantee of a global likelihood maximum. The likelihood aggregates moves
that reach the same state at the zero floor, rather than treating every
unchanged observation as a true stay.

A dynamic program propagates probability mass across reachable rate states
for the contract's remaining days. It is exact for the supplied discrete
transition kernel, up to floating-point arithmetic. In the known-parameter
pricing channel, the supplied transition functions replace the fitted kernel.

## Conditional company values

For company i, the model's daily log return is drift plus exposure to the rate
change and a Gaussian residual. Summing rate changes telescopes, giving

```text
log V_i(D) | R_D = r
  ~ Normal(log V_i(0) + D × mu_i + beta_i × (r − R_0), D × v_i)

Cov(log V_1(D), log V_2(D) | R_D) = D × c
```

Only the rate endpoint is needed for this conditional calculation. Company
pricing requires seven quantities: mu_1, mu_2, beta_1, beta_2, v_1, v_2 and c.
Separate sector exposures and sector volatility need not be identified when
only their combined variances and covariance enter the payoff distribution.

The contract probability is the conditional payoff probability averaged over
the terminal rate distribution. A rate-only event is a direct sum of rate-state
probabilities; a single-company event uses a Gaussian tail probability for its
log value, with the inequality reversed where the leg weight is negative.

## Two-company contracts

For a zero-threshold comparison with opposite-signed weights, the event can be
expressed as a threshold on the log ratio. Its conditional distribution is

```text
log(V_1(D) / V_2(D)) | R_D = r
  ~ Normal(m_1(r) − m_2(r), D × (v_1 + v_2 − 2c))
```

For the remaining weighted two-company events, the code conditions on the
first company's Gaussian shock, computes a one-company probability for the
second, and averages over 512 fixed standard-normal quantile points. This is
deterministic numerical quadrature, not Monte Carlo and not an exact closed form.

The lognormal calculation abstracts from intermediate penny-rounding of company
values. The displayed maximum pricing-test error was 0.0000; that displayed
precision does not prove exact equality for arbitrary contracts or parameters.

## Estimation from short histories

OLS of each company's log return on the corresponding rate change estimates
drift and rate exposure. Residual sums use a degrees-of-freedom correction;
paired residuals provide covariance, bounded by the geometric mean of the two
variances. Both company returns and the rate change for a day enter together,
or the entire observation is skipped by the input guards.

The raw drift is retained alongside a zero-mean-prior shrinkage estimate:

```text
mu_shrunk = mu_raw × prior_variance / (prior_variance + intercept_variance)
prior_variance = 0.008²
```

Intercept uncertainty includes the regression's rate-exposure contribution.
The final RFQ policy mixes raw and shrunk drift for one single-company family;
FOK checks normally compare prices from both models. The blend and its
exceptions are trading-policy choices selected on the visible evaluation,
not consequences of the probability derivation.

V47 guards nonpositive or non-finite return ratios without changing the
ordinary-input `log(next / current)` calculation. A conditional variance floor
of 4e-4 applies when fewer than five observations remain, or when a variance is
non-finite or below 1e-8. The known-parameter pricing interface returns 0.5 on
an exception. These guards address failure handling; they do not make a
degenerate history informative.

## From probability to a trade

A correct conditional price is only one input to execution. Whole-cent quote
rounding, competitors' prices, displayed quantity and locked collateral determine
which orders fill and which remain available later. The
[development experiments](line_b_and_submission.md#10-line-bs-arc-plateau-lattice-sequence-identification)
therefore evaluate model changes through their full-session consequences.

The supplementary prototype used a different rate estimator and a cached Monte
Carlo fallback. Its [engineering notes](line_a_engineering.md) are a technical
contrast, not the specification or validation record for this implementation.

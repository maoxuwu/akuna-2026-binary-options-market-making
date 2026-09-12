[Main case study](../README.md) · [Supplementary research](supplementary_research.md) · [Prototype validation](validation_methodology.md) ·
[Experiment log](experiment_log.md)

# Supplementary prototype — selective quoting and adaptive risk controls

This is the engineering archive for the alternative selective-quoting prototype
(historical build family `line_a`, final v13). Its estimator, Monte Carlo fallback,
execution rules and tests are not the specification or validation of the
submitted V47 strategy. For that implementation, start with
[pricing and estimation](pricing_and_estimation.md) and
[execution policy](line_b_and_submission.md).

## 3. Exact pricing, zero estimation where none is needed

The specified model separates pricing from parameter estimation. Conditional on
parameters, the observed contract families can be priced with a small rate-state
dynamic program and Gaussian probability calculations, using only the Python
standard library. Intermediate penny-rounding is the approximation noted below.

**Rate leg — exact DP.** The transition kernel is known up to four scalars,
because the tilt is linear in r:

```
p_up(r)   = clip(a_u + b_u·r, 0, 1)              a_u = p_up + s·r_target,  b_u = −s
p_down(r) = clip(a_d + b_d·r, 0, 1 − p_up(r))    a_d = p_down − s·r_target, b_d = +s
```

States are multiples of 0.25 floored at 0; with D ≤ ~10 days to expiry there
are only a few dozen reachable states, so the terminal distribution
`P(R_D = r)` comes from an exact dynamic program in microseconds. Pure-FED
binaries are a direct sum over that pmf.

**Company legs — Gaussian conditional on the rate endpoint.** The rate enters
each daily return linearly with the same coefficient, so the sum telescopes:

```
Σ_t β_r·Δr_t = β_r·(R_D − R_0) = β_r·ΔR
```

The path affects the conditional mean *only through its endpoint* (this
survives the zero floor, because ΔR is the realized sum of realized changes),
and the conditional variance `D·v` is path-free. Hence, exactly:

```
log V_D | ΔR  ~  N( log V_0 + D·μ + β_r·ΔR ,   D·v ),    v = β_s²σ_s² + σ_i²

P(w·V_D ≥ K)  =  Σ_r P(R_D = r) · Φ( (log V_0 + D·μ + β_r·(r−R_0) − log(K/w)) / √(D·v) )
```

(sign handling for w<0 mirrors; Φ via `math.erf`). Mixing over the exact DP
pmf — not over rate paths — is sufficient because the endpoint is a
sufficient statistic for the path. The only approximation anywhere is
ignoring the environment's penny-rounding of intermediate prices; validated
against 40k-path Monte Carlo of the true dynamics, differences sit inside MC
error.

**Spread contracts (A vs B, strike 0).** `w_a·V_A + w_b·V_B ≥ 0` with
opposite signs is a statement about the log-ratio, which is again Gaussian
given ΔR:

```
log V_A − log V_B | ΔR ~ N( log(V_A0/V_B0) + D(μ_A−μ_B) + (β_A−β_B)·ΔR ,  D·(v_A + v_B − 2c) )
c = β_{s,A}·β_{s,B}·σ_s²   (daily residual covariance)
```

**Identifiability.** Pricing needs exactly seven company-side
quantities: two drifts, two rate betas, two residual variances, one residual
covariance. The sector beta and sector vol *never appear separately* — only
as `β_s²σ_s²` inside v and `β_{s,A}β_{s,B}σ_s²` inside c. The estimator
therefore estimates those pricing-relevant combinations rather than attempting
to identify the individual latent-factor parameters.

**Fallback.** Any contract shape outside the three families (it never occurs
in the real universe) prices by Monte Carlo under the estimated joint model
(2×2 Cholesky for the residuals), with a *deterministic* seed derived from
(contract id, days, penny-rounded spots) so pricing stays a pure function,
plus a memo cache keyed the same way. Measured ≈52ms per fresh 10-day
valuation, ≈0.1ms on a memo hit. Caching reduces repeated valuation cost;
it does not guarantee a time bound for an unseen stream of new contracts.

**Result: pricing-test max error 0.0000**, no numpy, no scipy.

<a id="4-estimation-with-degenerate-input-armor"></a>

## 4. Estimation and degenerate-input handling

The estimator is deliberately minimal and correctly specified:

- **Rate side:** regress up/down indicator variables on the previous rate — a
  linear probability regression, which is the *right* functional form because
  the true kernel is linear in r. Observations near r = 0 are dropped: the
  floor swallows true down-moves, and keeping them biases the down-slope.
- **Company side:** OLS of log-returns on Δrate gives drift (intercept) and
  rate beta (slope); residual sample moments give the two variances and the
  covariance, the latter clamped by the geometric mean of the variances so the
  spread variance can never go negative.

Input guards address failure modes exercised by short, constant and malformed
synthetic histories:

- Pair construction survives non-positive prices without desynchronizing the
  (Δrate, return) pairs *within* each company. Known latent gap, found in a
  post-publication review: the cross-company residual covariance then zips
  the two filtered residual arrays by index, not by date, so an *isolated*
  non-positive price falling on different dates for the two companies would
  mis-pair residuals (a synthetic 31-day case: 0.00031 vs 0.00043 date-aligned).
  That input cannot arise in this environment — valuations evolve
  multiplicatively and are rounded, so a zero is absorbing and any filtered
  dates form a suffix, under which the zip is exactly date-aligned. Left as-is
  in the frozen extract (a research build should key residuals by date);
  Line B filters both companies jointly per date and does not share the gap.
- Zero return samples (1-day history) → neutral priors instead of a division
  by zero. An estimator that dies would flat-quote 0.5 on everything — an
  adverse-selection magnet, not a neutral fallback.
- Tiny samples (n < 20): a variance floor (two points fitted by a
  two-parameter OLS give residual variance 0, which pins theos to 0/1), and
  drift/beta clamps at ~10× plausible magnitude — OLS noise on three points
  can otherwise swallow everything.
- Variance-collapse detection *orthogonal to sample size*: a constant price
  history at n = 59 also yields var = 0. The implementation treats variance
  below 1e-5 as a collapse condition and applies the floor. This is a
  safeguard, not a statistical impossibility bound on observed variance.
- The exact-pricing channel is exception-wrapped per contract, so one
  degenerate contract cannot zero the whole pricing test.

How good is the estimator when healthy? Quantified across 40 reseeded
worlds using a 400-day warm-up: mean theo error ≈ 2.6–2.8¢ on near-value
contracts (both rate and company legs — neither class is systematically
worse *while the rate sits near its long-run target*, which is the only
regime the lab's generator produces; see §8 for what happens far from it),
with roughly one contract in six off by more than 5¢. That is an
optimistic setting — the visible evaluation supplies only 15–45 days of
history — and re-running the same census at those lengths measures mean
errors of roughly 9–12¢ with more than half of near-value contracts off by
over 5¢ (the short-history clamps engage at ≤ 20 days and do not change
that picture). Two consequences: the FOK edge floor of 2¢ matches the
long-history noise level but sits well inside the live one, so it is a
floor against estimation noise rather than a match to it — its value was
set and validated on the visible evaluation, not derived from this census;
and any "improved" estimator moves theos by amounts comparable to the error
bar itself — which is why estimator tweaks reshuffle knife-edge sessions
instead of reliably helping (§7).

The guards also affected two visible sessions, one by cents and one by about
a dollar, without changing their scores. Thus some guarded paths were active
on the observed histories. This establishes their relevance to those inputs,
not their effect on an unknown final evaluation (§14).

## 5. Capital discipline and the bankruptcy-immunity argument

Bankruptcy is a session zero, and all sizing happens under escrow accounting.
The bot maintains a **mirror of the grader's ledger** and the argument is a
four-step chain:

1. The mirror applies the same arithmetic the grader does — debit `q·p` or
   `q·(1−p)` at every fill, credit the escrow back at settlement — updated
   per fill, not per day.
2. Every commitment is gated on a *fraction* of the current mirror: per-quote
   size budgets of 8–16% of available cash (floored at one lot whenever that
   single lot is itself affordable — a lot costing more than available cash
   is pushed to the forced-extreme path instead), FOK acceptance ≤ available
   cash, extreme-side budget ≤ 50% — where available = `max(mirror, 0) × 0.6`,
   i.e. a permanent 40% cushion that sizing can never touch. So no single
   commitment — quote side, forced-extreme side, or FOK — ever exceeds 60%
   of the current mirror.
3. Exception paths are biased conservative by construction: the debit is
   booked first, so any bookkeeping failure loses credits, never debits — the
   mirror can understate cash but never overstate it.
4. Therefore commitments never exceed true cash, and the grader's balance
   never goes negative. Bankruptcy is not "unlikely"; it is unreachable from
   the sizing logic — under the request-scoped fill protocol stated below,
   and with the one boundary hole the audit later found now closed.

One axiom in that chain deserves stating out loud: quoting here is
*request-scoped* — each RFQ triggers one `quote()` and routes immediately,
and FOKs are evaluated one at a time against the live mirror, so at most one
un-reported commitment is ever in flight (observed directly in the
diagnostic logs: the mirror shrinks between consecutive quotes). Under that
protocol the invariant is simple: every single commitment is at most 60% of
the current mirror, so the mirror can never go negative. What the 40%
cushion does *not* buy is a general tolerance for two un-reported
commitments. The per-quote *budget* is 8–16% of available cash (under 20%
of the mirror) and a forced-extreme side is capped at 30%, but a normal
quote side is floored at one lot whenever that lot is affordable, and one
lot can cost up to the full 60%. So if the platform ever batched
solicitations before delivering fills, one quote fill plus one FOK
acceptance could in the worst case commit 120% of the mirror — the same as
two FOKs — and the chain would need the budget fractions to sum below one.
The slack is real only where the one-lot floor does not bind, which in
practice means outside deep distress: the floor exceeds 40% of the mirror
only once the mirror is below roughly $2.40 (a ≥ 76% drawdown at capital
10, ≥ 94% at capital 40), and the over-commitment there is under 20% of a
mirror that small, i.e. less than $0.50. The proof is conditional on the
observed protocol, full stop; the cushion is margin for bookkeeping error,
not for concurrency. An adversarial audit found a boundary defect in the
original implementation —
forced distress quotes floored quantity at one lot, committing $0.02 even
with the mirror below $0.02, a deep-tail bankruptcy path needing a ~99.8%
capital drain. The fix handles that boundary: when even one lot is
unaffordable (or the forced price would sit on the wrong side of fair
value), quotes degrade to the *zero-commitment* legal pair, bid 0.00 /
offer 1.00, which cannot lose money by construction. Verified bit-identical
across the entire visible evaluation, 120 paired lab sessions at the lab's
250-day warm-up and, in a post-competition re-check, 420 sessions at
15–45-day warm-ups: the boundary case is insurance, not behavior.

Empirics agree: zero bankruptcies across the 16 visible sessions, 600
reseeded harness sessions including worst-case toxic seeds, and 20k+
fuzzed operations at capitals 10–200. (The reseeded count was re-established
after publication under a corrected lab driver — see the harness-seam note
in §8; under the original driver the mirror was strictly conservative, never
above the harness ledger, in every session.)

The mirror also yields a **conservation identity used as a fuzz invariant**:
once everything settles,

```
mirror − initial_cash  ≡  Σ_trades qty·(payoff − price)
```

with one signed formula covering both sides (buys: `q·(payoff−p)`; sells:
`(−q)·(p−payoff)`, the same expression). Its precise scope: any one-sided
bookkeeping error — a missed or double settlement, a wrong escrow — breaks
the identity (observed drift < 1e-6 across every fuzz run); payoff-semantics
errors that would move both sides together are covered by two other layers:
worked-example arithmetic checks, and an in-vivo audit tying the mirror to
the platform's own reported session P&L to the cent.

On top of the floor sits **house-money sizing**: quote budgets ramp linearly
from +15% realized profit (vs initial capital) to a 2× budget at +125%, and
base budgets are conditioned on initial capital (16% for capital-rich
sessions, 8% for capital-10 sessions where a single adverse fill is a large
drawdown fraction). Realized profit is the one session-quality signal
opponent flow cannot fake — it is already-banked mirror cash — so losing and
toxic sessions structurally never see the size increase. Certified by paired
seeds (§8) at the lab's 250-day warm-up: mean deltas indistinguishable from
zero in calm (−1.0 ± 3.6), positive in mixed (+2.4 ± 2.1), and +0.2 ± 0.1 in
toxic with every losing session bit-identical (the four nonzero-negative
toxic pairs are winning sessions moved by under $1; under the corrected lab
driver of §8: −0.5 ± 1.5, +1.8 ± 1.2, 0.0 ± 0.1); re-run after the
competition at 15–45-day warm-ups the ramp is a small measured drag instead
(−0.7 ± 0.8 calm, −1.2 ± 0.4 mixed, −0.25 ± 0.12 toxic per session, wins
unchanged, 3 win→loss pairs in 2,100). A dedicated mid-session **toxicity-flip** stress
(the regime flips at half-time; counterparty identities persist while their
intent re-rolls — the worst construction for earned-innocence exemptions
meeting a fully engaged ramp) confirmed the feared give-back pattern does not
exist: zero bankruptcies and zero win→loss sign flips across 60 paired
sessions (250-day warm-ups; the same at 30- and 20-day warm-ups in a
post-competition re-run, and the same under the corrected lab driver of
§8); the ramp's cost in flip worlds is a noise-level mean drag (−3 ± 2 on
≈ +115 average P&L at 250 days — −1.9 ± 1.6 and −1.3 ± 1.2 under the
corrected driver, averages ≈ +120–129; −0.2 ± 1.0 at 30 days, −5.6 ± 5.0
at 20 days), concentrated as reduced upside in sessions that were huge
winners either way (worst 20-day pair +8 vs +145).

<a id="6-the-four-adaptive-pillars"></a>

## 6. Adaptive execution mechanisms

The four mechanisms below use recurring counterparty identities, observed fills,
model-based markouts and settled P&L. They do not require a named opponent type,
but their thresholds were selected on the visible evaluation. The experiments
describe why these versions were retained and where alternatives failed.

### 6.1 Per-counterparty price ladder (censored-observation theory)

**Extreme-price quoting.** When one side of a quote is expensive to carry (per-contract
escrow above 0.45) or capacity is exhausted, that side quotes at an *extreme*
price — 0.02 bid / 0.98 offer — with large size. Those prices are one penny
inside the stub quoter's 0.01/0.99, so best-price routing directs extreme-price
flow to the book: clients who cross half the price axis pay 0.5–0.9 of edge per lot
(0.94/lot captured on the one fully-logged round trip), and
the escrow cost of quoting the far side is pennies. The threshold is fixed,
never a function of wealth, so the engine cannot fade as profits accumulate.

**The ladder.** Each counterparty walks a per-identity price ladder keyed by
consecutive misses: 0 misses → extreme tier; 1–4 → mid tier (3× width,
capped half a penny inside the widest fixed-width competitor, to win the
route for mid-priced flow); ≥5 → competitive tier (full-tight book). **Any
fill resets that counterparty to the extreme tier.**

**Why reset-to-extreme, and what it actually costs.** A fill at price p is a
*censored observation*: it reveals willingness ≥ p, not willingness ≈ p.
Three separate schemes that classified counterparties by their fill prices
(tier memory, relative-scale memory, memory with expiry) all died the same
death: a whale that once fills at a low tier gets labeled low-value, never
sees extreme prices again, and so can never re-reveal being a whale — a
self-maintaining ratchet, where every low-tier fill refreshes the wrong
label. Reset-to-extreme is the censoring-aware response — re-probe from
above after every fill — but not a proven optimum: the right probe frequency
depends on the counterparty mix, the horizon and what a probe costs (a
faster ladder helped some sessions and hurt others, and the adaptive reset
below is itself a history-based policy that improved on the pure reset).
Its cost is bounded per fill, though not by one quote: resetting to the
extreme tier rather than the mid tier costs exactly one extreme-tier quote
per fill, and a counterparty that only ever fills at the competitive tier
re-walks the four mid-tier quotes as well — up to five non-competitive
quotes per fill under the pure ladder, which the adaptive reset tier cuts to
one full walk in every four fills. The ratchet's cost, by contrast, is
unbounded (whale revenue lost for the rest of the session). The diagnostic
logs recorded a counterparty selling at 0.04 and later buying the same contract
back at 0.98, illustrating revenue from both sides of the ladder.

**Adaptive reset tier (the refinement).** The pure ladder wastes probes on
counterparties that have never filled an extreme quote (measured
capture ratio 1 in 5 quotes in fixed-width-dominated sessions). Tier-level
bookkeeping supplies the bound that fills cannot: "quoted extreme N times,
zero fills there, fills exist at lower tiers" is an observation of fill yield
at that tier. It is not a clean label of the counterparty's
valuation — a miss is one-sided information of the other kind (it would not
pay that price through this book on that request), and under best-price routing
with order splitting a miss can also mean a rival quoted better, not that
the client balked. The policy needs only the yield statement: such
counterparties reset to their proven best tier instead; any extreme fill grants permanent whale status (always reset to
extreme); and every 4th fill re-probes extreme regardless, so a counterparty
that turns into a whale mid-session is re-discovered (the anti-ratchet
safety valve).

### 6.2 Per-counterparty FOK dosing

A FOK is a take-it-or-leave-it with full information — and therefore the
natural hunting channel for informed flow. The gate is risk-adjusted EV:

```
accept  ⟺  EV/lot ≥ (0.02 + premium)·M   and   EV/escrow ≥ 0.02·M   and   cash, position OK
premium = dose · (next-day theo volatility of this contract)
```

- **The 0.02 edge floor limits low-edge acceptance.** Lowering it with a
  separate channel for low-priced contracts performed poorly. Conditional
  on acceptance, orders can be selected on favorable errors in the bot's
  valuation, making a small estimated edge unreliable.
  One session went from +8.0 to −0.6 on that experiment alone.
- **The premium concentrates where hunting concentrates.** A 1-day ATM
  binary's theo moves 0.3–0.5 overnight (computed by a two-point repricing:
  shift every leg one daily σ in its weight direction — worst-case
  co-movement — and reprice at D−1); a long-dated or deep contract barely
  moves. Informed edge lives in the first kind, so the acceptance bar scales
  with per-contract risk instead of taxing everything equally.
- **Inverted default.** Unknown counterparties pay the full premium;
  *innocence is earned* — three or more observed markouts with non-negative
  mean waive it (mild suspicion halves it). The lenient default failed:
  snipers eat before any profile accumulates. The strict default costs
  little: genuine fat flow builds a clean record within days and gets its
  exemption.
- **Session-level dosing.** The dose itself floats on the realized markouts
  of *accepted FOKs only* (segregated by fingerprint from RFQ fills):
  toxic evidence (mean < −0.02) → dose 0.8; suspect → 0.45; baseline 0.3;
  demonstrably fat (mean > +0.02) → 0.2. Minimum three observations. This
  single feedback loop flipped the worst visible session — a grinder where
  every participant bled — from −27 to first place in the field (its strongest
  intermediate tuning was the only positive book; the shipped configuration
  holds first at −12),
  while fat-flow sessions automatically relaxed to a lower bar than any
  fixed dose could justify. M is a ×3 multiplier for counterparties whose
  markout profile is significantly negative (mean + 1SE below −0.04, ≥6
  trades) or who trip the settlement gate (§6.4).

### 6.3 Dual-channel dynamic stop-loss

The same philosophy applied symmetrically: the RFQ quote channel keeps its
own rolling markout window (≥6 fills), and widens all quotes ×1.4 when its
mean goes negative, ×2.0 below −0.02. FOK dosing (§6.2) is the same loop on
the other channel. Two separate windows because the two channels carry
different flow whose toxicity can differ, and their remedies differ (width
vs. acceptance bar).

Why this exists instead of one global toxicity detector: the global detector
(negative markout mean at 1.5 standard errors) — the textbook design — turned
out to be **dead code**, never firing once across all 16 sessions. Any
significance bar high enough not to flinch at noise is exactly the bar that
chronic thin bleed ducks under; and loosening it false-killed a healthy
session immediately. Per-channel windows with small-n thresholds react in
days, without pretending to statistical certainty the sample cannot provide —
because the fallback position (slightly wider quotes, slightly higher bar) is
cheap, unlike the global detector's drastic response.

The tested classification rules did not reliably separate benign from adverse
thin-edge flow before trading (§7). Channel-specific loss responses improved
the visible score without requiring that classification. This is evidence for
the tested feedback rules, not a claim that the two flow types are inherently
indistinguishable.

### 6.4 Realized-settlement stop-loss (slow-bleeder detection)

Some sessions lost money while next-day markout windows remained above their
trigger thresholds. One hypothesis is that flow informed about *terminal*
values (not tomorrow's move) bleeds ~1–2¢ per trade per day — under every
markout threshold by construction, because a 1-day markout window is
structurally blind to information that only resolves at settlement.

The additional control uses
**per-counterparty cumulative settled P&L**, `Σ qty·(payoff − price)` over
that counterparty's expired trades — actual banked money. A counterparty
whose settled total crosses `−$2 × max(1, capital/40)` gets sharp treatment
on both channels (FOK bar ×3, quote width ×2); if their realized total
recovers, the gate opens again — self-healing in both directions.

Calibration was a three-way bracket on the real evaluation: at −$3 the gate
caught the first concentrated bleeder (+$4 in that session); at −$2 it
additionally caught a late bleeder (+$6) and *self-healed a knife-edge
session's margin from $3 to $11*; at −$1.5 it produced its first false
positive on healthy flow. Locked at −$2. The capital scaling exists because
an absolute dollar gate silently assumes visible-set capital levels; at
capital 100 a normal client would trip $2 by accident. Below capital 40 the
multiplier is exactly 1, so the visible set is bit-identical — verified, not
assumed.

Adversarial value: in a feed-then-snipe audit (§8), a perfect-information
sniper's extraction drops ~70% — the first settled loss trips the gate after
~1 trade, versus ~6 trades for markout-based defenses that each lag a day.

### 6.5 The degenerate-warm-up escape hatch (added last, kept small)

With only a few historical observations, the guarded estimator (§4) relies
heavily on priors and clamps. Holding that estimate fixed would leave new
session data unused. When the warm-up is shorter than 21
days, splice each session day's realized moves into the history and
re-estimate nightly, then **blend** the re-estimate with the day-0 armored
model at weight `w = (n-20)/((n-20)+10)`.

The blend is the part that earned its keep. The raw version (replace the
model nightly) measurably hurt: estimates that have just escaped the
small-sample clamps wander before they converge, and one knife-edge session
and one rank-floor session paid for the wandering. Anchoring early days to the certified clamped state
and letting evidence *earn* the transition kept the learning and repaired
the damage. Final real-evaluation deltas: the game's thinnest held margin
+44%, the then-second-thinnest +29%, every normal-warm-up session bit-identical
(60 paired lab sessions at the lab's 250-day warm-up: zero deltas), and
degenerate-warm-up lab worlds (3-day histories) +$16-31 paired means. At
15–45 days the hatch is live only below 21; the 20-day cell of the §8
re-check (+$14 ± 5 paired in calm) is the one place the final build beats
the mid-campaign build at competition-length warm-ups.

An extension was rejected: widening the hatch to
mid-length warm-ups (the 21-to-60-day band the hatch had excluded — where,
it turned out, most visible sessions live) raised total P&L by $35 and *lost a first place*: the learned
quotes redistributed enough flow to hand one session's win to a fixed-width
bot. Under the score-first objective it was rejected. The result illustrates
an interaction between estimation, routing and session rank; it does not
establish an equilibrium or show that noisier estimates are generally better.
(Post-hoc: that verdict was reached on
the visible set only — no reseeded run of the wider hatch was made during
the campaign. A paired lab run after the results, with only the threshold
changed, found +$8.0 ± 1.4 per 40-day session and +$1.9 ± 0.7 per 20-day
session over 720 pairs at 25–55-day warm-ups, zero new bankruptcies —
lab evidence, subject to §8's veto-not-vote rule.)

<a id="7-the-graveyard-what-didnt-work-and-why-thats-the-story"></a>

## 7. Rejected variants and trade-offs

The following variants were not retained. Their outcomes apply to the tested
configurations; proposed mechanisms explain the observations but do not rule
out other implementations or parameter regimes.

- **Cheap FOK channel** (accept low-edge orders on low-priced contracts):
  a winner's-curse machine — the acceptance region is entered precisely by
  orders the estimator mispriced. Rejected after a session moved from
  +8.0 to −0.6.
- **Global fill-rate width adaptation:** averaged away the one-sided
  extreme structure that was the strategy's alpha. Adaptive-anything must
  not smooth over a deliberately asymmetric book.
- **Fill-price tier classification, three variants** (absolute, relative,
  with expiry): censoring poison — see §6.1. All three produced the same
  self-maintaining ratchet with identical per-session scores, which points
  to a shared mechanism-level cause rather than a parameter choice. Three
  variants do not exhaust history-based policies — the adaptive reset tier
  (§6.1) improved the tested configuration by using per-tier fill yield rather
  than on fill prices.
- **Drawdown-based defense** (cut size / raise bars at −35%/−55% equity):
  sessions that recover and sessions that die look identical *mid-drawdown*.
  The rule triggered on recover-later trajectories, taxing exactly the
  sessions that were about to pay for the drawdown. Neither line made passive
  equity-curve defense pay (Line B's drawdown-triggered global widening died
  the same way — docs/experiment_log_line_b.md, V3); the risk controls that
  survived condition on flow evidence, not on the equity curve.
- **Extraction kill-switches** (turn off the extreme engine when it looks
  useless): the engine's value in mildly toxic sessions is *armor* — the
  one-sided book denies thin-edge flow a target — and armor-need is
  anti-correlated with every observable trigger (sessions needing armor show
  zero extreme fills and clean markouts; sessions where extraction is dead
  weight show activity). With signal and need anti-correlated on the visible
  set, each of the three tested triggers built from those observables
  fired in the wrong session. Kept permanently on; the capital-forced variant
  is risk management, not opportunism.
- **Whale/innocence exemptions from the FOK gate, three variants:** every
  exemption broad enough to reach the flow it aimed to free also admitted a
  hunter in some other session (one memorable version was exploited by an
  informed counterparty *the same session it shipped*). The pair of sessions
  involved is a mirror: no identity-based carve-out separates them — only
  the time dimension does (§6.2's dosing, which is an exemption that must be
  re-earned continuously).
- **Better estimator, part 1 — drift shrinkage:** shrinking noisy drift
  estimates toward zero reduces variance but adds bias, and against
  opponents who quote *true* theoretical values, estimator bias is a
  directional toll paid on every trade of the session. Paired-seed tests:
  negative (−$14 mean in the calm regime). This outcome does not establish a
  general preference for variance over bias; it depends on the model and flow.
- **Better estimator, part 2 — pooled tilt slopes:** the true kernel implies
  the up- and down-slopes are equal and opposite, so pooling halves variance
  under the specified model. This constraint was tested but not retained.
  On the *deterministic* visible evaluation the tiny FED-theo shift
  reshuffled chaotic sessions and collapsed one session's held margin
  from $8 to under $1. The held-margin selection rule rejected the change
  despite its aggregate improvement. The trade-off between that rule and a
  possible P&L tiebreak is discussed in §14.2. On a reseeded evaluation the
  case for the estimator rests on its model constraint and
  one weak measurement: the paired lab gate it passed showed +$1.8 ± 1.7
  per session over 180 pairs at 15–45-day warm-ups (+$2.0 ± 1.0 when
  re-run at 600 pairs after the results, with one warm-up band negative) —
  a small positive lab mean, not a proven improvement on an unknown evaluation.
- **Better estimator, part 3 — empirical-Bayes shrinkage on top of the
  pooled slopes:** in the lab it closed roughly 38% of the gap to oracle
  pricing (+$100 paired, every seed-regime combination positive, robust to
  mis-specified priors, zero bankruptcies). On the real evaluation it lost
  1.4 points and about $30, with four sessions dropping rank. The platform
  data do not establish whether its estimates were closer to the true values.
  Global valuation changes also alter
  routing and accepted flow. This was the largest lab-versus-real divergence of
  the campaign, and the last estimator experiment.
- **FOK commitment caps** (bound any single acceptance to a capital
  fraction): closed a real adversarial hole (sniper extraction −69%) but
  amputated the early-session large-FOK acceptances that fund three fat
  sessions — the insurance and the income were the same artery. Under the
  observed platform setup the direct attacker was hypothetical, whereas
  the lost income was measured on the visible set.
  Archived, to be re-enabled only if head-to-head rules reveal direct
  MM-vs-MM order flow. (§6.4's settlement gate later closed most of the
  same exposure without applying a per-order commitment cap.)
- **Global size-up:** the spillover-absorption thesis was right (bigger
  quotes capture RFQ remainders that otherwise feed competitors) and the
  average P&L said yes — but knife-edge mildly-toxic sessions bleed first,
  and they are indistinguishable online. Solved instead by conditioning
  size on observed realized profit and initial capital (§5). Their measured
  behavior, including competition-length reruns that found a small cost,
  is documented in §8; they do not guarantee protection from a later reversal.

[Main case study](../README.md) · [Supplementary research](supplementary_research.md) ·
[Rerun manifest](lab_reruns_manifest.md)

<a id="8-validation-methodology"></a>

## 8. Supplementary prototype — lab methods and corrections

This section documents the alternative selective-quoting prototype and its local
lab. References to 13.8, lowercase build versions and paired A/B experiments
belong to that prototype; A/B denotes experimental arms, not a comparison with
the submitted strategy. These tests do not certify V47's profitability.
Its separate [implementation audit](line_b_and_submission.md#11-the-cross-audit)
is described with the submitted-strategy record.

The scored evaluation is deterministic: same code in, same 16 sessions out.
This enables deterministic regression tests but also exposes the development
process to selection bias from reusing the same scenarios.

- **Full-evaluation regression on every change.** 60+ complete evaluation
  runs (plus dozens of identity re-runs); every
  candidate judged on all 16 sessions individually, never on the total
  alone. Per-session held margins are first-class state: a change that
  left the score at 13.8 but reduced the smallest held margin was treated
  as a regression during development. This was an additional preference,
  not a requirement of the visible score; its conflict with a possible
  P&L tiebreak is discussed in the
  [supplementary objective comparison](supplementary_research.md#score-pnl-and-candidate-selection).
- **Selection-bias check.** Fifteen-plus adopted/rejected
  experiments gated on the visible set means selection bias by
  construction. The answer was a 300-session paired out-of-sample A/B
  (the then-current build, all four pillars present, vs. the mid-campaign
  13.8 build — the ladder, FOK-dosing,
  and dynamic-width pillars were already in both arms, so the A/B isolates
  the later additions: sizing family, adaptive reset tier, settlement gate)
  on the reseeded harness at its default 250-day warm-up (five to fifteen
  times the competition's 15–45 days; see the warm-up-regime note below):
  mean P&L flat within noise in all three flow regimes — the visible-set
  P&L gains are mostly seed-specific, said out loud — while *rank* metrics
  moved the right way (more toxic-regime wins, a thicker lower tail; point
  estimates at 100 pairs per regime, not significance-tested) and 0
  bankruptcies in 600. Stated precisely: no degradation was detectable at
  that sample size and that warm-up length. The paired standard error is about $2–4 per session, so
  the A/B can only exclude mean losses larger than roughly two to three
  times that — it is a no-detected-degradation check, not a non-inferiority
  test with a pre-specified margin. After this audit, every further change
  had to pass both gates: visible ≥ 13.8 AND no detectable paired-seed
  degradation (no regime significantly negative, no catastrophic tail). One
  caveat belongs here: the same lab seeds (0–N ranges of one generator)
  had served as a coarse screen before this A/B and served as the gate
  after it, so they are a development set, not an untouched holdout — no
  seed block was ever reserved for a final, selection-free check.
- **Why paired seeding is valid here:** environment generation is
  independent of the bot's actions — quotes move no underlying and no flow —
  so the same seed replays the identical world under any variant (checked
  directly: the environment stream — spawned contracts, every RFQ/FOK
  draw, daily values — hashes identically across builds). Pairing therefore
  removes the shared world component of the noise; what remains is the
  build×world interaction, and it is not small: the two arms correlate at
  0.88–0.94 across regimes, the paired difference still spreads $15–40 per
  session, and the A/B standard error falls about 3–4× (from $5–14 to
  $1.5–4 per session at 100 pairs) rather than to zero. Two engineering
  footnotes carry the identical-world claim: the RNG streams are isolated by
  design (flow and parameters from a seeded local generator, environment
  dynamics from a per-session reseeded stream, the bot's only internal
  randomness — the MC fallback — from its own derived instance), and
  decoherence has an operational detector: "no-op on the visible set" is
  repeatedly asserted as *bit*-identity, which any stream crossover would
  break. And the lab is only ever a variance tool — it holds a veto, never
  a vote: at least five measured lab-vs-real sign divergences are on record
  in the archived experiments, with platform outcomes taking precedence when
  available. Two fill
  conventions in the lab are assumptions rather than observed platform
  rules — FOK quantity is split floor(q/n) per accepter with the remainder
  left unallocated (about 1% of accepted FOK volume single-bot, 2–6% in
  crowded fields), and the single-bot scripts resolve equal-price RFQ ties
  in this bot's favour (about 0.6% of RFQs). Both arms of every paired run
  see the same conventions; re-running with round-robin remainders and
  independently randomized ties moved this bot's paired P&L by at most
  about $8 on means of $120–280 and changed rank in at most 4 of 40
  sessions per regime (all in the toxic regime). Two further lab
  assumptions deserve the same label. The scripted stub quoter is modelled
  as accepting extreme-priced FOKs (buys at 0.90 or above, sells at 0.10 or
  below); the one logged extreme-priced FOK this bot accepted filled in
  full while the stub quoter ended that session at exactly zero P&L, which
  under an equal split is consistent only with the stub not accepting FOKs
  at all. And the lab's rate process starts every world at the model's
  default target, so after the warm-up the session opens within about one
  point of it and the probability clamps never engage (0.0% of session
  days across 2,400 sessions); the visible sessions opened across a much
  wider band, several of them three to four points from that target. Any
  lab statement about rate-leg estimation — the census above, the
  pooled-slope gate in §7 — was therefore measured in a narrower rate
  regime than the evaluation's. Forcing the session-start rate three and a
  half points above target (a quarter of the days then sit on a clamp)
  raises the rate-leg theo error to ~14.6¢ against ~11.4¢ for company legs
  at a 30-day history, and at that history length the bot's mean P&L falls
  by about $24 (±$13 on each side) with first places dropping from 54 to
  43 of 90; the pooled-slope variant stays within noise of the base build
  in every rate regime tested (session-start rates 0.25–5.5), so the lab
  has no power on that variant anywhere — its real-evaluation margin
  collapse happened at a rate level the lab never sampled and, since the
  per-session rate parameters are unobservable, cannot reconstruct.
- **A harness seam, found after publication and disclosed here.** The
  three single-bot drivers (`harness.py`, `exp_e42_base15.py`,
  `exp_toxicity_flip.py` — and the ablation study, which imports the
  second) announce newly spawned contracts to the bot only at the end of
  the day they were spawned: day-0 contracts are announced before trading,
  every later contract is quoted and traded first and announced afterwards.
  The bot prices, sizes and escrows such a contract exactly as any other
  (the interface hands it the contract object), so the seam is invisible on
  multi-day contracts; but a one-day contract spawned after day 0 expires
  before it is ever announced, and the bot's bookkeeping — settlement
  refund, one-day markout, per-counterparty realized P&L — keys on the
  announced set and silently skips it. Measured on the final build (100
  seeds × 3 regimes): 26% of fills land on contracts not yet announced at
  the moment of the fill and 4.3% on contracts never announced; those and
  only those go unrefunded, so the mirror ends below the harness ledger by
  a one-signed amount — mean $39 calm, $21 mixed, $5 toxic, up to $127,
  never negative. The direction is conservative (an understated mirror
  shrinks budgets and the house-money ramp; the mirror never went negative
  in any session, so the zero-commitment path never fired), and the
  markout and settlement-gate loops were blind to about one in five
  one-day-contract fills. A corrected driver — announce after spawning,
  before trading; RNG order unchanged, environment stream verified
  identical on every seed — closes the gap to 1e-13 and raises the final
  build's lab P&L by +$8.8 ± 2.7 calm, +$9.1 ± 2.7 mixed, +$1.5 ± 1.0 toxic
  per session, so every Line A lab P&L *level* in this document is
  understated by about that much. Because both arms of every paired
  experiment shared the seam, the paired verdicts survive re-running under
  the corrected driver: ramp isolation −0.5 ± 1.5 / +1.8 ± 1.2 / 0.0 ± 0.1
  (was −1.0 / +2.4 / +0.2); toxicity flip −1.9 ± 1.6 and −1.3 ± 1.2 with 0
  bankruptcies and 0 sign flips; the 300-session A/B still flat within
  noise (−1.8 ± 3.1 / −3.1 ± 4.2 / −0.1 ± 1.9), toxic wins 35→37, 0
  bankruptcies in 600; the ablation keeps every cited reading (extraction
  +$34–36 in calm, hatch +$16–33 in degenerate worlds and bit-identical
  elsewhere, dynamic FOK dosing still negative at −$24 ± 7 mixed); the
  display-size-15 pre-screen still passes; the v12/v13 identity holds
  120/120. One verdict does not survive intact: the mid-tier budget floor
  (experiment log, E48) was vetoed by the lab alone on a calm-regime left
  tail of −$15 ± 7 (worst pair −105); under the corrected driver that reads
  −$2 ± 6 (two of twenty pairs still lose $58–66, the −105 pair becomes −8)
  and no regime is significantly negative — its status is *never tested on
  the real evaluation*, not *rejected*. The seam is the same class of
  defect the conservation identity caught in the stress battery below; the
  difference is that the stress script asserted the identity and the
  single-bot drivers did not. Scripts are left as run; the corrected
  driver's only change is the position of one announcement call. The
  corrected driver was afterwards combined with competition-length
  warm-ups (next bullet): the three pooled A/B readings move by less than one
  standard error when the seam is also closed, while individual cells and
  the 20-day flip cell move by more, so the short-history conclusions
  survive the seam correction; the two corrections were not shown to be
  independent in any statistical sense.
- **Warm-up regime of the lab certifications — a post-competition
  correction.** Every paired-seed study above and below in this section
  (the A/B, the ramp isolation and toxicity-flip stress of §5, the E42/E48
  lab gates of §7, the E51 identity check, the "normal" arm of the
  ablation) ran at the harness default of 250-day warm-ups, and the
  tournaments and sniper audit at 300 days; the competition supplies 15–45
  (§4), where estimation noise is 3–4× larger. Only the estimator studies
  of §7 (pooled slopes revisited, empirical-Bayes shrinkage), the
  degenerate arms (3-day) and the fuzz/worst-case batteries were run at
  competition-like lengths. Re-running the A/B (final build vs. the
  mid-campaign 13.8 build, 100 paired seeds × 3 regimes) at every length
  from 15 to 45 days changes the verdict, and the change survives closing
  the harness seam above: under the corrected driver the pooled paired
  mean is −$3.5 ± 1.7 in calm, −$5.3 ± 1.2 in mixed and −$1.0 ± 0.7 in
  toxic (on means of ≈ $240 / $75 / $8; the seamed driver read −$4.1 ± 1.6
  / −$5.0 ± 1.3 / −$0.8 ± 0.6), seven of 21 length×regime cells are
  negative beyond two standard errors and one — 20-day calm, where the
  escape hatch is live — is positive (+$14.5 ± 5.3) under both drivers;
  the final build wins 1,279 of the 2,100 sessions to the mid-campaign
  build's 1,296 and the lower tail is not thicker. So at
  competition-length warm-ups the later Line A additions were a small,
  detectable *cost* in the lab, not a no-op, and not an artefact of the
  seam; the 250-day check could not see it (the 250-day control under the
  corrected driver, −$1.8 ± 3.1 / −$3.1 ± 4.2 / −$0.1 ± 1.9, is the
  corrected 300-session A/B quoted above). What survives at 15–45 days
  under the corrected driver: the final build and its ramp-off variant each
  had 0 bankruptcies in 2,100 sessions (4,200 across those two arms).
  The final build also had 0/2,100 on the same seed grid under the seamed
  driver; these reruns are not additional independent worlds. The mid-campaign
  build lost one corrected-driver 20-day toxic session at capital 10 by one
  cent, −$10.01, versus none of 2,100 under the seamed driver. The ramp's
  cost is −$1.1 ± 0.7 calm / −$1.0 ± 0.5 mixed
  / −$0.05 ± 0.14 toxic (seamed −$0.7 / −$1.2 / −$0.25), no cell beyond
  two standard errors, wins within 10 of 2,100, 7 win→loss and 3 loss→win
  pairs in 2,100 (seamed 3 and 1; none at 250 days; four of the seven are
  ramp-side losses under $2); the toxicity-flip stress at 30 and 20 days
  still shows 0 bankruptcies and 0 win→loss flips (ramp effect +$1.6 ± 1.3
  and −$0.2 ± 1.3 calm→toxic, +$0.3 ± 0.3 and +$2.3 ± 5.5 toxic→calm; the
  worst 20-day pair is +$54 vs +$176, shaved upside rather than a loss);
  the E48 mid-tier budget floor, re-gated at 20/30/45 days (20 seeds,
  client sizes 10/30), shows no regime×size cell beyond two standard
  errors in either direction — heavy tails both ways, worst pair −$112,
  best +$129, 0 bankruptcies in 960 sessions — so its status stays
  *never tested on the real evaluation*; and the audit's tail fixes stay
  bit-identical in 420/420 sessions (seamed driver). The tournament and
  E42 conclusions were not re-run at competition lengths and should be
  read as long-warm-up results. The same lab holding a veto on the real evaluation
  (five sign divergences on record) makes the practical consequence small —
  no adoption rested on the lab alone — but the generalization claim as
  originally written was measured in an easier estimation regime than the
  one the bot was graded in.
- **Self-play clone tournaments** (N independently-imported module
  instances with separate configs): four clones of the then-current build are all
  profitable with zero bankruptcies and no mutual-exploitation loops
  (structural self-consistency); heterogeneous-width line-ups showed a
  **width free-rider pattern** — the tightest book eats the informed flow
  while wide books skim overpaying flow, so in these line-ups a wider book
  did better against a tight crowd. That is an observation over a few
  constellations under the lab's invented flow model, not a demonstrated
  equilibrium or optimal response. The final bot holds the
  visible-set-optimal base width and moves toward a wider book through its
  dynamic widening, i.e. on evidence instead of assumption. Mixed fields (clones plus
  scripted truth-quoting bots, the most realistic head-to-head shape)
  confirmed the ensemble stays self-consistent when flow is split many
  ways — extraction keeps firing, no starvation spirals, zero clone
  bankruptcies across every constellation — while the fixed-width bots,
  which quote true values but manage no capital, go bankrupt in almost
  every crowded session. Survival discipline is exactly what such fields
  select for. *Accounting note:* the tournament scripts score each seat as
  end-of-session cash minus starting capital with contracts still open at
  the close held at their worst-case escrow (the exchange's own ledger
  convention), so every figure above is a conservative lower bound on
  equity — open escrow was roughly 15–60% of fully-settled P&L per seat,
  and larger for tighter books, which trade more. Re-running every
  constellation with open contracts (a) marked to the lab's true-parameter
  model and (b) run to full settlement with no new contracts issued leaves
  each conclusion in this bullet unchanged: every clone seat-session is
  positive under full settlement, the wide > base > tight ordering and the
  wide book's 5/8 wins hold under both accountings, the tight rival in the
  mixed field stays a statistical tie (its point estimate moves from about
  −$3 to +$5 against the base build on a ±$26 standard error), and
  bankruptcy — negative cash at a day close — does not depend on
  end-of-session valuation at all.
- **Final-build ablation:**
  the final Line A build (all pillars present, before the audit's
  behaviour-identical tail fixes) minus each mechanism, one at a time — 20 paired seeds × 3 flow
  regimes × 2 warm-up lengths (250-day and 3-day) in the reseeded lab, with a built-in canary
  (the hatch arm must be bit-identical under normal warm-ups, and is).
  Clean confirmations: the escape hatch is worth +$16-31 paired in
  degenerate-warm-up worlds and exactly zero elsewhere; the extraction
  engine is the largest single component in benign regimes (+$28-44). In contrast,
  the dynamic FOK dose
  *costs* money under the lab's diffuse-sharp flow model (−$28 ± 10 in
  mixed regimes) while being the pillar that flipped the real evaluation's
  grinder session from −27 to the field's first place. The size of that
  number is conditional on the lab's FOK share convention and on the stub
  quoter accepting FOKs, neither of which the platform states: re-running
  the same arm on 30 fresh seeds gives −$22 ± 8 under the floor split,
  −$13 ± 10 with a round-robin remainder, −$19 ± 11 with a single random
  winner, and −$5 ± 9 if the stub quoter accepts no FOKs (mixed regime,
  250-day warm-up). The sign is what survives — negative in 27 of 30
  rule × regime × warm-up cells and in every rate regime tested — so the
  divergence is about informed-flow concentration, not the share rule. The lab and
  the real evaluation disagree about how concentrated informed flow is —
  which is exactly why every adoption decision was gated on the real
  evaluation, with the lab holding only a veto.
- **Adversarial audit** (feed-then-snipe simulation with a
  perfect-information attacker): quantified the two real holes —
  observation lag (markout defenses learn a day late) and unbounded first
  commitment. Also produced a counter-intuitive negative result: "feeding"
  the defenses to buy innocence *hurts* the attacker, because the feed
  builds the markout history that arms the profile earlier. The settlement
  gate (§6.4) closed most of the lag hole; the commitment cap stayed
  archived (§7).
- **Code and boundary-condition audit** (reproducibility and platform-input
  checks for each candidate finding): five confirmed findings
  converged on two real tail defects — the min-one-lot distress commitment
  above, and a stale FOK fingerprint that could misroute a later RFQ fill
  into the wrong markout channel — plus a wrong-side distress quote
  (position-pinned extreme bids kept buying at 0.02 after fair value
  decayed below it). All fixed; two other candidate findings were refuted
  on reproduction. The fixes close the identified boundary defects under
  the request-scoped fill assumptions in §5.
- **Invariant fuzzing:** 8 seeds × 2500 randomized operations — degenerate
  warm-ups (2/5/60/300 days), exotic three-leg contracts, negative strikes,
  interleaved quote/FOK/trade/advance in adversarial orders, capitals
  10–200. Three invariants: every quote constructible under the grader's
  validators; the conservation identity (§5) within 1e-6; zero swallowed
  exceptions. Mechanism *interactions* get machine-checked, not just units
  (37 unit tests cover those). The identity earned its keep in both
  directions: it once flagged a $2 discrepancy that turned out to be a
  settlement-timing seam in the *test harness itself* — the bot's books
  were exact. The identity was asserted only in the fuzzer and the stress
  battery; the single-bot session drivers never asserted it, which is how
  the larger announcement-timing seam disclosed above went unnoticed until
  after publication.
- **In-vivo decision audit:** every logged decision in the diagnostic
  sessions re-derived line by line against the final build — quote prices (tier,
  inventory skew, penny rounding), sizes (budget arithmetic to the lot),
  every FOK accept/reject against the vol-scaled floor — zero deviations
  from design intent. Score-based testing cannot see "legal-but-wrong"
  behavior; a line-by-line trace audit can.
- **Structured worst-case battery** (beyond the fuzzer's random walks):
  parameter boundaries (no reversion, probabilities at the clamp edge,
  frozen rates, zero correlation, extreme drift and vol), capitals 1–500,
  2-day warm-ups, 100-day sessions, 50-option-per-day floods — 39
  sessions, zero crashes, zero bankruptcies, conservation intact, and the
  exception fallback does not activate: degenerate inputs are handled before
  they can raise.
- **Timeout headroom, measured:** warm-up 0.6ms; 0.14ms per quote; a
  hypothetical 100-day session flooded with 200 live contracts costs ≈5
  seconds end to end. The only slow path — the Monte Carlo fallback at
  52ms cold — is memoized to 0.1ms.
- **Operational hygiene, learned the expensive way:** the scored channel is
  parsed from stdout, so a single stray print can corrupt scored output.
  The archived final prototype has zero prints and a debug flag that is
  permanently off; its release checks included a mechanical search.

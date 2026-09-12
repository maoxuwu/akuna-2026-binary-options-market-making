# Round-2 playbook — pre-computed responses to the three unknowns

Archive scope: this is a contingency memo for the supplementary selective-quoting
prototype, not the submitted V47 strategy or a plan that was executed.
See [supplementary research](supplementary_research.md) for its current context.

> Publication note: reproduced as written before results were known, with private-archive file references annotated in parentheses.
> Internal build numbers (v11 etc.) are Line A snapshots current at the
> time of writing; v11 ≈ the near-final Line A build.

Three things are unknowable before results come out (accepted as such: the
organizers cannot fairly answer them privately): whether hidden test cases
run after submission, how many advance and on what tiebreak, and the
mechanics of the head-to-head round. This file pre-computes the response to
each way the information could resolve, so that no decision has to be
invented under time pressure. Every flip listed here still requires re-running
whatever gates the new evidence regime supports.

| If it turns out that… | Then… | Evidence / archive |
|---|---|---|
| Round 2 = shared client flow, mixed field of top bots + house bots (the most natural reading) | Ship v11 unchanged. | Mixed-tournament study: the ensemble is self-consistent in every clone+bot constellation (extraction survives flow-splitting, zero clone bankruptcies in 64 seat-sessions); truth-quoting fixed-width bots go bankrupt in 7–8 of 8 crowded sessions — survival discipline is what such fields select for. |
| Opponents can hit our quotes / send us FOKs directly (true MM-vs-MM) | Enable the archived FOK commitment caps (new counterparty 0.10 × available, known 0.30) — if code changes are allowed at that stage. | `solution_exp_e35_rejected.py` (private archive, not published — see docs/experiment_log.md, E35). Caps cut a perfect-information sniper's extraction $29 → $9. They were rejected in round 1 only because counterparties there are *clients* whose large early FOKs fund three sessions; that argument dies when counterparties become adversaries. |
| The evaluation is re-seeded (not the fixed 16 sessions) | Two archived estimator upgrades flip from rejected to attractive: pooled tilt slopes, and extending the online-re-estimation hatch to mid-length (21–59 day) warm-ups. | `solution_exp_e34_rejected.py`, `solution_exp_e50.py` (private archive, not published — see docs/experiment_log.md, E34 and E50). Both were vetoed *against a fixed realization* (E34 collapsed one thin margin; E50 earned +$35 total P&L but reshuffled one first place away). In expectation over fresh seeds both dominate — the cleanest examples of decisions that invert with the evaluation regime. |
| Round 2 features direct MM-vs-MM order flow AND sniping bursts | Besides the commit caps, a per-counterparty daily FOK-acceptance count cap (allow 1–2, block bursts) is a cheap complement — the settlement gate already trips after ~1 settled loss, the count cap closes the same-day burst window it can't see. | Design note only (never needed against client-only flow; single large FOKs — the real income — have count 1 and pass untouched). |
| Capital is much larger than 40 | Nothing to do — already scale-invariant. | Realized-settlement gate scales ×max(1, capital/40) (verified bit-identical below 40); all budgets are fractions of the mirror; the only absolute constants (display sizes 10/500) were measured neutral-to-harmful to raise at current scales. |
| Flow turns adversarial mid-session (regime flips, earned innocence exploited) | Nothing to do — the dynamic stack self-arms. | Toxicity-flip stress: 60 paired sessions, identities persisting while intent re-rolls against a fully engaged ramp — zero bankruptcies, zero win→loss flips. |
| Standings are visible between rounds and PnL is the tiebreak | No pre-approved aggression flips exist. | Every same-score PnL-thickening candidate was measured: display size (rejected, thins a knife-edge), mid-tier budget floor (rejected at the paired gate, calm-world left tail), global budget raises (rejected, knife-edge bleed). The thickening that survived the gates is already in v11. |

Standing rule: nothing on this list is a promise to act — each row is a
*hypothesis → response* pair, and the response still passes through
whatever verification the moment allows before it ships.

> Post-hoc note (added after the results, September 2026; the table above
> is unchanged). The re-seeded row says both archived estimator variants
> "dominate in expectation over fresh seeds". That was a conjecture when
> written, and the actual reseeded evidence is thinner than the sentence:
>
> - Pooled tilt slopes (E34): the only reseeded measurement is the paired
>   lab gate of the E34 revisit (12 seeds × 3 regimes × 5 warm-up lengths
>   15–45 days, 180 pairs): +$1.8 ± 1.7 per session — about one standard
>   error — with the gain concentrated in 15–20-day warm-ups and the
>   25–45-day bands flat. Re-run at 40 seeds (600 pairs) after the results:
>   +$2.0 ± 1.0, one warm-up band negative, zero new bankruptcies. A small
>   positive lab mean, not a demonstrated dominance. The next variant of the
>   same family (E52) passed the lab decisively and lost 1.4 points on the
>   real evaluation.
> - Mid-length hatch (E50): no reseeded run of the wider threshold existed
>   during the campaign or in the archive; "+$35" is the visible-set total.
>   A paired lab run made after the results (final Line A build with only
>   the threshold changed, 40 seeds × 3 regimes × warm-ups 25–55 days, 720
>   pairs, zero new bankruptcies) is directionally supportive: +$8.0 ± 1.4
>   per 40-day session, +$1.9 ± 0.7 per 20-day session, positive in every
>   flow regime, not in every warm-up band.
>
> Both figures come from the lab whose flow model is invented and which,
> per writeup [§8](validation_methodology.md), holds a veto and never a vote. The rows remain hypotheses;
> nothing in the results (writeup [§14](results_and_postmortem.md)) tests them either way.
>
> The "ship v11 unchanged" row rests on the mixed-tournament study (writeup [§8](validation_methodology.md)): a lab study under the same invented flow model, reported there with
> its caveats.

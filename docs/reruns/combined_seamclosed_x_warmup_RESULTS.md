# Combined correction: announce-first driver × competition-length warm-ups

Builds: v3 = `solution_best_138_v3.py` (mid-campaign 13.8 build, sha256 d98a2408ccc9…), v13 = `solution.py` = `solution_best_138_v13.py` (final build, sha256 b0559c0847…), v13nr = v13 with `size_ramp_mult=0`. Driver: `seam/harness_patched.py` (announce-first; sha256 14b295a7…) and the `_patched` flip/E42 drivers. Python 3.11 via uv. 100 seeds × 3 regimes × 8 warm-ups × 3 arms = 7,200 sessions (6,300 at 15–45, 900 at 250); per arm 2,400 (2,100 + 300).

'orig' = ORIGINAL (seamed) driver from warmup_recheck/results_n100.json; 'comb' = announce-first driver (this run). Paired deltas by seed within a warm-up length.

## ab: v13 − v3

| wu | regime | comb Δ ± SE | orig Δ ± SE | comb wins A/B | comb bk | comb W→L | identical |
|---|---|---|---|---|---|---|---|
| 15 | calm_dumb | +0.54 ± 6.13 | -2.96 ± 5.96 | 84/89 | 0/0 | 1 | 0 |
| 15 | mixed | -1.60 ± 3.47 | -3.57 ± 3.74 | 57/57 | 0/0 | 8 | 0 |
| 15 | toxic | -2.15 ± 1.85 | -0.92 ± 1.75 | 30/31 | 0/0 | 8 | 0 |
| 20 | calm_dumb | +14.50 ± 5.26 ** | +14.40 ± 4.67 | 91/82 | 0/0 | 0 | 0 |
| 20 | mixed | +5.07 ± 4.05 | +4.36 ± 4.13 | 67/62 | 0/0 | 3 | 0 |
| 20 | toxic | +1.64 ± 2.41 | +0.98 ± 2.20 | 37/35 | 0/1 | 11 | 0 |
| 25 | calm_dumb | -7.07 ± 3.02 ** | -10.28 ± 3.15 | 83/84 | 0/0 | 1 | 0 |
| 25 | mixed | -10.90 ± 3.45 ** | -9.26 ± 3.56 | 58/63 | 0/0 | 2 | 0 |
| 25 | toxic | -1.70 ± 1.73 | -3.06 ± 1.83 | 30/29 | 0/0 | 6 | 4 |
| 30 | calm_dumb | -8.11 ± 3.36 ** | -7.66 ± 3.25 | 84/86 | 0/0 | 0 | 0 |
| 30 | mixed | -3.88 ± 2.36 | -1.08 ± 2.39 | 65/65 | 0/0 | 3 | 1 |
| 30 | toxic | -1.53 ± 1.66 | -1.57 ± 1.55 | 28/30 | 0/0 | 8 | 5 |
| 35 | calm_dumb | -5.48 ± 4.19 | -9.35 ± 4.23 | 90/92 | 0/0 | 0 | 0 |
| 35 | mixed | -3.07 ± 2.69 | -3.98 ± 2.26 | 70/70 | 0/0 | 6 | 0 |
| 35 | toxic | -1.26 ± 0.96 | -1.99 ± 1.10 | 29/30 | 0/0 | 4 | 4 |
| 40 | calm_dumb | -6.94 ± 2.96 ** | -4.07 ± 3.19 | 91/91 | 0/0 | 0 | 0 |
| 40 | mixed | -6.08 ± 2.69 ** | -7.42 ± 2.58 | 69/70 | 0/0 | 5 | 0 |
| 40 | toxic | -0.91 ± 1.76 | +0.06 ± 1.64 | 27/30 | 0/0 | 10 | 5 |
| 45 | calm_dumb | -11.72 ± 4.45 ** | -8.99 ± 4.28 | 86/86 | 0/0 | 1 | 0 |
| 45 | mixed | -16.71 ± 3.38 ** | -14.16 ± 3.77 | 70/77 | 0/0 | 9 | 0 |
| 45 | toxic | -1.40 ± 1.56 | +0.87 ± 1.60 | 33/37 | 0/0 | 4 | 3 |
| 250 | calm_dumb | -1.82 ± 3.07 | -3.06 ± 3.46 | 96/95 | 0/0 | 0 | 0 |
| 250 | mixed | -3.10 ± 4.16 | -3.49 ± 4.25 | 83/80 | 0/0 | 1 | 1 |
| 250 | toxic | -0.08 ± 1.92 | +0.12 ± 1.55 | 37/35 | 0/0 | 4 | 6 |

| pooled | regime | comb Δ ± SE (n) | orig Δ ± SE | comb wins A/B | comb bk | comb W→L |
|---|---|---|---|---|---|---|
| 15-45 | calm_dumb | -3.47 ± 1.66 (n=700) | -4.13 ± 1.61 | 609/610 | 0/0 | 3 |
| 15-45 | mixed | -5.31 ± 1.23 (n=700) | -5.01 ± 1.25 | 456/464 | 0/0 | 36 |
| 15-45 | toxic | -1.04 ± 0.66 (n=700) | -0.81 ± 0.64 | 214/222 | 0/1 | 51 |
| 250 | calm_dumb | -1.82 ± 3.07 (n=100) | -3.06 ± 3.46 | 96/95 | 0/0 | 0 |
| 250 | mixed | -3.10 ± 4.16 (n=100) | -3.49 ± 4.25 | 83/80 | 0/0 | 1 |
| 250 | toxic | -0.08 ± 1.92 (n=100) | +0.12 ± 1.55 | 37/35 | 0/0 | 4 |

Cells beyond ±2 SE at 15–45 (comb): ['20|calm_dumb', '25|calm_dumb', '25|mixed', '30|calm_dumb', '40|calm_dumb', '40|mixed', '45|calm_dumb', '45|mixed']

## ramp: v13 − v13nr

| wu | regime | comb Δ ± SE | orig Δ ± SE | comb wins A/B | comb bk | comb W→L | identical |
|---|---|---|---|---|---|---|---|
| 15 | calm_dumb | -0.43 ± 2.06 | -1.57 ± 2.38 | 84/85 | 0/0 | 0 | 23 |
| 15 | mixed | +0.20 ± 0.87 | -0.09 ± 0.86 | 57/59 | 0/0 | 1 | 40 |
| 15 | toxic | -0.29 ± 0.41 | -0.19 ± 0.22 | 30/31 | 0/0 | 2 | 78 |
| 20 | calm_dumb | -2.71 ± 1.71 | -2.88 ± 2.24 | 91/90 | 0/0 | 0 | 22 |
| 20 | mixed | -0.23 ± 1.14 | -2.09 ± 1.17 | 67/65 | 0/0 | 0 | 38 |
| 20 | toxic | +0.88 ± 0.65 | -0.12 ± 0.17 | 37/38 | 0/0 | 0 | 76 |
| 25 | calm_dumb | +0.98 ± 1.31 | +0.09 ± 1.54 | 83/84 | 0/0 | 0 | 27 |
| 25 | mixed | -1.18 ± 1.50 | -0.03 ± 0.83 | 58/61 | 0/0 | 0 | 43 |
| 25 | toxic | +0.29 ± 0.21 | -0.22 ± 0.32 | 30/29 | 0/0 | 0 | 81 |
| 30 | calm_dumb | +0.17 ± 1.52 | -0.10 ± 1.67 | 84/85 | 0/0 | 0 | 18 |
| 30 | mixed | -1.37 ± 0.86 | -0.55 ± 0.49 | 65/65 | 0/0 | 1 | 38 |
| 30 | toxic | -0.35 ± 0.24 | -0.27 ± 0.23 | 28/29 | 0/0 | 0 | 79 |
| 35 | calm_dumb | -0.86 ± 1.32 | -1.57 ± 1.41 | 90/90 | 0/0 | 0 | 19 |
| 35 | mixed | -1.28 ± 1.55 | -2.20 ± 1.61 | 70/70 | 0/0 | 0 | 39 |
| 35 | toxic | -0.19 ± 0.21 | -0.38 ± 0.56 | 29/29 | 0/0 | 0 | 88 |
| 40 | calm_dumb | -2.60 ± 1.59 | +0.18 ± 1.58 | 91/91 | 0/0 | 0 | 21 |
| 40 | mixed | -0.86 ± 1.22 | -1.42 ± 1.52 | 69/69 | 0/0 | 0 | 34 |
| 40 | toxic | -0.16 ± 0.14 | -0.04 ± 0.09 | 27/27 | 0/0 | 0 | 78 |
| 45 | calm_dumb | -2.55 ± 2.85 | +1.12 ± 2.70 | 86/87 | 0/0 | 0 | 22 |
| 45 | mixed | -2.08 ± 1.05 | -2.26 ± 0.90 | 70/71 | 0/0 | 2 | 38 |
| 45 | toxic | -0.50 ± 0.44 | -0.50 ± 0.44 | 33/34 | 0/0 | 1 | 81 |
| 250 | calm_dumb | -0.39 ± 1.28 | -1.75 ± 1.82 | 96/96 | 0/0 | 0 | 20 |
| 250 | mixed | +1.33 ± 0.93 | +2.86 ± 1.99 | 83/83 | 0/0 | 0 | 26 |
| 250 | toxic | -0.09 ± 0.38 | -0.15 ± 0.16 | 37/37 | 0/0 | 0 | 79 |

| pooled | regime | comb Δ ± SE (n) | orig Δ ± SE | comb wins A/B | comb bk | comb W→L |
|---|---|---|---|---|---|---|
| 15-45 | calm_dumb | -1.14 ± 0.69 (n=700) | -0.68 ± 0.75 | 609/612 | 0/0 | 0 |
| 15-45 | mixed | -0.97 ± 0.45 (n=700) | -1.23 ± 0.42 | 456/460 | 0/0 | 4 |
| 15-45 | toxic | -0.05 ± 0.14 (n=700) | -0.25 ± 0.12 | 214/217 | 0/0 | 3 |
| 250 | calm_dumb | -0.39 ± 1.28 (n=100) | -1.75 ± 1.82 | 96/96 | 0/0 | 0 |
| 250 | mixed | +1.33 ± 0.93 (n=100) | +2.86 ± 1.99 | 83/83 | 0/0 | 0 |
| 250 | toxic | -0.09 ± 0.38 (n=100) | -0.15 ± 0.16 | 37/37 | 0/0 | 0 |

Cells beyond ±2 SE at 15–45 (comb): []

## Bankruptcies per arm (comb)

{'v3': {'total': 1, 'n': 2400, 'short': 1}, 'v13': {'total': 0, 'n': 2400, 'short': 0}, 'v13nr': {'total': 0, 'n': 2400, 'short': 0}}

## E48 gate (cp_mid_budget_floor 0.3 − off), announce-first driver, 20 seeds

| wu | regime | qty | Δ ± SE | min | max | bk off/on |
|---|---|---|---|---|---|---|
| 250 | calm_dumb | 10 | -0.46 ± 0.64 | -9.12 | +6.02 | 0/0 |
| 250 | calm_dumb | 30 | -2.26 ± 5.58 | -66.08 | +61.59 | 0/0 |
| 250 | mixed | 10 | +0.10 ± 4.27 | -52.09 | +60.65 | 0/0 |
| 250 | mixed | 30 | +3.73 ± 4.51 | -47.41 | +48.01 | 0/0 |
| 250 | toxic | 10 | -0.53 ± 1.86 | -31.36 | +13.78 | 0/0 |
| 250 | toxic | 30 | +1.81 ± 1.58 | -21.55 | +15.38 | 0/0 |
| 20 | calm_dumb | 10 | -5.33 ± 5.92 | -111.98 | +30.38 | 0/0 |
| 20 | calm_dumb | 30 | +8.69 ± 7.53 | -48.41 | +129.14 | 0/0 |
| 20 | mixed | 10 | +3.51 ± 3.69 | -30.38 | +57.29 | 0/0 |
| 20 | mixed | 30 | -3.31 ± 5.24 | -61.42 | +57.01 | 0/0 |
| 20 | toxic | 10 | -0.79 ± 2.54 | -41.52 | +25.32 | 0/0 |
| 20 | toxic | 30 | +0.03 ± 0.97 | -6.46 | +13.56 | 0/0 |
| 30 | calm_dumb | 10 | -6.81 ± 4.24 | -73.21 | +5.22 | 0/0 |
| 30 | calm_dumb | 30 | -0.24 ± 2.18 | -37.58 | +11.86 | 0/0 |
| 30 | mixed | 10 | -4.29 ± 2.82 | -35.26 | +10.50 | 0/0 |
| 30 | mixed | 30 | +6.44 ± 4.71 | -18.49 | +84.09 | 0/0 |
| 30 | toxic | 10 | +0.60 ± 0.93 | -7.15 | +11.01 | 0/0 |
| 30 | toxic | 30 | -2.18 ± 3.11 | -34.93 | +42.49 | 0/0 |
| 45 | calm_dumb | 10 | -1.25 ± 0.78 | -14.04 | +0.49 | 0/0 |
| 45 | calm_dumb | 30 | +6.55 ± 4.99 | -23.67 | +93.12 | 0/0 |
| 45 | mixed | 10 | +0.62 ± 3.40 | -29.71 | +37.78 | 0/0 |
| 45 | mixed | 30 | +3.99 ± 4.55 | -33.54 | +52.78 | 0/0 |
| 45 | toxic | 10 | -2.82 ± 2.51 | -48.45 | +5.58 | 0/0 |
| 45 | toxic | 30 | -1.63 ± 2.21 | -28.19 | +25.16 | 0/0 |

## Toxicity flip (ramp − no ramp), announce-first driver, 30 seeds

| wu | direction | Δ final ± SE | min | max | Δ post-flip ± SE | bk on/off | losing on/off | win→loss |
|---|---|---|---|---|---|---|---|---|
| 250 | calm->toxic | -1.94 ± 1.60 | -32.65 | +17.27 | -0.73 ± 1.17 | 0/0 | 0/0 | 0 |
| 250 | toxic->calm | -1.31 ± 1.20 | -32.69 | +8.22 | -1.33 ± 1.20 | 0/0 | 0/0 | 0 |
| 30 | calm->toxic | +1.56 ± 1.28 | -13.47 | +31.24 | +2.48 ± 1.68 | 0/0 | 1/1 | 0 |
| 30 | toxic->calm | +0.32 ± 0.27 | -4.48 | +5.10 | +0.32 ± 0.27 | 0/0 | 1/1 | 0 |
| 20 | calm->toxic | -0.19 ± 1.33 | -25.11 | +18.19 | +0.48 ± 0.83 | 0/0 | 0/0 | 0 |
| 20 | toxic->calm | +2.33 ± 5.51 | -121.27 | +66.01 | +2.65 ± 5.17 | 0/0 | 2/2 | 0 |

## Verdicts (combined = announce-first driver × 15–45-day warm-ups; 'seamed' = original driver, warmup_recheck)

1. **A/B final (v13) vs mid-campaign 13.8 (v3) — PERSISTS.** Pooled 15–45: calm −3.47 ± 1.66 (seamed −4.13 ± 1.61), mixed −5.31 ± 1.23 (−5.01 ± 1.25), toxic −1.04 ± 0.66 (−0.81 ± 0.64). Each pooled regime reading moves by < 1 SE when the seam is closed (individual cells move by more). Cells beyond ±2 SE: 8/21 under both drivers — 7 negative + 20-day calm positive (+14.5 ± 5.3 combined, +14.4 ± 4.7 seamed); the negative set swaps 35-calm (seamed) for 40-calm (combined). Wins at 15–45: v13 1,279 vs v3 1,296 (seamed 1,261 vs 1,284). Bankruptcies at 15–45: v13 0/2,100; v3 1/2,100 (20-day toxic, seed 31, capital 10, P&L −$10.01, i.e. cash −$0.01; the same session read −$9.98 under the seamed driver and v13 read −$9.94 — a one-cent crossing; no per-event trace was kept, so whether it is a new failure mode is not established). 250 control: −1.82 ± 3.07 / −3.10 ± 4.16 / −0.08 ± 1.92 — identical to the corrected 300-session A/B already in writeup [§8](../validation_methodology.md) (−1.8 ± 3.1 / −3.1 ± 4.2 / −0.1 ± 1.9). The degradation at competition lengths is not an artefact of the seam.

2. **Ramp isolation (v13 vs v13 with size_ramp_mult=0) — PERSISTS in substance, toxic drag WEAKENS to zero.** Pooled 15–45: calm −1.14 ± 0.69 (seamed −0.68 ± 0.75), mixed −0.97 ± 0.45 (−1.23 ± 0.42), toxic −0.05 ± 0.14 (−0.25 ± 0.12). No cell beyond ±2 SE (seamed had one: 45-mixed −2.26 ± 0.90). Wins 1,279 vs 1,289 (seamed 1,261 vs 1,272). Win→loss pairs in 2,100: 7 (seamed 3), loss→win 3 (seamed 1); four of the seven are ramp-on losses under $2 (−0.11/−0.40/−1.65/−1.82 vs no-ramp +0.04/+13.4/+14.3/+56.2), the other three −3.68 vs +1.45, −3.94 vs +36.4, −14.04 vs +29.53 (this last pair is bit-identical to the seamed run). Losing toxic sessions identical to no-ramp: 376/400 (seamed 383/405). 250 control: −0.39 ± 1.28 / +1.33 ± 0.93 / −0.09 ± 0.38, 0 flips. 0 bankruptcies in both arms (4,200 at 15–45).

3. **E48 mid-tier budget floor gate — no competition-length reading was on record; combined result is INCONCLUSIVE both ways.** 250 (corrected driver) reproduces the writeup's −2 ± 6 calm/qty30 (§8) (−2.26 ± 5.58, worst −66). At 20/30/45 days no regime×client-size cell is beyond ±2 SE in either direction: most negative 30-calm/qty10 −6.81 ± 4.24 and 20-calm/qty10 −5.33 ± 5.92 (worst pairs −73, −112); most positive 20-calm/qty30 +8.69 ± 7.53, 45-calm/qty30 +6.55 ± 4.99, 30-mixed/qty30 +6.44 ± 4.71 (best pairs +129, +93, +84). 0 bankruptcies in 960 sessions. Status 'never tested on the real evaluation, not rejected' stands; the calm left tail is still there at short warm-ups but is matched by a right tail.

4. **Toxicity flip at 30 and 20 days — PERSISTS (0/0).** 0 bankruptcies and 0 win→loss flips in every cell. 30 days: calm→toxic +1.56 ± 1.28 (seamed −0.24 ± 1.01), toxic→calm +0.32 ± 0.27 (−0.35 ± 0.52). 20 days: calm→toxic −0.19 ± 1.33 (seamed −5.58 ± 5.03), toxic→calm +2.33 ± 5.51 (+0.36 ± 2.73; worst pair seed 15 cap 10: +54.47 ramp vs +175.74 no-ramp — shaved upside, both sides positive). 250: −1.94 ± 1.60 / −1.31 ± 1.20, reproducing writeup [§8](../validation_methodology.md)'s corrected −1.9 ± 1.6 / −1.3 ± 1.2 to the decimal. Losing sessions ramp/no-ramp: 1/1, 1/1, 0/0, 2/2 — never differ.

## Session-count reconciliation

- Recheck grid: 3 arms (v3, v13, v13nr) × 8 warm-ups × 3 regimes × 100 seeds = **7,200 sessions** (2,400 per arm). At 15–45: 7 × 300 × 3 = **6,300** (2,100 per arm). At 250: **900** (300 per arm).
- Per *pair* (A/B = v13 vs v3; ramp = v13 vs v13nr, v13 arm shared): 2 arms × 2,400 = **4,800 sessions = 2,400 paired deltas**, of which 2,100 pairs at 15–45 and 300 at 250. The experiment-log phrase "7,200 sessions per pair" is wrong; 7,200 is the whole three-arm grid. writeup [§13](../results_and_postmortem.md)'s "7,200 at 15–45-day warm-ups" is wrong; it is 6,300 at 15–45 (plus 900 at 250). writeup [§8](../validation_methodology.md)'s "0 bankruptcies in 7,200 sessions across three builds" mixes both lengths and, under the corrected driver, becomes 1 (mid-campaign build) — the final build is 0 in 4,800 (0 in 4,200 at 15–45).
- This run additionally: E48 gate 4 warm-ups × 3 regimes × 2 sizes × 20 seeds × 2 arms = 960 sessions; flip 3 warm-ups × 2 directions × 30 seeds × 2 arms = 360 (240 at 30/20 days). Grand total 8,520 sessions; wall ≈ 93 s (recheck, 3 parallel children) + ~100 s (E48) + 17 s (flip). Full 100-seed grid ran; no seed reduction was needed.
- Original-driver (seamed) comparison values are the earlier agent's warmup_recheck/results_n100.json, same seeds, same builds (v3 sha256 d98a2408…, v13 sha256 b0559c08…), same capital draw.

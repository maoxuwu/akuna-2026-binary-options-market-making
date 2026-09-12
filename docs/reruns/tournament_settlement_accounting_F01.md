# Tournament settlement-accounting re-check (F01)

Seat P&L under three accountings computed from ONE run per seed: `reported` = end-of-day-40 cash − capital with open contracts at worst-case escrow (the original scripts' figure); `marked` = reported + mark-to-model value of open contracts (lab true-parameter model); `settled` = extend the session with no new issuance and no flow until every contract expires (fully realized). Mode `cap` = alternative correction that caps new-contract expiry at days-left so nothing is open at day 40 (changes the flow RNG stream from day 33 on, so it is NOT paired with the other modes). 8 seeds per line-up. Columns: mean ± SE, worst seed, wins (seat with the highest figure among seats in that seed), mean open contracts / open escrow at day 40, bankruptcies at day 40 / after settlement.

## MX2_base+tight+SQ+FW10 — build `solution_v11.py` — mode `cap` — seeds 8 — settle-through days [0, 0, 0, 0, 0, 0, 0, 0]

| seat | reported | marked | settled | open n / escrow | bankrupt d40/final |
|---|---|---|---|---|---|
| base | 102.50 ± 26.44 (min 13.68, wins 5/8) | 102.50 ± 26.44 (min 13.68, wins 5/8) | 102.50 ± 26.44 (min 13.68, wins 5/8) | 0.0 / 0.00 | 0/0 |
| tight | 108.00 ± 30.47 (min -2.11, wins 3/8) | 108.00 ± 30.47 (min -2.11, wins 3/8) | 108.00 ± 30.47 (min -2.11, wins 3/8) | 0.0 / 0.00 | 0/0 |
| SQ | 19.98 ± 14.28 (min -16.63, wins 0/8) | 19.98 ± 14.28 (min -16.63, wins 0/8) | 19.98 ± 14.28 (min -16.63, wins 0/8) | 0.0 / 0.00 | 0/0 |
| FW0.10 | 6.60 ± 9.10 (min -49.72, wins 0/8) | 6.60 ± 9.10 (min -49.72, wins 0/8) | 6.60 ± 9.10 (min -49.72, wins 0/8) | 0.0 / 0.00 | 8/8 |

## MX3_4clones+FW25+SQ — build `solution_v11.py` — mode `cap` — seeds 8 — settle-through days [0, 0, 0, 0, 0, 0, 0, 0]

| seat | reported | marked | settled | open n / escrow | bankrupt d40/final |
|---|---|---|---|---|---|
| clone_a | 43.44 ± 16.70 (min -2.01, wins 2/8) | 43.44 ± 16.70 (min -2.01, wins 2/8) | 43.44 ± 16.70 (min -2.01, wins 2/8) | 0.0 / 0.00 | 0/0 |
| clone_b | 37.52 ± 8.12 (min 0.79, wins 1/8) | 37.52 ± 8.12 (min 0.79, wins 1/8) | 37.52 ± 8.12 (min 0.79, wins 1/8) | 0.0 / 0.00 | 0/0 |
| clone_c | 42.92 ± 7.10 (min 4.20, wins 1/8) | 42.92 ± 7.10 (min 4.20, wins 1/8) | 42.92 ± 7.10 (min 4.20, wins 1/8) | 0.0 / 0.00 | 0/0 |
| clone_d | 53.11 ± 11.40 (min 15.95, wins 2/8) | 53.11 ± 11.40 (min 15.95, wins 2/8) | 53.11 ± 11.40 (min 15.95, wins 2/8) | 0.0 / 0.00 | 0/0 |
| FW0.25 | 26.80 ± 26.84 (min -36.68, wins 1/8) | 26.80 ± 26.84 (min -36.68, wins 1/8) | 26.80 ± 26.84 (min -36.68, wins 1/8) | 0.0 / 0.00 | 7/7 |
| SQ | 7.32 ± 9.68 (min -16.67, wins 1/8) | 7.32 ± 9.68 (min -16.67, wins 1/8) | 7.32 ± 9.68 (min -16.67, wins 1/8) | 0.0 / 0.00 | 0/0 |

## MX1_2clones+SQ+FW10+FW05 — build `solution_v11.py` — mode `extend` — seeds 8 — settle-through days [7, 6, 7, 5, 5, 5, 7, 6]

| seat | reported | marked | settled | open n / escrow | bankrupt d40/final |
|---|---|---|---|---|---|
| clone_a | 89.74 ± 23.63 (min 11.32, wins 5/8) | 105.49 ± 25.60 (min 11.45, wins 5/8) | 104.12 ± 25.46 (min 11.32, wins 5/8) | 4.0 / 12.94 | 0/0 |
| clone_b | 88.69 ± 26.12 (min 9.13, wins 3/8) | 104.49 ± 29.28 (min 19.61, wins 3/8) | 102.06 ± 28.94 (min 16.13, wins 3/8) | 4.1 / 11.71 | 0/0 |
| SQ | 16.58 ± 5.18 (min -5.67, wins 0/8) | 18.35 ± 5.39 (min -5.67, wins 0/8) | 17.45 ± 5.00 (min -5.67, wins 0/8) | 3.1 / 0.76 | 0/0 |
| FW0.10 | 4.10 ± 7.09 (min -25.48, wins 0/8) | 4.10 ± 7.09 (min -25.48, wins 0/8) | 4.10 ± 7.09 (min -25.48, wins 0/8) | 0.0 / 0.00 | 8/8 |
| FW0.05 | -4.95 ± 5.55 (min -39.88, wins 0/8) | -4.95 ± 5.55 (min -39.88, wins 0/8) | -4.95 ± 5.55 (min -39.88, wins 0/8) | 0.0 / 0.00 | 8/8 |

## MX2_base+tight+SQ+FW10 — build `solution_v11.py` — mode `extend` — seeds 8 — settle-through days [5, 6, 6, 6, 6, 5, 5, 6]

| seat | reported | marked | settled | open n / escrow | bankrupt d40/final |
|---|---|---|---|---|---|
| base | 74.19 ± 23.36 (min -0.19, wins 3/8) | 103.47 ± 25.20 (min 13.21, wins 4/8) | 103.69 ± 25.90 (min 12.81, wins 4/8) | 4.5 / 21.13 | 0/0 |
| tight | 71.26 ± 23.80 (min -8.87, wins 3/8) | 108.32 ± 28.58 (min 1.47, wins 4/8) | 108.64 ± 28.88 (min 3.82, wins 4/8) | 4.9 / 27.60 | 0/0 |
| SQ | 14.95 ± 10.30 (min -10.77, wins 0/8) | 16.09 ± 10.02 (min -8.52, wins 0/8) | 16.45 ± 9.96 (min -10.77, wins 0/8) | 2.8 / 0.52 | 0/0 |
| FW0.10 | 6.60 ± 9.10 (min -49.72, wins 2/8) | 6.60 ± 9.10 (min -49.72, wins 0/8) | 6.60 ± 9.10 (min -49.72, wins 0/8) | 0.0 / 0.00 | 8/8 |

## MX3_4clones+FW25+SQ — build `solution_v11.py` — mode `extend` — seeds 8 — settle-through days [6, 7, 4, 6, 4, 5, 4, 6]

| seat | reported | marked | settled | open n / escrow | bankrupt d40/final |
|---|---|---|---|---|---|
| clone_a | 27.92 ± 14.16 (min -8.93, wins 2/8) | 48.44 ± 15.87 (min -5.37, wins 2/8) | 51.04 ± 15.19 (min -3.93, wins 2/8) | 4.8 / 13.92 | 0/0 |
| clone_b | 17.19 ± 7.48 (min -7.12, wins 1/8) | 40.27 ± 9.42 (min 4.68, wins 2/8) | 42.69 ± 11.34 (min 7.88, wins 2/8) | 4.6 / 15.54 | 0/0 |
| clone_c | 24.00 ± 7.66 (min 3.47, wins 1/8) | 40.91 ± 6.82 (min 8.72, wins 1/8) | 40.75 ± 6.94 (min 8.47, wins 1/8) | 4.2 / 12.21 | 0/0 |
| clone_d | 33.29 ± 8.40 (min 1.58, wins 2/8) | 56.17 ± 9.27 (min 25.72, wins 2/8) | 56.16 ± 9.32 (min 23.54, wins 2/8) | 5.6 / 16.64 | 0/0 |
| FW0.25 | 20.18 ± 20.43 (min -36.68, wins 2/8) | 26.35 ± 26.40 (min -36.68, wins 1/8) | 26.43 ± 26.48 (min -36.68, wins 1/8) | 0.6 / 3.86 | 7/7 |
| SQ | 0.42 ± 2.95 (min -12.88, wins 0/8) | 2.44 ± 3.32 (min -11.71, wins 0/8) | 5.55 ± 6.08 (min -12.88, wins 0/8) | 3.8 / 0.99 | 0/0 |

## SP_mirror — build `solution_v13.py` — mode `extend` — seeds 8 — settle-through days [7, 7, 6, 7, 4, 6, 5, 7]

| seat | reported | marked | settled | open n / escrow | bankrupt d40/final |
|---|---|---|---|---|---|
| solution_v13.py_a | 40.00 ± 13.86 (min -0.43, wins 0/8) | 53.96 ± 13.77 (min 17.76, wins 0/8) | 53.38 ± 13.96 (min 17.57, wins 0/8) | 4.6 / 10.17 | 0/0 |
| solution_v13.py_b | 47.49 ± 13.48 (min -12.22, wins 2/8) | 58.47 ± 13.86 (min -5.97, wins 2/8) | 57.74 ± 13.69 (min -4.22, wins 3/8) | 4.5 / 8.91 | 0/0 |
| solution_v13.py_c | 53.34 ± 17.76 (min 2.33, wins 4/8) | 79.97 ± 22.62 (min 4.35, wins 4/8) | 79.96 ± 22.96 (min 4.33, wins 4/8) | 4.8 / 18.33 | 0/0 |
| solution_v13.py_d | 58.11 ± 11.85 (min 10.45, wins 2/8) | 74.69 ± 12.34 (min 32.09, wins 2/8) | 75.23 ± 12.86 (min 32.45, wins 1/8) | 4.9 / 12.51 | 0/0 |

## SP_hetero — build `solution_v13.py` — mode `extend` — seeds 8 — settle-through days [7, 7, 6, 7, 4, 6, 5, 7]

| seat | reported | marked | settled | open n / escrow | bankrupt d40/final |
|---|---|---|---|---|---|
| base | 42.18 ± 18.12 (min 1.98, wins 2/8) | 60.89 ± 17.58 (min 22.47, wins 2/8) | 60.93 ± 17.60 (min 23.42, wins 2/8) | 5.1 / 13.87 | 0/0 |
| tight | 40.98 ± 16.59 (min -5.67, wins 1/8) | 57.51 ± 17.16 (min 8.24, wins 1/8) | 55.98 ± 17.60 (min 5.92, wins 1/8) | 5.5 / 12.58 | 0/0 |
| wide | 57.20 ± 13.04 (min 19.38, wins 4/8) | 78.79 ± 15.38 (min 30.84, wins 4/8) | 80.07 ± 16.54 (min 30.38, wins 4/8) | 4.8 / 15.09 | 0/0 |
| no_extract | 31.60 ± 11.17 (min -3.35, wins 1/8) | 53.82 ± 14.83 (min 5.03, wins 1/8) | 53.85 ± 14.90 (min 10.65, wins 1/8) | 5.4 / 16.98 | 0/0 |

## MX1_2clones+SQ+FW10+FW05 — build `solution_v13.py` — mode `extend` — seeds 8 — settle-through days [7, 6, 7, 5, 5, 5, 7, 6]

| seat | reported | marked | settled | open n / escrow | bankrupt d40/final |
|---|---|---|---|---|---|
| clone_a | 89.74 ± 23.63 (min 11.32, wins 5/8) | 105.49 ± 25.60 (min 11.45, wins 5/8) | 104.12 ± 25.46 (min 11.32, wins 5/8) | 4.0 / 12.94 | 0/0 |
| clone_b | 88.69 ± 26.12 (min 9.13, wins 3/8) | 104.49 ± 29.28 (min 19.61, wins 3/8) | 102.06 ± 28.94 (min 16.13, wins 3/8) | 4.1 / 11.71 | 0/0 |
| SQ | 16.58 ± 5.18 (min -5.67, wins 0/8) | 18.35 ± 5.39 (min -5.67, wins 0/8) | 17.45 ± 5.00 (min -5.67, wins 0/8) | 3.1 / 0.76 | 0/0 |
| FW0.10 | 4.10 ± 7.09 (min -25.48, wins 0/8) | 4.10 ± 7.09 (min -25.48, wins 0/8) | 4.10 ± 7.09 (min -25.48, wins 0/8) | 0.0 / 0.00 | 8/8 |
| FW0.05 | -4.95 ± 5.55 (min -39.88, wins 0/8) | -4.95 ± 5.55 (min -39.88, wins 0/8) | -4.95 ± 5.55 (min -39.88, wins 0/8) | 0.0 / 0.00 | 8/8 |

## MX2_base+tight+SQ+FW10 — build `solution_v13.py` — mode `extend` — seeds 8 — settle-through days [5, 6, 6, 6, 6, 5, 5, 6]

| seat | reported | marked | settled | open n / escrow | bankrupt d40/final |
|---|---|---|---|---|---|
| base | 74.19 ± 23.36 (min -0.19, wins 3/8) | 103.47 ± 25.20 (min 13.21, wins 4/8) | 103.69 ± 25.90 (min 12.81, wins 4/8) | 4.5 / 21.13 | 0/0 |
| tight | 71.26 ± 23.80 (min -8.87, wins 3/8) | 108.32 ± 28.58 (min 1.47, wins 4/8) | 108.64 ± 28.88 (min 3.82, wins 4/8) | 4.9 / 27.60 | 0/0 |
| SQ | 14.95 ± 10.30 (min -10.77, wins 0/8) | 16.09 ± 10.02 (min -8.52, wins 0/8) | 16.45 ± 9.96 (min -10.77, wins 0/8) | 2.8 / 0.52 | 0/0 |
| FW0.10 | 6.60 ± 9.10 (min -49.72, wins 2/8) | 6.60 ± 9.10 (min -49.72, wins 0/8) | 6.60 ± 9.10 (min -49.72, wins 0/8) | 0.0 / 0.00 | 8/8 |

## MX3_4clones+FW25+SQ — build `solution_v13.py` — mode `extend` — seeds 8 — settle-through days [6, 7, 4, 6, 4, 5, 4, 6]

| seat | reported | marked | settled | open n / escrow | bankrupt d40/final |
|---|---|---|---|---|---|
| clone_a | 25.51 ± 13.95 (min -8.93, wins 2/8) | 46.17 ± 15.71 (min -5.37, wins 2/8) | 48.76 ± 14.90 (min -3.93, wins 2/8) | 4.6 / 14.09 | 0/0 |
| clone_b | 18.29 ± 8.42 (min -7.12, wins 1/8) | 41.37 ± 10.06 (min 4.68, wins 2/8) | 43.79 ± 11.93 (min 7.88, wins 2/8) | 4.6 / 15.54 | 0/0 |
| clone_c | 23.62 ± 7.66 (min 3.47, wins 1/8) | 40.02 ± 6.82 (min 8.72, wins 1/8) | 39.87 ± 6.83 (min 8.47, wins 1/8) | 4.2 / 11.75 | 0/0 |
| clone_d | 33.84 ± 8.52 (min 1.58, wins 2/8) | 56.72 ± 9.36 (min 25.72, wins 2/8) | 56.72 ± 9.47 (min 23.54, wins 2/8) | 5.6 / 16.64 | 0/0 |
| FW0.25 | 20.18 ± 20.43 (min -36.68, wins 2/8) | 26.35 ± 26.40 (min -36.68, wins 1/8) | 26.43 ± 26.48 (min -36.68, wins 1/8) | 0.6 / 3.86 | 7/7 |
| SQ | 1.19 ± 3.31 (min -12.88, wins 0/8) | 3.20 ± 3.59 (min -11.71, wins 0/8) | 6.31 ± 6.17 (min -12.88, wins 0/8) | 3.8 / 0.99 | 0/0 |

## CODEX_probe — build `solution_v13.py` — mode `extend` — seeds 8 — settle-through days [5, 6, 6, 6, 6, 5, 5, 6]

| seat | reported | marked | settled | open n / escrow | bankrupt d40/final |
|---|---|---|---|---|---|
| baseline | 83.46 ± 18.17 (min 9.62, wins 8/8) | 107.53 ± 19.65 (min 23.46, wins 6/8) | 107.84 ± 20.18 (min 19.62, wins 6/8) | 4.6 / 17.34 | 0/0 |
| tight | 43.56 ± 14.54 (min -6.24, wins 0/8) | 69.01 ± 13.74 (min 13.94, wins 1/8) | 69.93 ± 14.03 (min 14.38, wins 1/8) | 4.6 / 18.29 | 0/0 |
| wide | 58.31 ± 16.55 (min -9.25, wins 0/8) | 78.44 ± 20.28 (min 3.00, wins 1/8) | 78.06 ± 21.43 (min -0.25, wins 1/8) | 4.0 / 15.23 | 0/0 |
| fixed_width | 3.92 ± 9.91 (min -58.66, wins 0/8) | 3.92 ± 9.91 (min -58.66, wins 0/8) | 3.92 ± 9.91 (min -58.66, wins 0/8) | 0.0 / 0.00 | 8/8 |

## SP_hetero — build `solution_v13.py` — mode `cap` — seeds 8 — settle-through days [0, 0, 0, 0, 0, 0, 0, 0]

| seat | reported | marked | settled | open n / escrow | bankrupt d40/final |
|---|---|---|---|---|---|
| base | 58.39 ± 18.74 (min 17.96, wins 2/8) | 58.39 ± 18.74 (min 17.96, wins 2/8) | 58.39 ± 18.74 (min 17.96, wins 2/8) | 0.0 / 0.00 | 0/0 |
| tight | 61.11 ± 19.61 (min 1.87, wins 1/8) | 61.11 ± 19.61 (min 1.87, wins 1/8) | 61.11 ± 19.61 (min 1.87, wins 1/8) | 0.0 / 0.00 | 0/0 |
| wide | 83.75 ± 15.13 (min 30.80, wins 4/8) | 83.75 ± 15.13 (min 30.80, wins 4/8) | 83.75 ± 15.13 (min 30.80, wins 4/8) | 0.0 / 0.00 | 0/0 |
| no_extract | 56.99 ± 15.50 (min 3.29, wins 1/8) | 56.99 ± 15.50 (min 3.29, wins 1/8) | 56.99 ± 15.50 (min 3.29, wins 1/8) | 0.0 / 0.00 | 0/0 |

## MX2_base+tight+SQ+FW10 — build `solution_v13.py` — mode `cap` — seeds 8 — settle-through days [0, 0, 0, 0, 0, 0, 0, 0]

| seat | reported | marked | settled | open n / escrow | bankrupt d40/final |
|---|---|---|---|---|---|
| base | 102.50 ± 26.44 (min 13.68, wins 5/8) | 102.50 ± 26.44 (min 13.68, wins 5/8) | 102.50 ± 26.44 (min 13.68, wins 5/8) | 0.0 / 0.00 | 0/0 |
| tight | 108.00 ± 30.47 (min -2.11, wins 3/8) | 108.00 ± 30.47 (min -2.11, wins 3/8) | 108.00 ± 30.47 (min -2.11, wins 3/8) | 0.0 / 0.00 | 0/0 |
| SQ | 19.98 ± 14.28 (min -16.63, wins 0/8) | 19.98 ± 14.28 (min -16.63, wins 0/8) | 19.98 ± 14.28 (min -16.63, wins 0/8) | 0.0 / 0.00 | 0/0 |
| FW0.10 | 6.60 ± 9.10 (min -49.72, wins 0/8) | 6.60 ± 9.10 (min -49.72, wins 0/8) | 6.60 ± 9.10 (min -49.72, wins 0/8) | 0.0 / 0.00 | 8/8 |

## SP_hetero — build `solution_v7.py` — mode `cap` — seeds 8 — settle-through days [0, 0, 0, 0, 0, 0, 0, 0]

| seat | reported | marked | settled | open n / escrow | bankrupt d40/final |
|---|---|---|---|---|---|
| base | 63.36 ± 16.49 (min 10.66, wins 1/8) | 63.36 ± 16.49 (min 10.66, wins 1/8) | 63.36 ± 16.49 (min 10.66, wins 1/8) | 0.0 / 0.00 | 0/0 |
| tight | 54.11 ± 21.56 (min -11.13, wins 2/8) | 54.11 ± 21.56 (min -11.13, wins 2/8) | 54.11 ± 21.56 (min -11.13, wins 2/8) | 0.0 / 0.00 | 0/0 |
| wide | 86.87 ± 14.72 (min 37.81, wins 5/8) | 86.87 ± 14.72 (min 37.81, wins 5/8) | 86.87 ± 14.72 (min 37.81, wins 5/8) | 0.0 / 0.00 | 0/0 |
| no_extract | 52.70 ± 14.70 (min 7.62, wins 0/8) | 52.70 ± 14.70 (min 7.62, wins 0/8) | 52.70 ± 14.70 (min 7.62, wins 0/8) | 0.0 / 0.00 | 0/0 |

## SP_hetero — build `solution_v7.py` — mode `extend` — seeds 8 — settle-through days [7, 7, 6, 7, 4, 6, 5, 7]

| seat | reported | marked | settled | open n / escrow | bankrupt d40/final |
|---|---|---|---|---|---|
| base | 44.15 ± 15.73 (min 0.93, wins 2/8) | 59.49 ± 16.34 (min 7.81, wins 2/8) | 59.27 ± 16.48 (min 6.93, wins 2/8) | 4.9 / 11.56 | 0/0 |
| tight | 36.80 ± 18.07 (min -15.10, wins 1/8) | 51.91 ± 19.47 (min -7.40, wins 1/8) | 49.80 ± 19.49 (min -7.10, wins 1/8) | 5.6 / 11.25 | 0/0 |
| wide | 61.44 ± 12.00 (min 30.33, wins 5/8) | 84.52 ± 14.91 (min 33.47, wins 4/8) | 85.82 ± 16.32 (min 33.33, wins 5/8) | 4.8 / 16.02 | 0/0 |
| no_extract | 29.31 ± 12.83 (min -3.78, wins 0/8) | 51.46 ± 12.70 (min 14.53, wins 1/8) | 51.44 ± 12.80 (min 13.22, wins 0/8) | 6.4 / 17.34 | 0/0 |

## SP_mirror — build `solution_v7.py` — mode `extend` — seeds 8 — settle-through days [7, 7, 6, 7, 4, 6, 5, 7]

| seat | reported | marked | settled | open n / escrow | bankrupt d40/final |
|---|---|---|---|---|---|
| solution_v7.py_a | 35.49 ± 14.44 (min -3.34, wins 1/8) | 52.52 ± 13.86 (min 14.45, wins 0/8) | 51.99 ± 13.90 (min 16.61, wins 0/8) | 4.5 / 12.23 | 0/0 |
| solution_v7.py_b | 45.44 ± 13.74 (min -6.13, wins 2/8) | 58.93 ± 13.50 (min 2.39, wins 3/8) | 58.44 ± 14.05 (min 1.87, wins 3/8) | 5.2 / 10.23 | 0/0 |
| solution_v7.py_c | 61.62 ± 15.82 (min 10.31, wins 5/8) | 87.64 ± 20.49 (min 16.99, wins 5/8) | 89.12 ± 21.04 (min 17.31, wins 5/8) | 5.4 / 17.95 | 0/0 |
| solution_v7.py_d | 46.27 ± 12.29 (min 10.89, wins 0/8) | 61.22 ± 13.50 (min 27.44, wins 0/8) | 60.40 ± 13.95 (min 27.18, wins 0/8) | 4.9 / 10.96 | 0/0 |

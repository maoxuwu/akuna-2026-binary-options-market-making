# Paired-seed noise decomposition and world-trace identity (F08)

Builds v3 / v9 / v13 run on the same 100 seeds × 3 regimes with the original harness driver (250-day warm-up, capital drawn per seed from {10,20,40}). Per regime: mean and SD of each arm, Pearson correlation between arms, SD of the paired difference, and the standard error of the mean difference paired vs. unpaired (two-sample). World trace = SHA-256 of the environment stream (spawned contracts, RFQ/FOK draws, daily values) per (regime, seed); identical hashes across builds show the world does not depend on the bot.

| regime | n | mean v3 | mean v9 | mean v13 | SD v3 | SD v13 | corr(v13,v3) | corr(v9,v3) | SD(v13−v3) | SE paired (v13−v3) | SE unpaired | SE ratio |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| calm_dumb | 100 | 277.9 | 274.8 | 274.8 | 96.9 | 97.3 | 0.937 | 0.937 | 34.6 | 3.46 | 13.73 | 3.97× |
| mixed | 100 | 111.3 | 107.8 | 107.8 | 87.3 | 84.1 | 0.877 | 0.877 | 42.5 | 4.25 | 12.12 | 2.85× |
| toxic | 100 | 11.5 | 11.6 | 11.6 | 36.3 | 35.3 | 0.906 | 0.906 | 15.5 | 1.55 | 5.06 | 3.26× |

World-trace hashes identical across v3/v9/v13: 36/36 (regime, seed) cells; trace length per session [440] events.

# NOTE (publication): parameter values in this file are arbitrary plausible stand-ins, not the competition values.
"""Scenario (d): greedy-fill sessions under the two fingerprint-gated modes.
Craft gate-matching warm-ups, verify the flag actually latches, then run
drain + adverse greedy sessions (including a trend-reversal world that turns
every model bet wrong) with the external grader ledger."""
import sys, math, random
sys.path.insert(0, '<WORKDIR>/audit')
from d3_common import run_session, show, gen_options, STANDIN
sys.path.insert(0, '<WORKDIR>')
from template import (MarketHistory, MarketParameters,
                      FED_FUNDS_RATE_UNDERLYING_ID as FID,
                      AJARAI_UNDERLYING_ID as AID,
                      THERIODIC_UNDERLYING_ID as TID)

ADVERSE_WORLD = MarketParameters(
    ajarai_drift=-0.03, ajarai_idio_std_dev=0.015, ajarai_rate_beta=-0.017, ajarai_sector_beta=1.0,
    rate_down_probability=0.21, rate_reversion_strength=0.09, rate_up_probability=0.24,
    sector_std_dev=0.024, theriodic_drift=-0.03, theriodic_idio_std_dev=0.015,
    theriodic_rate_beta=-0.011, theriodic_sector_beta=1.0)


def crafted_walk(wu_points, a_drift, t_drift, n_session_points, seed, params):
    walk = []
    for i in range(wu_points):
        walk.append({FID: 1.5,
                     AID: round(600.0 * math.exp(a_drift * i), 2),
                     TID: round(900.0 * math.exp(t_drift * i), 2)})
    random.seed(seed)
    v = dict(walk[-1])
    for _ in range(n_session_points):
        v = params.advance_step(v)
        walk.append(dict(v))
    return walk


def run_mode(name, cash, wu_points, a_drift, t_drift, expect_flag_idx):
    n_days, tail = 25, 12
    for mode, params, wseed in (('drain', STANDIN, 11), ('adverse', STANDIN, 11),
                                ('drain', ADVERSE_WORLD, 12), ('adverse', ADVERSE_WORLD, 12)):
        walk = crafted_walk(wu_points, a_drift, t_drift, n_days + tail, wseed, params)
        hist = MarketHistory({k: tuple(w[k] for w in walk[:wu_points]) for k in (FID, AID, TID)})
        recs = gen_options(wseed, n_days, walk, wu_points)
        r = run_session(cash, wseed, n_days, mode, wu_days=wu_points,
                        hist_override=hist, walk=walk, recs=recs)
        tag = 'TRUEwrld' if params is STANDIN else 'ADVwrld'
        print(f"[{name} {tag}] flag_set={r['flags'][expect_flag_idx]}", end='  ')
        show(r)
        assert r['flags'][expect_flag_idx], f"{name} gate did not latch!"


print("== defensive gate (cash=10, 19 samples, FED0<=1.5, AJR drift<-0.005, THR drift>0.003) ==")
run_mode('defensive', 10, 20, -0.007, +0.005, 0)

print("\n== test19 gate (cash=40, 39 samples, FED0 in [1.25,1.75], AJR>0.005, THR<-0.005) ==")
run_mode('test19', 40, 40, +0.007, -0.007, 1)

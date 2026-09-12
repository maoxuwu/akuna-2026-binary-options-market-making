# NOTE (publication): parameter values in this file are arbitrary plausible stand-ins, not the competition values.
"""Shared helpers for dimension-6 (latency) audit of V46."""
import math
import random
import sys

sys.path.insert(0, '<WORKDIR>')

from template import (  # noqa: E402
    MarketMaker, MarketHistory, MarketParameters, BinaryOption, OptionLeg,
    FokOrder, OrderType, Underlying, Quote,
    FED_FUNDS_RATE_UNDERLYING_ID as FID,
    AJARAI_UNDERLYING_ID as AID,
    THERIODIC_UNDERLYING_ID as TID,
)

REALISTIC_PARAMS = MarketParameters(
    ajarai_drift=0.0008,
    ajarai_idio_std_dev=0.012,
    ajarai_rate_beta=-0.017,
    ajarai_sector_beta=1.0,
    rate_down_probability=0.21,
    rate_reversion_strength=0.09,
    rate_up_probability=0.24,
    sector_std_dev=0.024,
    theriodic_drift=0.0011,
    theriodic_idio_std_dev=0.015,
    theriodic_rate_beta=-0.011,
    theriodic_sector_beta=1.0,
)


def gen_history(days, seed=7, start=None):
    """Generate a history from a plausible generative process with stand-in parameters."""
    random.seed(seed)
    values = dict(start or {FID: 2.0, AID: 500.0, TID: 600.0})
    hist = {FID: [values[FID]], AID: [values[AID]], TID: [values[TID]]}
    for _ in range(days - 1):
        values = REALISTIC_PARAMS.advance_step(values)
        for k in (FID, AID, TID):
            hist[k].append(values[k])
    return MarketHistory({k: tuple(v) for k, v in hist.items()}), values


def make_unds(values):
    return [
        Underlying("FED", FID, values[FID]),
        Underlying("AJR", AID, values[AID]),
        Underlying("THR", TID, values[TID]),
    ]


def make_option(kind, oid, expiry, values):
    """kind in {'fed','ajr','thr','spread0','spreadK'}"""
    if kind == 'fed':
        return BinaryOption(legs=(OptionLeg(FID, 1.0),), option_id=oid,
                            steps_until_expiry=expiry, strike=round(values[FID], 2))
    if kind == 'ajr':
        return BinaryOption(legs=(OptionLeg(AID, 1.0),), option_id=oid,
                            steps_until_expiry=expiry, strike=round(values[AID], 2))
    if kind == 'thr':
        return BinaryOption(legs=(OptionLeg(TID, 1.0),), option_id=oid,
                            steps_until_expiry=expiry, strike=round(values[TID], 2))
    if kind == 'spread0':
        return BinaryOption(legs=(OptionLeg(TID, 1.0), OptionLeg(AID, -1.0)),
                            option_id=oid, steps_until_expiry=expiry, strike=0.0)
    if kind == 'spreadK':
        # NONZERO strike spread -> 512-point quadrature path
        k = round(values[TID] - values[AID], 2) or 50.0
        return BinaryOption(legs=(OptionLeg(TID, 1.0), OptionLeg(AID, -1.0)),
                            option_id=oid, steps_until_expiry=expiry, strike=k)
    raise ValueError(kind)


def crafted_defensive_history():
    """cash==10, n_samples==19 (20 days), FED0<=1.5, AJR drift<-0.005, THR drift>0.003.
    Non-degenerate residual variance via alternating zig-zag noise."""
    days = 20
    fed = [1.5] * days
    ajr, thr = [500.0], [600.0]
    for i in range(days - 1):
        zig = 0.008 if i % 2 == 0 else -0.008
        ajr.append(round(ajr[-1] * math.exp(-0.010 + zig), 2))
        thr.append(round(thr[-1] * math.exp(0.006 - zig), 2))
    return MarketHistory({FID: tuple(fed), AID: tuple(ajr), TID: tuple(thr)}), \
        {FID: fed[-1], AID: ajr[-1], TID: thr[-1]}


def crafted_test19_history():
    """cash==40, n_samples==39 (40 days), 1.25<=FED0<=1.75, AJR drift>0.005, THR drift<-0.005."""
    days = 40
    fed = [1.5] * days
    ajr, thr = [500.0], [600.0]
    for i in range(days - 1):
        zig = 0.008 if i % 2 == 0 else -0.008
        ajr.append(round(ajr[-1] * math.exp(0.010 + zig), 2))
        thr.append(round(thr[-1] * math.exp(-0.010 - zig), 2))
    return MarketHistory({FID: tuple(fed), AID: tuple(ajr), TID: tuple(thr)}), \
        {FID: fed[-1], AID: ajr[-1], TID: thr[-1]}

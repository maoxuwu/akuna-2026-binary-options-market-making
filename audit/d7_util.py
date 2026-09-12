# NOTE (publication): parameter values in this file are arbitrary plausible stand-ins, not the competition values.
"""Shared helpers for the D7 state-machine / mirror-ledger audit of V46.

Never modifies template.py. All simulation is external: we play the grader.
Ledger convention (matches the problem statement and the grader):
  buy  q@p  costs q*p          expiry credits q*payoff
  sell q@p  costs q*(1-p)      expiry credits q*(1-payoff)
"""
import math
import random
import sys
from dataclasses import replace

sys.path.insert(0, '<WORKDIR>')
from template import (  # noqa: E402
    MarketMaker, MarketHistory, MarketParameters, BinaryOption, OptionLeg,
    FokOrder, OrderType, Underlying, Quote,
    FED_FUNDS_RATE_UNDERLYING_ID as FID,
    AJARAI_UNDERLYING_ID as AID,
    THERIODIC_UNDERLYING_ID as TID,
)

STANDIN_PARAMS = MarketParameters(
    ajarai_drift=0.0008, ajarai_idio_std_dev=0.012, ajarai_rate_beta=-0.017,
    ajarai_sector_beta=1.0, rate_down_probability=0.21, rate_reversion_strength=0.09,
    rate_up_probability=0.24, sector_std_dev=0.024, theriodic_drift=0.0011,
    theriodic_idio_std_dev=0.015, theriodic_rate_beta=-0.011, theriodic_sector_beta=1.0,
)


def make_underlyings(fed, ajr, thr):
    return [Underlying("FED", FID, fed), Underlying("AJR", AID, ajr), Underlying("THR", TID, thr)]


def drift_history(days, ajr0, thr0, ajr_drift, thr_drift, noise_amp=0.006, fed=1.5, seed=7):
    """History with EXACT mean log-return = target drift (noise recentred), constant FED."""
    rng = random.Random(seed)
    n = days - 1
    out = {}
    for uid, v0, d in ((AID, ajr0, ajr_drift), (TID, thr0, thr_drift)):
        noise = [rng.gauss(0.0, noise_amp) for _ in range(n)]
        m = sum(noise) / n
        rets = [d + (x - m) for x in noise]
        vals = [v0]
        for r in rets:
            vals.append(round(vals[-1] * math.exp(r), 2))
        out[uid] = tuple(vals)
    out[FID] = (fed,) * days
    return MarketHistory(out)


def generated_history(days, seed, fed0=1.5, ajr0=500.0, thr0=600.0):
    random.seed(seed)
    vals = {FID: fed0, AID: ajr0, TID: thr0}
    hist = {FID: [fed0], AID: [ajr0], TID: [thr0]}
    for _ in range(days - 1):
        vals = STANDIN_PARAMS.advance_step(vals)
        for k in (FID, AID, TID):
            hist[k].append(vals[k])
    return MarketHistory({k: tuple(v) for k, v in hist.items()}), vals


def make_defensive_mm(seed=7):
    """cash 10, 20-day history, FED0<=1.5, AJR drift<-0.005, THR drift>0.003."""
    mm = MarketMaker(make_underlyings(1.5, 500.0, 600.0), [], 10.0)
    mm.warm_up(drift_history(20, 500.0, 600.0, -0.008, 0.006, seed=seed))
    return mm


def make_test19_mm(seed=7, noise=0.02):
    """cash 40, 40-day history, FED0 in [1.25,1.75], AJR drift>0.005, THR drift<-0.005.
    noise=0.02 gives realistic residual variance so the drift shrinkage actually bites
    (raw vs shrunk model disagreement, needed for the THR fallback machine)."""
    mm = MarketMaker(make_underlyings(1.5, 500.0, 600.0), [], 40.0)
    mm.warm_up(drift_history(40, 500.0, 600.0, 0.008, -0.008, noise_amp=noise, seed=seed))
    return mm


class ExternalLedger:
    """The grader's ledger + per-option position, kept fully outside the MM."""

    def __init__(self, cash):
        self.cash = cash
        self.long_by_id = {}
        self.short_by_id = {}

    def trade(self, option_id, price, qty_signed):
        if qty_signed > 0:
            self.cash -= qty_signed * price
            self.long_by_id[option_id] = self.long_by_id.get(option_id, 0) + qty_signed
        else:
            q = -qty_signed
            self.cash -= q * (1.0 - price)
            self.short_by_id[option_id] = self.short_by_id.get(option_id, 0) + q

    def settle(self, option, values):
        payoff = option.expiry_valuation(values)
        oid = option.option_id
        self.cash += self.long_by_id.pop(oid, 0) * payoff
        self.cash += self.short_by_id.pop(oid, 0) * (1.0 - payoff)


def identity_gap(mm, initial_cash):
    return mm._available_cash - (initial_cash + sum(mm._settled_pnl_by_counterparty.values()))


def run_session(mode, seed, days=22, verbose=False):
    """Full random session honoring the observed platform contract:
    per-day: announce -> sequential (quote -> maybe fill -> on_trade) -> FOKs
    (accept -> immediate on_trade) -> advance (settle expiry-1 options at new values,
    drop them, decrement the rest).  All options expire before the session ends.
    Returns a report dict."""
    rng = random.Random(seed)
    if mode == "generic":
        cash = 20.0
        hist, vals = generated_history(30, seed * 11 + 1)
        mm = MarketMaker(make_underlyings(vals[FID], vals[AID], vals[TID]), [], cash)
        mm.warm_up(hist)
    elif mode == "defensive":
        cash = 10.0
        mm = make_defensive_mm(seed)
        vals = {FID: 1.5, AID: 500.0 * math.exp(-0.008 * 19), TID: 600.0 * math.exp(0.006 * 19)}
        vals = {k: round(v, 2) for k, v in vals.items()}
        assert mm._is_defensive_environment, "defensive gate not set"
    elif mode == "test19":
        cash = 40.0
        mm = make_test19_mm(seed)
        vals = {FID: 1.5, AID: round(500.0 * math.exp(0.008 * 39), 2),
                TID: round(600.0 * math.exp(-0.008 * 39), 2)}
        assert mm._is_test_nineteen_environment, "test19 gate not set"
    else:
        raise ValueError(mode)

    ext = ExternalLedger(cash)
    active = []  # current-version BinaryOptions
    next_id = 1000
    min_day_end_cash = math.inf
    n_trades = n_fok_acc = n_fok_rej = 0

    def new_option(max_expiry):
        nonlocal next_id
        next_id += 1
        kind = rng.random()
        e = rng.randint(1, max(1, max_expiry))
        if kind < 0.3:
            k = round(rng.choice([1.0, 1.25, 1.5, 1.75, 2.0]), 2)
            return BinaryOption(legs=(OptionLeg(FID, 1.0),), option_id=next_id,
                                steps_until_expiry=e, strike=k)
        if kind < 0.55:
            return BinaryOption(legs=(OptionLeg(AID, 1.0),), option_id=next_id,
                                steps_until_expiry=e, strike=round(vals[AID] * rng.uniform(0.97, 1.03), 2))
        if kind < 0.8:
            return BinaryOption(legs=(OptionLeg(TID, 1.0),), option_id=next_id,
                                steps_until_expiry=e, strike=round(vals[TID] * rng.uniform(0.97, 1.03), 2))
        if kind < 0.93:
            return BinaryOption(legs=(OptionLeg(TID, 1.0), OptionLeg(AID, -1.0)), option_id=next_id,
                                steps_until_expiry=e, strike=0.0)
        # non-zero strike spread: exercises the 512-point quadrature
        return BinaryOption(legs=(OptionLeg(TID, 1.0), OptionLeg(AID, -1.0)), option_id=next_id,
                            steps_until_expiry=e, strike=round(vals[TID] - vals[AID] + rng.uniform(-20, 20), 2))

    # initial announcements
    for _ in range(rng.randint(1, 3)):
        active.append(new_option(min(6, days)))
    mm.active_option_state = list(active)  # grader passes them via constructor normally;
    mm._option_by_id.update({o.option_id: o for o in active})

    for day in range(days):
        # --- RFQ phase: sequential quote -> fill -> on_trade
        for opt in list(active):
            for _ in range(rng.randint(1, 3)):
                cp = rng.randint(1, 12)
                q = mm.quote(opt, cp)
                assert isinstance(q, Quote)
                if rng.random() < 0.55:
                    if rng.random() < 0.5:  # hit our bid: we buy
                        qty = q.bid_quantity if rng.random() < 0.1 else rng.randint(1, min(q.bid_quantity, 30))
                        mm.on_trade(opt, q.bid_price, qty, cp)
                        ext.trade(opt.option_id, q.bid_price, qty)
                    else:  # lift our offer: we sell
                        qty = q.offer_quantity if rng.random() < 0.1 else rng.randint(1, min(q.offer_quantity, 30))
                        mm.on_trade(opt, q.offer_price, -qty, cp)
                        ext.trade(opt.option_id, q.offer_price, -qty)
                    n_trades += 1
        # --- FOK phase: accept -> immediate on_trade
        for _ in range(rng.randint(0, 4)):
            if not active:
                break
            opt = rng.choice(active)
            cp = rng.randint(1, 12)
            ot = rng.choice([OrderType.BUY, OrderType.SELL])
            r = rng.random()
            if r < 0.5:  # near-theo prices so accepts actually happen
                c = mm.price_option(opt)
                off = rng.uniform(0.01, 0.12)
                p = max(0.0, c + off) if ot == OrderType.BUY else max(0.0, c - off)
            elif r < 0.9:
                p = rng.uniform(0.0, 1.0)
            else:  # price above 1 is contract-legal for FOK
                p = rng.uniform(1.0, 3.0)
            qty = rng.randint(1, 30)
            fok = FokOrder(cp, opt.option_id, ot, round(p, 4), qty)
            acc = mm.respond_to_fok(opt, fok)
            if acc:
                signed = -qty if ot == OrderType.BUY else qty
                mm.on_trade(opt, fok.price, signed, cp)
                ext.trade(opt.option_id, fok.price, signed)
                n_fok_acc += 1
            else:
                n_fok_rej += 1
        # --- advance
        random.seed(seed * 100000 + day)
        vals = STANDIN_PARAMS.advance_step(vals)
        expiring = [o for o in active if o.steps_until_expiry == 1]
        for o in expiring:
            ext.settle(o, vals)
        active = [replace(o, steps_until_expiry=o.steps_until_expiry - 1)
                  for o in active if o.steps_until_expiry > 1]
        remaining = days - day - 1
        if remaining >= 1:
            for _ in range(rng.randint(0, 2)):
                active.append(new_option(min(6, remaining)))
        mm.on_step_advance(make_underlyings(vals[FID], vals[AID], vals[TID]), list(active))
        min_day_end_cash = min(min_day_end_cash, ext.cash)

    assert not active, "options left alive at session end"
    unsettled = set(mm._trade_lots_by_option_id) - mm._settled_option_ids
    return {
        "mode": mode, "seed": seed,
        "gap": identity_gap(mm, cash),
        "mirror_vs_grader": mm._available_cash - ext.cash,
        "min_day_end_cash": min_day_end_cash,
        "unsettled_traded_ids": sorted(unsettled),
        "trades": n_trades, "fok_acc": n_fok_acc, "fok_rej": n_fok_rej,
        "final_cash": ext.cash,
    }

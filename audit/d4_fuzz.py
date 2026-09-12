#!/usr/bin/env python3
"""d4_fuzz.py -- DIMENSION 4 audit: randomized interleaving fuzz of V46 template.py.

Deterministic given --seed. Drives random interleavings of
quote / respond_to_fok / on_trade / on_step_advance / price_option /
price_option_from_parameters with contract-valid but wild inputs.

Per-seed rotation:
  warm-up style = seed % 6:
    0 = warm_up never called at all
    1 = 1-day history
    2 = 20-day gate-matching (defensive gate: cash 10, FED0 1.5, AJR drift<-0.005, THR drift>+0.003)
    3 = 40-day gate-matching (test19 gate: cash 40, FED0 1.5, AJR drift>+0.005, THR drift<-0.005)
    4 = 45-day realistic history
    5 = 20-day random history with near-zero / zero company days
  capital = {1,5,10,40,200}[seed % 5], overridden to 10 / 40 for styles 2 / 3.

Assertions on every op: no uncaught exception, every Quote legal (double-checked
explicitly beyond Quote.__post_init__), every price finite in [0,1], every FOK
response a bool. A sha256 digest of all outputs is printed per seed so behavior
can be compared bit-for-bit between Python 3.14 and 3.11.

Only rng.random / rng.uniform / rng.randint / rng.choice are used in the driver
(all bit-stable across CPython 3.11..3.14 for a given seed).
"""
import argparse
import hashlib
import math
import sys
import time
import traceback
import random as _random

sys.path.insert(0, '<WORKDIR>')
from template import (  # noqa: E402
    MarketMaker, MarketHistory, MarketParameters, BinaryOption, OptionLeg,
    FokOrder, OrderType, Underlying, Quote,
    FED_FUNDS_RATE_UNDERLYING_ID as FID,
    AJARAI_UNDERLYING_ID as AID,
    THERIODIC_UNDERLYING_ID as TID,
)

CAPITALS = [1, 5, 10, 40, 200]
LEG_COMBOS = [
    (FID,), (AID,), (TID,),
    (FID, AID), (FID, TID), (AID, TID), (TID, AID),
    (FID, AID, TID), (AID, TID, FID),
]


def rand_weight(rng):
    r = rng.random()
    if r < 0.50:
        w = 1.0 if rng.random() < 0.5 else -1.0
    elif r < 0.90:
        w = rng.uniform(-5.0, 5.0)
    else:
        w = rng.uniform(-500.0, 500.0)
    if w == 0.0:
        w = 1.0
    return w


def rand_option(rng, oid, cur_values):
    ids = rng.choice(LEG_COMBOS)
    legs = tuple(OptionLeg(u, rand_weight(rng)) for u in ids)
    r = rng.random()
    if r < 0.08:
        exp = 0
    elif r < 0.80:
        exp = rng.randint(1, 10)
    elif r < 0.97:
        exp = rng.randint(11, 30)
    else:
        exp = rng.randint(31, 60)
    obs = sum(l.weight * cur_values.get(l.underlying_id, 0.0) for l in legs)
    if rng.random() < 0.6:
        strike = round(obs * rng.uniform(0.5, 1.5) + rng.uniform(-2.0, 2.0), 2)
    else:
        strike = round(rng.uniform(-1000.0, 5000.0), 2)
    strike = max(-1000.0, min(5000.0, strike))
    return BinaryOption(legs=legs, option_id=oid, steps_until_expiry=exp, strike=strike)


def rand_params(rng):
    up = rng.uniform(0.01, 0.6)
    down = rng.uniform(0.01, min(0.95 - up, 0.6))
    return MarketParameters(
        ajarai_drift=rng.uniform(-0.05, 0.05),
        ajarai_idio_std_dev=rng.uniform(0.0, 0.1),
        ajarai_rate_beta=rng.uniform(-0.5, 0.5),
        ajarai_sector_beta=rng.uniform(-2.0, 2.0),
        rate_down_probability=down,
        rate_reversion_strength=rng.uniform(0.0, 1.0),
        rate_up_probability=up,
        sector_std_dev=rng.uniform(0.0, 0.1),
        theriodic_drift=rng.uniform(-0.05, 0.05),
        theriodic_idio_std_dev=rng.uniform(0.0, 0.1),
        theriodic_rate_beta=rng.uniform(-0.5, 0.5),
        theriodic_sector_beta=rng.uniform(-2.0, 2.0),
        rate_step=0.25 if rng.random() < 0.8 else 0.5,
        rate_target=rng.uniform(0.0, 8.0),
    )


def grid_walk(rng, start, days, jump_prob=0.05):
    vals = [start]
    r = start
    for _ in range(days - 1):
        u = rng.random()
        if u < jump_prob:
            r = max(round(r + rng.choice([-1, 1]) * rng.randint(2, 8) * 0.25, 2), 0.0)
        elif u < 0.35:
            r = max(round(r + 0.25, 2), 0.0)
        elif u < 0.60:
            r = max(round(r - 0.25, 2), 0.0)
        vals.append(r)
    return tuple(vals)


def company_walk(rng, start, days, drift=0.0, noise=0.03, zero_prob=0.0):
    vals = [round(start, 2)]
    v = start
    for _ in range(days - 1):
        if zero_prob and rng.random() < zero_prob:
            v = rng.choice([0.0, 0.01, 0.01])
        elif v > 0.0:
            v = round(v * math.exp(drift + rng.uniform(-noise, noise)), 2)
        vals.append(round(v, 2))
    return tuple(vals)


def build_history(style, rng, cur):
    f0, a0, t0 = cur[FID], cur[AID], cur[TID]
    if style == 1:
        return MarketHistory({FID: (f0,), AID: (a0,), TID: (t0,)})
    if style == 2:  # defensive gate: 20 days -> 19 samples
        fed = tuple([1.5] * 20)
        ajr = company_walk(rng, a0, 20, drift=-0.012, noise=0.002)
        thr = company_walk(rng, t0, 20, drift=+0.010, noise=0.002)
        return MarketHistory({FID: fed, AID: ajr, TID: thr})
    if style == 3:  # test19 gate: 40 days -> 39 samples
        fed = tuple([1.5] * 40)
        ajr = company_walk(rng, a0, 40, drift=+0.010, noise=0.002)
        thr = company_walk(rng, t0, 40, drift=-0.012, noise=0.002)
        return MarketHistory({FID: fed, AID: ajr, TID: thr})
    if style == 4:  # realistic 45d
        fed = grid_walk(rng, f0, 45, jump_prob=0.0)
        ajr = company_walk(rng, a0, 45, drift=0.001, noise=0.03)
        thr = company_walk(rng, t0, 45, drift=0.001, noise=0.03)
        return MarketHistory({FID: fed, AID: ajr, TID: thr})
    # style 5: 20d random incl zero / near-zero company days
    fed = grid_walk(rng, f0, 20, jump_prob=0.10)
    ajr = company_walk(rng, a0, 20, drift=0.0, noise=0.30, zero_prob=0.10)
    thr = company_walk(rng, t0, 20, drift=0.0, noise=0.30, zero_prob=0.10)
    return MarketHistory({FID: fed, AID: ajr, TID: thr})


def run_seed(seed, n_ops, verbose=False):
    rng = _random.Random(seed)
    style = seed % 6
    cash = CAPITALS[seed % 5]
    if style == 2:
        cash = 10
    elif style == 3:
        cash = 40

    if style in (2, 3):
        f0 = 1.5
    else:
        f0 = rng.choice([0.0, 0.25, 1.0, 1.5, 2.0, 3.0, 5.5])
    a0 = round(rng.uniform(1.0, 3000.0), 2)
    t0 = round(rng.uniform(1.0, 3000.0), 2)
    if rng.random() < 0.1:
        a0 = 0.01
    cur = {FID: f0, AID: a0, TID: t0}

    next_oid = [1]

    def new_oid():
        oid = next_oid[0]
        next_oid[0] += 1
        return oid

    active = {}
    for _ in range(rng.randint(1, 6)):
        o = rand_option(rng, new_oid(), cur)
        active[o.option_id] = o

    unds = [Underlying("FED", FID, cur[FID]),
            Underlying("AJR", AID, cur[AID]),
            Underlying("THR", TID, cur[TID])]
    mm = MarketMaker(unds, list(active.values()), float(cash))

    h = hashlib.sha256()

    def rec(*xs):
        h.update(repr(xs).encode())

    failures = []
    if style != 0:
        try:
            hist = build_history(style, rng, cur)
            mm.warm_up(hist)
        except Exception:
            failures.append(("warm_up", -1, traceback.format_exc()))
    rec('gates', mm._is_defensive_environment, mm._is_test_nineteen_environment,
        round(mm._estimated_rate_step, 6))
    gates = (mm._is_defensive_environment, mm._is_test_nineteen_environment)

    cps = [1, 2, 3, 7, -5, 10**9, 123456789123456789]
    counts = {"quote": 0, "fok": 0, "fok_acc": 0, "trade": 0, "price": 0,
              "pfp": 0, "advance": 0, "fresh_opt": 0}

    def pick_option():
        if active and rng.random() < 0.8:
            keys = sorted(active.keys())
            return active[keys[rng.randint(0, len(keys) - 1)]]
        counts["fresh_opt"] += 1
        return rand_option(rng, new_oid(), cur)

    for op_i in range(n_ops):
        r = rng.random()
        try:
            if r < 0.26:  # quote
                opt = pick_option()
                cp = rng.choice(cps)
                q = mm.quote(opt, cp)
                assert isinstance(q, Quote)
                assert isinstance(q.bid_quantity, int) and isinstance(q.offer_quantity, int)
                assert q.bid_quantity > 0 and q.offer_quantity > 0
                assert 0.0 <= q.bid_price < q.offer_price <= 1.0
                assert abs(round(q.bid_price * 100) - q.bid_price * 100) < 1e-6
                assert abs(round(q.offer_price * 100) - q.offer_price * 100) < 1e-6
                counts["quote"] += 1
                rec('q', op_i, q.bid_price, q.bid_quantity, q.offer_price, q.offer_quantity)
            elif r < 0.46:  # respond_to_fok (+ follow-up on_trade if accepted)
                opt = pick_option()
                cp = rng.choice(cps)
                if rng.random() < 0.90:
                    price = round(rng.uniform(0.0, 1.0), 2)
                else:
                    price = round(rng.uniform(1.0, 3.0), 2)  # dataclass allows >1
                qty = rng.randint(1, 500)
                oid = opt.option_id if rng.random() < 0.9 else opt.option_id + 100000
                ot = OrderType.BUY if rng.random() < 0.5 else OrderType.SELL
                fo = FokOrder(cp, oid, ot, price, qty)
                a = mm.respond_to_fok(opt, fo)
                assert a is True or a is False
                counts["fok"] += 1
                counts["fok_acc"] += int(bool(a))
                rec('f', op_i, bool(a))
                if a and oid == opt.option_id and rng.random() < 0.8:
                    signed = -qty if ot == OrderType.BUY else qty
                    mm.on_trade(opt, price, signed, cp)
                    counts["trade"] += 1
                    rec('ft', op_i, round(mm._available_cash, 9))
            elif r < 0.58:  # standalone on_trade (grader-driven fill)
                opt = pick_option()
                cp = rng.choice(cps)
                price = round(rng.uniform(0.01, 0.99), 2)
                qty = rng.randint(1, 500) * (1 if rng.random() < 0.5 else -1)
                mm.on_trade(opt, price, qty, cp)
                counts["trade"] += 1
                rec('t', op_i, round(mm._available_cash, 9))
            elif r < 0.80:  # price_option
                opt = pick_option()
                p = mm.price_option(opt)
                assert isinstance(p, float) and math.isfinite(p) and 0.0 <= p <= 1.0, f"price={p!r}"
                counts["price"] += 1
                rec('p', op_i, round(p, 12))
                if rng.random() < 0.15:
                    mp = rand_params(rng)
                    p2 = mm.price_option_from_parameters(mp, opt)
                    assert isinstance(p2, float) and math.isfinite(p2) and 0.0 <= p2 <= 1.0, f"pfp={p2!r}"
                    counts["pfp"] += 1
                    rec('pp', op_i, round(p2, 12))
            else:  # on_step_advance
                # evolve underlyings (contract: all three always present)
                u = rng.random()
                if u < 0.05:
                    cur[FID] = max(round(cur[FID] + rng.choice([-1, 1]) * rng.randint(2, 8) * 0.25, 2), 0.0)
                elif u < 0.40:
                    cur[FID] = max(round(cur[FID] + 0.25, 2), 0.0)
                elif u < 0.70:
                    cur[FID] = max(round(cur[FID] - 0.25, 2), 0.0)
                for cid in (AID, TID):
                    v = cur[cid]
                    w = rng.random()
                    if w < 0.01:
                        v = 0.0  # deliverable: round(v*exp(r),2) can hit 0.00
                    elif w < 0.04:
                        v = 0.01  # approaching 0+
                    elif v > 0.0:
                        if w < 0.09:
                            v = round(v * math.exp(rng.uniform(-3.0, 3.0)), 2)  # huge jump
                        else:
                            v = round(v * math.exp(rng.uniform(-0.05, 0.05)), 2)
                    cur[cid] = v
                new_opts = []
                for oid in sorted(active.keys()):
                    o = active[oid].advance_step()
                    if o.steps_until_expiry == 0:
                        if rng.random() < 0.1:
                            new_opts.append(o)  # driver leaves a zero-day option
                        # else expired option vanishes
                    elif rng.random() < 0.05:
                        pass  # option vanishes mid-life
                    else:
                        new_opts.append(o)
                for _ in range(rng.randint(0, 3)):
                    new_opts.append(rand_option(rng, new_oid(), cur))
                active = {o.option_id: o for o in new_opts}
                new_unds = [Underlying("FED", FID, cur[FID]),
                            Underlying("AJR", AID, cur[AID]),
                            Underlying("THR", TID, cur[TID])]
                mm.on_step_advance(new_unds, new_opts)
                counts["advance"] += 1
                rec('a', op_i, round(mm._available_cash, 9), len(new_opts))
        except Exception:
            failures.append((f"op{op_i}", op_i, traceback.format_exc()))
            if len(failures) >= 5:
                break

    digest = h.hexdigest()
    return digest, gates, counts, failures


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--seeds", type=str, default=None, help="e.g. 0-13")
    ap.add_argument("--ops", type=int, default=1500)
    args = ap.parse_args()

    if args.seed is not None:
        seeds = [args.seed]
    elif args.seeds:
        lo, hi = args.seeds.split("-")
        seeds = list(range(int(lo), int(hi) + 1))
    else:
        seeds = list(range(14))

    any_fail = False
    for seed in seeds:
        t0 = time.time()
        digest, gates, counts, failures = run_seed(seed, args.ops)
        dt = time.time() - t0
        status = "FAIL" if failures else "PASS"
        any_fail = any_fail or bool(failures)
        print(f"seed={seed:2d} style={seed % 6} {status} digest={digest[:16]} "
              f"defensive={gates[0]} test19={gates[1]} t={dt:.1f}s "
              f"counts={counts}")
        for tag, op_i, tb in failures:
            print(f"  FAILURE at {tag}:")
            print("    " + "\n    ".join(tb.strip().splitlines()))
    print("OVERALL:", "FAIL" if any_fail else "ALL PASS")
    sys.exit(1 if any_fail else 0)


if __name__ == "__main__":
    main()

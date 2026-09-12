"""Exercise the THR shrunk-model FOK fallback tiers (both the test19 branch and the
generic branch) at their collateral boundaries, with the external grader ledger.
Requires a noisy history so variances are realistic and raw/shrunk centers separate."""
import sys, math, random
sys.path.insert(0, '<WORKDIR>/audit')
from d3_common import ExternalLedger, unds_of
sys.path.insert(0, '<WORKDIR>')
from template import (MarketMaker, MarketHistory, BinaryOption, OptionLeg, FokOrder,
                      OrderType, FED_FUNDS_RATE_UNDERLYING_ID as FID,
                      AJARAI_UNDERLYING_ID as AID, THERIODIC_UNDERLYING_ID as TID)


def noisy_hist(n, a_drift, t_drift, seed):
    rng = random.Random(seed)
    walk = []
    a, t = 500.0, 900.0
    for i in range(n):
        walk.append({FID: 1.5, AID: round(a, 2), TID: round(t, 2)})
        a *= math.exp(a_drift + rng.gauss(0, 0.010))
        t *= math.exp(t_drift + rng.gauss(0, 0.010))
    return walk


def probe(mm, opt, cash, led, label):
    reserve = max(0.02, 0.02 * cash)
    raw_c = mm._inventory_adjusted_value(opt, mm.price_option(opt))
    shr_c = mm._inventory_adjusted_value(
        opt, mm._price_option_with_estimated_drift(opt, mm._shrunk_drift_by_id))
    req = max(0.0025, 0.60 * mm._trading_margin(7))
    print(f"[{label}] raw_center={raw_c:.4f} shrunk_center={shr_c:.4f} required_edge={req:.4f} "
          f"test19={mm._is_test_nineteen_environment}")
    if shr_c - raw_c < req + 0.01:
        print("   centers not separated enough; adjust drifts")
        return
    # price in the disagreement zone: shrunk edge comfortable, raw edge insufficient
    price = round(min(max(raw_c - req + 0.01, 0.01), 0.99), 2)
    if shr_c - price < req + 0.005:
        price = round(max(shr_c - req - 0.02, 0.01), 2)
    raw_edge, shr_edge = raw_c - price, shr_c - price
    print(f"   probe price={price} raw_edge={raw_edge:.4f} (<req) shrunk_edge={shr_edge:.4f} (>=req)")
    tiers = [(0.30 * cash, 'over cap  (>0.25C)  expect REJECT'),
             (0.05 * cash, 'small pre-unlock    expect REJECT'),
             (0.20 * cash, 'medium (unlock)     expect ACCEPT'),
             (0.05 * cash, 'small post-unlock   expect ACCEPT')]
    for col_target, tag in tiers:
        qty = max(1, int(col_target / price))
        ok = mm.respond_to_fok(opt, FokOrder(7, opt.option_id, OrderType.SELL, price, qty))
        col = qty * price
        dep = max(mm._available_cash - reserve, 0.0)
        print(f"   {tag}: qty={qty} col={col:.2f} dep={dep:.2f} accepted={ok}")
        if ok:
            if col > led.cash + 1e-9:
                print(f"   *** CRITICAL over-commit: col={col} > external={led.cash}")
            led.trade(opt.option_id, price, qty)
            mm.on_trade(opt, price, qty, 7)
            print(f"      external={led.cash:.4f} mirror={mm._available_cash:.4f}")
    # exhaust: giant order beyond deployable must reject even post-unlock
    big = int((max(mm._available_cash - reserve, 0.0) + 5.0) / price)
    ok = mm.respond_to_fok(opt, FokOrder(7, opt.option_id, OrderType.SELL, price, big))
    print(f"   beyond-deployable qty={big} accepted={ok} (expect False)")
    print()


# --- test19 branch ---
for seed in (1, 2, 3):
    walk = noisy_hist(40, +0.007, -0.009, seed)
    hist = MarketHistory({k: tuple(w[k] for w in walk) for k in (FID, AID, TID)})
    v0 = walk[-1]
    # near-money THR option, few days out: shrunk (milder down-drift) prices it higher than raw
    opt = BinaryOption((OptionLeg(TID, 1.0),), 1, 4, round(v0[TID] * 0.985, 2))
    mm = MarketMaker(unds_of(v0), [opt], 40.0)
    mm.warm_up(hist)
    if not mm._is_test_nineteen_environment:
        print(f"[test19 seed {seed}] gate missed (drift draw), skip")
        continue
    probe(mm, opt, 40.0, ExternalLedger(40.0), f"test19 seed {seed}")

# --- generic branch (no gate: cash 20, 30-day history) ---
for seed in (4, 5):
    walk = noisy_hist(30, +0.002, -0.011, seed)
    hist = MarketHistory({k: tuple(w[k] for w in walk) for k in (FID, AID, TID)})
    v0 = walk[-1]
    opt = BinaryOption((OptionLeg(TID, 1.0),), 1, 4, round(v0[TID] * 0.985, 2))
    mm = MarketMaker(unds_of(v0), [opt], 20.0)
    mm.warm_up(hist)
    assert not mm._is_test_nineteen_environment and not mm._is_defensive_environment
    probe(mm, opt, 20.0, ExternalLedger(20.0), f"generic seed {seed}")

"""Scenario (c): forced big one-sided positions, then continue quoting/FOKing.
Also: exact FOK acceptance boundary at full capacity (qmax accepted, qmax+1 rejected),
and the informational both-sides-of-one-quote measurement."""
import sys
sys.path.insert(0, '<WORKDIR>/audit')
from d3_common import ExternalLedger, gen_walk, unds_of
sys.path.insert(0, '<WORKDIR>')
from template import (MarketMaker, MarketHistory, BinaryOption, OptionLeg, FokOrder,
                      OrderType, FED_FUNDS_RATE_UNDERLYING_ID as FID,
                      AJARAI_UNDERLYING_ID as AID, THERIODIC_UNDERLYING_ID as TID)


def fresh(cash, seed=200):
    walk = gen_walk(seed, 40)
    wu = 30
    hist = MarketHistory({k: tuple(w[k] for w in walk[:wu]) for k in (FID, AID, TID)})
    v0 = walk[wu - 1]
    opts = [BinaryOption((OptionLeg(AID, 1.0),), 1, 8, round(v0[AID], 2)),
            BinaryOption((OptionLeg(TID, 1.0),), 2, 8, round(v0[TID], 2))]
    mm = MarketMaker(unds_of(v0), opts, cash)
    mm.warm_up(hist)
    return mm, opts, v0

print("== exact FOK boundary at full capacity ==")
for cash in (10, 40):
    mm, opts, _ = fresh(cash)
    opt = opts[0]
    theo = mm.price_option(opt)
    price = round(min(max(theo - 0.10, 0.01), 0.99), 2)
    reserve = max(0.02, 0.02 * cash)
    dep = max(mm._available_cash - reserve, 0.0)
    qmax = int((dep + 1e-12) / price)
    at = mm.respond_to_fok(opt, FokOrder(9, 1, OrderType.SELL, price, qmax))
    over = mm.respond_to_fok(opt, FokOrder(9, 1, OrderType.SELL, price, qmax + 1))
    print(f"cash={cash}: theo={theo:.3f} price={price} dep={dep:.4f} qmax={qmax} "
          f"accept(qmax)={at} accept(qmax+1)={over} "
          f"commit(qmax)={qmax*price:.4f} ledger_after={cash - qmax*price:.4f}")

print("\n== forced +80 / -80 lots (direct on_trade injection, beyond grader authority) ==")
for signed in (80, -80):
    cash = 40
    mm, opts, _ = fresh(cash)
    led = ExternalLedger(cash)
    opt = opts[0]
    led.trade(1, 0.5, signed)
    mm.on_trade(opt, 0.5, signed, 5)
    print(f"forced {signed:+d}@0.50: external={led.cash:.4f} mirror={mm._available_cash:.4f}")
    # continue quoting: every side must be zero-collateral or affordable vs EXTERNAL ledger
    bad = 0
    q = None
    for cp in range(1, 8):
        for o in opts:
            q = mm.quote(o, cp)
            for col in (q.bid_quantity * q.bid_price, q.offer_quantity * (1 - q.offer_price)):
                if col > max(led.cash, 0.0) + 1e-9:
                    bad += 1
    fok_acc = 0
    for o in opts:
        theo = mm.price_option(o)
        for otype, price in ((OrderType.SELL, round(max(theo - 0.10, 0.01), 2)),
                             (OrderType.BUY, round(min(theo + 0.10, 0.99), 2))):
            if mm.respond_to_fok(o, FokOrder(9, o.option_id, otype, price, 5)):
                fok_acc += 1
    print(f"  post-force: over-committed quote sides={bad}, fat-edge FOKs accepted={fok_acc}, "
          f"last quote=({q.bid_price},{q.bid_quantity},{q.offer_price},{q.offer_quantity})")

print("\n== legit-fill accumulation to a big one-sided position, then wrong-side check ==")
cash = 40
mm, opts, v0 = fresh(cash)
led = ExternalLedger(cash)
opt = opts[0]
pos = 0
for i in range(50):
    q = mm.quote(opt, 3)
    if q.bid_quantity * q.bid_price < 1e-9:
        break
    led.trade(1, q.bid_price, q.bid_quantity)
    mm.on_trade(opt, q.bid_price, q.bid_quantity, 3)
    pos += q.bid_quantity
print(f"accumulated +{pos} lots; external={led.cash:.4f} mirror={mm._available_cash:.4f}")
q = mm.quote(opt, 4)
print(f"next quote: bid {q.bid_price}x{q.bid_quantity} (commit {q.bid_quantity*q.bid_price:.4f}) "
      f"offer {q.offer_price}x{q.offer_quantity} (commit {q.offer_quantity*(1-q.offer_price):.4f}) "
      f"vs external {led.cash:.4f}")

print("\n== INFO: both sides of ONE quote filled (not grader-deliverable per 46-run evidence) ==")
for cash in (10, 40):
    mm, opts, _ = fresh(cash)
    led = ExternalLedger(cash)
    opt = opts[0]
    q = mm.quote(opt, 1)
    led.trade(1, q.bid_price, q.bid_quantity)
    mm.on_trade(opt, q.bid_price, q.bid_quantity, 1)
    led.trade(1, q.offer_price, -q.offer_quantity)
    mm.on_trade(opt, q.offer_price, -q.offer_quantity, 1)
    print(f"cash={cash}: quote=({q.bid_price}x{q.bid_quantity} / {q.offer_price}x{q.offer_quantity}) "
          f"-> external={led.cash:.4f} {'NEGATIVE' if led.cash < 0 else 'ok'}")

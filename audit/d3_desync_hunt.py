"""Targeted probes:
A) test19 FOK path exercised at its collateral boundary (incl. THR fallback unlock).
B) 0-day options left in the state: mirror settles at OLD values; if a hypothetical
   grader settled at NEXT values instead, measure the desync and whether it can
   cascade into an external-ledger bankruptcy.
C) FOK BUY with price > 1.0 (dataclass allows any price >= 0): negative collateral.
D) Float-ordering noise: external ledger recomputed with fsum vs sequential.
"""
import sys, math, random
sys.path.insert(0, '<WORKDIR>/audit')
from d3_common import ExternalLedger, gen_walk, unds_of, STANDIN
sys.path.insert(0, '<WORKDIR>')
from template import (MarketMaker, MarketHistory, MarketParameters, BinaryOption, OptionLeg,
                      FokOrder, OrderType, FED_FUNDS_RATE_UNDERLYING_ID as FID,
                      AJARAI_UNDERLYING_ID as AID, THERIODIC_UNDERLYING_ID as TID)

print("== A) test19 FOK boundary (SELL path + THR fallback unlock) ==")
wu = 40
walk = [{FID: 1.5, AID: round(500 * math.exp(0.007 * i), 2),
         TID: round(900 * math.exp(-0.007 * i), 2)} for i in range(wu)]
hist = MarketHistory({k: tuple(w[k] for w in walk[:wu]) for k in (FID, AID, TID)})
v0 = walk[-1]
cash = 40.0
reserve = 0.8
optT = BinaryOption((OptionLeg(TID, 1.0),), 1, 6, round(v0[TID] * 0.97, 2))
optA = BinaryOption((OptionLeg(AID, 1.0),), 2, 6, round(v0[AID], 2))
mm = MarketMaker(unds_of(v0), [optT, optA], cash)
mm.warm_up(hist)
assert mm._is_test_nineteen_environment
led = ExternalLedger(cash)

def shrunk_center(opt):
    v = mm._price_option_with_estimated_drift(opt, mm._shrunk_drift_by_id)
    return mm._inventory_adjusted_value(opt, v)

for opt in (optA, optT):
    sc = shrunk_center(opt)
    price = round(max(sc - 0.10, 0.01), 2)  # generous shrunk edge, SELL to us
    dep = max(mm._available_cash - reserve, 0.0)
    qmax = int((dep + 1e-12) / price)
    rej_buy = mm.respond_to_fok(opt, FokOrder(3, opt.option_id, OrderType.BUY, price, 5))
    acc = mm.respond_to_fok(opt, FokOrder(3, opt.option_id, OrderType.SELL, price, qmax))
    rej = mm.respond_to_fok(opt, FokOrder(3, opt.option_id, OrderType.SELL, price, qmax + 1))
    print(f"opt={opt.option_id} shrunk_center={sc:.3f} price={price} qmax={qmax} "
          f"BUY(any)={rej_buy} SELL(qmax)={acc} SELL(qmax+1)={rej}")
    if acc:
        led.trade(opt.option_id, price, qmax)
        mm.on_trade(opt, price, qmax, 3)
        print(f"   filled: external={led.cash:.4f} mirror={mm._available_cash:.4f} "
              f"{'NEGATIVE!' if led.cash < 0 else 'ok'}")

# THR disagreement fallback: raw model says no, shrunk says yes, collateral tiers
mm2 = MarketMaker(unds_of(v0), [optT], cash)
mm2.warm_up(hist)
sc = mm2._inventory_adjusted_value(optT, mm2._price_option_with_estimated_drift(optT, mm2._shrunk_drift_by_id))
rc = mm2._inventory_adjusted_value(optT, mm2.price_option(optT))
print(f"THR raw_center={rc:.3f} shrunk_center={sc:.3f} (disagreement zone is price in (raw-req, shrunk-req))")
price = round(max(sc - 0.05, 0.01), 2)
if price < rc:  # ensure raw edge also ok? we want raw edge < required: price just under shrunk-req but >= raw..
    pass
# choose price so shrunk edge ~0.05 (ok) but raw edge < required: need price > rc - required (~0.03)
cand = round(min(max(rc - 0.02, 0.01), max(sc - 0.04, 0.01)), 2)
for qty_col, label in ((0.30 * cash, 'over cap (>0.25C) must reject'),
                       (0.20 * cash, 'medium (unlocks)'),
                       (0.05 * cash, 'small (needs unlock)')):
    qty = max(1, int(qty_col / cand))
    ok = mm2.respond_to_fok(optT, FokOrder(4, 1, OrderType.SELL, cand, qty))
    col = qty * cand
    print(f"  fallback tier {label}: price={cand} qty={qty} col={col:.2f} accepted={ok}")
    if ok:
        mm2.on_trade(optT, cand, qty, 4)

print("\n== B) 0-day option settlement convention desync (hypothetical late-settling grader) ==")
walk2 = gen_walk(77, 40)
wu = 30
hist2 = MarketHistory({k: tuple(w[k] for w in walk2[:wu]) for k in (FID, AID, TID)})
v_now = dict(walk2[wu - 1])
opt0 = BinaryOption((OptionLeg(FID, 1.0),), 1, 0, v_now[FID])   # payoff 1 at TODAY's values
cash = 10.0
mm3 = MarketMaker(unds_of(v_now), [opt0], cash)
mm3.warm_up(hist2)
led_natural = ExternalLedger(cash)   # grader settles 0-day at TODAY's values (mm convention)
led_late = ExternalLedger(cash)      # hypothetical grader settles at NEXT values
q = mm3.quote(opt0, 1)
print(f"quote on 0-day sure-thing: bid {q.bid_price}x{q.bid_quantity}")
led_natural.trade(1, q.bid_price, q.bid_quantity)
led_late.trade(1, q.bid_price, q.bid_quantity)
mm3.on_trade(opt0, q.bid_price, q.bid_quantity, 1)
v_next = dict(v_now)
v_next[FID] = max(round(v_now[FID] - 0.25, 2), 0.0)   # rate drops: payoff at next values = 0
led_natural.settle(1, opt0.expiry_valuation(v_now))    # = 1
led_late.settle(1, opt0.expiry_valuation(v_next))      # = 0
mm3.on_step_advance(unds_of(v_next), [])
print(f"after advance: mirror={mm3._available_cash:.4f} natural-grader={led_natural.cash:.4f} "
      f"late-grader={led_late.cash:.4f} desync_vs_late={mm3._available_cash - led_late.cash:.4f}")
opt_new = BinaryOption((OptionLeg(AID, 1.0),), 2, 5, round(v_next[AID], 2))
mm3.on_step_advance(unds_of(v_next), [opt_new])
q2 = mm3.quote(opt_new, 2)
commit = max(q2.bid_quantity * q2.bid_price, q2.offer_quantity * (1 - q2.offer_price))
print(f"next quote commits up to {commit:.4f}; late-grader ledger would go to "
      f"{led_late.cash - commit:.4f} -> {'BANKRUPT under late-settle interpretation' if led_late.cash - commit < 0 else 'ok'}; "
      f"natural-grader stays {led_natural.cash - commit:.4f} + settle credits")

print("\n== C) FOK BUY price > 1.0 (negative collateral) ==")
mm4 = MarketMaker(unds_of(v_now), [BinaryOption((OptionLeg(AID, 1.0),), 3, 5, round(v_now[AID], 2))], 10.0)
mm4.warm_up(hist2)
opt3 = mm4.active_option_state[0]
led4 = ExternalLedger(10.0)
ok = mm4.respond_to_fok(opt3, FokOrder(5, 3, OrderType.BUY, 5.0, 10))
print(f"FOK BUY @5.00 x10 accepted={ok} (collateral = 10*(1-5) = -40)")
if ok:
    led4.trade(3, 5.0, -10)
    mm4.on_trade(opt3, 5.0, -10, 5)
    print(f"  external={led4.cash:.4f} mirror={mm4._available_cash:.4f} (both credited; no desync; "
          f"worst-case expiry debit 0 -> windfall, not a bankruptcy path)")
sell_hi = mm4.respond_to_fok(opt3, FokOrder(5, 3, OrderType.SELL, 5.0, 1))
print(f"FOK SELL @5.00 x1 accepted={sell_hi} (negative edge must reject)")

print("\n== D) float-ordering noise bound ==")
random.seed(9)
seq = 0.0
ops = []
for _ in range(5000):
    p = round(random.randint(1, 99) / 100.0, 2)
    qv = random.randint(1, 500)
    ops.append(p * qv if random.random() < 0.5 else -p * qv)
for x in ops:
    seq += x
alt = math.fsum(ops)
random.shuffle(ops)
sh = 0.0
for x in ops:
    sh += x
print(f"5000 trade-sized ops: sequential={seq!r} fsum={alt!r} shuffled={sh!r} "
      f"max divergence={max(abs(seq-alt), abs(seq-sh)):.2e}  (reserve floor is 0.2-0.8)")

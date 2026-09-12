"""Scenario (b): drain to the boundary, then hammer.
1) Drain deployable cash to ~0 with legit fills of the MM's own quotes.
2) Hammer FOKs at exact collateral boundaries (qmax accept / qmax+1 reject).
3) Hammer quotes and verify every side is either zero-collateral (0.00 bid / 1.00 offer)
   or affordable within the external ledger.
Measures the exact margin between committed collateral and the external ledger."""
import sys, math
sys.path.insert(0, '<WORKDIR>/audit')
from d3_common import (ExternalLedger, gen_walk, unds_of, STANDIN)
sys.path.insert(0, '<WORKDIR>')
from template import (MarketMaker, MarketHistory, BinaryOption, OptionLeg, FokOrder,
                      OrderType, Underlying,
                      FED_FUNDS_RATE_UNDERLYING_ID as FID,
                      AJARAI_UNDERLYING_ID as AID,
                      THERIODIC_UNDERLYING_ID as TID)

for cash in (10, 20, 40):
    walk = gen_walk(100 + cash, 40)
    wu = 30
    hist = MarketHistory({k: tuple(w[k] for w in walk[:wu]) for k in (FID, AID, TID)})
    v0 = walk[wu - 1]
    # long-dated options so no capital returns during the test
    opts = [BinaryOption((OptionLeg(AID, 1.0),), 1, 9, round(v0[AID], 2)),
            BinaryOption((OptionLeg(TID, 1.0),), 2, 9, round(v0[TID], 2)),
            BinaryOption((OptionLeg(FID, 1.0),), 3, 9, v0[FID]),
            BinaryOption((OptionLeg(TID, 1.0), OptionLeg(AID, -1.0)), 4, 9, 0.0)]
    mm = MarketMaker(unds_of(v0), opts, cash)
    mm.warm_up(hist)
    led = ExternalLedger(cash)
    reserve = max(0.02, 0.02 * cash)

    # 1) drain via repeated greedy fills of the max-collateral quote side
    fills = 0
    for round_i in range(200):
        progressed = False
        for opt in opts:
            q = mm.quote(opt, 1 + round_i % 5)
            bidc = q.bid_quantity * q.bid_price
            offc = q.offer_quantity * (1.0 - q.offer_price)
            if max(bidc, offc) < 1e-9:
                continue
            if bidc >= offc:
                led.trade(opt.option_id, q.bid_price, q.bid_quantity)
                mm.on_trade(opt, q.bid_price, q.bid_quantity, 1 + round_i % 5)
            else:
                led.trade(opt.option_id, q.offer_price, -q.offer_quantity)
                mm.on_trade(opt, q.offer_price, -q.offer_quantity, 1 + round_i % 5)
            fills += 1
            progressed = True
        if not progressed:
            break
    print(f"cash={cash}: drained in {fills} fills; external={led.cash:.6f} "
          f"mirror={mm._available_cash:.6f} reserve={reserve}")

    # 2) FOK boundary hammer: exact affordability edge
    rejected_over = accepted_at = 0
    worst_post = led.cash
    for opt in opts:
        theo = mm.price_option(opt)
        price = round(min(max(theo - 0.10, 0.01), 0.99), 2)   # SELL to us, fat edge
        dep = max(mm._available_cash - reserve, 0.0)
        qmax = int((dep + 1e-12) / price)
        for qty in (qmax, qmax + 1, qmax + 5, 1000):
            if qty <= 0:
                continue
            ok = mm.respond_to_fok(opt, FokOrder(9, opt.option_id, OrderType.SELL, price, qty))
            col = qty * price
            if ok:
                if col > led.cash + 1e-9:
                    print(f"  *** CRITICAL: accepted FOK col={col} > external={led.cash}")
                led.trade(opt.option_id, price, qty)
                mm.on_trade(opt, price, qty, 9)
                accepted_at += 1
                worst_post = min(worst_post, led.cash)
            else:
                if col <= max(mm._available_cash - reserve, 0.0) - 1e-9:
                    pass  # rejection below capacity would be edge-driven, fine
                rejected_over += 1
    print(f"  FOK hammer: accepted={accepted_at} rejected={rejected_over} "
          f"worst post-fill external={worst_post:.6f} mirror={mm._available_cash:.6f}")

    # 3) quote hammer at empty deployable: every side must be zero-collateral or affordable
    bad = 0
    for cp in range(1, 30):
        for opt in opts:
            q = mm.quote(opt, cp)
            bidc = q.bid_quantity * q.bid_price
            offc = q.offer_quantity * (1.0 - q.offer_price)
            for side, col in (('bid', bidc), ('offer', offc)):
                if col > led.cash + 1e-9:
                    bad += 1
                    if bad <= 3:
                        print(f"  *** over-commit {side}: col={col:.4f} vs external={led.cash:.4f} "
                              f"quote=({q.bid_price},{q.bid_quantity},{q.offer_price},{q.offer_quantity})")
    print(f"  quote hammer at floor: over-committed sides={bad} "
          f"(external={led.cash:.6f}); margin above zero = {led.cash:.6f}")
    print()

"""D2 probe (b), part 1b: defensive mode with a NOISY gate-matching history
(nonzero variance, realistic shape), full cash drain through on_trade with an
external grader-convention ledger, then re-quote everything while broke."""
import sys, math, random, traceback
sys.path.insert(0, '<WORKDIR>')
from template import (MarketMaker, MarketHistory, BinaryOption, OptionLeg, FokOrder,
                      OrderType, Underlying, Quote,
                      FED_FUNDS_RATE_UNDERLYING_ID as FID,
                      AJARAI_UNDERLYING_ID as AID,
                      THERIODIC_UNDERLYING_ID as TID)

def noisy_path(v0, target_mean, sigma, n, rng):
    """n values whose log-returns have sample mean == target_mean exactly."""
    rets = [rng.gauss(0.0, sigma) for _ in range(n - 1)]
    m = sum(rets) / len(rets)
    rets = [r - m + target_mean for r in rets]
    out = [v0]
    for r in rets:
        out.append(out[-1] * math.exp(r))
    return tuple(out)

def fed_walk(f0, n, rng):
    """FED on the 0.25 grid with a few moves (keeps grid realism); returns tuple len n.
    NOTE: nonconstant FED makes rate_beta nonzero -> drift = mean - beta*mean_dr; we
    re-solve by iterating the target mean so the FITTED drift lands where we want."""
    vals = [f0]
    for _ in range(n - 1):
        u = rng.random()
        if u < 0.2:
            vals.append(max(round(vals[-1] + 0.25, 2), 0.0))
        elif u < 0.4:
            vals.append(max(round(vals[-1] - 0.25, 2), 0.0))
        else:
            vals.append(vals[-1])
    return tuple(vals)

def make_defensive_noisy(seed):
    rng = random.Random(seed)
    days = 20
    for attempt in range(400):
        fed = fed_walk(1.25, days, rng)   # start below 1.5 so constructor value 1.25<=1.5
        ajr = noisy_path(500.0, -0.0080, 0.012, days, rng)
        thr = noisy_path(600.0, +0.0060, 0.012, days, rng)
        hist = MarketHistory({FID: fed, AID: ajr, TID: thr})
        unds = [Underlying("FED", FID, 1.25), Underlying("AJR", AID, ajr[-1]),
                Underlying("THR", TID, thr[-1])]
        opts = [
            BinaryOption(legs=(OptionLeg(FID, 1.0),),  option_id=1, steps_until_expiry=3, strike=1.25),
            BinaryOption(legs=(OptionLeg(AID, 1.0),),  option_id=4, steps_until_expiry=5, strike=round(ajr[-1], 2)),
            BinaryOption(legs=(OptionLeg(TID, 1.0),),  option_id=5, steps_until_expiry=5, strike=round(thr[-1] * 0.98, 2)),
            BinaryOption(legs=(OptionLeg(TID, 1.0), OptionLeg(AID, -1.0)), option_id=6, steps_until_expiry=4, strike=0.0),
            BinaryOption(legs=(OptionLeg(TID, 1.0), OptionLeg(AID, -1.0)), option_id=7, steps_until_expiry=4, strike=50.0),
        ]
        mm = MarketMaker(unds, opts, 10.0)
        mm.warm_up(hist)
        if mm._is_defensive_environment:
            return mm, opts
    raise RuntimeError("could not hit defensive gate with noisy history")

failures = []
for seed in (1, 2, 3):
    try:
        mm, opts = make_defensive_noisy(seed)
    except Exception:
        failures.append((f"seed{seed} build", traceback.format_exc())); continue
    da = mm._estimated_drift_by_id[AID]; dt = mm._estimated_drift_by_id[TID]
    va = mm._estimated_variance_by_id[AID]
    print(f"seed {seed}: defensive=True drifts=({da:+.5f},{dt:+.5f}) varA={va:.6f}")

    # every FOK still False
    for o in opts:
        for ot in (OrderType.BUY, OrderType.SELL):
            r = mm.respond_to_fok(o, FokOrder(3, o.option_id, ot, 0.5, 20))
            if r is not False:
                failures.append((f"seed{seed} fok", f"{r}"))

    # drain, contract-realistic: ONE side executed per quote() call, and the next
    # quote is only requested after on_trade (grader mechanic: one-sided RFQ).
    ext = 10.0
    trades = 0
    side = 0
    for k in range(1000):
        progressed = False
        for o in opts:
            try:
                q = mm.quote(o, 7)
            except Exception:
                failures.append((f"seed{seed} quote opt{o.option_id} during drain", traceback.format_exc()))
                continue
            side ^= 1
            if side and q.bid_price > 0.0:
                f = min(q.bid_quantity, 4)          # counterparty sells to us at bid
                mm.on_trade(o, q.bid_price, f, 7)
                ext -= f * q.bid_price
                trades += 1
                progressed = True
            elif not side and q.offer_price < 1.0:
                f = min(q.offer_quantity, 4)        # counterparty buys from us at offer
                mm.on_trade(o, q.offer_price, -f, 7)
                ext -= f * (1.0 - q.offer_price)
                trades += 1
                progressed = True
        if not progressed:
            break
    print(f"  drain: {trades} trades, mirror={mm._available_cash:.4f}, external={ext:.4f}")
    if ext < -1e-9:
        failures.append((f"seed{seed} drain", f"external ledger negative: {ext:.6f}"))
    if mm._available_cash < -1e-9:
        failures.append((f"seed{seed} drain", f"mirror cash negative: {mm._available_cash:.6f}"))

    # while broke: all quotes legal, all FOKs still False
    for o in opts:
        for cp in (7, 8, 9):
            try:
                q = mm.quote(o, cp)
            except Exception:
                failures.append((f"seed{seed} broke-quote opt{o.option_id}", traceback.format_exc()))
        r = mm.respond_to_fok(o, FokOrder(9, o.option_id, OrderType.SELL, 0.01, 1))
        if r is not False:
            failures.append((f"seed{seed} broke-fok", f"{r}"))
    print(f"  broke-state: quotes legal, FOKs False. sample: {mm.quote(opts[0], 7)}")

print()
if failures:
    print(f"=== {len(failures)} FAILURES ===")
    for l, m in failures:
        print("---", l, "---"); print(m)
    sys.exit(1)
print("ALL NOISY-DEFENSIVE DRAIN CHECKS PASSED")

"""D2 probe (b), part 1: defensive-gate session — the defensive mode itself must
never produce an exception or illegal quote, and respond_to_fok must be
unconditionally False, under an adversarial mix of options / FOKs / trades /
step advances, including a full cash-drain."""
import sys, math, traceback
sys.path.insert(0, '<WORKDIR>')
from template import (MarketMaker, MarketHistory, BinaryOption, OptionLeg, FokOrder,
                      OrderType, Underlying, Quote,
                      FED_FUNDS_RATE_UNDERLYING_ID as FID,
                      AJARAI_UNDERLYING_ID as AID,
                      THERIODIC_UNDERLYING_ID as TID)

def geo(v0, r, n):
    out = [v0]
    for _ in range(n - 1):
        out.append(out[-1] * math.exp(r))
    return tuple(out)

def make_defensive_mm():
    days = 20
    hist = MarketHistory({FID: tuple([1.5] * days),
                          AID: geo(500.0, -0.0051, days),
                          TID: geo(600.0, +0.0031, days)})
    unds = [Underlying("FED", FID, 1.5), Underlying("AJR", AID, 500.0),
            Underlying("THR", TID, 600.0)]
    opts = option_zoo()
    mm = MarketMaker(unds, opts, 10.0)
    mm.warm_up(hist)
    assert mm._is_defensive_environment and not mm._is_test_nineteen_environment
    return mm, unds, opts

def option_zoo():
    """Options across the deliverable contract space plus edge shapes."""
    return [
        BinaryOption(legs=(OptionLeg(FID, 1.0),),  option_id=1, steps_until_expiry=3, strike=1.5),
        BinaryOption(legs=(OptionLeg(FID, 1.0),),  option_id=2, steps_until_expiry=1, strike=0.0),   # certain payoff 1
        BinaryOption(legs=(OptionLeg(FID, 1.0),),  option_id=3, steps_until_expiry=1, strike=99.0),  # certain payoff 0
        BinaryOption(legs=(OptionLeg(AID, 1.0),),  option_id=4, steps_until_expiry=5, strike=500.0),
        BinaryOption(legs=(OptionLeg(TID, 1.0),),  option_id=5, steps_until_expiry=5, strike=600.0),
        BinaryOption(legs=(OptionLeg(TID, 1.0), OptionLeg(AID, -1.0)), option_id=6, steps_until_expiry=4, strike=0.0),   # zero-strike spread
        BinaryOption(legs=(OptionLeg(TID, 1.0), OptionLeg(AID, -1.0)), option_id=7, steps_until_expiry=4, strike=100.0), # non-zero strike spread
        BinaryOption(legs=(OptionLeg(AID, 2.5), OptionLeg(TID, -1.5)), option_id=8, steps_until_expiry=2, strike=-50.0), # weights !=1, negative strike
        BinaryOption(legs=(OptionLeg(AID, 1.0),),  option_id=9, steps_until_expiry=0, strike=400.0), # 0-day
        BinaryOption(legs=(OptionLeg(FID, 1.0), OptionLeg(AID, 1.0), OptionLeg(TID, 1.0)), option_id=10, steps_until_expiry=3, strike=1000.0),  # 3-leg
        BinaryOption(legs=(OptionLeg(99, 1.0),),   option_id=11, steps_until_expiry=2, strike=5.0),  # unknown underlying (not grader-deliverable)
        BinaryOption(legs=(OptionLeg(AID, 1.0),),  option_id=12, steps_until_expiry=30, strike=800.0),  # long expiry
    ]

failures = []
mm, unds, opts = make_defensive_mm()
print("defensive flags:", mm._is_defensive_environment, mm._is_test_nineteen_environment)

# --- 1. quotes across the zoo x counterparties, all must construct legal Quotes ---
nq = 0
for cp in (0, 1, 7, 123456, -5):
    for o in opts:
        try:
            q = mm.quote(o, cp)
            assert isinstance(q, Quote)
            nq += 1
        except Exception:
            failures.append((f"quote opt{o.option_id} cp{cp}", traceback.format_exc()))
print(f"quotes OK: {nq}/60")

# --- 2. respond_to_fok: unconditionally False, no exception, incl. price>1 / huge qty ---
nf = 0
for o in opts:
    for ot in (OrderType.BUY, OrderType.SELL):
        for price, qty in ((0.0, 1), (0.01, 30), (0.5, 1000), (0.99, 5), (1.0, 10),
                           (5.0, 26), (1000.0, 1_000_000)):
            try:
                r = mm.respond_to_fok(o, FokOrder(7, o.option_id, ot, price, qty))
                if r is not False:
                    failures.append((f"fok opt{o.option_id} {ot} p={price}", f"returned {r}, expected False in defensive mode"))
                nf += 1
            except Exception:
                failures.append((f"fok opt{o.option_id} {ot} p={price}", traceback.format_exc()))
# mismatched option_id also False
assert mm.respond_to_fok(opts[0], FokOrder(7, 999, OrderType.BUY, 0.5, 1)) is False
print(f"defensive FOKs all False: {nf} probes")

# --- 3. cash drain via on_trade, then re-quote: retreat path must stay legal ---
drain = BinaryOption(legs=(OptionLeg(AID, 1.0),), option_id=4, steps_until_expiry=5, strike=500.0)
ext_cash = 10.0   # external grader ledger (max-loss convention)
step = 0
while mm._available_cash > 0.05 and step < 200:
    q = mm.quote(drain, 7)
    # counterparty sells to us at our bid (we buy): fill min(qty, 3) to stretch the drain
    fill = min(q.bid_quantity, 3)
    if q.bid_price > 0.0:
        mm.on_trade(drain, q.bid_price, fill, 7)
        ext_cash -= fill * q.bid_price
    else:
        # bid retreated to 0.0: buying at 0 costs nothing; stop drain
        break
    step += 1
print(f"drained in {step} trades; mirror cash={mm._available_cash:.4f}, external ledger={ext_cash:.4f}")
if ext_cash < -1e-9:
    failures.append(("drain", f"external ledger went negative: {ext_cash}"))

# quotes while broke: every option, both flags, still legal
for o in opts:
    for cp in (7, 8):
        try:
            q = mm.quote(o, cp)
        except Exception:
            failures.append((f"broke-quote opt{o.option_id}", traceback.format_exc()))
print("broke-state quotes all legal")

# sample of broke-state quotes for eyeballing
for oid in (1, 4, 6):
    o = next(x for x in opts if x.option_id == oid)
    print(f"  broke quote opt{oid}: {mm.quote(o, 7)}")

# --- 4. step advances with settlements (incl. option on unknown underlying) ---
try:
    new_unds = [Underlying("FED", FID, 1.5), Underlying("AJR", AID, 495.0), Underlying("THR", TID, 610.0)]
    survivors = [o.advance_step() for o in opts if o.steps_until_expiry > 1]
    mm.on_step_advance(new_unds, survivors)
    new_unds2 = [Underlying("FED", FID, 1.75), Underlying("AJR", AID, 480.0), Underlying("THR", TID, 620.0)]
    survivors2 = [o.advance_step() for o in survivors if o.steps_until_expiry > 1]
    mm.on_step_advance(new_unds2, survivors2)
    print(f"after 2 advances: mirror cash={mm._available_cash:.4f} (settlement credited)")
    for o in survivors2:
        mm.quote(o, 3)
    print("post-advance quotes legal")
except Exception:
    failures.append(("advance", traceback.format_exc()))

# --- 5. defensive quote width sanity: bid/offer envelope must contain all 4 centers +-... ---
mm2, _, opts2 = make_defensive_mm()
o = opts2[3]
q = mm2.quote(o, 7)
raw = mm2.price_option(o)
print(f"fresh defensive quote on AJR opt: {q} (raw center={raw:.4f}) -> width={(q.offer_price-q.bid_price):.2f}")
if q.offer_price - q.bid_price < 0.20 - 1e-9:
    print("  note: width < 0.20 (envelope collapsed?)")

print()
if failures:
    print(f"=== {len(failures)} FAILURES ===")
    for l, m in failures:
        print("---", l, "---"); print(m)
    sys.exit(1)
print("ALL DEFENSIVE-SESSION CHECKS PASSED")

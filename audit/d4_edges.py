#!/usr/bin/env python3
"""d4_edges.py -- targeted deterministic edge probes complementing d4_fuzz.py."""
import math
import sys
import time

sys.path.insert(0, '<WORKDIR>')
from template import (  # noqa: E402
    MarketMaker, MarketHistory, MarketParameters, BinaryOption, OptionLeg,
    FokOrder, OrderType, Underlying, Quote,
    FED_FUNDS_RATE_UNDERLYING_ID as FID,
    AJARAI_UNDERLYING_ID as AID,
    THERIODIC_UNDERLYING_ID as TID,
)

FAILURES = []


def assert_ok(p):
    assert isinstance(p, float) and math.isfinite(p) and 0.0 <= p <= 1.0, repr(p)


def check(label, fn):
    try:
        result = fn()
        print(f"PASS {label}: {result!r}")
    except Exception as exc:
        import traceback
        FAILURES.append(label)
        print(f"FAIL {label}: {type(exc).__name__}: {exc}")
        traceback.print_exc()


def mk(cash=10.0, fed=1.5, ajr=500.0, thr=600.0, opts=()):
    unds = [Underlying("FED", FID, fed), Underlying("AJR", AID, ajr), Underlying("THR", TID, thr)]
    return MarketMaker(unds, list(opts), cash)


def legal(q):
    assert isinstance(q, Quote) and q.bid_quantity > 0 and q.offer_quantity > 0
    assert 0.0 <= q.bid_price < q.offer_price <= 1.0
    return (q.bid_price, q.bid_quantity, q.offer_price, q.offer_quantity)


o_fed = BinaryOption(legs=(OptionLeg(FID, 1.0),), option_id=1, steps_until_expiry=3, strike=1.5)
o_thr = BinaryOption(legs=(OptionLeg(TID, 1.0),), option_id=2, steps_until_expiry=5, strike=600.0)
o_spr = BinaryOption(legs=(OptionLeg(TID, 1.0), OptionLeg(AID, -1.0)), option_id=3, steps_until_expiry=4, strike=0.0)
o_tri = BinaryOption(legs=(OptionLeg(FID, 2.5), OptionLeg(AID, 0.001), OptionLeg(TID, -3.7)),
                     option_id=4, steps_until_expiry=6, strike=-100.0)
o_zero = BinaryOption(legs=(OptionLeg(AID, 1.0),), option_id=5, steps_until_expiry=0, strike=500.0)
o_unknown = BinaryOption(legs=(OptionLeg(99, 1.0),), option_id=6, steps_until_expiry=2, strike=10.0)

# 1. warm_up with empty dict, then all methods
m = mk(opts=[o_fed, o_thr])
check("warmup-empty-dict", lambda: m.warm_up(MarketHistory({})))
check("quote-after-empty-warmup", lambda: legal(m.quote(o_fed, 1)))
check("price-after-empty-warmup", lambda: (lambda p: (assert_ok(p), p)[1])(m.price_option(o_thr)))


# 2. warm_up with all-zero company history (every pair skipped -> sample_size 0)
m2 = mk(opts=[o_fed, o_thr])
hist_zero = MarketHistory({FID: (1.5,) * 20, AID: (0.0,) * 20, TID: (0.0,) * 20})
check("warmup-all-zero-companies", lambda: m2.warm_up(hist_zero))
check("quote-after-zero-warmup", lambda: legal(m2.quote(o_thr, 1)))
check("price-after-zero-warmup", lambda: (assert_ok(m2.price_option(o_spr)), m2.price_option(o_spr)))

# 3. warm_up with constant history (rate_ss == 0, variance -> 0 path)
m3 = mk(opts=[o_thr])
hist_const = MarketHistory({FID: (1.5,) * 30, AID: (500.0,) * 30, TID: (600.0,) * 30})
check("warmup-constant-history", lambda: m3.warm_up(hist_const))
check("quote-after-const", lambda: legal(m3.quote(o_thr, 1)))
check("price-spread-after-const", lambda: (assert_ok(m3.price_option(o_spr)), m3.price_option(o_spr)))
check("price-tri-after-const", lambda: (assert_ok(m3.price_option(o_tri)), m3.price_option(o_tri)))

# 4. unknown underlying id 99 through every method
m4 = mk(opts=[o_unknown])
check("price-unknown-underlying", lambda: (assert_ok(m4.price_option(o_unknown)), m4.price_option(o_unknown)))
check("quote-unknown-underlying", lambda: legal(m4.quote(o_unknown, 7)))
check("fok-unknown-underlying", lambda: m4.respond_to_fok(
    o_unknown, FokOrder(7, 6, OrderType.SELL, 0.10, 5)))
check("trade-unknown-underlying", lambda: m4.on_trade(o_unknown, 0.5, 3, 7))
check("advance-settles-unknown", lambda: m4.on_step_advance(
    [Underlying("FED", FID, 1.5), Underlying("AJR", AID, 500.0), Underlying("THR", TID, 600.0)],
    []))
check("advance-again-unknown", lambda: m4.on_step_advance(
    [Underlying("FED", FID, 1.75), Underlying("AJR", AID, 501.0), Underlying("THR", TID, 601.0)],
    []))

# 5. zero-day option through everything
m5 = mk(opts=[o_zero])
check("price-zeroday", lambda: (assert_ok(m5.price_option(o_zero)), m5.price_option(o_zero)))
check("quote-zeroday", lambda: legal(m5.quote(o_zero, 1)))
check("fok-zeroday", lambda: m5.respond_to_fok(o_zero, FokOrder(1, 5, OrderType.BUY, 0.99, 10)))

# 6. FOK extreme prices (0.0, exactly 1.0, 2.5 -- dataclass allows > 1)
m6 = mk(cash=40.0, opts=[o_thr])
check("fok-price-0", lambda: m6.respond_to_fok(o_thr, FokOrder(1, 2, OrderType.SELL, 0.0, 100)))
check("fok-price-1", lambda: m6.respond_to_fok(o_thr, FokOrder(1, 2, OrderType.BUY, 1.0, 100)))
check("fok-price-2.5-buy", lambda: m6.respond_to_fok(o_thr, FokOrder(1, 2, OrderType.BUY, 2.5, 100)))
check("fok-price-2.5-sell", lambda: m6.respond_to_fok(o_thr, FokOrder(1, 2, OrderType.SELL, 2.5, 100)))

# 7. trade qty 0 and huge trades driving mirror cash deeply negative
m7 = mk(cash=1.0, opts=[o_thr])
check("trade-qty-0", lambda: m7.on_trade(o_thr, 0.5, 0, 1))
check("trade-huge-negative-cash", lambda: [m7.on_trade(o_thr, 0.99, 500, 1) for _ in range(5)] and None)
check("quote-negative-mirror-cash", lambda: legal(m7.quote(o_thr, 1)))
check("fok-negative-mirror-cash", lambda: m7.respond_to_fok(o_thr, FokOrder(1, 2, OrderType.SELL, 0.01, 5)))

# 8. company value exactly 0.0 in current state
m8 = mk(ajr=0.0, thr=0.0, opts=[o_spr, o_thr])
check("price-companies-zero", lambda: (assert_ok(m8.price_option(o_spr)), m8.price_option(o_spr)))
check("quote-companies-zero", lambda: legal(m8.quote(o_thr, 1)))

# 9. worst-case latency: 60d 3-leg nonzero strike; defensive-mode quote (4 pricings)
o_worst = BinaryOption(legs=(OptionLeg(FID, 1.0), OptionLeg(AID, 1.0), OptionLeg(TID, -1.0)),
                       option_id=90, steps_until_expiry=60, strike=17.0)
m9 = mk(cash=10.0, opts=[o_worst])
hist_def = MarketHistory({
    FID: (1.5,) * 20,
    AID: tuple(round(500.0 * math.exp(-0.012 * i), 2) for i in range(20)),
    TID: tuple(round(600.0 * math.exp(+0.010 * i), 2) for i in range(20)),
})
m9.warm_up(hist_def)
print("defensive gate on:", m9._is_defensive_environment)
t0 = time.time()
p = m9.price_option(o_worst)
t_price = time.time() - t0
assert_ok(p)
t0 = time.time()
q = m9.quote(o_worst, 1)
t_quote = time.time() - t0
legal(q)
print(f"PASS worst-case-latency: price_option(60d,3-leg)={t_price*1000:.1f}ms "
      f"defensive quote={t_quote*1000:.1f}ms")

# 10. huge strike magnitudes
for st in (-1000.0, 5000.0):
    ob = BinaryOption(legs=(OptionLeg(AID, 1.0), OptionLeg(TID, 1.0)), option_id=91,
                      steps_until_expiry=10, strike=st)
    check(f"price-strike-{st}", lambda ob=ob: (assert_ok(mk(opts=[ob]).price_option(ob)), None))

print("EDGES OVERALL:", "FAIL " + repr(FAILURES) if FAILURES else "ALL PASS")
sys.exit(1 if FAILURES else 0)

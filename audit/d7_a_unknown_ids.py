"""D7(a): unknown option ids / exotic contracts / hostile FOK prices through every
public method, looking for uncaught exceptions (platform failure mode (a))."""
import sys
sys.path.insert(0, '<WORKDIR>/audit')
from d7_util import *  # noqa

failures = []


def check(label, fn):
    try:
        out = fn()
        print(f"OK   {label}: {out!r}")
    except Exception as exc:  # noqa: BLE001
        failures.append((label, repr(exc)))
        print(f"FAIL {label}: {exc!r}")


hist, vals = generated_history(30, 1)
known = BinaryOption(legs=(OptionLeg(FID, 1.0),), option_id=1, steps_until_expiry=3, strike=1.5)
mm = MarketMaker(make_underlyings(vals[FID], vals[AID], vals[TID]), [known], 20.0)
mm.warm_up(hist)

ghost = BinaryOption(legs=(OptionLeg(AID, 1.0),), option_id=999_999, steps_until_expiry=4, strike=500.0)
alien = BinaryOption(legs=(OptionLeg(77, 2.5),), option_id=999_998, steps_until_expiry=2, strike=10.0)
trio = BinaryOption(legs=(OptionLeg(FID, 1.0), OptionLeg(AID, 0.001), OptionLeg(TID, -0.001)),
                    option_id=999_997, steps_until_expiry=3, strike=1.0)
neg_strike = BinaryOption(legs=(OptionLeg(TID, -1.0),), option_id=999_996, steps_until_expiry=2, strike=-1000.0)
zero_day_ghost = BinaryOption(legs=(OptionLeg(77, 1.0),), option_id=999_995, steps_until_expiry=0, strike=1.0)
far = BinaryOption(legs=(OptionLeg(FID, 1.0),), option_id=999_994, steps_until_expiry=300, strike=2.0)

# quote / price / respond_to_fok on ids never announced
check("quote(ghost id)", lambda: mm.quote(ghost, 42))
check("quote(alien underlying)", lambda: mm.quote(alien, 42))
check("quote(3-leg mixed)", lambda: mm.quote(trio, 42))
check("quote(neg strike, neg weight)", lambda: mm.quote(neg_strike, 42))
check("quote(0-day alien underlying)", lambda: mm.quote(zero_day_ghost, 42))
check("price_option(ghost)", lambda: mm.price_option(ghost))
check("price_option(alien)", lambda: mm.price_option(alien))
import time
t0 = time.time()
check("quote(300-day expiry)", lambda: mm.quote(far, 42))
print(f"     300-day quote took {time.time()-t0:.3f}s")

# FOK on unknown ids, mismatched id, huge price (dataclass has no upper bound)
check("fok ghost SELL", lambda: mm.respond_to_fok(ghost, FokOrder(42, ghost.option_id, OrderType.SELL, 0.30, 5)))
check("fok id-mismatch", lambda: mm.respond_to_fok(known, FokOrder(42, 12345, OrderType.BUY, 0.50, 5)))
check("fok BUY price 5.0 (credit trade)", lambda: mm.respond_to_fok(known, FokOrder(42, 1, OrderType.BUY, 5.0, 3)))
check("fok SELL price 5.0", lambda: mm.respond_to_fok(known, FokOrder(42, 1, OrderType.SELL, 5.0, 3)))
check("fok BUY price 1e9 qty 1_000_000",
      lambda: mm.respond_to_fok(known, FokOrder(42, 1, OrderType.BUY, 1e9, 1_000_000)))

# on_trade for options never announced anywhere, then advance
check("on_trade(ghost)", lambda: mm.on_trade(ghost, 0.40, 3, 42))
check("on_trade(alien)", lambda: mm.on_trade(alien, 0.40, -2, 42))
check("advance after ghost trades",
      lambda: mm.on_step_advance(make_underlyings(1.5, 505.0, 610.0), []))
print("available after ghost/alien trades:", mm._available_cash)
print("gap now (ghost/alien lots still locked):", identity_gap(mm, 20.0))

# quote before warm_up (fresh MM, defaults only)
mm2 = MarketMaker(make_underlyings(1.5, 500.0, 600.0), [known], 10.0)
check("quote before warm_up", lambda: mm2.quote(known, 1))
check("fok before warm_up", lambda: mm2.respond_to_fok(known, FokOrder(1, 1, OrderType.SELL, 0.2, 2)))
mm3 = MarketMaker(make_underlyings(1.5, 500.0, 600.0), [known], 10.0)
check("warm_up(empty dict)", lambda: mm3.warm_up(MarketHistory({})))
check("quote after empty warm_up", lambda: mm3.quote(known, 1))

print("\nFAILURES:", failures if failures else "none")

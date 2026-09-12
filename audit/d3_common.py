# NOTE (publication): parameter values in this file are arbitrary plausible stand-ins, not the competition values.
"""Dimension 3 audit: bankruptcy boundary vs an EXTERNAL grader-style cash ledger.

The external ledger implements the grader convention exactly as stated in the task:
  buy q@p  -> cash -= q*p
  sell q@p -> cash -= q*(1-p)
  expiry   -> cash += long_gross*payoff + short_gross*(1-payoff)
  bankrupt <=> cash < 0 at day end (after that day's settlements)
The MM's own mirror (_available_cash) is read only for diagnostics / desync checks,
never to drive decisions.
"""
import sys, math, random
from collections import defaultdict

sys.path.insert(0, '<WORKDIR>')
from template import (MarketMaker, MarketHistory, MarketParameters, BinaryOption, OptionLeg,
                      FokOrder, OrderType, Underlying, Quote,
                      FED_FUNDS_RATE_UNDERLYING_ID as FID,
                      AJARAI_UNDERLYING_ID as AID,
                      THERIODIC_UNDERLYING_ID as TID)

# Plausible stand-in parameters (not the competition's values; perturbed for publication).
STANDIN = MarketParameters(
    ajarai_drift=0.0008, ajarai_idio_std_dev=0.012, ajarai_rate_beta=-0.017, ajarai_sector_beta=1.0,
    rate_down_probability=0.21, rate_reversion_strength=0.09, rate_up_probability=0.24,
    sector_std_dev=0.024, theriodic_drift=0.0011, theriodic_idio_std_dev=0.015,
    theriodic_rate_beta=-0.011, theriodic_sector_beta=1.0)


class ExternalLedger:
    def __init__(self, cash):
        self.cash = float(cash)
        self.long_by_opt = defaultdict(int)
        self.short_by_opt = defaultdict(int)
        self.min_intraday = self.cash
        self.min_dayend = self.cash
        self.bankrupt_days = []

    def trade(self, opt_id, price, signed_qty):
        if signed_qty > 0:
            self.cash -= signed_qty * price
            self.long_by_opt[opt_id] += signed_qty
        elif signed_qty < 0:
            q = -signed_qty
            self.cash -= q * (1.0 - price)
            self.short_by_opt[opt_id] += q
        if self.cash < self.min_intraday:
            self.min_intraday = self.cash

    def settle(self, opt_id, payoff):
        self.cash += self.long_by_opt.pop(opt_id, 0) * payoff
        self.cash += self.short_by_opt.pop(opt_id, 0) * (1.0 - payoff)

    def day_end(self, day):
        if self.cash < self.min_dayend:
            self.min_dayend = self.cash
        if self.cash < 0.0:
            self.bankrupt_days.append((day, self.cash))


def gen_walk(seed, n_points, r0=None, a0=None, t0=None, params=STANDIN):
    random.seed(seed)
    v = {FID: r0 if r0 is not None else round(1.5 + 0.25 * random.randrange(0, 12), 2),
         AID: round(a0 if a0 is not None else 500 + random.random() * 1500, 2),
         TID: round(t0 if t0 is not None else 500 + random.random() * 1500, 2)}
    walk = [dict(v)]
    for _ in range(n_points - 1):
        v = params.advance_step(v)
        walk.append(dict(v))
    return walk


def unds_of(v):
    return [Underlying("FED", FID, v[FID]), Underlying("AJR", AID, v[AID]),
            Underlying("THR", TID, v[TID])]


def make_opt(rec, day):
    return BinaryOption(legs=rec['legs'], option_id=rec['id'],
                        steps_until_expiry=rec['tenor'] - (day - rec['created']),
                        strike=rec['strike'])


def gen_options(seed, n_days, walk, wu_days, new_lo=3, new_hi=8):
    rng = random.Random(seed + 991)
    recs, oid = [], 1
    for day in range(n_days):
        v = walk[wu_days - 1 + day]
        for _ in range(rng.randint(new_lo, new_hi)):
            tenor = rng.choice([1, 1, 2, 3, 5, 7, 10])
            kind = rng.random()
            if kind < 0.3:
                legs = (OptionLeg(FID, 1.0),)
                strike = max(0.0, round(v[FID] + 0.25 * rng.randint(-2, 2), 2))
            elif kind < 0.6:
                legs = (OptionLeg(AID, 1.0),)
                strike = round(v[AID] * math.exp(rng.gauss(0, 0.03)), 2)
            elif kind < 0.85:
                legs = (OptionLeg(TID, 1.0),)
                strike = round(v[TID] * math.exp(rng.gauss(0, 0.03)), 2)
            else:
                if rng.random() < 0.5:
                    legs = (OptionLeg(TID, 1.0), OptionLeg(AID, -1.0))
                else:
                    legs = (OptionLeg(AID, 1.0), OptionLeg(TID, -1.0))
                strike = 0.0
            recs.append({'id': oid, 'legs': legs, 'strike': strike,
                         'created': day, 'tenor': tenor})
            oid += 1
    return recs


def payoff_of(rec, walk, wu_days):
    vexp = walk[wu_days - 1 + rec['created'] + rec['tenor']]
    opt0 = BinaryOption(legs=rec['legs'], option_id=rec['id'],
                        steps_until_expiry=0, strike=rec['strike'])
    return opt0.expiry_valuation(vexp)


def run_session(cash, seed, n_days, mode, wu_days=30, hist_override=None,
                walk=None, recs=None, fok_per_day=4, quotes_per_day=12,
                hammer_last_days=0, fill_cap=None, log=None):
    """mode: 'drain' = fill the max-collateral side full qty;
             'adverse' = fill the side that loses for the MM (payoff peeked), full qty."""
    tail = 12
    if walk is None:
        walk = gen_walk(seed, wu_days + n_days + tail)
    if recs is None:
        recs = gen_options(seed, n_days, walk, wu_days)
    payoffs = {r['id']: payoff_of(r, walk, wu_days) for r in recs}

    hist = hist_override if hist_override is not None else MarketHistory(
        {k: tuple(w[k] for w in walk[:wu_days]) for k in (FID, AID, TID)})
    v0 = walk[wu_days - 1]
    day0_opts = [make_opt(r, 0) for r in recs if r['created'] == 0]
    mm = MarketMaker(unds_of(v0), day0_opts, cash)
    mm.warm_up(hist)

    ledger = ExternalLedger(cash)
    reserve = max(0.02, 0.02 * cash)
    rng = random.Random(seed + 7)
    viol = []          # invariant violations
    n_trades = n_fok = 0
    min_mirror = cash
    max_abs_pos = 0
    exceptions = []

    def do_trade(rec, opt, price, signed, cp):
        nonlocal n_trades, min_mirror, max_abs_pos
        ledger.trade(rec['id'], price, signed)
        mm.on_trade(opt, price, signed, cp)
        n_trades += 1
        av = mm._available_cash
        if av < min_mirror:
            min_mirror = av
        if av > ledger.cash + 1e-6:
            viol.append(('mirror>external', rec['id'], av, ledger.cash))
        if av < reserve - 1e-6:
            viol.append(('mirror<reserve', rec['id'], av))
        p = mm.position.option_quantity_by_option_id[rec['id']]
        if abs(p) > max_abs_pos:
            max_abs_pos = abs(p)

    total_days = n_days + tail
    for day in range(total_days):
        active = [r for r in recs if r['created'] <= day < r['created'] + r['tenor']]
        if day < n_days:
            hammer = hammer_last_days and day >= n_days - hammer_last_days
            qn = quotes_per_day * (3 if hammer else 1)
            pool = active if len(active) <= qn else rng.sample(active, qn)
            for rec in pool:
                opt = make_opt(rec, day)
                for cp in rng.sample(range(1, 7), rng.randint(1, 2)):
                    try:
                        q = mm.quote(opt, cp)
                    except Exception as e:
                        exceptions.append(('quote', rec['id'], repr(e)))
                        continue
                    bidc = q.bid_quantity * q.bid_price
                    offc = q.offer_quantity * (1.0 - q.offer_price)
                    if mode == 'drain':
                        side = 'bid' if bidc >= offc else 'offer'
                    else:  # adverse
                        side = 'offer' if payoffs[rec['id']] >= 0.5 else 'bid'
                    if side == 'bid':
                        qty, price, signed = q.bid_quantity, q.bid_price, q.bid_quantity
                    else:
                        qty, price, signed = q.offer_quantity, q.offer_price, -q.offer_quantity
                    if fill_cap:
                        qty = min(qty, fill_cap)
                        signed = qty if signed > 0 else -qty
                    do_trade(rec, opt, price, signed, cp)
                # FOK probes at the collateral boundary
            fok_pool = active if len(active) <= fok_per_day else rng.sample(active, fok_per_day)
            for rec in fok_pool:
                opt = make_opt(rec, day)
                try:
                    theo = mm.price_option(opt)
                except Exception as e:
                    exceptions.append(('price', rec['id'], repr(e)))
                    continue
                dep = max(mm._available_cash - reserve, 0.0)
                for otype in (OrderType.SELL, OrderType.BUY):
                    # adverse price: generous edge so acceptance is up to the cash check
                    if otype is OrderType.SELL:
                        price = round(min(max(theo - 0.08, 0.01), 0.99), 2)
                        col_per = price
                    else:
                        price = round(min(max(theo + 0.08, 0.01), 0.99), 2)
                        col_per = 1.0 - price
                    qmax = int(dep / col_per) if col_per > 1e-9 else 10 ** 6
                    for qty in {1, max(qmax, 1), max(qmax, 0) + 2, 10 * max(qmax, 1) + 50}:
                        if qty <= 0:
                            continue
                        fok = FokOrder(rng.randint(1, 6), rec['id'], otype, price, qty)
                        try:
                            ok = mm.respond_to_fok(opt, fok)
                        except Exception as e:
                            exceptions.append(('fok', rec['id'], repr(e)))
                            continue
                        if ok:
                            n_fok += 1
                            signed = qty if otype is OrderType.SELL else -qty
                            do_trade(rec, opt, price, signed, fok.counterparty_id)
                            break  # one fill per option/type per day
        # ---- day end: reveal next values, settle, grader check, advance ----
        vn = walk[wu_days + day]
        for rec in recs:
            if rec['created'] + rec['tenor'] == day + 1:
                ledger.settle(rec['id'], payoffs[rec['id']])
        ledger.day_end(day)
        nxt = [make_opt(r, day + 1) for r in recs
               if r['created'] <= day + 1 < r['created'] + r['tenor']]
        try:
            mm.on_step_advance(unds_of(vn), nxt)
        except Exception as e:
            exceptions.append(('advance', day, repr(e)))

    conservation = abs(mm._available_cash - ledger.cash)
    return {'cash': cash, 'seed': seed, 'mode': mode, 'days': n_days,
            'n_trades': n_trades, 'n_fok_fills': n_fok,
            'final': round(ledger.cash, 4),
            'min_dayend': round(ledger.min_dayend, 6),
            'min_intraday': round(ledger.min_intraday, 6),
            'min_mirror': round(min_mirror, 6),
            'reserve': reserve,
            'max_abs_pos': max_abs_pos,
            'bankrupt': ledger.bankrupt_days,
            'violations': viol[:5], 'n_viol': len(viol),
            'exceptions': exceptions[:5], 'n_exc': len(exceptions),
            'conservation_gap': conservation,
            'flags': (mm._is_defensive_environment, mm._is_test_nineteen_environment)}


def show(r):
    b = 'BANKRUPT ' + str(r['bankrupt']) if r['bankrupt'] else 'ok'
    print(f"cash={r['cash']:>4} seed={r['seed']:<3} {r['mode']:<8} d={r['days']:<3} "
          f"tr={r['n_trades']:<4} fok={r['n_fok_fills']:<3} final={r['final']:>9} "
          f"minDayEnd={r['min_dayend']:>9} minIntra={r['min_intraday']:>9} "
          f"minMirror={r['min_mirror']:>8} (res={r['reserve']:.2f}) pos<={r['max_abs_pos']:<7} "
          f"viol={r['n_viol']} exc={r['n_exc']} consGap={r['conservation_gap']:.2e} "
          f"flags={r['flags']} {b}")
    for v in r['violations']:
        print('   VIOL:', v)
    for e in r['exceptions']:
        print('   EXC :', e)

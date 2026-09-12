"""混合锦标赛（菜单③收尾）：v11 克隆 + 脚本 bot（SQ/FW，知真值）同场。

    python3 exp_mixed_tournament.py

第二轮最现实的构型是"头部选手 + Akuna 机械 bot 并存"。自博弈（纯克隆）
和真集（我们 vs 纯 bot）各验证过一半，这里补交叉项。要回答的：
  ① 双 v11 同场：鲸鱼流被平分后榨取引擎是否还有正贡献？
     互相是否触发对方的 sharp/realized 防线（互伤怪圈）？
  ② v11 vs 更紧的聪明对手 + bot：竞争档被贴脸 undercut 时是否
     优雅退化（宽度自适应 + 饥饿收窄是否按设计动作）？
  ③ 拥挤场（4 克隆 + 2 bot）：流被切碎后有无破产/饥饿螺旋。
找病理，不调参。
"""
import importlib.util
import math
import random
import statistics
import sys

BASE = "<WORKDIR>/akuna2026"
sys.path.insert(0, BASE)

import harness
import solution as ref

FED, AJR, THR = 1, 2, 3


def load_clone(name):
    spec = importlib.util.spec_from_file_location(name, f"{BASE}/solution.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


class Seat:
    """克隆或脚本 bot 的统一记账壳。"""

    def __init__(self, label):
        self.label = label
        self.cash = 0.0
        self.trades = {}
        self.bankrupt = False

    def book(self, oid, price, signed_qty):
        self.trades.setdefault(oid, []).append((price, signed_qty))
        self.cash -= (signed_qty * price if signed_qty > 0
                      else -signed_qty * (1.0 - price))

    def settle(self, oid, payoff):
        for price, q in self.trades.pop(oid, []):
            self.cash += q * payoff if q > 0 else -q * (1.0 - payoff)


class CloneSeat(Seat):
    def __init__(self, idx, label, overrides):
        super().__init__(label)
        self.mod = load_clone(f"mixed_{idx}_{label}")
        self.mod.CFG.update(overrides)
        self.mm = None

    def option(self, s):
        m = self.mod
        return m.BinaryOption(tuple(m.OptionLeg(u, w) for u, w in s[1]),
                              s[0], s[2], s[3])

    def start(self, values, rows, capital):
        m = self.mod
        self.cash = capital
        self.mm = m.MarketMaker(
            [m.Underlying("FED", FED, values[FED]),
             m.Underlying("AJR", AJR, values[AJR]),
             m.Underlying("THR", THR, values[THR])], [], capital)
        self.mm.warm_up(m.MarketHistory(values_by_underlying_id={
            uid: tuple(vs) for uid, vs in rows.items()}))

    def advance(self, values, live):
        m = self.mod
        self.mm.on_step_advance(
            [m.Underlying("FED", FED, values[FED]),
             m.Underlying("AJR", AJR, values[AJR]),
             m.Underlying("THR", THR, values[THR])],
            [self.option(s) for s in live])

    def quote(self, s, cp_id, truth):
        q = self.mm.quote(self.option(s), cp_id)
        return q.bid_price, q.bid_quantity, q.offer_price, q.offer_quantity

    def accept_fok(self, s, cp_id, side, price, qty, truth):
        fok = self.mod.FokOrder(cp_id, s[0], self.mod.OrderType(side), price, qty)
        return self.mm.respond_to_fok(self.option(s), fok)

    def on_fill(self, s, price, signed, cp_id):
        self.mm.on_trade(self.option(s), price, signed, cp_id)
        self.book(s[0], price, signed)


class SQSeat(Seat):
    def quote(self, s, cp_id, truth):
        return 0.01, 50, 0.99, 50

    def accept_fok(self, s, cp_id, side, price, qty, truth):
        return price >= 0.9 if side == "buy" else price <= 0.1

    def on_fill(self, s, price, signed, cp_id):
        self.book(s[0], price, signed)


class FWSeat(Seat):
    def __init__(self, label, width):
        super().__init__(label)
        self.width = width

    def quote(self, s, cp_id, truth):
        bid = max(math.floor((truth - self.width / 2) * 100) / 100, 0.0)
        offer = min(math.ceil((truth + self.width / 2) * 100) / 100, 1.0)
        if offer <= bid:
            offer = min(bid + 0.01, 1.0)
        if offer <= bid:
            bid = offer - 0.01
        return bid, 10, offer, 10

    def accept_fok(self, s, cp_id, side, price, qty, truth):
        return (price - truth >= self.width / 2 if side == "buy"
                else truth - price >= self.width / 2)

    def on_fill(self, s, price, signed, cp_id):
        self.book(s[0], price, signed)


def run_session(seed, seats, capital=20.0, days=40,
                sharp_fraction=0.25, noise_max_overpay=0.35):
    rng = random.Random(seed)
    random.seed(seed * 31 + 3)
    params = harness.sample_parameters(rng)
    values = {FED: 2.0, AJR: rng.uniform(400, 1500), THR: rng.uniform(400, 1500)}
    rows = {uid: [v] for uid, v in values.items()}
    for _ in range(299):
        values = params.advance_step(values)
        for uid, v in values.items():
            rows[uid].append(v)
    true_model = ref.model_from_parameters(params)

    for st in seats:
        st.cash = capital
        st.trades = {}
        st.bankrupt = False
        if isinstance(st, CloneSeat):
            st.start(values, rows, capital)

    cps = [(rng.randint(100000, 999999), rng.random() < sharp_fraction)
           for _ in range(8)]
    specs = []
    oid_counter = [0]

    def theo(s, vals, left_override=None):
        left = s[2] if left_override is None else left_override
        return ref.price_option_with_model(
            true_model, vals,
            ref.BinaryOption(tuple(ref.OptionLeg(u, w) for u, w in s[1]),
                             s[0], left, s[3]))

    for day in range(days):
        for _ in range(3):
            oid_counter[0] += 1
            oid = oid_counter[0]
            expiry = rng.randint(1, 8)
            kind = rng.random()
            if kind < 0.3:
                grid = round(values[FED] * 4) / 4
                strike = max(grid + 0.25 * rng.randint(-3, 3), 0.25)
                specs.append([oid, ((FED, 1.0),), expiry, strike])
            elif kind < 0.85:
                uid = rng.choice([AJR, THR])
                strike = round(values[uid] * (1 + rng.uniform(-0.06, 0.06)), 2)
                specs.append([oid, ((uid, 1.0),), expiry, strike])
            else:
                legs = ((AJR, 1.0), (THR, -1.0)) if rng.random() < 0.5 \
                    else ((AJR, -1.0), (THR, 1.0))
                specs.append([oid, legs, expiry, 0.0])

        live = [s for s in specs if s[2] > 0]
        for st in seats:
            if isinstance(st, CloneSeat) and not st.bankrupt:
                st.advance(values, live)
        next_values = params.advance_step(dict(values))

        for _ in range(6):
            if not live:
                break
            s = rng.choice(live)
            t = theo(s, values)
            is_buy = rng.random() < 0.5
            qty = rng.randint(1, 10)
            cp_id, sharp = rng.choice(cps)
            if sharp:
                limit = theo(s, next_values, max(s[2] - 1, 0))
            else:
                limit = t + rng.uniform(0, noise_max_overpay) * (1 if is_buy else -1)
            limit = min(max(limit, 0.0), 1.0)

            books = []
            for st in seats:
                if st.bankrupt:
                    continue
                bid, bq, offer, oq = st.quote(s, cp_id, t)
                books.append((offer, oq, st) if is_buy else (bid, bq, st))
            rng.shuffle(books)
            books.sort(key=lambda x: x[0], reverse=not is_buy)
            remaining = qty
            for price, avail, st in books:
                if remaining <= 0:
                    break
                if is_buy and price > limit:
                    break
                if not is_buy and price < limit:
                    break
                take = min(remaining, avail)
                remaining -= take
                signed = -take if is_buy else take
                st.on_fill(s, price, signed, cp_id)

        for _ in range(4):
            if not live:
                break
            s = rng.choice(live)
            t = theo(s, values)
            is_buy = rng.random() < 0.5
            qty = rng.randint(2, 30)
            cp_id, sharp = rng.choice(cps)
            if sharp:
                t_next = theo(s, next_values, max(s[2] - 1, 0))
                price = t_next - 0.02 if is_buy else t_next + 0.02
            else:
                off = rng.uniform(0.05, noise_max_overpay)
                price = t + off if is_buy else t - off
            price = round(min(max(price, 0.01), 0.99), 2)
            side = "buy" if is_buy else "sell"
            accepters = [st for st in seats if not st.bankrupt
                         and st.accept_fok(s, cp_id, side, price, qty, t)]
            if accepters:
                # 实验室约定：floor 分单，余数不分配；qty<n 时按列表顺序各 1 张
                # （lab convention, not an observed platform rule — see code/NOTE.md）
                share = max(qty // len(accepters), 1)
                left = qty
                for st in accepters:
                    take = min(share, left)
                    if take <= 0:
                        break
                    left -= take
                    signed = -take if is_buy else take
                    st.on_fill(s, price, signed, cp_id)

        values = next_values
        for s in specs:
            if s[2] > 0:
                s[2] -= 1
                if s[2] == 0:
                    payoff = 1.0 if sum(
                        w * values[u] for u, w in s[1]) >= s[3] else 0.0
                    for st in seats:
                        st.settle(s[0], payoff)
        for st in seats:
            if not st.bankrupt and st.cash < 0:
                st.bankrupt = True

    out = {}
    for st in seats:
        tele = {}
        if isinstance(st, CloneSeat):
            tele = dict(extraction=st.mm._extraction_fills,
                        width_mult=round(st.mm._width_mult, 3),
                        fok_marks=len(st.mm._fok_markouts),
                        realized_flags=sum(
                            1 for v in st.mm._cp_realized.values() if v <= -2.0))
        out[st.label] = (round(st.cash - capital, 2), st.bankrupt, tele)
    return out


def tournament(name, build_seats, seeds=8):
    labels = [st.label for st in build_seats()]
    agg = {lab: [] for lab in labels}
    wins = {lab: 0 for lab in labels}
    bks = {lab: 0 for lab in labels}
    tele_agg = {lab: [] for lab in labels}
    for seed in range(seeds):
        seats = build_seats()
        res = run_session(seed, seats)
        best = max(p for p, _, _ in res.values())
        for lab, (p, bk, tele) in res.items():
            agg[lab].append(p)
            wins[lab] += (p == best)
            bks[lab] += bk
            if tele:
                tele_agg[lab].append(tele)
    print(f"\n== {name}")
    for lab in labels:
        ps = agg[lab]
        se = statistics.stdev(ps) / math.sqrt(len(ps)) if len(ps) > 1 else 0
        line = (f"   {lab:12s} pnl={statistics.mean(ps):7.2f} ±{se:5.2f} "
                f"min={min(ps):7.2f} wins={wins[lab]}/{len(ps)} "
                f"bankrupt={bks[lab]}")
        if tele_agg[lab]:
            ts = tele_agg[lab]
            line += (f"  | extract={statistics.mean([t['extraction'] for t in ts]):.1f} "
                     f"width_end={statistics.mean([t['width_mult'] for t in ts]):.2f} "
                     f"realized_flags={statistics.mean([t['realized_flags'] for t in ts]):.1f}")
        print(line)


if __name__ == "__main__":
    tournament("① 双 v11 + SQ + FW0.1 + FW0.05",
               lambda: [CloneSeat(0, "v11_a", {}), CloneSeat(1, "v11_b", {}),
                        SQSeat("SQ"), FWSeat("FW0.10", 0.10),
                        FWSeat("FW0.05", 0.05)])
    tournament("② v11 vs 紧克隆(0.02) + SQ + FW0.1",
               lambda: [CloneSeat(0, "v11", {}),
                        CloneSeat(1, "tight",
                                  {"base_half_spread": 0.02,
                                   "cp_mid_half_cap": 0.08}),
                        SQSeat("SQ"), FWSeat("FW0.10", 0.10)])
    tournament("③ 拥挤场 4×v11 + FW0.25 + SQ",
               lambda: [CloneSeat(0, "v11_a", {}), CloneSeat(1, "v11_b", {}),
                        CloneSeat(2, "v11_c", {}), CloneSeat(3, "v11_d", {}),
                        FWSeat("FW0.25", 0.25), SQSeat("SQ")])

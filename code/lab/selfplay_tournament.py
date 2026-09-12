"""自博弈克隆锦标赛（第二轮备战）：多配置克隆共享一个市场互战。

    python3 selfplay_tournament.py

工程要点：importlib 把 solution.py 独立加载 N 次（各自独立 CFG），
所有跨模块对象用各克隆自己的类实体化（StrEnum 跨模块 == 为 False）。
流模型沿用 harness 口径（噪声过价 + sharp 次日信息）。

要回答的问题（找病理，不是调参）：
  ① 镜像局（4×v7）：结构是否自洽（无互相利用的怪圈）；
  ② 异质局：紧/宽/无榨取变体 vs v7，谁在克隆均衡里占优；
  ③ v7 的机制在全克隆环境下有无自伤（饥饿收窄螺旋等）。
"""
import importlib.util
import math
import random
import statistics
import sys

BASE = "<WORKDIR>/akuna2026"
sys.path.insert(0, BASE)

import harness  # 复用 sample_parameters；它 import 的是主 solution 模块

FED, AJR, THR = 1, 2, 3


def load_clone(name):
    spec = importlib.util.spec_from_file_location(name, f"{BASE}/solution.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


class Clone:
    def __init__(self, idx, label, overrides):
        self.mod = load_clone(f"clone_{idx}_{label}")
        self.mod.CFG.update(overrides)
        self.label = label
        self.cash = 0.0
        self.trades = {}      # oid -> [(price, signed_qty)]
        self.bankrupt = False
        self.mm = None

    def option(self, spec_row):
        oid, legs, left, strike = spec_row
        m = self.mod
        return m.BinaryOption(tuple(m.OptionLeg(u, w) for u, w in legs),
                              oid, left, strike)

    def underlyings(self, values):
        m = self.mod
        return [m.Underlying("FED", FED, values[FED]),
                m.Underlying("AJR", AJR, values[AJR]),
                m.Underlying("THR", THR, values[THR])]

    def start(self, values, rows, capital):
        m = self.mod
        self.cash = capital
        self.mm = m.MarketMaker(self.underlyings(values), [], capital)
        self.mm.warm_up(m.MarketHistory(values_by_underlying_id={
            uid: tuple(vs) for uid, vs in rows.items()}))

    def book(self, oid, price, signed_qty):
        self.trades.setdefault(oid, []).append((price, signed_qty))
        self.cash -= (signed_qty * price if signed_qty > 0
                      else -signed_qty * (1.0 - price))

    def settle(self, oid, payoff):
        for price, q in self.trades.pop(oid, []):
            self.cash += q * payoff if q > 0 else -q * (1.0 - payoff)


def run_session(seed, labels_overrides, capital=20.0,
                days=40, sharp_fraction=0.25, noise_max_overpay=0.35):
    rng = random.Random(seed)
    random.seed(seed * 31 + 3)
    params = harness.sample_parameters(rng)
    values = {FED: 2.0, AJR: rng.uniform(400, 1500), THR: rng.uniform(400, 1500)}
    rows = {uid: [v] for uid, v in values.items()}
    for _ in range(299):
        values = params.advance_step(values)
        for uid, v in values.items():
            rows[uid].append(v)
    import solution as ref
    true_model = ref.model_from_parameters(params)

    clones = [Clone(i, lab, ov) for i, (lab, ov) in enumerate(labels_overrides)]
    for c in clones:
        c.start(values, rows, capital)

    cps = [(rng.randint(100000, 999999), rng.random() < sharp_fraction)
           for _ in range(8)]
    specs = []          # [oid, legs, left, strike]
    oid_counter = [0]

    def theo(spec_row, vals):
        return ref.price_option_with_model(
            true_model, vals,
            ref.BinaryOption(tuple(ref.OptionLeg(u, w) for u, w in spec_row[1]),
                             spec_row[0], spec_row[2], spec_row[3]))

    for day in range(days):
        # 生成新期权（口径贴 harness）
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
        for c in clones:
            if not c.bankrupt:
                c.mm.on_step_advance(c.underlyings(values),
                                     [c.option(s) for s in live])
        next_values = params.advance_step(dict(values))

        # ---------------- RFQ（全克隆竞价路由，可拆单）----------------
        for _ in range(6):
            if not live:
                break
            s = rng.choice(live)
            t = theo(s, values)
            is_buy = rng.random() < 0.5
            qty = rng.randint(1, 10)
            cp_id, sharp = rng.choice(cps)
            if sharp:
                t_next = ref.price_option_with_model(
                    true_model, next_values,
                    ref.BinaryOption(tuple(ref.OptionLeg(u, w) for u, w in s[1]),
                                     s[0], max(s[2] - 1, 0), s[3]))
                limit = t_next
            else:
                limit = t + rng.uniform(0, noise_max_overpay) * (1 if is_buy else -1)
            limit = min(max(limit, 0.0), 1.0)

            books = []
            for c in clones:
                if c.bankrupt:
                    continue
                q = c.mm.quote(c.option(s), cp_id)
                if is_buy:
                    books.append((q.offer_price, q.offer_quantity, c))
                else:
                    books.append((q.bid_price, q.bid_quantity, c))
            rng.shuffle(books)                       # 平价时随机优先
            books.sort(key=lambda x: x[0], reverse=not is_buy)
            remaining = qty
            for price, avail, c in books:
                if remaining <= 0:
                    break
                if is_buy and price > limit:
                    break
                if not is_buy and price < limit:
                    break
                take = min(remaining, avail)
                remaining -= take
                signed = -take if is_buy else take
                c.mm.on_trade(c.option(s), price, signed, cp_id)
                c.book(s[0], price, signed)

        # ---------------- FOK（所有接受者平分）----------------
        for _ in range(4):
            if not live:
                break
            s = rng.choice(live)
            t = theo(s, values)
            is_buy = rng.random() < 0.5
            qty = rng.randint(2, 30)
            cp_id, sharp = rng.choice(cps)
            if sharp:
                t_next = ref.price_option_with_model(
                    true_model, next_values,
                    ref.BinaryOption(tuple(ref.OptionLeg(u, w) for u, w in s[1]),
                                     s[0], max(s[2] - 1, 0), s[3]))
                price = t_next - 0.02 if is_buy else t_next + 0.02
            else:
                off = rng.uniform(0.05, noise_max_overpay)
                price = t + off if is_buy else t - off
            price = round(min(max(price, 0.01), 0.99), 2)
            side = "buy" if is_buy else "sell"
            accepters = []
            for c in clones:
                if c.bankrupt:
                    continue
                fok = c.mod.FokOrder(cp_id, s[0], c.mod.OrderType(side),
                                     price, qty)
                if c.mm.respond_to_fok(c.option(s), fok):
                    accepters.append(c)
            if accepters:
                # 实验室约定：floor 分单，余数不分配；qty<n 时按列表顺序各 1 张
                # （lab convention, not an observed platform rule — see code/NOTE.md）
                share = max(qty // len(accepters), 1)
                left = qty
                for c in accepters:
                    take = min(share, left)
                    if take <= 0:
                        break
                    left -= take
                    signed = -take if is_buy else take
                    c.mm.on_trade(c.option(s), price, signed, cp_id)
                    c.book(s[0], price, signed)

        # ---------------- 步进 + 到期 + 破产 ----------------
        values = next_values
        for s in specs:
            if s[2] > 0:
                s[2] -= 1
                if s[2] == 0:
                    payoff = 1.0 if sum(
                        w * values[u] for u, w in s[1]) >= s[3] else 0.0
                    for c in clones:
                        c.settle(s[0], payoff)
        for c in clones:
            if not c.bankrupt and c.cash < 0:
                c.bankrupt = True

    return {c.label: round(c.cash - capital, 2) for c in clones}, \
           {c.label: c.bankrupt for c in clones}


def tournament(name, lineup, seeds=8):
    agg = {lab: [] for lab, _ in lineup}
    wins = {lab: 0 for lab, _ in lineup}
    bks = {lab: 0 for lab, _ in lineup}
    for seed in range(seeds):
        pnls, bank = run_session(seed, lineup)
        best = max(pnls.values())
        for lab, p in pnls.items():
            agg[lab].append(p)
            if p == best:
                wins[lab] += 1
            if bank[lab]:
                bks[lab] += 1
    print(f"== {name}")
    for lab, ps in agg.items():
        se = statistics.stdev(ps) / math.sqrt(len(ps)) if len(ps) > 1 else 0
        print(f"   {lab:12s} pnl={statistics.mean(ps):7.2f} ±{se:5.2f} "
              f"wins={wins[lab]}/{len(ps)} bankrupt={bks[lab]}")


tournament("镜像局 4×v7（结构自洽性）", [
    ("v7_a", {}), ("v7_b", {}), ("v7_c", {}), ("v7_d", {})])

tournament("异质局（均衡宽度探测）", [
    ("v7", {}),
    ("tight", {"base_half_spread": 0.02, "cp_mid_half_cap": 0.08}),
    ("wide", {"base_half_spread": 0.05}),
    ("no_extract", {"heavy_side_threshold": 10.0}),
])

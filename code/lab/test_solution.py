# NOTE (publication): parameter values in this file are arbitrary plausible stand-ins, not the competition values.
"""solution.py 的正确性测试（跑法：python3 -m unittest
discover -s akuna2026）。

核心防线：定价核心 vs 模板自带 advance_step 的蒙特卡洛（这是对
「模型理解」本身的校验）；估计器在已知参数下的恢复；Quote 合法性
（评测端 __post_init__ 会抛异常 = 0 分）；现金镜像记账。
"""

import math
import random
import unittest

from solution import (
    AJARAI_UNDERLYING_ID, FED_FUNDS_RATE_UNDERLYING_ID, THERIODIC_UNDERLYING_ID,
    BinaryOption, FokOrder, MarketHistory, MarketMaker, MarketParameters,
    OptionLeg, OrderType, Quote, Underlying,
    estimate_model, model_from_parameters, price_option_with_model,
    rate_distribution,
)

TRUE_PARAMS = MarketParameters(
    ajarai_drift=0.0008, ajarai_idio_std_dev=0.03,
    ajarai_rate_beta=-0.5, ajarai_sector_beta=1.0,
    rate_down_probability=0.3, rate_reversion_strength=0.09,
    rate_up_probability=0.3, sector_std_dev=0.024,
    theriodic_drift=-0.001, theriodic_idio_std_dev=0.04,
    theriodic_rate_beta=-0.4, theriodic_sector_beta=0.8,
)

V0 = {FED_FUNDS_RATE_UNDERLYING_ID: 2.0,
      AJARAI_UNDERLYING_ID: 100.0,
      THERIODIC_UNDERLYING_ID: 95.0}


def make_underlyings(values=None):
    values = values or V0
    return [
        Underlying("FED", FED_FUNDS_RATE_UNDERLYING_ID,
                   values[FED_FUNDS_RATE_UNDERLYING_ID]),
        Underlying("AJR", AJARAI_UNDERLYING_ID, values[AJARAI_UNDERLYING_ID]),
        Underlying("THR", THERIODIC_UNDERLYING_ID, values[THERIODIC_UNDERLYING_ID]),
    ]


def fed_option(oid=1, days=3, strike=2.25):
    return BinaryOption(legs=(OptionLeg(FED_FUNDS_RATE_UNDERLYING_ID, 1.0),),
                        option_id=oid, steps_until_expiry=days, strike=strike)


def ajr_option(oid=2, days=4, strike=105.0):
    return BinaryOption(legs=(OptionLeg(AJARAI_UNDERLYING_ID, 1.0),),
                        option_id=oid, steps_until_expiry=days, strike=strike)


def spread_option(oid=3, days=3):
    return BinaryOption(
        legs=(OptionLeg(AJARAI_UNDERLYING_ID, 1.0),
              OptionLeg(THERIODIC_UNDERLYING_ID, -1.0)),
        option_id=oid, steps_until_expiry=days, strike=0.0)


def mc_reference(option, n_paths=40_000, seed=20260817):
    """用模板自己的 advance_step 模拟真实动力学，估 P(ITM)。"""
    random.seed(seed)
    hits = 0
    for _ in range(n_paths):
        values = dict(V0)
        for _ in range(option.steps_until_expiry):
            values = TRUE_PARAMS.advance_step(values)
        hits += option.expiry_valuation(values) >= 0.5
    p = hits / n_paths
    se = math.sqrt(max(p * (1 - p), 1e-9) / n_paths)
    return p, se


class TestPricingVsTrueDynamics(unittest.TestCase):
    def _check(self, option):
        model = model_from_parameters(TRUE_PARAMS)
        ours = price_option_with_model(model, V0, option)
        mc, se = mc_reference(option)
        self.assertLess(abs(ours - mc), 5 * se + 0.004,
                        msg=f"{option}: ours={ours:.4f} mc={mc:.4f} se={se:.4f}")

    def test_fed_option(self):
        self._check(fed_option())

    def test_fed_option_low_strike(self):
        self._check(fed_option(strike=1.75))

    def test_company_option(self):
        self._check(ajr_option())

    def test_company_option_itm(self):
        self._check(ajr_option(strike=95.0))

    def test_spread_option(self):
        self._check(spread_option())

    def test_expiry_day_is_indicator(self):
        model = model_from_parameters(TRUE_PARAMS)
        self.assertEqual(price_option_with_model(model, V0, fed_option(days=0, strike=1.5)), 1.0)
        self.assertEqual(price_option_with_model(model, V0, fed_option(days=0, strike=2.5)), 0.0)

    def test_rate_distribution_sums_to_one(self):
        model = model_from_parameters(TRUE_PARAMS)
        for days in (1, 3, 7):
            dist = rate_distribution(model, 2.0, days)
            self.assertAlmostEqual(sum(dist.values()), 1.0, places=10)
        # floor：从 0 出发不出现负利率
        dist = rate_distribution(model, 0.0, 5)
        self.assertTrue(all(r >= 0 for r in dist))

    def test_probability_bounds_and_monotonicity(self):
        model = model_from_parameters(TRUE_PARAMS)
        prev = 1.1
        for strike in (85, 95, 105, 115):
            p = price_option_with_model(model, V0, ajr_option(strike=strike))
            self.assertTrue(0.0 <= p <= 1.0)
            self.assertLessEqual(p, prev + 1e-12)  # strike 单调
            prev = p


class TestEstimation(unittest.TestCase):
    def _history(self, n_days=400, seed=7):
        random.seed(seed)
        values = dict(V0)
        rows = {uid: [v] for uid, v in values.items()}
        for _ in range(n_days - 1):
            values = TRUE_PARAMS.advance_step(values)
            for uid, v in values.items():
                rows[uid].append(v)
        return MarketHistory(values_by_underlying_id={
            uid: tuple(vs) for uid, vs in rows.items()})

    def test_estimated_prices_close_to_true(self):
        history = self._history()
        est = estimate_model(history)
        true_model = model_from_parameters(TRUE_PARAMS)
        # 用估计终点的现值定价（与历史终点一致，避免状态错位）
        last = {uid: vs[-1] for uid, vs in history.values_by_underlying_id.items()}
        for option in (fed_option(), ajr_option(strike=last[AJARAI_UNDERLYING_ID] * 1.05),
                       spread_option()):
            p_est = price_option_with_model(est, last, option)
            p_true = price_option_with_model(true_model, last, option)
            self.assertLess(abs(p_est - p_true), 0.06,
                            msg=f"{option}: est={p_est:.4f} true={p_true:.4f}")

    def test_covariance_sign_recovered(self):
        est = estimate_model(self._history())
        self.assertGreater(est.daily_cov, 0)  # 共享 sector 因子 → 正相关


class TestMarketMaker(unittest.TestCase):
    def _mm(self, cash=1000.0):
        options = [fed_option(), ajr_option(), spread_option()]
        mm = MarketMaker(make_underlyings(), options, cash)
        random.seed(11)
        values = dict(V0)
        rows = {uid: [v] for uid, v in values.items()}
        for _ in range(300):
            values = TRUE_PARAMS.advance_step(values)
            for uid, v in values.items():
                rows[uid].append(v)
        mm.warm_up(MarketHistory(values_by_underlying_id={
            uid: tuple(vs) for uid, vs in rows.items()}))
        return mm

    def test_quote_always_valid(self):
        mm = self._mm()
        for option in mm.active_option_state:
            for pos in (-100, -60, 0, 60, 100):
                mm.position.option_quantity_by_option_id[option.option_id] = pos
                q = mm.quote(option, counterparty_id=1)
                self.assertIsInstance(q, Quote)  # __post_init__ 即校验

    def test_quote_valid_when_broke(self):
        mm = self._mm(cash=0.5)
        for option in mm.active_option_state:
            q = mm.quote(option, counterparty_id=1)
            # 现金见底时报价占用必须极小
            self.assertLessEqual(q.bid_price * q.bid_quantity
                                 + (1 - q.offer_price) * q.offer_quantity, 0.5)

    def test_quote_brackets_theo_and_skew(self):
        mm = self._mm()
        option = ajr_option(strike=108.0)  # theo 低 → bid 侧不会触发极端档
        mm.active_option_state.append(option)
        theo = mm.price_option(option)
        q0 = mm.quote(option, 1)
        self.assertLessEqual(q0.bid_price, theo)
        self.assertGreaterEqual(q0.offer_price, theo)
        mm.position.option_quantity_by_option_id[option.option_id] = 40
        # 用新 counterparty（阶梯是按 cp 记的，同 cp 第二次报价会降档）
        q1 = mm.quote(option, 2)
        self.assertLessEqual(q1.bid_price, q0.bid_price)   # 多头 → 中心下移

    def test_fok_edge_gate(self):
        mm = self._mm()
        option = mm.active_option_state[1]
        theo = mm.price_option(option)
        good_sell = FokOrder(counterparty_id=9, option_id=option.option_id,
                             order_type=OrderType.SELL,
                             price=round(max(theo - 0.10, 0.01), 2), quantity=5)
        bad_sell = FokOrder(counterparty_id=9, option_id=option.option_id,
                            order_type=OrderType.SELL,
                            price=round(min(theo + 0.10, 0.99), 2), quantity=5)
        self.assertTrue(mm.respond_to_fok(option, good_sell))
        self.assertFalse(mm.respond_to_fok(option, bad_sell))

    def test_cash_mirror_accounting(self):
        mm = self._mm(cash=100.0)
        option = mm.active_option_state[0]
        mm.on_trade(option, price=0.20, quantity=5, counterparty_id=1)   # 买 5@0.20
        self.assertAlmostEqual(mm._mirror_cash, 100.0 - 1.0)
        mm.on_trade(option, price=0.20, quantity=-5, counterparty_id=1)  # 卖 5@0.20
        self.assertAlmostEqual(mm._mirror_cash, 99.0 - 4.0)

    def test_expiry_settlement_credits(self):
        mm = self._mm(cash=100.0)
        option = fed_option(oid=99, days=1, strike=1.0)
        mm.active_option_state.append(option)
        mm._option_by_id[99] = option
        mm.on_trade(option, price=0.60, quantity=10, counterparty_id=1)  # 买 10@0.6
        self.assertAlmostEqual(mm._mirror_cash, 94.0)
        # 到期：FED=2.0 ≥ 1.0 → payoff 1 → 多头拿回 10
        mm.on_step_advance(make_underlyings(), [])
        self.assertAlmostEqual(mm._mirror_cash, 104.0)

    def test_price_option_side_effect_free(self):
        mm = self._mm()
        option = mm.active_option_state[1]
        p1 = mm.price_option(option)
        p2 = mm.price_option(option)
        self.assertEqual(p1, p2)


class TestRoundTwoGeneralization(unittest.TestCase):
    """第二轮泛化机制（鲸鱼死亡开关 / 饥饿收窄 / MC 缓存）。
    这些机制设计为在可见 16 场上 no-op——单测只验证机制本身会动，
    可见集不回归由平台 16 场复验裁决。"""

    def _mm(self, cash=1000.0):
        options = [fed_option(), ajr_option(), spread_option()]
        mm = MarketMaker(make_underlyings(), options, cash)
        random.seed(11)
        values = dict(V0)
        rows = {uid: [v] for uid, v in values.items()}
        for _ in range(300):
            values = TRUE_PARAMS.advance_step(values)
            for uid, v in values.items():
                rows[uid].append(v)
        mm.warm_up(MarketHistory(values_by_underlying_id={
            uid: tuple(vs) for uid, vs in rows.items()}))
        return mm

    def test_extraction_dead_switch(self):
        from solution import CFG
        mm = self._mm()
        option = ajr_option(oid=50, strike=85.0)  # 深度价内 → theo 高 →
        mm.active_option_state.append(option)     # bid 侧占用 >0.45 触发榨取
        theo = mm.price_option(option)
        self.assertGreater(theo, 0.8)
        # 生产配置：开关停用（E26 终审），机制用临时配置验证
        self.assertEqual(CFG["extraction_dead_day"], 0)
        CFG["extraction_dead_day"] = 15
        self.addCleanup(lambda: CFG.update({"extraction_dead_day": 0}))
        # dead_day 之前：extreme 档正常（新 cp → nofill=0 → 榨取价）
        q_before = mm.quote(option, counterparty_id=101)
        self.assertAlmostEqual(q_before.bid_price, CFG["extreme_bid"])
        # dead_day 之后、极端价位零成交、markout 干净：榨取关闭
        mm._day = CFG["extraction_dead_day"] + 5
        self.assertEqual(mm._extraction_fills, 0)
        q_dead = mm.quote(option, counterparty_id=102)
        self.assertGreater(q_dead.bid_price, 0.4)
        # 毒流护甲：FOK markout 为负时不判死（E26 的 C6 教训）
        mm._fok_markouts = [-0.05] * 5
        q_armor = mm.quote(option, counterparty_id=104)
        self.assertAlmostEqual(q_armor.bid_price, CFG["extreme_bid"])
        mm._fok_markouts = []
        # 极端价位有过成交（0.02 买入高 theo，edge≥0.05）→ 榨取保持
        mm.on_trade(option, price=0.02, quantity=3, counterparty_id=102)
        self.assertEqual(mm._extraction_fills, 1)
        q_alive = mm.quote(option, counterparty_id=103)
        self.assertAlmostEqual(q_alive.bid_price, CFG["extreme_bid"])

    def test_starvation_shrinks_width_and_recovers(self):
        from solution import CFG
        mm = self._mm()
        option = ajr_option(oid=51, strike=108.0)
        mm.active_option_state.append(option)
        threshold = int(CFG["starve_after_quotes"])
        for i in range(threshold):
            mm.quote(option, counterparty_id=200 + i)
        self.assertEqual(mm._width_mult, 1.0)  # 未到阈值：no-op
        # 证据真空（无已解决 markout）：即使饥饿也不收窄（E26 C6 教训）
        for i in range(15):
            mm.quote(option, counterparty_id=400 + i)
        self.assertEqual(mm._width_mult, 1.0)
        # 有正面证据（干净 markout 够数）→ 收窄启动
        mm._rfq_markouts = [0.01] * 8
        for i in range(30):
            mm.quote(option, counterparty_id=500 + i)
        self.assertLess(mm._width_mult, 1.0)   # 饥饿中：收窄
        self.assertGreaterEqual(mm._width_mult, CFG["starve_floor"])
        shrunk = mm._width_mult
        # RFQ 成交 → 时钟归零 + 回弹（封顶 1.0）
        mm.on_trade(option, price=0.10, quantity=5, counterparty_id=999)
        self.assertEqual(mm._quotes_since_rfq_fill, 0)
        self.assertGreater(mm._width_mult, shrunk)
        self.assertLessEqual(mm._width_mult, 1.0)

    def test_starvation_blocked_when_rfq_toxic(self):
        from solution import CFG
        mm = self._mm()
        option = ajr_option(oid=52, strike=108.0)
        mm.active_option_state.append(option)
        mm._rfq_markouts = [-0.05] * 10        # RFQ 通道显性中毒
        for i in range(int(CFG["starve_after_quotes"]) + 30):
            mm.quote(option, counterparty_id=700 + i)
        self.assertEqual(mm._width_mult, 1.0)  # 毒场不收窄（归加宽管）

    def test_house_money_size_ramp(self):
        from solution import CFG
        mm = self._mm(cash=10.0)  # 小资本：per_quote 是数量的绑定约束
        option = ajr_option(oid=53, strike=108.0)  # theo 低，bid 不触发榨取
        mm.active_option_state.append(option)
        mm._mirror_cash = 25.0    # 盈利 +150%，超过 ramp_full
        q_ramp = mm.quote(option, counterparty_id=301)
        CFG["size_ramp_mult"] = 0.0
        self.addCleanup(lambda: CFG.update({"size_ramp_mult": 1.0}))
        q_flat = mm.quote(option, counterparty_id=302)
        self.assertGreater(q_ramp.bid_quantity, q_flat.bid_quantity)
        CFG["size_ramp_mult"] = 1.0
        # 亏损时 ramp 不生效：与关闭态逐位一致
        mm._mirror_cash = 6.0
        q_down = mm.quote(option, counterparty_id=303)
        CFG["size_ramp_mult"] = 0.0
        q_down_flat = mm.quote(option, counterparty_id=304)
        self.assertEqual(q_down.bid_quantity, q_down_flat.bid_quantity)

    def test_highcap_budget_boost(self):
        from solution import CFG
        mm = self._mm(cash=20.0)   # ≥ threshold → 高预算档
        option = ajr_option(oid=54, strike=108.0)
        mm.active_option_state.append(option)
        q_high = mm.quote(option, counterparty_id=401)
        CFG["per_quote_capital_fraction_highcap"] = CFG["per_quote_capital_fraction"]
        self.addCleanup(
            lambda: CFG.update({"per_quote_capital_fraction_highcap": 0.16}))
        q_flat = mm.quote(option, counterparty_id=402)
        self.assertGreater(q_high.bid_quantity, q_flat.bid_quantity)
        # 低资本场不受 highcap 档影响（结构性保证 C5-C9 行为不变）
        mm_low = self._mm(cash=10.0)
        mm_low.active_option_state.append(option)
        CFG["per_quote_capital_fraction_highcap"] = 0.16
        q_low_a = mm_low.quote(option, counterparty_id=403)
        CFG["per_quote_capital_fraction_highcap"] = CFG["per_quote_capital_fraction"]
        q_low_b = mm_low.quote(option, counterparty_id=404)
        self.assertEqual(q_low_a.bid_quantity, q_low_b.bid_quantity)

    def test_reset_tier_adaptive(self):
        from solution import CFG
        mm = self._mm()
        option = ajr_option(oid=55, strike=85.0)   # 深度价内 → 极端档报榨取价
        mm.active_option_state.append(option)
        cp = 501
        # 3 轮循环：极端档报价 miss ×3（tq[0]=3），竞争档成交 ×3
        for _ in range(3):
            mm.quote(option, cp)                   # 极端档（nofill=0）
            for _ in range(5):
                mm.quote(option, cp)               # 爬到竞争档
            mm.on_trade(option, price=0.90, quantity=-2, counterparty_id=cp)
        # tight 判定成立（极端档 0 成交、低档成交够数，n%4!=0）→ 回竞争档
        self.assertEqual(mm._cp_nofill[cp], int(CFG["cp_mid_strikes"]))
        q = mm.quote(option, cp)
        self.assertGreater(q.bid_price, 0.4)       # 竞争档：非榨取价
        # 第 4 笔成交 → reprobe（n % 4 == 0）：回极端档
        mm.on_trade(option, price=0.90, quantity=-2, counterparty_id=cp)
        self.assertEqual(mm._cp_nofill[cp], 0)
        # 鲸鱼保护：极端档成交过的 cp 永远回极端档
        whale = 502
        mm.quote(option, whale)                    # 极端档报价
        mm.on_trade(option, price=0.98, quantity=-3, counterparty_id=whale)
        for _ in range(8):
            mm.quote(option, whale)
            mm.on_trade(option, price=0.90, quantity=-1, counterparty_id=whale)
            self.assertEqual(mm._cp_nofill[whale], 0)
        # 总开关关闭 → 一律回极端档（旧行为）
        CFG["reset_tier_adaptive"] = 0.0
        self.addCleanup(lambda: CFG.update({"reset_tier_adaptive": 1.0}))
        mm.on_trade(option, price=0.90, quantity=-2, counterparty_id=cp)
        self.assertEqual(mm._cp_nofill[cp], 0)

    def test_cp_realized_stop_loss(self):
        from solution import CFG
        mm = self._mm(cash=100.0)
        option = fed_option(oid=98, days=1, strike=5.0)   # FED 2.0 → 到期归 0
        mm.active_option_state.append(option)
        mm._option_by_id[98] = option
        bleeder, whale = 601, 602
        # bleeder 卖给我们 10@0.5 → 到期 payoff 0 → realized −5
        mm.on_trade(option, price=0.50, quantity=10, counterparty_id=bleeder)
        # whale 从我们手里买 5@0.9（我们卖出）→ payoff 0 → realized +4.5
        option2 = fed_option(oid=97, days=1, strike=5.0)
        mm.active_option_state.append(option2)
        mm._option_by_id[97] = option2
        mm.on_trade(option2, price=0.90, quantity=-5, counterparty_id=whale)
        mm.on_step_advance(make_underlyings(), [])        # 双双到期结算
        self.assertAlmostEqual(mm._cp_realized[bleeder], -5.0)
        self.assertAlmostEqual(mm._cp_realized[whale], 4.5)
        # bleeder 触闸（≤ −3.0）：FOK 门槛按 sharp ×3，报价加宽
        # （strike 深 OTM → theo 低，bid 侧远离 heavy 0.45 不会转极端价）
        option3 = ajr_option(oid=96, strike=110.0)
        mm.active_option_state.append(option3)
        theo = mm.price_option(option3)
        edge_price = round(max(theo - 0.10, 0.01), 2)     # 0.10 edge：正常该接
        fok_b = FokOrder(bleeder, 96, OrderType.SELL, edge_price, 2)
        fok_w = FokOrder(whale, 96, OrderType.SELL, edge_price, 2)
        self.assertFalse(mm.respond_to_fok(option3, fok_b))  # 放血者被拒
        self.assertTrue(mm.respond_to_fok(option3, fok_w))   # 正 realized 不受累
        q_b = mm.quote(option3, bleeder)
        q_w = mm.quote(option3, whale)
        self.assertLess(q_b.bid_price, q_w.bid_price)        # 放血者见到更宽的价

    def test_mc_cache_hit_and_isolation(self):
        model = model_from_parameters(TRUE_PARAMS)
        exotic = BinaryOption(
            legs=(OptionLeg(FED_FUNDS_RATE_UNDERLYING_ID, 100.0),
                  OptionLeg(AJARAI_UNDERLYING_ID, 1.0),
                  OptionLeg(THERIODIC_UNDERLYING_ID, -1.0)),
            option_id=60, steps_until_expiry=2, strike=100.0)
        p1 = price_option_with_model(model, V0, exotic)
        cache = getattr(model, "_mc_cache", None)
        self.assertIsNotNone(cache)
        self.assertEqual(len(cache), 1)
        p2 = price_option_with_model(model, V0, exotic)
        self.assertEqual(p1, p2)
        self.assertEqual(len(cache), 1)        # 第二次是缓存命中
        # 现值变化 → 新键，不串结果
        v2 = dict(V0)
        v2[AJARAI_UNDERLYING_ID] = 101.0
        price_option_with_model(model, v2, exotic)
        self.assertEqual(len(cache), 2)
        # 新 model 实例 → 独立缓存（price_option_from_parameters 隔离）
        model_b = model_from_parameters(TRUE_PARAMS)
        self.assertIsNone(getattr(model_b, "_mc_cache", None))


class TestRobustness(unittest.TestCase):
    """菜单⑤：退化输入专项——评测端可能喂出的极端场景下不崩、
    不产生非法报价、不过度自信（theo 贴死 0/1 = 逆向选择磁铁）。"""

    def _mm_with_history(self, rows, cash=50.0):
        options = [fed_option(oid=71), ajr_option(oid=72), spread_option(oid=73)]
        mm = MarketMaker(make_underlyings(), options, cash)
        mm.warm_up(MarketHistory(values_by_underlying_id={
            uid: tuple(vs) for uid, vs in rows.items()}))
        return mm

    def _history_rows(self, n_days, seed=3):
        random.seed(seed)
        values = dict(V0)
        rows = {uid: [v] for uid, v in values.items()}
        for _ in range(n_days - 1):
            values = TRUE_PARAMS.advance_step(values)
            for uid, v in values.items():
                rows[uid].append(v)
        return rows

    def _assert_functional(self, mm):
        for option in mm.active_option_state:
            p = mm.price_option(option)
            self.assertTrue(0.0 <= p <= 1.0)
            q = mm.quote(option, counterparty_id=1)
            self.assertIsInstance(q, Quote)
            fok = FokOrder(counterparty_id=2, option_id=option.option_id,
                           order_type=OrderType.SELL, price=0.01, quantity=1)
            self.assertIn(mm.respond_to_fok(option, fok), (True, False))

    def test_warmup_ultra_short_histories(self):
        for n_days in (1, 2, 3, 5, 8):
            mm = self._mm_with_history(self._history_rows(n_days))
            self._assert_functional(mm)

    def test_short_history_not_overconfident(self):
        # 3 天历史 = 2 个收益样本，被 2 参数 OLS 完美拟合 → 样本方差 0。
        # 必须有先验托底，否则近 ATM theo 贴死 0/1
        mm = self._mm_with_history(self._history_rows(3))
        self.assertIsNotNone(mm._model)
        atm = ajr_option(oid=74, days=5,
                         strike=V0[AJARAI_UNDERLYING_ID] * 1.002)
        p = mm.price_option(atm)
        self.assertTrue(0.05 < p < 0.95, msg=f"p={p}")

    def test_warmup_constant_history(self):
        rows = {FED_FUNDS_RATE_UNDERLYING_ID: [2.0] * 60,
                AJARAI_UNDERLYING_ID: [100.0] * 60,
                THERIODIC_UNDERLYING_ID: [95.0] * 60}
        mm = self._mm_with_history(rows)
        self._assert_functional(mm)
        atm = ajr_option(oid=75, days=5, strike=100.2)
        p = mm.price_option(atm)
        self.assertTrue(0.05 < p < 0.95, msg=f"p={p}")

    def test_warmup_zero_rate_history(self):
        random.seed(5)
        n = 100
        rows = {FED_FUNDS_RATE_UNDERLYING_ID: [0.0] * n}
        for uid in (AJARAI_UNDERLYING_ID, THERIODIC_UNDERLYING_ID):
            v = V0[uid]
            vs = [v]
            for _ in range(n - 1):
                v = round(v * math.exp(random.gauss(0.0, 0.02)), 2)
                vs.append(v)
            rows[uid] = vs
        mm = self._mm_with_history(rows)
        self._assert_functional(mm)

    def test_price_from_parameters_never_raises(self):
        # THEO 通道：标的价被喂成 0（环境舍入的理论极端）也不许炸——
        # 一个合约炸掉会拖垮整个 THEO 测试
        mm = self._mm_with_history(self._history_rows(300))
        mm.underlying_state = make_underlyings({
            FED_FUNDS_RATE_UNDERLYING_ID: 0.0,
            AJARAI_UNDERLYING_ID: 0.0,
            THERIODIC_UNDERLYING_ID: 0.0})
        for option in (fed_option(oid=76), ajr_option(oid=77),
                       spread_option(oid=78)):
            p = mm.price_option_from_parameters(TRUE_PARAMS, option)
            self.assertTrue(0.0 <= p <= 1.0)

    def test_quote_legal_on_exotic_contracts(self):
        mm = self._mm_with_history(self._history_rows(300))
        exotics = [
            BinaryOption(legs=(OptionLeg(FED_FUNDS_RATE_UNDERLYING_ID, 50.0),
                               OptionLeg(AJARAI_UNDERLYING_ID, 1.0),
                               OptionLeg(THERIODIC_UNDERLYING_ID, -1.0)),
                         option_id=80, steps_until_expiry=3, strike=110.0),
            BinaryOption(legs=(OptionLeg(AJARAI_UNDERLYING_ID, 1.0),
                               OptionLeg(THERIODIC_UNDERLYING_ID, 1.0)),
                         option_id=81, steps_until_expiry=4, strike=190.0),
            BinaryOption(legs=(OptionLeg(AJARAI_UNDERLYING_ID, 2.5),
                               OptionLeg(THERIODIC_UNDERLYING_ID, -1.5)),
                         option_id=82, steps_until_expiry=2, strike=120.0),
        ]
        for option in exotics:
            mm.active_option_state.append(option)
            p = mm.price_option(option)
            self.assertTrue(0.0 <= p <= 1.0)
            q = mm.quote(option, counterparty_id=9)
            self.assertIsInstance(q, Quote)

    def test_long_expiry_pricing_bounded_and_fast(self):
        import time as _t
        mm = self._mm_with_history(self._history_rows(300))
        t0 = _t.perf_counter()
        p = mm.price_option(fed_option(oid=83, days=90, strike=3.0))
        dt = _t.perf_counter() - t0
        self.assertTrue(0.0 <= p <= 1.0)
        self.assertLess(dt, 1.0)


class TestE49ReestimationHatch(unittest.TestCase):
    """E49/E49b：退化 warm-up（<21 天）在线重估 + day-0 渐进混合。
    正常 warm-up 必须结构性惰性（对象同一性级），退化 warm-up 必须
    随 session 数据向真值收敛。"""

    def _rows(self, n_days, seed=11):
        random.seed(seed)
        values = dict(V0)
        rows = {uid: [v] for uid, v in values.items()}
        for _ in range(n_days - 1):
            values = TRUE_PARAMS.advance_step(values)
            for uid, v in values.items():
                rows[uid].append(v)
        return rows, values

    def _mm(self, rows):
        mm = MarketMaker(make_underlyings(), [], 40.0)
        mm.warm_up(MarketHistory(values_by_underlying_id={
            uid: tuple(vs) for uid, vs in rows.items()}))
        return mm

    def _underlyings(self, values):
        return [Underlying("FED", FED_FUNDS_RATE_UNDERLYING_ID,
                           values[FED_FUNDS_RATE_UNDERLYING_ID]),
                Underlying("AJR", AJARAI_UNDERLYING_ID,
                           values[AJARAI_UNDERLYING_ID]),
                Underlying("THR", THERIODIC_UNDERLYING_ID,
                           values[THERIODIC_UNDERLYING_ID])]

    def test_normal_warmup_structurally_inert(self):
        rows, values = self._rows(300)
        mm = self._mm(rows)
        self.assertFalse(mm._degenerate_warmup)
        m0 = mm._model
        random.seed(7)
        for _ in range(10):
            values = TRUE_PARAMS.advance_step(values)
            mm.on_step_advance(self._underlyings(values), [])
        self.assertIs(mm._model, m0)  # 模型对象未被替换 = 逐位惰性

    def test_degenerate_warmup_learns_toward_truth(self):
        rows, values = self._rows(3)
        mm = self._mm(rows)
        self.assertTrue(mm._degenerate_warmup)
        true_model = model_from_parameters(TRUE_PARAMS)
        probe_vals = dict(values)
        probe = ajr_option(oid=901, days=5,
                           strike=round(probe_vals[AJARAI_UNDERLYING_ID], 2))
        p_true = price_option_with_model(true_model, probe_vals, probe)
        err0 = abs(price_option_with_model(mm._model_day0, probe_vals, probe)
                   - p_true)
        random.seed(13)
        for _ in range(120):
            values = TRUE_PARAMS.advance_step(values)
            mm.on_step_advance(self._underlyings(values), [])
        self.assertIsNot(mm._model, mm._model_day0)  # 逃生舱在工作
        err1 = abs(price_option_with_model(mm._model, probe_vals, probe)
                   - p_true)
        # 120 天实盘数据后，混合模型对真值的定价误差应显著缩小
        self.assertLess(err1, err0)


class TestV13TailHardening(unittest.TestCase):
    """V13 审计修复：零占用退化、错侧防护、指纹日界清空。"""

    def _mm(self, cash=40.0):
        random.seed(3)
        values = dict(V0)
        rows = {uid: [v] for uid, v in values.items()}
        for _ in range(299):
            values = TRUE_PARAMS.advance_step(values)
            for uid, v in values.items():
                rows[uid].append(v)
        mm = MarketMaker(make_underlyings(), [], cash)
        mm.warm_up(MarketHistory(values_by_underlying_id={
            uid: tuple(vs) for uid, vs in rows.items()}))
        return mm

    def test_broke_quote_commits_exactly_zero(self):
        mm = self._mm()
        mm._mirror_cash = 0.01   # 连 1 张极端价都付不起
        opt = ajr_option(oid=950, days=3, strike=100.0)
        mm.active_option_state.append(opt)
        q = mm.quote(opt, counterparty_id=3)
        commit = q.bid_price * q.bid_quantity + (1 - q.offer_price) * q.offer_quantity
        self.assertEqual(commit, 0.0)   # bid 0.00 / offer 1.00 → 零占用

    def test_wrongside_extreme_guard(self):
        mm = self._mm()
        # 深度 OTM（theo ≈ 0）+ 多头顶格 → 不得再 bid 0.02 买垃圾
        far = ajr_option(oid=951, days=1, strike=10.0 ** 6)
        mm.active_option_state.append(far)
        self.assertLess(mm.price_option(far), 0.02)
        mm.position.option_quantity_by_option_id[far.option_id] = 100
        q = mm.quote(far, counterparty_id=4)
        self.assertEqual(q.bid_price, 0.0)
        # 深度 ITM（theo ≈ 1）+ 空头顶格 → 不得再 0.98 折价卖
        deep = ajr_option(oid=952, days=1, strike=0.01)
        mm.active_option_state.append(deep)
        self.assertGreater(mm.price_option(deep), 0.98)
        mm.position.option_quantity_by_option_id[deep.option_id] = -100
        q2 = mm.quote(deep, counterparty_id=5)
        self.assertEqual(q2.offer_price, 1.0)

    def test_fingerprint_purged_at_day_boundary(self):
        mm = self._mm()
        opt = ajr_option(oid=953, days=5, strike=100.0)
        mm.active_option_state.append(opt)
        fok = FokOrder(counterparty_id=7, option_id=opt.option_id,
                       order_type=OrderType.BUY, price=0.98, quantity=2)
        if mm.respond_to_fok(opt, fok):
            self.assertTrue(mm._accepted_foks)
        mm.on_step_advance(make_underlyings(), [opt.advance_step()])
        self.assertEqual(mm._accepted_foks, [])   # 跨日指纹清空
        # 次日同 (option, cp, price) 的 RFQ 成交必须走 RFQ 通道
        mm.on_trade(opt.advance_step(), 0.98, -1, 7)
        self.assertEqual(len(mm._pending_markouts), 1)
        self.assertFalse(mm._pending_markouts[0][4])   # is_fok == False


if __name__ == "__main__":
    unittest.main()

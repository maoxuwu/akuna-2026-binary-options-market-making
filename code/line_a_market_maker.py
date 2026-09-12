"""2026 Akuna 正赛提交（Line A）的自写部分：二元期权做市。

原提交为单文件（官方模板环境类 + 本文件内容）；本发布版已剥离模板，
只保留自写的 MarketMaker 与模块级辅助（题面允许 "add helpers"），
文件不可独立运行，见下方 NOTE。

定价思路（纯 stdlib，无 numpy）：
    FED 是 0.25 网格上带均值回归的三态马尔可夫链 → D 天终态分布用
    DP 精确算。ΔR_total = R_T − R_0（telescoping）。公司 log 终值在
    给定 ΔR 下是高斯（sector+idio 合成方差），于是：
      - 单腿 FED：对 DP 分布直接求和；
      - 单腿公司：Σ_r P(R_T=r)·Φ(...)；
      - AJR/THR 反号价差 strike=0：log 比值仍是高斯，同样解析；
      - 其余形状：按估计的联合分布做蒙特卡洛兜底（确定性种子）。

估计（warm_up）只需 7 个可识别量：两家公司的 drift、rate_beta（对
Δrate 的 OLS）、残差方差、残差协方差——sector 的 β 和 σ 只以乘积
进入定价，不必分离。利率侧：涨/跌指示变量对 r 的线性概率回归，
恰好对应 tilt 的线性结构。

风控：镜像评测端的最坏损失现金记账（买 q@p 占用 q·p，卖占 q(1−p)，
到期返还），报价数量由现金余量反推——破产 = 0 分，资本预算是
第一约束。
"""

# NOTE (publication extract): this file contains only the self-authored part of
# the Line A submission. It references the competition scaffolding types
# (BinaryOption, FokOrder, MarketHistory, MarketParameters, OptionLeg,
# OrderType, Position, Quote, Underlying, StrEnum import, UNDERLYING ids),
# which are the organizers' starter code and are deliberately not included.
# It will not run standalone; it documents the implementation.
#
# Orientation for English readers (comments below are in Chinese, the working
# language during the competition; README.md is the English narrative):
#   - The stdlib import block (math, random, collections.defaultdict,
#     dataclasses, typing.Final) was part of the omitted organizer header.
#   - Layout: CFG (every tunable, with the experiment id that set it) →
#     PARTICIPANT_NAME and penny/Φ helpers → CompanyParams / PricingModel →
#     model_from_parameters (exact-pricing channel) → estimate_model and
#     _blend_models (7-quantity estimator with degenerate-input armor and the
#     warm-up escape hatch) → rate_distribution / _company_leg_prob /
#     price_option_with_model / _price_by_monte_carlo (semi-analytic pricing
#     plus the memoized MC fallback) → class MarketMaker (mirror ledger,
#     per-counterparty ladder, FOK dosing, dual-channel and settlement
#     stop-losses, house-money sizing).
#   - "E<n>", "W<n>", "v<n>" in comments are Line A experiment/build ids; see
#     docs/experiment_log.md. "C5"–"C20" are the sixteen scored sessions.

# ============================================================================
# 辅助层：定价模型抽象 + 估计 + 定价核心（模块级 helper，题面允许）
# ============================================================================

#: 策略参数（初值由平台诊断日志与本地回测校准，正赛期间持续调）
CFG: Final[dict[str, float]] = {
    "base_half_spread": 0.03,     # 基础半价差（概率单位）
    #: 旧的"每天加宽"已停用（方向反了：二元期权的隔夜 theo 波动
    #: 随剩余天数递减，1d ATM 明天就归 0/1、theo 日波动可达 0.3-0.5，
    #: 线性递增公式在短期限 ATM 上裸奔）
    "spread_per_day": 0.0,
    #: 风险刻度宽度：half += mult × (明天 theo 的两点近似波动)。
    #: 险处自动宽（1d ATM），安处自动窄（长期限/深度价内外）
    "vol_spread_mult": 0.0,
    #: FOK 门槛同理按 theo 日波动加码（sharp 对手的信息优势集中在
    #: 高波动合约上）。剂量按对手方 markout 履历分层：
    #: 干净（mean ≥ clean）免溢价，可疑半剂量，恶劣（≤ suspect）全剂量，
    #: 无履历按 unknown_scale
    "fok_vol_mult": 0.3,
    "fok_vol_unknown_scale": 1.0,
    #: FOK 剂量按本场已接受 FOK 的 markout 动态调：被狙击 → 加深，
    #: 肥流 → 放松（全局毒性检测的 FOK 专用紧反馈版）
    "fok_markout_min_n": 3,
    #: RFQ 报价宽度的动态调节（E22 哲学复制到报价通道）：
    #: 本场 RFQ 成交的 markout 均值变坏 → 报价加宽
    "rfq_markout_min_n": 6,
    "rfq_width_toxic": 2.0,
    "rfq_width_suspect": 1.4,
    "fok_vol_mult_toxic": 0.8,
    "fok_vol_mult_suspect": 0.45,
    "fok_vol_mult_benign": 0.2,
    "cp_clean_markout": 0.0,
    "cp_suspect_markout": -0.03,
    "min_half_spread": 0.01,      # 至少 1 分钱
    "skew_per_contract": 0.001,   # 每张库存把报价中心反向移多少
    "max_skew": 0.10,
    "base_quote_size": 10,        # 基础报价数量
    "extreme_quote_size": 500,    # 极端价侧挂单上限（E40：250→500，预算 0.5 仍是真约束，只在富场解绑）
    #: 极端价：比 常驻极端报价者 的 0.01/0.99 各让 1 分钱，按最优价路由
    #: 把它的鲸鱼流整体截胡。distress 触发时 theo 必在对侧远端，
    #: （0.02 买 theo≥0.5 / 0.98 卖 theo≤0.5）每笔都是厚利
    "extreme_bid": 0.02,
    "extreme_offer": 0.98,
    #: 极端侧最多占可用现金的比例（每张只占 0.02，预算大点无妨）
    "extreme_capital_fraction": 0.5,
    "max_position_per_option": 80,        # 单只期权持仓上限（张）
    "capital_use_fraction": 0.6,          # 可动用现金比例（余下是防破产垫）
    #: 每张占用超过该值的一侧直接转极端价（"单边做市+极端价收割
    #: 鲸鱼"结构，v1 意外发现、实测显著优于双边全窄）。固定阈值
    #: 而非挂钩资金——保证 extraction 全场生效，不随盈利消失
    "heavy_side_threshold": 0.45,
    #: 鲸鱼探测：开局按 0.45 试探；probe_days 天后若极端价成交的
    #: 累计利润（Σ qty·|theo−price|）不足 min_profit（= 鲸鱼流不够
    #: 肥，抵不上让出半本书的机会成本），quiet 阈值 10 = 彻底关掉
    #: 榨取、回到双边正常做市
    "heavy_side_threshold_quiet": 10.0,
    #: min_profit=0 → 全局探测永不触发（被按对手方探测取代，保留备用）
    "extreme_probe_days": 10,
    "extreme_min_profit": 0.0,     # dormant: 0 = probe shutdown never fires
    #: 榨取死亡开关【E26 终审停用=0】：任何可触发的判死都误杀 C6
    #: （其榨取档价值 = heavy 侧单边护甲，且毒性不显于 markout——
    #: 信号与需求反相关的信息墙，详 docs/experiment_log.md E26）。代码休眠保留
    "extraction_dead_day": 0,      # dormant: 0 = kill-switch disabled (E26)
    "extraction_fill_min_edge": 0.05,
    #: 按对手方价格阶梯（C3 日志确认 cp 复现）：按"连续未成交次数"
    #: 降档 极端 → 中档(half×mid_width_mult) → 竞争价；任何成交立刻
    #: 重置回极端档（刚付过钱的对手接着宰）。这是对每个 cp 的
    #: 在线价格发现
    "cp_extreme_strikes": 1,
    "cp_mid_strikes": 5,
    #: 【E32】重置档自适应：从不吃极端价的对手（极端报满 miss 且
    #: 低档有成交）回其证明过的档位；极端成交 = 永久鲸鱼保护；每
    #: 第 reprobe 笔成交回极端重探（详 docs/experiment_log.md E32）。0 = 关闭
    "reset_tier_adaptive": 1.0,
    "reset_tier_min_extreme_quotes": 3,
    "reset_tier_min_fills": 2,
    "reset_tier_reprobe_every": 4,
    #: 中档宽度 = base_half×mult，封顶 cap——cap 取 0.12 是刻意贴在
    #: 最宽固定宽度报价者的内侧半分钱，把中价流从它嘴里抢过来
    "cp_mid_width_mult": 3.0,
    "cp_mid_half_cap": 0.12,
    #: 正常侧的报价数量预算（占可用现金比例）。
    #: E28 实测：全局 0.16 → 固定宽度报价者场大增厚（C13 +6/C14 +6/C15 +23/
    #: C8 +4.6）但 C6 刀锋翻车（+0.25→−0.48）→ 改为盈利 ramp
    "per_quote_capital_fraction": 0.08,
    #: 【E30】初始资本 ≥ threshold 的场用更高基础预算：E28 证明
    #: 资本 20/40 场全体受益（C13/C14 刀锋边际被抹平、C15 +23），
    #: 受害者只有资本 10 的轻毒场（粒度效应：小资本下单笔逆向
    #: 成交即大比例回撤）。资本是环境 init 参数，非对手特化；
    #: 低资本欠仓只损失机会不损失分数，方向保守自洽
    "per_quote_capital_fraction_highcap": 0.16,
    "highcap_threshold": 20.0,
    #: 【E49】退化 warm-up（<21 天）时每日拼入实盘走势在线重估；
    #: 正常 warm-up 结构性不触发（详 docs/experiment_log.md E49）。0 = 关闭
    "reestimate_if_degenerate": 1.0,
    #: 【E49b】重估与 day-0 模型按 w=(n−20)/((n−20)+K) 渐进混合，
    #: 防过渡区 theo 游走（详 docs/experiment_log.md E49b）
    "reestimate_blend_k": 10.0,
    #: 赢冲输缩（house-money）sizing：盈利超过初始资本 ramp_start
    #: 比例后线性加大 RFQ 预算，至 ramp_full 封顶 ×(1+ramp_mult)。
    #: 吃下 E28 的溢流吸收收益而不碰 C6 类不盈利刀锋场——已实现
    #: 盈利是无法被对手流伪造的场景毒性总信号。ramp_mult=0 关闭
    "size_ramp_start": 0.15,
    "size_ramp_full": 1.25,
    "size_ramp_mult": 1.0,
    # FOK：风险调整 EV 门槛（替代旧的固定 edge——它拒掉了近无风险单）
    # FOK 门槛（v1 口径实测最优：0.02 盖过 theo 估计噪声。曾试过
    # 0.005/0.015+近无风险通道，在低概率区被赢家诅咒放血，C8 从
    # +8.04 亏到 −0.64，已回退——见 docs/experiment_log.md v4–v6 行）
    "fok_min_ev": 0.02,           # 每张期望利润下限
    "fok_min_roc": 0.02,          # 期望利润 / 占用资本 下限（极少约束）
    "fok_max_commit_fraction": 1.0,       # 单笔 FOK 可用满可动用现金
    "mc_paths": 4000,             # 蒙特卡洛兜底路径数
    # 毒性自适应：滚动窗口 markout 均值显著为负 → 被逆向选择 → 加宽
    "toxicity_window": 40,
    "toxicity_spread_mult": 25.0, # half ×= 1 + mult·信号（超出 1SE 的负均值）
    "toxicity_max_mult": 4.0,
    #: 【E36】按对手方累计已实现结算盈亏的止损闸。C6 毒 FOK 之谜的
    #: 答案假说：慢性放血流（终值信息型）每天 markout 都小于阈值、
    #: 毒性只在到期结算显形——1 天 markout 窗口天然失明。
    #: realized = Σ qty·(payoff−price)（带符号统一公式），跨期限、
    #: 无法伪造。亏到 −flag 美元的对手按 sharp 待遇（FOK 门槛×3 +
    #: 报价加宽）。肥流对手 realized 为正永不受累——E35 承诺上限
    #: 杀 C8/C10 的问题被根除的外科手术版。0 = 关闭
    "cp_realized_flag": 2.0,
    #: 闸值的资本规模化（过拟合审计 E39）：$2 隐含假设可见集资本
    #: 10-40；隐藏场资本更大时正常客户也会随手越过绝对闸值。
    #: 有效闸 = flag × max(1, 资本/ref)——资本 ≤ref 时乘数恰为 1，
    #: 对可见集结构性逐位恒等；更大资本线性放大
    "cp_realized_ref_capital": 40.0,
    # 对手方画像：markout 均值显著低于阈值才判 sharp（误判的代价是
    # 把肥流让给竞争者，宁可漏判不可误判）
    "cp_sharp_threshold": -0.04,
    "cp_min_trades": 6,
    "cp_sharp_spread_mult": 2.0,
    "cp_sharp_fok_mult": 3.0,
    # 成交率自适应宽度【实测有害，关闭（up=down=1）——它把 v1 的
    # 单边结构磨平了。保留机制以备正赛对手环境不同时重新启用】
    "width_adapt_up": 1.0,
    "width_adapt_down": 1.0,
    "width_mult_min": 0.6,
    "width_mult_max": 12.0,
    #: 【第二轮泛化】饥饿收窄：连续 starve_after 次 RFQ 报价零成交且
    #: RFQ markout 无毒（毒场归动态加宽管，不抢戏）→ 宽度乘数逐次
    #: ×decay 收窄（下限 floor），成交后 ×recover 回弹（封顶 1）。
    #: 竞争者书比我们窄时用成交率反推市场宽度——这是项目笔记里
    #: 「成交率骤降 = 报在竞争者外面」的自动化。可见集从不连续饿
    #: 这么久 → no-op，回归复验。starve_after 取 0 = 关闭
    "starve_after_quotes": 120,
    "starve_decay": 0.985,
    "starve_floor": 0.7,
    "starve_recover": 1.15,
    #: 遥测打印已移除（评分通道不允许任何 stdout 输出）；键保留，恒为 0
    "debug_every": 0,
}

PARTICIPANT_NAME: Final[str] = "Maoxu"


def norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def floor_penny(x: float) -> float:
    return math.floor(x * 100 + 1e-9) / 100


def ceil_penny(x: float) -> float:
    return math.ceil(x * 100 - 1e-9) / 100


@dataclass(frozen=True)
class CompanyParams:
    """单家公司每日 log 收益的可识别参数。"""
    drift: float
    rate_beta: float
    daily_var: float   # sector_beta²·σ_sector² + σ_idio²（合成，无需分离）


@dataclass(frozen=True)
class PricingModel:
    """定价所需的全部可识别量。真参数（THEO 测试）和估计参数都先映射到
    这里，定价核心只认这个抽象——保证两条路径共享同一套定价代码。

    利率涨/跌概率是 r 的线性函数（与模板 tilt 的代数形式恒等）：
        p_up(r)   = clamp01(up_intercept + up_slope·r)
        p_down(r) = clamp(down_intercept + down_slope·r, 0, 1−p_up)
    截断顺序照抄模板 tilted_rate_probabilities。
    """
    up_intercept: float
    up_slope: float
    down_intercept: float
    down_slope: float
    rate_step: float
    company: dict[int, CompanyParams]
    daily_cov: float   # AJR/THR 每日残差协方差 = βa_s·βt_s·σ_s²

    def rate_probs(self, rate_value: float) -> tuple[float, float]:
        up = min(max(self.up_intercept + self.up_slope * rate_value, 0.0), 1.0)
        down = min(max(self.down_intercept + self.down_slope * rate_value, 0.0), 1.0 - up)
        return up, down


def model_from_parameters(params: MarketParameters) -> PricingModel:
    s = params.rate_reversion_strength
    return PricingModel(
        up_intercept=params.rate_up_probability + s * params.rate_target,
        up_slope=-s,
        down_intercept=params.rate_down_probability - s * params.rate_target,
        down_slope=s,
        rate_step=params.rate_step,
        company={
            AJARAI_UNDERLYING_ID: CompanyParams(
                drift=params.ajarai_drift,
                rate_beta=params.ajarai_rate_beta,
                daily_var=params.ajarai_sector_beta ** 2 * params.sector_std_dev ** 2
                + params.ajarai_idio_std_dev ** 2,
            ),
            THERIODIC_UNDERLYING_ID: CompanyParams(
                drift=params.theriodic_drift,
                rate_beta=params.theriodic_rate_beta,
                daily_var=params.theriodic_sector_beta ** 2 * params.sector_std_dev ** 2
                + params.theriodic_idio_std_dev ** 2,
            ),
        },
        daily_cov=params.ajarai_sector_beta * params.theriodic_sector_beta
        * params.sector_std_dev ** 2,
    )


def _ols2(xs: list[float], ys: list[float]) -> tuple[float, float]:
    """一元 OLS：y = a + b·x，返回 (a, b)。x 无方差时 b=0。"""
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx < 1e-12:
        return my, 0.0
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    return my - b * mx, b


def estimate_model(history: MarketHistory) -> PricingModel:
    """从 warm-up 历史估计 PricingModel。

    利率：涨/跌指示变量对 r 的线性概率回归——模板的 tilt 结构本身就是
    线性的，所以这个回归是正确设定（r=0 的观测剔除：floor 会把真实
    下调吞成不动，混进样本会压低跌概率估计）。
    公司：log 收益对 Δrate 的 OLS，残差方差/协方差直接取样本矩。
    样本不足时退到保守默认（对称小概率、零 beta、历史方差兜底）。
    """
    rates = list(history.values_by_underlying_id[FED_FUNDS_RATE_UNDERLYING_ID])
    step = RATE_STRIKE_GRID

    r_prev: list[float] = []
    up_ind: list[float] = []
    down_ind: list[float] = []
    rate_changes: list[float] = []
    for prev, curr in zip(rates, rates[1:]):
        change = round(curr - prev, 2)
        rate_changes.append(change)
        if prev <= step / 2:   # r=0 附近 floor 污染涨跌观测，剔除
            continue
        r_prev.append(prev)
        up_ind.append(1.0 if change > step / 2 else 0.0)
        down_ind.append(1.0 if change < -step / 2 else 0.0)

    if len(r_prev) >= 10:
        up_a, up_b = _ols2(r_prev, up_ind)
        down_a, down_b = _ols2(r_prev, down_ind)
    else:  # 样本不足：无回归信息，用无 tilt 的对称默认
        p_up = sum(up_ind) / len(up_ind) if up_ind else 0.3
        p_down = sum(down_ind) / len(down_ind) if down_ind else 0.3
        up_a, up_b, down_a, down_b = p_up, 0.0, p_down, 0.0

    #: 样本不足时的方差先验托底（取一个与日收益量级相称的保守先验
    #: 5e-4）。可见集 warm-up 仅 15–45 天，最短的场（≤19 个收益样本）
    #: 会进入下面的 n<20 分支——上线时实测两场 PnL 微变、排名不变
    prior_var = 5e-4
    company: dict[int, CompanyParams] = {}
    residuals: dict[int, list[float]] = {}
    for uid in (AJARAI_UNDERLYING_ID, THERIODIC_UNDERLYING_ID):
        values = list(history.values_by_underlying_id[uid])
        # (Δrate, log收益) 成对构造，剔除非正价格（log 会炸）且保持配对
        pairs = [(x, math.log(b / a))
                 for x, (a, b) in zip(rate_changes, zip(values, values[1:]))
                 if a > 0 and b > 0]
        if not pairs:   # 1 天历史/全零价：无收益样本 → 中性先验
            company[uid] = CompanyParams(drift=0.0, rate_beta=0.0,
                                         daily_var=prior_var)
            residuals[uid] = []
            continue
        xs = [x for x, _ in pairs]
        log_rets = [y for _, y in pairs]
        drift, beta = _ols2(xs, log_rets)
        resid = [y - drift - beta * x for x, y in pairs]
        n = len(resid)
        var = sum(e * e for e in resid) / max(n - 2, 1)
        if n < 20:
            # 短历史三重防线：残差方差塌缩（2 样本被 2 参数完美拟合）
            # 用先验托底；drift/beta 的 OLS 噪声可放大到吞掉一切，
            # 夹在一个宽松的合理区间内（纯守门，不当估计用）
            var = max(var, prior_var)
            drift = min(max(drift, -0.01), 0.01)
            beta = min(max(beta, -0.2), 0.2)
        if var < 1e-5:
            # 方差塌缩与样本量正交（常数历史 n=59 也会 var=0）：
            # 量级正常的市场（哪怕只有 15–45 天）估不出 <1e-5，塌缩必是
            # 退化输入 → 托底防 theo 贴死 0/1
            var = prior_var
        company[uid] = CompanyParams(drift=drift, rate_beta=beta, daily_var=max(var, 1e-12))
        residuals[uid] = resid

    ra, rt = residuals[AJARAI_UNDERLYING_ID], residuals[THERIODIC_UNDERLYING_ID]
    # 已知局限（发布后审计，仅注释）：两家残差按各自剔除后的下标 zip，不按
    # 日期索引；若两家在不同的"中间"日期出现非正价格，配对会错日期（合成例：
    # 31 天各含一个孤立零，cov 0.000312 vs 按日期对齐 0.000433）。环境里不可达：
    # 估值按 round(v·exp(r), 2) 演化，负值不可能、零是吸收态 → 非正值只能是
    # 后缀 → 两数组是同一日期前缀，zip 精确对齐（已数值验证）。研究版应按日期键配对。
    # Known limitation (comment only): residuals are zipped by post-filter index,
    # not by date — an *interior* non-positive price on different dates would
    # mis-pair them. Unreachable here (zero is absorbing under round(v*exp(r), 2),
    # so filtered dates can only be a suffix, under which the zip is date-aligned).
    n = min(len(ra), len(rt))
    if n >= 3:
        cov = sum(a * b for a, b in zip(ra, rt)) / max(n - 2, 1)
    else:
        cov = 0.0   # 样本不足不估协方差（配对也可能因剔除而错位）
    # 协方差不能超过方差几何均值（数值噪声防护，保证价差方差非负）
    cov_cap = math.sqrt(company[AJARAI_UNDERLYING_ID].daily_var
                        * company[THERIODIC_UNDERLYING_ID].daily_var)
    cov = min(max(cov, -cov_cap), cov_cap)

    return PricingModel(
        up_intercept=up_a, up_slope=up_b,
        down_intercept=down_a, down_slope=down_b,
        rate_step=step, company=company, daily_cov=cov,
    )


def _blend_models(m0: PricingModel, m1: PricingModel, w: float) -> PricingModel:
    """E49b：两模型凸组合（w = 学习值权重）；协方差重夹几何均值界。"""
    def bc(a: CompanyParams, b: CompanyParams) -> CompanyParams:
        return CompanyParams(
            drift=(1 - w) * a.drift + w * b.drift,
            rate_beta=(1 - w) * a.rate_beta + w * b.rate_beta,
            daily_var=(1 - w) * a.daily_var + w * b.daily_var)
    company = {uid: bc(m0.company[uid], m1.company[uid]) for uid in m0.company}
    cov = (1 - w) * m0.daily_cov + w * m1.daily_cov
    cap = math.sqrt(company[AJARAI_UNDERLYING_ID].daily_var
                    * company[THERIODIC_UNDERLYING_ID].daily_var)
    cov = min(max(cov, -cap), cap)
    return PricingModel(
        up_intercept=(1 - w) * m0.up_intercept + w * m1.up_intercept,
        up_slope=(1 - w) * m0.up_slope + w * m1.up_slope,
        down_intercept=(1 - w) * m0.down_intercept + w * m1.down_intercept,
        down_slope=(1 - w) * m0.down_slope + w * m1.down_slope,
        rate_step=m1.rate_step, company=company, daily_cov=cov)


def rate_distribution(model: PricingModel, r0: float, days: int) -> dict[float, float]:
    """D 天后利率终态的精确分布（DP over 网格状态）。"""
    dist: dict[float, float] = {round(r0, 2): 1.0}
    for _ in range(days):
        nxt: dict[float, float] = defaultdict(float)
        for r, p in dist.items():
            up, down = model.rate_probs(r)
            nxt[max(round(r + model.rate_step, 2), 0.0)] += p * up
            nxt[max(round(r - model.rate_step, 2), 0.0)] += p * down
            nxt[r] += p * (1.0 - up - down)
        dist = dict(nxt)
    return dist


def _company_leg_prob(model: PricingModel, uid: int, v0: float, days: int,
                      weight: float, threshold: float, rate_change: float) -> float:
    """P(weight·V_D ≥ threshold | ΔR=rate_change)。V_D 对数正态。"""
    p = model.company[uid]
    mean = days * p.drift + p.rate_beta * rate_change
    std = math.sqrt(days * p.daily_var)
    if weight > 0:
        bound = threshold / weight
        if bound <= 0:
            return 1.0
        z = math.log(bound / v0)
        return norm_cdf((mean - z) / std) if std > 0 else (1.0 if mean >= z else 0.0)
    bound = threshold / weight  # weight<0 → 不等号翻转：V ≤ bound
    if bound <= 0:
        return 0.0
    z = math.log(bound / v0)
    return norm_cdf((z - mean) / std) if std > 0 else (1.0 if mean <= z else 0.0)


def price_option_with_model(
    model: PricingModel,
    values: dict[int, float],
    option: BinaryOption,
) -> float:
    """定价核心：返回 P(observable ≥ strike)，∈ [0,1]。"""
    days = option.steps_until_expiry
    if days == 0:
        return option.expiry_valuation(values)

    legs = option.legs
    fed_legs = [l for l in legs if l.underlying_id == FED_FUNDS_RATE_UNDERLYING_ID]
    comp_legs = [l for l in legs if l.underlying_id != FED_FUNDS_RATE_UNDERLYING_ID]
    r0 = values[FED_FUNDS_RATE_UNDERLYING_ID]
    dist = rate_distribution(model, r0, days)

    total = 0.0
    if not comp_legs:
        # 纯 FED：对终态分布直接求和
        w = fed_legs[0].weight
        for r, pr in dist.items():
            total += pr * (1.0 if w * r >= option.strike else 0.0)
        return min(max(total, 0.0), 1.0)

    if len(comp_legs) == 1:
        # （可选的 FED 腿）+ 单公司腿：给定 ΔR 是解析高斯
        cl = comp_legs[0]
        fw = fed_legs[0].weight if fed_legs else 0.0
        for r, pr in dist.items():
            thresh = option.strike - fw * r
            total += pr * _company_leg_prob(
                model, cl.underlying_id, values[cl.underlying_id],
                days, cl.weight, thresh, round(r - r0, 2))
        return min(max(total, 0.0), 1.0)

    if len(comp_legs) == 2 and not fed_legs:
        wa = next(l.weight for l in comp_legs if l.underlying_id == AJARAI_UNDERLYING_ID)
        wt = next(l.weight for l in comp_legs if l.underlying_id == THERIODIC_UNDERLYING_ID)
        if abs(option.strike) < 1e-12 and wa * wt < 0:
            # 反号价差 strike=0：wa·VA + wt·VT ≥ 0 ⟺ log 比值超过阈值，
            # log VA − log VT 给定 ΔR 是高斯（方差 = va + vt − 2cov）
            pa = model.company[AJARAI_UNDERLYING_ID]
            pt = model.company[THERIODIC_UNDERLYING_ID]
            var_diff = max(pa.daily_var + pt.daily_var - 2 * model.daily_cov, 1e-16)
            v0a = values[AJARAI_UNDERLYING_ID]
            v0t = values[THERIODIC_UNDERLYING_ID]
            # wa>0, wt<0: VA/VT ≥ |wt|/wa；wa<0, wt>0: VA/VT ≤ |wa|⁻¹... 统一处理
            thresh = math.log(abs(wt) / abs(wa))
            for r, pr in dist.items():
                dr = round(r - r0, 2)
                mean = math.log(v0a / v0t) + days * (pa.drift - pt.drift) \
                    + (pa.rate_beta - pt.rate_beta) * dr
                z = (mean - thresh) / math.sqrt(days * var_diff)
                p_ratio_above = norm_cdf(z)
                total += pr * (p_ratio_above if wa > 0 else 1.0 - p_ratio_above)
            return min(max(total, 0.0), 1.0)

    return _price_by_monte_carlo(model, values, option)


def _price_by_monte_carlo(model: PricingModel, values: dict[int, float],
                          option: BinaryOption) -> float:
    """兜底：按估计的联合分布模拟（确定性种子，price_option 无副作用）。

    联合模拟用协方差的 Cholesky 分解：xa = μa + σa·z1，
    xt = μt + (cov/σa)·z1 + √(vt − cov²/va)·z2。

    缓存：同一 (合约, 剩余天数, 三标的现值) 下结果确定（种子亦由此
    生成），缓存是纯加速、零行为改变。实测 4000 路径 ≈ 5ms/到期日
    （10d 合约 51ms/次），而同一合约每天会被 quote/FOK/markout 反复
    重定价——若正式评测有奇异多腿合约+时限，无缓存是隐患。缓存挂在
    model 实例上：估计模型全场一份、持续复用；price_option_from_
    parameters 每次新建 model → 天然隔离，不会串到错误参数的结果。
    """
    days = option.steps_until_expiry
    key = (option.option_id, days,
           round(values[FED_FUNDS_RATE_UNDERLYING_ID] * 100),
           round(values[AJARAI_UNDERLYING_ID] * 100),
           round(values[THERIODIC_UNDERLYING_ID] * 100))
    cache = getattr(model, "_mc_cache", None)
    if cache is None:
        cache = {}
        object.__setattr__(model, "_mc_cache", cache)  # frozen 亦可挂私有属性
    cached = cache.get(key)
    if cached is not None:
        return cached
    seed = (option.option_id * 1_000_003
            + int(values[FED_FUNDS_RATE_UNDERLYING_ID] * 100) * 101
            + int(values[AJARAI_UNDERLYING_ID] * 100) % 97_001
            + days)
    rng = random.Random(seed)
    pa = model.company[AJARAI_UNDERLYING_ID]
    pt = model.company[THERIODIC_UNDERLYING_ID]
    sa = math.sqrt(pa.daily_var)
    cross = model.daily_cov / sa if sa > 0 else 0.0
    resid_t = math.sqrt(max(pt.daily_var - cross * cross, 0.0))

    hits = 0
    n = int(CFG["mc_paths"])
    for _ in range(n):
        r = values[FED_FUNDS_RATE_UNDERLYING_ID]
        la = math.log(values[AJARAI_UNDERLYING_ID])
        lt = math.log(values[THERIODIC_UNDERLYING_ID])
        for _ in range(days):
            up, down = model.rate_probs(r)
            draw = rng.random()
            if draw < up:
                r_new = max(round(r + model.rate_step, 2), 0.0)
            elif draw < up + down:
                r_new = max(round(r - model.rate_step, 2), 0.0)
            else:
                r_new = r
            dr = round(r_new - r, 2)
            r = r_new
            z1, z2 = rng.gauss(0, 1), rng.gauss(0, 1)
            la += pa.drift + pa.rate_beta * dr + sa * z1
            lt += pt.drift + pt.rate_beta * dr + cross * z1 + resid_t * z2
        terminal = {
            FED_FUNDS_RATE_UNDERLYING_ID: r,
            AJARAI_UNDERLYING_ID: math.exp(la),
            THERIODIC_UNDERLYING_ID: math.exp(lt),
        }
        hits += option.expiry_valuation(terminal) >= 0.5
    result = hits / n
    if len(cache) >= 20_000:   # 防极端场景下无界增长（正常远够不着）
        cache.clear()
    cache[key] = result
    return result


# ----------------------------------------------------------------------------
# Market maker implementation. The class name and constructor signature below
# are the grader-mandated interface; the four base-state assignments that open
# the organizer's constructor scaffold are omitted (organizer code).
# ----------------------------------------------------------------------------


class MarketMaker:
    def __init__(
        self,
        underlying_initial_state: list[Underlying],
        option_initial_state: list[BinaryOption],
        cash_balance: float,
    ) -> None:
        # [4 interface-mandated base-state assignments omitted — organizer scaffold]

        # ---- 我们的状态 ----
        self._model: PricingModel | None = None
        #: 镜像评测端的最坏损失现金记账（sizing 的依据）
        self._mirror_cash: float = cash_balance
        #: option_id -> 我们的成交明细（到期返还 + 按对手方结算记账）：
        #: [(price, signed_qty, counterparty_id)]（下方注解早于 E36 扩展，未同步）
        self._trades_by_option: dict[int, list[tuple[float, int]]] = defaultdict(list)
        self._option_by_id: dict[int, BinaryOption] = {
            o.option_id: o for o in option_initial_state}
        #: 对手方遥测：counterparty_id -> [每笔成交的 1 天 markout]
        self._markouts_by_counterparty: dict[int, list[float]] = defaultdict(list)
        #: 按对手方累计已实现结算盈亏（E36 慢性放血止损闸的原料）
        self._cp_realized: dict[int, float] = defaultdict(float)
        #: 全局 1 天 markout 滚动窗口（负均值且统计显著 = 被逆向选择）
        self._recent_markouts: list[float] = []
        #: 已接受 FOK 的 markout（FOK 剂量动态调节的依据）
        self._fok_markouts: list[float] = []
        #: RFQ 成交的 markout（报价宽度动态调节的依据）
        self._rfq_markouts: list[float] = []
        #: 待结算 markout：(option_id, 方向符号, 成交时 theo, counterparty_id, is_fok)（注解未同步）
        self._pending_markouts: list[tuple[int, int, float, int]] = []
        self._initial_cash: float = cash_balance
        self._day: int = 0
        self._buy_fills: int = 0
        self._sell_fills: int = 0
        #: 极端价（≤0.03 / ≥0.97）成交的累计毛利——鲸鱼有多肥的证据
        self._extreme_profit: float = 0.0
        #: 极端价位成交笔数（榨取死亡开关的活性证据，口径见 CFG 注释）
        self._extraction_fills: int = 0
        #: 按对手方价格阶梯：连续未成交的报价次数（成交即归零）
        self._cp_nofill: dict[int, int] = defaultdict(int)
        self._cp_extreme_fills: dict[int, int] = defaultdict(int)
        #: 重置档自适应的档位记账：cp -> [极端, 中, 竞争] 的报价/成交数
        self._cp_tier_quotes: dict[int, list[int]] = {}
        self._cp_tier_fills: dict[int, list[int]] = {}
        self._cp_last_tier: dict[int, int] = {}
        #: option_id -> (day, 明天 theo 的近似日波动)——报价宽度的风险刻度
        self._theo_vol_cache: dict[int, tuple[int, float]] = {}
        #: 成交率自适应宽度乘数（对数域随机逼近）
        self._width_mult: float = 1.0
        #: 距上一笔 RFQ 成交已连续报出的报价数（饥饿收窄的时钟）
        self._quotes_since_rfq_fill: int = 0
        #: 最近接受的 FOK 指纹，用于把 FOK 成交从宽度自适应里剔除
        self._accepted_foks: list[tuple[int, int, float]] = []
        #: E49：warm-up 原始行情行 + 退化标记（<21 天才在线重估）
        self._history_rows: dict[int, list[float]] = {}
        self._degenerate_warmup: bool = False
        #: E49b：day-0 护甲模型（渐进混合的锚点）
        self._model_day0: PricingModel | None = None
        self._error_count: int = 0

    # ------------------------------------------------------------------
    # 环境回调
    # ------------------------------------------------------------------

    def on_step_advance(self, new_underlying_state: list[Underlying],
                        new_option_state: list[BinaryOption]) -> None:
        try:
            self._settle_expired(new_underlying_state, new_option_state)
        except Exception:
            self._error_count += 1
        self._day += 1
        self._accepted_foks.clear()   # E51 (Line A v13)：FOK 同日结算，跨日指纹=悬空
        old_options = self._option_by_id
        # interface-mandated state update (identical to the organizer scaffold; retained)
        self.underlying_state = new_underlying_state
        self.active_option_state = new_option_state
        self._option_by_id = {o.option_id: o for o in new_option_state}
        try:
            self._resolve_markouts(old_options)
        except Exception:
            self._error_count += 1
        # E49/E49b：退化场每日重估（markout 后），与 day-0 模型渐进混合
        if self._degenerate_warmup and CFG["reestimate_if_degenerate"] > 0:
            try:
                for u in new_underlying_state:
                    self._history_rows[u.underlying_id].append(u.value)
                fresh = estimate_model(MarketHistory(
                    values_by_underlying_id={
                        uid: tuple(vs)
                        for uid, vs in self._history_rows.items()}))
                n_rets = len(next(iter(self._history_rows.values()))) - 1
                excess = max(0.0, n_rets - 20.0)
                w = excess / (excess + CFG["reestimate_blend_k"])
                base = self._model_day0
                if base is None or w >= 1.0:
                    self._model = fresh
                else:
                    self._model = _blend_models(base, fresh, w)
            except Exception:
                self._error_count += 1

    def on_trade(self, option: BinaryOption, price: float, quantity: int,
                 counterparty_id: int) -> None:
        # interface-mandated position update (identical to the organizer scaffold; retained)
        self.position.add_option_quantity(option.option_id, quantity)
        try:
            # 镜像评测端记账：买 q@p 占 q·p，卖占 |q|·(1−p)
            if quantity > 0:
                self._mirror_cash -= quantity * price
            else:
                self._mirror_cash -= (-quantity) * (1.0 - price)
            self._trades_by_option[option.option_id].append(
                (price, quantity, counterparty_id))
            theo = self.price_option(option)
            sign = 1 if quantity > 0 else -1
            fingerprint = (option.option_id, counterparty_id, round(price, 2))
            is_fok = fingerprint in self._accepted_foks
            self._pending_markouts.append(
                (option.option_id, sign, theo, counterparty_id, is_fok))
            if quantity > 0:
                self._buy_fills += 1
            else:
                self._sell_fills += 1
            # 鲸鱼判定：成交价离理论价 ≥0.3（纯价格极端不算——便宜期权
            # 的正常报价本身就可能 ≤0.03）
            if abs(theo - price) >= 0.3:
                self._extreme_profit += abs(quantity) * abs(theo - price)
                self._cp_extreme_fills[counterparty_id] += 1
            # 榨取活性：成交发生在极端价位且有实质 edge（含资金强制价）
            min_edge = CFG["extraction_fill_min_edge"]
            if ((quantity > 0 and price <= CFG["extreme_bid"] + 1e-9
                 and theo - price >= min_edge)
                    or (quantity < 0 and price >= CFG["extreme_offer"] - 1e-9
                        and price - theo >= min_edge)):
                self._extraction_fills += 1
            # 价格阶梯重置：默认回极端档接着探（E5 删失校正）；
            # tight 对手回它成交过的最高档（E32，见 CFG 注释）。
            # FOK 成交不参与档位记账（没经过 quote()，档位不可归因）
            reset_to = 0
            if CFG["reset_tier_adaptive"] > 0 and not is_fok:
                tier = self._cp_last_tier.get(counterparty_id, 0)
                tf = self._cp_tier_fills.setdefault(counterparty_id, [0, 0, 0])
                tf[tier] += 1
                tq = self._cp_tier_quotes.get(counterparty_id, [0, 0, 0])
                n_fills = tf[0] + tf[1] + tf[2]
                if (tf[0] == 0
                        and tq[0] >= CFG["reset_tier_min_extreme_quotes"]
                        and tf[1] + tf[2] >= CFG["reset_tier_min_fills"]
                        and n_fills % int(CFG["reset_tier_reprobe_every"]) != 0):
                    reset_to = (int(CFG["cp_extreme_strikes"]) if tf[1] > 0
                                else int(CFG["cp_mid_strikes"]))
            self._cp_nofill[counterparty_id] = reset_to
            # 成交率自适应：RFQ 成交 → 加宽。FOK 成交按指纹剔除
            if is_fok:
                self._accepted_foks.remove(fingerprint)
            else:
                self._quotes_since_rfq_fill = 0
                if self._width_mult < 1.0:  # 饥饿收窄的回弹（只回不冲）
                    self._width_mult = min(
                        self._width_mult * CFG["starve_recover"], 1.0)
                self._width_mult = min(
                    self._width_mult * CFG["width_adapt_up"],
                    CFG["width_mult_max"])
        except Exception:
            self._error_count += 1

    # ------------------------------------------------------------------
    # 六个必填方法
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return PARTICIPANT_NAME

    def price_option(self, option: BinaryOption) -> float:
        try:
            if self._model is None:
                return 0.5
            return price_option_with_model(self._model, self._values(), option)
        except Exception:
            self._error_count += 1
            return 0.5

    def price_option_from_parameters(
        self, market_parameters: MarketParameters, option: BinaryOption
    ) -> float:
        # THEO 通道曾裸奔：退化输入（如标的价被舍入到 0）炸一个合约
        # 会拖垮整个 THEO 测试；兜底 0.5 保住其余合约的得分
        try:
            return price_option_with_model(
                model_from_parameters(market_parameters), self._values(), option)
        except Exception:
            self._error_count += 1
            return 0.5

    def quote(self, option: BinaryOption, counterparty_id: int) -> Quote:
        try:
            return self._quote_inner(option, counterparty_id)
        except Exception:
            self._error_count += 1
            # 零占用合法报价：买 1 张 @0.00 占 0，卖 1 张 @1.00 占 0
            return Quote(bid_price=0.0, bid_quantity=1,
                         offer_price=1.0, offer_quantity=1)

    def respond_to_fok(self, option: BinaryOption, fok_order: FokOrder) -> bool:
        """风险调整 EV 决策：每张期望利润 ≥ 下限，且期望利润/占用资本
        ≥ 下限（这样 0.99 卖 theo≈1 的近无风险单会被接——旧的固定
        edge 门槛拒掉了它们），且最坏占用在资本预算内。sharp 对手
        （markout 画像）门槛按倍数提高。"""
        try:
            theo = self.price_option(option)
            pos = self.position.option_quantity_by_option_id.get(option.option_id, 0)
            if fok_order.order_type == OrderType.BUY:
                ev_per = fok_order.price - theo       # 我们卖
                commit_per = 1.0 - fok_order.price
                pos_ok = pos - fok_order.quantity >= -CFG["max_position_per_option"]
            else:
                ev_per = theo - fok_order.price       # 我们买
                commit_per = fok_order.price
                pos_ok = pos + fok_order.quantity <= CFG["max_position_per_option"]
            # 送 ≥0.3/张的 FOK = 鲸鱼行为，标记该对手方（无论是否成交）
            if ev_per >= 0.3:
                self._cp_extreme_fills[fok_order.counterparty_id] += 1

            # 只用对手方画像提门槛；全局毒性不进 FOK（W4 实验证明会
            # 拒掉本该吃的肥单，C18 从 +31 掉到 −1.5）
            mult = self._cp_multiplier(fok_order.counterparty_id,
                                       CFG["cp_sharp_fok_mult"])
            # E36：累计结算亏损超过闸值 → 按 sharp 待遇（慢性放血流
            # 的 markout 显干净，只有 realized 能抓到）
            rflag = CFG["cp_realized_flag"] * max(
                1.0, self._initial_cash / CFG["cp_realized_ref_capital"])
            if (CFG["cp_realized_flag"] > 0 and self._cp_realized.get(
                    fok_order.counterparty_id, 0.0) <= -rflag):
                mult = max(mult, CFG["cp_sharp_fok_mult"])
            roc = ev_per / commit_per if commit_per > 1e-9 else float("inf")
            # 门槛按合约的 theo 日波动加码：sharp 对手的信息优势集中在
            # 高波动（短期限 ATM）合约
            eff_mult = CFG["fok_vol_mult"]
            fok_marks = self._fok_markouts
            if len(fok_marks) >= CFG["fok_markout_min_n"]:
                mean_fok = sum(fok_marks) / len(fok_marks)
                if mean_fok < -0.02:
                    eff_mult = CFG["fok_vol_mult_toxic"]
                elif mean_fok < 0.0:
                    eff_mult = CFG["fok_vol_mult_suspect"]
                elif mean_fok > 0.02:
                    eff_mult = CFG["fok_vol_mult_benign"]
            vol_premium = eff_mult * self._theo_daily_vol(option)
            marks = self._markouts_by_counterparty.get(fok_order.counterparty_id)
            if marks and len(marks) >= 3:
                mean_mark = sum(marks) / len(marks)
                if mean_mark >= CFG["cp_clean_markout"]:
                    vol_premium = 0.0          # 3 笔以上正 markout 才算清白
                elif mean_mark >= CFG["cp_suspect_markout"]:
                    vol_premium *= 0.5         # 轻度可疑：半剂量
            else:
                vol_premium *= CFG["fok_vol_unknown_scale"]
            ev_floor = CFG["fok_min_ev"] + vol_premium
            ev_ok = (ev_per >= ev_floor * mult
                     and roc >= CFG["fok_min_roc"] * mult)
            cash_ok = (fok_order.quantity * commit_per
                       <= self._available_cash() * CFG["fok_max_commit_fraction"])
            accept = ev_ok and cash_ok and pos_ok
            if accept:
                self._accepted_foks.append(
                    (option.option_id, fok_order.counterparty_id,
                     round(fok_order.price, 2)))
                if len(self._accepted_foks) > 50:
                    self._accepted_foks.pop(0)
            return accept
        except Exception:
            self._error_count += 1
            return False

    def warm_up(self, market_history: MarketHistory) -> None:
        try:
            self._model = estimate_model(market_history)
            # E49：保留原始行情行；<21 天标记退化 → session 在线重估
            self._history_rows = {
                uid: list(vs)
                for uid, vs in market_history.values_by_underlying_id.items()}
            self._degenerate_warmup = market_history.num_days < 21
            self._model_day0 = self._model
        except Exception:
            self._error_count += 1
            self._model = None

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------

    def _values(self) -> dict[int, float]:
        return {u.underlying_id: u.value for u in self.underlying_state}

    def _available_cash(self) -> float:
        """可动用现金 = 镜像余额 × use_fraction，余下是防破产垫。"""
        return max(self._mirror_cash, 0.0) * CFG["capital_use_fraction"]

    def _cp_multiplier(self, counterparty_id: int, sharp_mult: float) -> float:
        """对手方画像：markout 均值显著为负 → sharp → 返回加宽倍数。"""
        marks = self._markouts_by_counterparty.get(counterparty_id)
        if not marks or len(marks) < CFG["cp_min_trades"]:
            return 1.0
        n = len(marks)
        mean = sum(marks) / n
        var = sum((m - mean) ** 2 for m in marks) / (n - 1)
        se = math.sqrt(var / n)
        # 均值 + 1SE 仍低于阈值才算显著（漏判优于误判）
        if mean + se <= CFG["cp_sharp_threshold"]:
            return sharp_mult
        return 1.0

    def _toxicity_mult(self) -> float:
        """毒性信号 = markout 均值中超出 1 个标准误的负值部分。
        收缩处理防止小样本噪声导致的过度反应（EWMA 版实测把价差
        随机撑大、吓跑噪声流，已废弃）。"""
        marks = self._recent_markouts
        n = len(marks)
        if n < 12:
            return 1.0
        mean = sum(marks) / n
        var = sum((m - mean) ** 2 for m in marks) / (n - 1)
        se = math.sqrt(var / n)
        signal = max(0.0, -(mean + 1.5 * se))
        return min(1.0 + CFG["toxicity_spread_mult"] * signal,
                   CFG["toxicity_max_mult"])

    def _resolve_markouts(self, old_options: dict[int, BinaryOption]) -> None:
        """结算 1 天 markout：新状态下重估昨天的成交。期权已到期则用
        结算值。更新全局滚动窗口（FOK/RFQ/合计 markout）与对手方画像。"""
        if not self._pending_markouts:
            return
        pending, self._pending_markouts = self._pending_markouts, []
        values = self._values()
        for option_id, sign, theo_then, cp_id, is_fok in pending:
            option = self._option_by_id.get(option_id)
            if option is not None:
                theo_now = self.price_option(option)
            else:
                old = old_options.get(option_id)
                if old is None:
                    continue
                theo_now = old.expiry_valuation(values)
            markout = sign * (theo_now - theo_then)
            if is_fok:
                self._fok_markouts.append(markout)
                if len(self._fok_markouts) > 60:
                    self._fok_markouts.pop(0)
            else:
                self._rfq_markouts.append(markout)
                if len(self._rfq_markouts) > 60:
                    self._rfq_markouts.pop(0)
            self._recent_markouts.append(markout)
            if len(self._recent_markouts) > int(CFG["toxicity_window"]):
                self._recent_markouts.pop(0)
            self._markouts_by_counterparty[cp_id].append(markout)

    def _settle_expired(self, new_underlyings: list[Underlying],
                        new_options: list[BinaryOption]) -> None:
        """镜像评测端的到期返还：多头收 payoff，空头收 (1−payoff)。"""
        new_ids = {o.option_id for o in new_options}
        new_values = {u.underlying_id: u.value for u in new_underlyings}
        for option_id, trades in list(self._trades_by_option.items()):
            if option_id in new_ids:
                continue
            option = self._option_by_id.get(option_id)
            if option is None:
                continue
            payoff = option.expiry_valuation(new_values)
            for price, qty, cp in trades:
                if qty > 0:
                    self._mirror_cash += qty * payoff
                else:
                    self._mirror_cash += (-qty) * (1.0 - payoff)
                # E36：按对手方记账已实现结算盈亏（带符号统一公式：
                # 买 q(pay−p)，卖 (−q)(p−pay) = q(pay−p)）
                self._cp_realized[cp] += qty * (payoff - price)
            del self._trades_by_option[option_id]

    def _theo_daily_vol(self, option: BinaryOption) -> float:
        """明天 theo 变动的两点近似标准差（宽度的风险刻度）。

        所有腿按权重方向同时移动 1 个日σ（对可观测量的最坏相关情形；
        价差期权因此是两腿反向），FED 腿动一格 0.25，然后在 D−1 上
        重定价。1d ATM 会得到 0.3-0.5 的量级，长期限/深度价内外趋近 0。
        """
        if option.steps_until_expiry <= 0 or self._model is None:
            return 0.0
        cached = self._theo_vol_cache.get(option.option_id)
        if cached is not None and cached[0] == self._day:
            return cached[1]
        values = self._values()
        up = dict(values)
        down = dict(values)
        for leg in option.legs:
            uid = leg.underlying_id
            direction = 1.0 if leg.weight > 0 else -1.0
            if uid == FED_FUNDS_RATE_UNDERLYING_ID:
                up[uid] = max(round(values[uid] + direction * 0.25, 2), 0.0)
                down[uid] = max(round(values[uid] - direction * 0.25, 2), 0.0)
            else:
                sigma = math.sqrt(self._model.company[uid].daily_var)
                up[uid] = values[uid] * math.exp(direction * sigma)
                down[uid] = values[uid] * math.exp(-direction * sigma)
        nxt = option.advance_step()
        vol = abs(price_option_with_model(self._model, up, nxt)
                  - price_option_with_model(self._model, down, nxt)) / 2.0
        self._theo_vol_cache[option.option_id] = (self._day, vol)
        return vol

    def _quote_inner(self, option: BinaryOption, counterparty_id: int) -> Quote:
        theo = self.price_option(option)
        pos = self.position.option_quantity_by_option_id.get(option.option_id, 0)

        # 按对手方价格阶梯：连续未成交次数决定档位（成交即归零回极端档）
        nofill = self._cp_nofill.get(counterparty_id, 0)
        cp_width_mult = 1.0
        cp_heavy = CFG["heavy_side_threshold"]
        if nofill >= CFG["cp_mid_strikes"]:
            cp_heavy = 10.0         # 竞争档：报最窄去卷固定宽度报价者
        elif nofill >= CFG["cp_extreme_strikes"]:
            cp_heavy = 10.0         # 中档：不报极端，价差放宽收割中价流
            cp_width_mult = CFG["cp_mid_width_mult"]
        # 档位记账（重置档自适应 E32 的原料）：0=极端 1=中 2=竞争
        cur_tier = (0 if nofill < CFG["cp_extreme_strikes"]
                    else 1 if nofill < CFG["cp_mid_strikes"] else 2)
        self._cp_last_tier[counterparty_id] = cur_tier
        self._cp_tier_quotes.setdefault(
            counterparty_id, [0, 0, 0])[cur_tier] += 1

        half = max(CFG["base_half_spread"]
                   + CFG["spread_per_day"] * option.steps_until_expiry,
                   CFG["min_half_spread"])
        half += CFG["vol_spread_mult"] * self._theo_daily_vol(option)
        if cp_width_mult > 1.0:
            # cap 不得把宽度压到风险刻度以下（1d ATM 的 half 可能 >0.12）
            half = min(half * cp_width_mult, max(CFG["cp_mid_half_cap"], half))
        # 三层自适应：成交率（流愿付多少就收多少）、毒性（被逆向选择
        # → 加宽）、对手方画像（sharp 对手针对性加宽）
        # 饥饿收窄：长期零 RFQ 成交 → 主动收窄探市场宽度。
        # 【E26 教训】必须要求正面证据（已解决 markout 够数且均值非负）
        # 才准收窄：零成交本身可能是流恶劣的症状（C6 的最宽固定宽度报价者场里
        # 宽度即防守），证据真空期收窄 = 把防御性缺席当成安全信号
        if (CFG["starve_after_quotes"] > 0
                and self._quotes_since_rfq_fill >= CFG["starve_after_quotes"]):
            marks_s = self._rfq_markouts
            if (len(marks_s) >= CFG["rfq_markout_min_n"]
                    and sum(marks_s) / len(marks_s) >= 0.0):
                self._width_mult = max(
                    self._width_mult * CFG["starve_decay"],
                    CFG["starve_floor"])
        self._width_mult = max(self._width_mult * CFG["width_adapt_down"],
                               CFG["width_mult_min"])
        half *= self._width_mult
        half *= self._toxicity_mult()
        rfq_marks = self._rfq_markouts
        if len(rfq_marks) >= CFG["rfq_markout_min_n"]:
            mean_rfq = sum(rfq_marks) / len(rfq_marks)
            if mean_rfq < -0.02:
                half *= CFG["rfq_width_toxic"]
            elif mean_rfq < 0.0:
                half *= CFG["rfq_width_suspect"]
        half *= self._cp_multiplier(counterparty_id, CFG["cp_sharp_spread_mult"])
        # E36：慢性放血对手（累计结算亏损超闸值）报价同样加宽
        if (CFG["cp_realized_flag"] > 0
                and self._cp_realized.get(counterparty_id, 0.0)
                <= -CFG["cp_realized_flag"] * max(
                    1.0, self._initial_cash / CFG["cp_realized_ref_capital"])):
            half *= CFG["cp_sharp_spread_mult"]
        skew = -CFG["skew_per_contract"] * pos
        skew = min(max(skew, -CFG["max_skew"]), CFG["max_skew"])
        center = theo + skew

        bid = floor_penny(center - half)
        offer = ceil_penny(center + half)
        bid = min(max(bid, 0.0), 0.98)
        offer = min(max(offer, bid + 0.01), 1.0)
        offer = max(offer, 0.01)
        if bid >= offer:  # 双保险（浮点边界）
            bid = max(offer - 0.01, 0.0)

        cash = self._available_cash()
        # 赢冲输缩：盈利场加大预算吃溢流（拆单机制下余量才不喂固定宽度报价者），
        # 不盈利场保持基线——见 CFG size_ramp 注释
        profit_frac = ((self._mirror_cash - self._initial_cash)
                       / max(self._initial_cash, 1e-9))
        ramp = min(max((profit_frac - CFG["size_ramp_start"])
                       / max(CFG["size_ramp_full"] - CFG["size_ramp_start"],
                             1e-9), 0.0), 1.0)
        base_frac = CFG["per_quote_capital_fraction"]
        if self._initial_cash >= CFG["highcap_threshold"] - 1e-9:
            base_frac = CFG["per_quote_capital_fraction_highcap"]
        per_quote = cash * base_frac * (1.0 + CFG["size_ramp_mult"] * ramp)
        max_pos = CFG["max_position_per_option"]
        # 毒性高时按比例砍数量（加宽保护价格，砍量保护本金）
        size_scale = 1.0 / self._toxicity_mult()
        base_size = max(CFG["base_quote_size"] * size_scale, 1.0)
        # 买入侧每张占 bid，卖出侧每张占 (1−offer)；持仓上限双向约束
        bid_qty = min(base_size,
                      per_quote / max(bid, 0.01),
                      max_pos - pos)
        offer_qty = min(base_size,
                        per_quote / max(1.0 - offer, 0.01),
                        max_pos + pos)
        bid_qty = max(int(bid_qty), 1)
        offer_qty = max(int(offer_qty), 1)

        # 持仓/资金逼近上限的一侧退到极端价（qty 必须 ≥1，用价格表达
        # "不想要"；W1"付得起就报真价"已试并回退，详 docs/experiment_log.md W1 行）
        extreme_qty = int(CFG["extreme_quote_size"])
        extreme_budget = cash * CFG["extreme_capital_fraction"]
        heavy = cp_heavy
        if (self._day >= CFG["extreme_probe_days"]
                and self._extreme_profit < CFG["extreme_min_profit"]):
            heavy = CFG["heavy_side_threshold_quiet"]  # 鲸鱼不够肥，回双边
        # 榨取死亡开关：极端价位零成交 AND 双通道 markout 干净才判死
        # （第二轮泛化；资金/持仓强制的极端价不受影响，下面仍会触发）。
        # 【E26 教训】毒流场里单边极端结构是护甲：C6 关榨取 0.7→0.4，
        # 损失不来自错过鲸鱼、而来自 heavy 侧失去单边保护被薄边流咬；
        # 反例 C12/C14 干净场关榨取 PnL +12/+6。故毒性通道任一为负时
        # 不判死——干净紧书市场里榨取才纯粹是档位浪费
        dead_day = CFG["extraction_dead_day"]
        if (dead_day > 0 and self._day >= dead_day
                and self._extraction_fills == 0):
            fm = self._fok_markouts
            rm = self._rfq_markouts
            fok_bad = (len(fm) >= CFG["fok_markout_min_n"]
                       and sum(fm) / len(fm) < 0.0)
            rfq_bad = (len(rm) >= CFG["rfq_markout_min_n"]
                       and sum(rm) / len(rm) < 0.0)
            if not (fok_bad or rfq_bad):
                heavy = CFG["heavy_side_threshold_quiet"]
        if pos >= max_pos or (bid > 0 and (bid > heavy or bid > cash)):
            bid = CFG["extreme_bid"]
            # E51 (Line A v13)：theo 在错侧（买高于公允）或预算付不起 1 张 → 0.00 零占用
            if theo < bid or extreme_budget < bid:
                bid = 0.0
            bid_qty = max(min(extreme_qty, int(extreme_budget / max(bid, 0.01))), 1)
            offer = max(offer, bid + 0.01)
        if pos <= -max_pos or (1.0 - offer) > heavy or (1.0 - offer) > cash:
            offer = CFG["extreme_offer"]
            if theo > offer or extreme_budget < 1.0 - offer:
                offer = 1.0
            offer_qty = max(min(extreme_qty,
                                int(extreme_budget / max(1.0 - offer, 0.01))), 1)
            if bid >= offer:
                bid = max(offer - 0.01, 0.0)

        self._cp_nofill[counterparty_id] = nofill + 1  # 成交时会被归零
        self._quotes_since_rfq_fill += 1               # 饥饿时钟

        return Quote(bid_price=round(bid, 2), bid_quantity=bid_qty,
                     offer_price=round(offer, 2), offer_quantity=offer_qty)

"""C8-FED 之谜的量化（菜单④）：估计误差按合约类别的分布。

    python3 exp_c8_fed_sensitivity.py

背景：E34 显示 C8/C18/C20 的边际全挂在 FED theo 上（斜率合并的
微小移动引发三场大重排）。假说：FED 二元的估计误差比公司二元
**大且长尾**——tilt 斜率是二次矩很小的线性概率回归（一天只动
±0.25 一格，样本信息稀薄），误差经 DP 逐日复利；而公司腿的
drift/beta 噪声在 Φ 里被 √D·σ 摊薄。若 FED theo 误差经常越过
±0.05（= 中等宽度固定报价者的半宽 = 路由翻转阈值），FW 场的边际就是估计噪声
的函数——这解释超敏感，也解释为什么 E34 那种"更优估计器"在
固定种子上是彩票。

输出：按类别（FED / 公司 / 价差）× 期限的 |est−true| 均值、p90、
超阈值比例。纯量化研究，不改任何代码。
"""
import math
import random
import statistics
import sys

BASE = "<WORKDIR>/akuna2026"
sys.path.insert(0, BASE)

import harness
from solution import (
    AJARAI_UNDERLYING_ID as AJR, FED_FUNDS_RATE_UNDERLYING_ID as FED,
    THERIODIC_UNDERLYING_ID as THR, BinaryOption, MarketHistory, OptionLeg,
    estimate_model, model_from_parameters, price_option_with_model,
)

WARMUP = int(sys.argv[1]) if len(sys.argv) > 1 else 400   # 默认 400 天复现历史数字；比赛实际 warm-up 为 15–45 天，传参重跑可见误差约 3–4 倍（均值 ≈ 9–12¢）
HORIZONS = (1, 2, 4, 8)
SEEDS = 40


def gen(seed):
    rng = random.Random(seed)
    random.seed(seed * 13 + 7)
    params = harness.sample_parameters(rng)
    values = {FED: 2.0, AJR: rng.uniform(400, 1500), THR: rng.uniform(400, 1500)}
    rows = {uid: [v] for uid, v in values.items()}
    for _ in range(WARMUP - 1):
        values = params.advance_step(values)
        for uid, v in values.items():
            rows[uid].append(v)
    hist = MarketHistory(values_by_underlying_id={
        uid: tuple(vs) for uid, vs in rows.items()})
    return params, values, hist


def contracts(values, oid_start=1):
    """近值区网格：FED ±3 格、公司 ±6%、价差 strike 0。"""
    out = []
    oid = oid_start
    grid = round(values[FED] * 4) / 4
    for d in HORIZONS:
        for k in range(-3, 4):
            strike = grid + 0.25 * k
            if strike < 0.25:
                continue
            out.append(("FED", d, BinaryOption(
                (OptionLeg(FED, 1.0),), oid, d, strike)))
            oid += 1
        for uid, tag in ((AJR, "COMP"), (THR, "COMP")):
            for pct in (-0.06, -0.03, -0.01, 0.0, 0.01, 0.03, 0.06):
                strike = round(values[uid] * (1 + pct), 2)
                out.append((tag, d, BinaryOption(
                    (OptionLeg(uid, 1.0),), oid, d, strike)))
                oid += 1
        for legs in (((AJR, 1.0), (THR, -1.0)), ((AJR, -1.0), (THR, 1.0))):
            out.append(("SPRD", d, BinaryOption(
                tuple(OptionLeg(u, w) for u, w in legs), oid, d, 0.0)))
            oid += 1
    return out


def main():
    errs = {}          # (class, horizon) -> [abs err]
    for seed in range(SEEDS):
        params, values, hist = gen(seed)
        true_m = model_from_parameters(params)
        est_m = estimate_model(hist)
        for tag, d, opt in contracts(values):
            t = price_option_with_model(true_m, values, opt)
            e = price_option_with_model(est_m, values, opt)
            # 只统计有肉的区间（深度 0/1 两边误差天然为 0，会稀释信号）
            if 0.02 <= t <= 0.98:
                errs.setdefault((tag, d), []).append(abs(e - t))

    print(f"{SEEDS} 种子 × 近值网格，|est theo − true theo| 按类别×期限：")
    print(f"{'类别':6s} {'期限':4s} {'n':>5s} {'均值':>7s} {'p90':>7s} "
          f"{'>0.025':>7s} {'>0.05':>7s}")
    for tag in ("FED", "COMP", "SPRD"):
        for d in HORIZONS:
            xs = errs.get((tag, d))
            if not xs:
                continue
            xs_sorted = sorted(xs)
            p90 = xs_sorted[int(0.9 * len(xs))]
            f25 = sum(1 for x in xs if x > 0.025) / len(xs)
            f50 = sum(1 for x in xs if x > 0.05) / len(xs)
            print(f"{tag:6s} {d:>3d}d {len(xs):5d} {statistics.mean(xs):7.4f} "
                  f"{p90:7.4f} {f25:6.1%} {f50:6.1%}")
    all_by_tag = {}
    for (tag, _), xs in errs.items():
        all_by_tag.setdefault(tag, []).extend(xs)
    print("\n汇总（全期限）：")
    for tag, xs in all_by_tag.items():
        f50 = sum(1 for x in xs if x > 0.05) / len(xs)
        print(f"  {tag:6s} n={len(xs):5d} 均值={statistics.mean(xs):.4f} "
              f"max={max(xs):.4f} >0.05比例={f50:.1%}")


if __name__ == "__main__":
    main()

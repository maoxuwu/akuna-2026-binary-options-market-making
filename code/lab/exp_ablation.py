"""终版消融（红队 critic 提议）：v12 逐支柱关闭 × 配对种子。

    python3 exp_ablation.py

四支柱 + 三辅助机制的价值证据此前全是"采纳当时对彼时基座的增量"
（E22 对 E18 基座、E25 对 E23 基座……月距代码），从未在 v12 终版上
统一消融。本实验：v12 完整版 vs 逐一关闭每个机制，20 配对种子 ×
3 流量制度 × 2 warm-up 长度（250 天正常 / 3 天退化——逃生舱只在
后者活跃）。Δ = full − ablated = 该机制在终版组合里的边际价值。
多进程并行（每 arm 独立进程，CFG 突变天然隔离）。
"""
import concurrent.futures as cf
import math
import statistics
import sys

BASE = "<WORKDIR>/akuna2026"

ARMS = {
    "full": {},
    "-ladder_probe": {"cp_extreme_strikes": 9999},      # 永不降档 = 关闭阶梯探测
    "-reset_tier": {"reset_tier_adaptive": 0.0},
    "-extraction": {"heavy_side_threshold": 10.0},       # 关单边榨取结构
    "-fok_dose": {"fok_markout_min_n": 99999},           # 冻结动态 FOK 剂量在基线
    "-rfq_width": {"rfq_width_toxic": 1.0, "rfq_width_suspect": 1.0},  # 只关加宽，不伤饥饿收窄
    "-realized_gate": {"cp_realized_flag": 0.0},
    "-ramp": {"size_ramp_mult": 0.0},
    "-hatch": {"reestimate_if_degenerate": 0.0},
}

SCENARIOS = ("calm_dumb", "mixed", "toxic")
WARMUPS = (250, 3)
SEEDS = 20


def run_cell(args):
    arm, overrides, warmup, scen = args
    sys.path.insert(0, BASE)
    import random
    import solution
    from solution import CFG
    import exp_e42_base15 as X
    # worker 进程会被复用：每 cell 先从原始快照恢复 CFG，防臂间污染
    if not hasattr(solution, "_pristine_cfg"):
        solution._pristine_cfg = dict(CFG)
    CFG.clear(); CFG.update(solution._pristine_cfg); CFG.update(overrides)
    X.WARMUP_DAYS = warmup
    kw = X.SCENARIOS[scen]
    pnls = []
    for seed in range(SEEDS):
        capital = random.Random(seed).choice([10.0, 20.0, 40.0])
        r = X.run_session(seed, capital, rfq_qty_max=30, **kw)
        pnls.append(r["pnl"])
    return arm, warmup, scen, pnls


def main():
    tasks = [(arm, ov, w, s) for arm, ov in ARMS.items()
             for w in WARMUPS for s in SCENARIOS]
    results = {}
    with cf.ProcessPoolExecutor(max_workers=9) as ex:
        for arm, w, s, pnls in ex.map(run_cell, tasks):
            results[(arm, w, s)] = pnls

    print(f"{'机制（关闭项）':16s}", end="")
    for w in WARMUPS:
        for s in SCENARIOS:
            print(f" | {'wu' + str(w) + ':' + s[:5]:>13s}", end="")
    print()
    for arm in ARMS:
        if arm == "full":
            continue
        print(f"{arm:16s}", end="")
        for w in WARMUPS:
            for s in SCENARIOS:
                base = results[("full", w, s)]
                abl = results[(arm, w, s)]
                deltas = [b - a for b, a in zip(base, abl)]
                m = statistics.mean(deltas)
                se = (statistics.stdev(deltas) / math.sqrt(len(deltas))
                      if len(deltas) > 1 else 0)
                print(f" | {m:+7.2f}±{se:4.1f}", end="")
        print()
    # 金丝雀：-hatch 在 wu250 必须逐位恒等（结构性不触发）
    for s in SCENARIOS:
        base = results[("full", 250, s)]
        abl = results[("-hatch", 250, s)]
        assert all(abs(b - a) < 1e-9 for b, a in zip(base, abl)), f"金丝雀失败: {s}"
    print("\n金丝雀通过：-hatch@wu250 逐位恒等 ✓")
    print("（Δ = full − ablated：正 = 该机制在 v12 终版组合中贡献为正）")


if __name__ == "__main__":
    main()

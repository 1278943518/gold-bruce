# -*- coding: utf-8 -*-
"""④ 正式公式：COT「购买速度」指数（2026-10-04 反解锁定）

博主 09-19 原话：
  "看这些资金变化的速率……我每个月买进 100 单，这个月突然买了 200 单，
   它买得有点急了因为它看涨……在总量上变化不大，
   但相对时间内的量能变化会显露出来，把这个细微变化放大"

落成公式：
  speed(t) = (多头持仓(t) − 多头持仓(t−K)) / K        # 每周平均【买入速度】
  idx(t)   = (speed(t) − min_N(speed)) / (max_N(speed) − min_N(speed))   ∈ [0,1]
             ↑ "把量能的细微变化放大" → 归一化成 0~1 摆荡指标（"干到顶部"＝接近 1）

默认参数：K=13 周（一个季度）、N=52 周（一年）、持仓口径=多头持仓（他说的"买量"）
三条线（他视频配色）：绿=商业头寸 蓝=管理基金 红=其他可报告（散户小机构）

锁定依据：
  1) 数值锚点：2026-08-25 绿线 = 0.9109 vs 他画面 0.908（差 0.3%）
  2) 取值区间：2026 年 0.36~1.00 vs 他画面 0.35~1.1
  3) 叙事①：蓝线 2026-01-20 = 0.900 打顶 → 金价 5217 跌到 4021（他说"26年2月干顶后跌了一大波"）
  4) 叙事②：绿线 2026-06-30 = 0.906 打顶 → 金价 4021 涨到 4716（他说"绿线干顶＝底部，4000→4600"）
  5) 叙事③：8/25 蓝线 0.972 且连涨（他说"蓝线涨了两个月，到顶差不多了"）
"""
import json, os

# ⚠ 本文件在本机另有一份副本：C:/Users/Leo/WorkBuddy/抖音博主蒸馏/scripts/
# 两份**故意不同**：此处 BASE 按脚本位置推导（GitHub Actions 用），抖音那份写死本机路径。
# 同步时只同步「算法与口径」部分，不要整文件覆盖，否则会把可移植路径冲掉（2026-10-05 踩过）。
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MKT = os.path.join(BASE, "data", "market")
OUT = os.path.join(MKT, "cot_speed_index.json")

K = 13       # 速度窗口（周）
N = 52       # 归一化窗口（周）
# 口径＝毛多头寸 long（2026-10-05 复核后确定，别再改回 net）。
# 反证：布鲁斯 2026-08-25 画面绿线读数 0.908，全部 12 条候选口径（商业/管理基金/散户 × 多/空/净）
# 里只有 prod_long 对得上（本模型 0.9109，差 0.3%）；改成 net 会变成 0.158，差 75%，直接否掉。
# net 能让绿蓝相关性从 +0.09 变成 −0.74（看起来"一上一下"），但代价是绿线读数彻底对不上他画面，
# 且回测信号同时变弱（蓝线打顶超额 +25.5pp → +5.7pp）。「他那种一上一下」是视觉/坐标轴效应，
# 不是口径效应 —— 在 prod_long 约束下，蓝线换任何口径相关性都在 −0.11~+0.26 之间，做不出负相关。
BASIS = "long"
CATS = [("prod", "绿线·商业头寸（市场最大资金）"),
        ("mm", "蓝线·管理基金（华尔街投机资金）"),
        ("other", "红线·其他可报告（散户小机构）")]


def delta(v, k):
    return [None] * k + [(v[i] - v[i - k]) / k for i in range(k, len(v))]


def stoch(v, n):
    o = [None] * len(v)
    for i in range(n - 1, len(v)):
        w = [x for x in v[i - n + 1:i + 1] if x is not None]
        if len(w) < n or v[i] is None:
            continue
        lo, hi = min(w), max(w)
        o[i] = None if hi == lo else (v[i] - lo) / (hi - lo)
    return o


def main():
    cot = json.load(open(os.path.join(MKT, "cot_gold.json"), encoding="utf-8"))
    cot.sort(key=lambda c: c["date"])
    dates = [c["date"] for c in cot]

    out = {"params": {"speed_weeks": K, "norm_weeks": N, "basis": BASIS},
           "formula": "speed=(%s_t - %s_{t-K})/K ; idx=(speed-min_N)/(max_N-min_N)" % (BASIS, BASIS),
           "dates": dates, "lines": {}}
    for key, label in CATS:
        v = [c[key + "_" + BASIS] for c in cot]
        sp = delta(v, K)
        out["lines"][key] = {"label": label, "speed": sp, "idx": stoch(sp, N)}
        out[key + "_idx"] = stoch(sp, N)

    # 有效区间（预热 = K + N - 1 周）
    warm = K + N - 1
    out["valid_from"] = dates[warm]
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    print("COT 购买速度指数已生成:", OUT)
    print("公式 speed=(long_t−long_{t−%d})/%d ；idx= stochastic_%d(speed)" % (K, K, N))
    print("有效区间 %s ~ %s（预热 %d 周）" % (dates[warm], dates[-1], warm))
    i = dates.index("2026-08-25")
    for key, label in CATS:
        val = out[key + "_idx"][i]
        print("  %-28s 8/25 = %s" % (label, ("%.4f" % val) if val is not None else "—"))
    print()
    print("最近 8 周读数：")
    print("  %-12s %-8s %-8s %-8s" % ("date", "绿", "蓝", "红"))
    for j in range(len(dates) - 8, len(dates)):
        f = lambda v: ("%.3f" % v) if v is not None else "—"
        print("  %-12s %-8s %-8s %-8s" % (dates[j], f(out["prod_idx"][j]),
                                          f(out["mm_idx"][j]), f(out["other_idx"][j])))


if __name__ == "__main__":
    main()

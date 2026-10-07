# -*- coding: utf-8 -*-
"""④ 正式公式：经典 COT Index（2026-10-08 由博主视频截图反解锁定）

博主 2026-09-19 视频画面里的第三栏指示器叫 `COT-index comm/large/specs`，
右边 Y 轴 0 ~ 100、一条 50 虚线 —— 这是经典的 COT Index：

    idx(t) = (net_t − min_N(net)) / (max_N(net) − min_N(net)) × 100

即 **作用在【净头寸】上、窗口 N 周、没有速度差分** 的随机指标（0~100）。

锁定依据（2026-10-08，逐像素反解）
--------------------------------
把截图第三栏那条「蓝线」按像素逐列取出（1379 个有效列），再拿本地 CFTC 真实数据
做滑动相关，在 5.4~6.6 px/周 × 13 种序列 × 4 种窗口 × 3 种算法 里比：

    蓝线 ×「商业 Producer/Merchant 净头寸 + 26 周 + 无差分」→ r = 0.886
    （第 1 名；前 5 名全是这一条，第 2 名 0.828）

对照：管理基金(net,26) r=0.402、其他类(net,52) r=0.445，毛多头寸 / 速度差分的
所有组合都 < 0.70。→ **博主图上的蓝线＝商业（Producer/Merchant）**。

同源核对：蓝线在 2026-02-02 十字线处读数 ≈ 90~93；
本模型商业 index 2026-02-03 = 100、2026-02-24 = 94 ✓
他口播「蓝线最近一次干到顶是 26 年 2 月」= 商业净头寸当时处在 26 周最高位 ✓

⚠⚠ 旧的 (毛多_t − 毛多_{t−13})/13 再 52 周归一化 **是错的，已弃用**。
它唯一的"证据"是 2026-08-25 画面读数 0.908 ≈ 商业毛多 0.9109 ——
现在看是巧合：正确口径下该点商业 = 0、管理基金 = 100。

配色与类别（与博主画面一致）
--------------------------
    绿线 = 管理基金 Managed Money（投机资金）
    蓝线 = 商业 Producer/Merchant（产业套保）
    红线 = 散户 Non-Reportable
    互换商 Swap Dealers / 其他 Other Reportable 他图上没有，本页也不画。
"""
import json, os

# ⚠ 本文件在本机另有一份副本：C:/Users/Leo/WorkBuddy/抖音博主蒸馏/scripts/
# 两份**故意不同**：此处 BASE 按脚本位置推导（GitHub Actions 用），抖音那份写死本机路径。
# 同步时只同步「算法与口径」部分，不要整文件覆盖，否则会把可移植路径冲掉（2026-10-05 踩过）。
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MKT = os.path.join(BASE, "data", "market")
OUT = os.path.join(MKT, "cot_speed_index.json")

N = 26        # 归一化窗口（周）—— 由截图反解
BASIS = "net"  # 口径＝净头寸（多 − 空）。别再改成 long：截图反解已否掉毛多。
CATS = [("mm", "绿线·管理基金（Managed Money｜投机资金）"),
        ("prod", "蓝线·商业（Producer/Merchant｜产业套保）"),
        ("nonrept", "红线·散户（Non-Reportable）")]


def stoch(v, n):
    """经典 COT Index：v 在近 n 期中的相对位置，输出 0~100"""
    o = [None] * len(v)
    for i in range(n - 1, len(v)):
        w = [x for x in v[i - n + 1:i + 1] if x is not None]
        if len(w) < n or v[i] is None:
            continue
        lo, hi = min(w), max(w)
        o[i] = None if hi == lo else (v[i] - lo) / (hi - lo) * 100.0
    return o


def main():
    cot = json.load(open(os.path.join(MKT, "cot_gold.json"), encoding="utf-8"))
    cot.sort(key=lambda c: c["date"])
    dates = [c["date"] for c in cot]

    out = {"params": {"norm_weeks": N, "basis": BASIS, "speed_weeks": None},
           "formula": "idx = (net_t - min_N(net)) / (max_N(net) - min_N(net)) * 100",
           "dates": dates, "lines": {}}
    for key, label in CATS:
        v = [c[key + "_" + BASIS] for c in cot]
        idx = stoch(v, N)
        out["lines"][key] = {"label": label, "idx": idx}
        out[key + "_idx"] = idx

    warm = N - 1
    out["valid_from"] = dates[warm]
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    print("COT Index 已生成:", OUT)
    print("公式 idx = (净头寸 − 近 %d 周最低) / (近 %d 周最高 − 最低) × 100" % (N, N))
    print("有效区间 %s ~ %s（预热 %d 周）" % (dates[warm], dates[-1], warm))

    print("\n最近 8 周读数：")
    keys = [k for k, _ in CATS]
    print("  %-12s" % "date" + "".join("%-10s" % k for k in keys))
    for j in range(len(dates) - 8, len(dates)):
        f = lambda v: ("%.0f" % v) if v is not None else "—"
        print("  %-12s" % dates[j] + "".join("%-10s" % f(out[k + "_idx"][j]) for k in keys))

    print("\n关键锚点（对照博主 2026-09-19 口播）：")
    for d in ("2026-02-03", "2026-02-10", "2026-08-25", "2026-09-29"):
        if d not in dates:
            continue
        i = dates.index(d)
        print("  %s  商业(蓝)=%s  管理基金(绿)=%s  散户(红)=%s"
              % (d,
                 "%.0f" % out["prod_idx"][i] if out["prod_idx"][i] is not None else "—",
                 "%.0f" % out["mm_idx"][i] if out["mm_idx"][i] is not None else "—",
                 "%.0f" % out["nonrept_idx"][i] if out["nonrept_idx"][i] is not None else "—"))


if __name__ == "__main__":
    main()

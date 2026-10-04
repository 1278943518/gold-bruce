# -*- coding: utf-8 -*-
"""COT（中期）与 PCR（短中期）冲突时怎么办？——实证对照【全区间版】

他的规则（蒸馏稿 7687194569271757155 / 7687566412227132136）：
  优先级：COT持仓 > 升贴水 > 期权PCR > 技术分析
  COT  ：绿线（最大资金）打顶＝买点/看多；蓝线（投机资金）打顶＝行情衰减/看空
  PCR  ：破标准差上轨＝顶，开空；击穿下轨＝底，开多（不可重仓）；通道内＝空仓等

他没明说"两者矛盾怎么办"，只给了优先级。本脚本把历史区间切成四类状态，
统计各自的后续收益，用数据回答"共振 vs 矛盾"差多少。

状态定义（每个交易日 t）：
  COT 状态 = +1（绿线打顶，8 周内有效）/ −1（蓝线打顶，20 周内有效）/ 0（无信号）
  PCR 状态 = +1（%B≤0 击穿下轨）/ −1（%B≥100 破上轨）/ 0（通道内），20 个交易日内有效
  共振=两者同号；矛盾=异号；单边=一个有信号另一个 0；无信号=都 0

价格用 COMEX 黄金 GC（与 COT 同源）；PCR 用上期所并对异日历做前向填充。
"""
import datetime, json, os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MKT = os.path.join(BASE, "data", "market")
OUT = os.path.join(MKT, "cot_pcr_crosscheck.json")

TOP = 0.90
COT_GREEN_WEEKS = 8      # 绿线打顶后按实证 8 周最有效
COT_BLUE_WEEKS = 20      # 蓝线打顶后按实证 20 周才兑现
PCR_DAYS = 20
FWD_DAYS = 20
START = "2024-01-01"


def load(n):
    return json.load(open(os.path.join(MKT, n), encoding="utf-8"))


def bb(vals, n=20, k=2.0):
    up, dn = [], []
    for i in range(len(vals)):
        if i < n - 1 or vals[i] is None:
            up.append(None); dn.append(None); continue
        seg = vals[i - n + 1:i + 1]
        if any(x is None for x in seg):
            up.append(None); dn.append(None); continue
        m = sum(seg) / n
        sd = (sum((x - m) ** 2 for x in seg) / n) ** 0.5
        up.append(m + k * sd); dn.append(m - k * sd)
    return up, dn


def main():
    gc = [x for x in load("gc_day.json") if x["d"] >= START]
    pcr_rows = load("pcr_au.json")
    sg = load("cot_speed_index.json")

    # 右端对齐到 PCR 最新日
    pcr_end = max(x["date"] for x in pcr_rows if x.get("pcr_oi") is not None)
    gc = [x for x in gc if x["d"] <= pcr_end]
    dates = [x["d"] for x in gc]
    px = [x["c"] for x in gc]
    N = len(dates)

    # ---- PCR 状态（前向填充解决上期所 / COMEX 日历差异）----
    pmap = {x["date"]: x for x in pcr_rows if x.get("pcr_oi") is not None}
    po = []
    last = None
    for d in dates:
        if d in pmap:
            last = pmap[d]["pcr_oi"]
        po.append(last)
    up, dn = bb(po)
    pcr_sig = {}
    for i in range(N):
        if po[i] is None or up[i] is None:
            continue
        if po[i] >= up[i]:
            s = -1
        elif po[i] <= dn[i]:
            s = 1
        else:
            continue
        for j in range(i, min(i + PCR_DAYS, N)):
            pcr_sig[j] = s

    # ---- COT 状态（周频触发，映射到日频有效期）----
    wd = sg["dates"]
    cot_sig = {}
    for i, w in enumerate(wd):
        g, b = sg["prod_idx"][i], sg["mm_idx"][i]
        if g is not None and g >= TOP:
            s, weeks = 1, COT_GREEN_WEEKS
        elif b is not None and b >= TOP:
            s, weeks = -1, COT_BLUE_WEEKS
        else:
            continue
        end = (datetime.date.fromisoformat(w) + datetime.timedelta(days=weeks * 7)).isoformat()
        for j, d in enumerate(dates):
            if d < w:
                continue
            if d > end:
                break
            cot_sig[j] = s

    buckets, bydir, detail = {}, {}, []
    for i in range(N):
        j = min(i + FWD_DAYS, N - 1)
        if j <= i:
            continue
        r = (px[j] / px[i] - 1) * 100
        c = cot_sig.get(i, 0)
        p = pcr_sig.get(i, 0)
        if c and p:
            k = "共振" if c == p else "矛盾"
        elif c or p:
            k = "单边"
        else:
            k = "无信号"
        buckets.setdefault(k, []).append(r)
        if c and p:
            key = ("共振·看多" if c == 1 and p == 1 else
                   "共振·看空" if c == -1 and p == -1 else
                   "矛盾·COT多/PCR空" if c == 1 and p == -1 else "矛盾·COT空/PCR多")
            bydir.setdefault(key, []).append(r)
            if k == "矛盾":
                detail.append({"date": dates[i], "cot": c, "pcr": p, "fwd": round(r, 2)})

    def stat(v):
        if not v:
            return {"n": 0}
        return {"n": len(v), "avg_ret": round(sum(v) / len(v), 2),
                "median": round(sorted(v)[len(v) // 2], 2),
                "win_rate": round(sum(1 for x in v if x > 0) / len(v) * 100, 1)}

    res = {"fwd_days": FWD_DAYS, "top": TOP,
           "cot_window": {"green_weeks": COT_GREEN_WEEKS, "blue_weeks": COT_BLUE_WEEKS},
           "pcr_days": PCR_DAYS, "range": [dates[0], dates[-1]], "n_days": N,
           "buckets": {k: stat(v) for k, v in buckets.items()},
           "by_direction": {k: stat(v) for k, v in bydir.items()},
           "detail": detail}
    json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    print("样本区间 %s ~ %s（%d 个交易日）" % (dates[0], dates[-1], N))
    print("%-10s %6s %10s %10s %8s" % ("状态", "观测日", "平均收益", "中位", "方向一致率"))
    print("-" * 52)
    for k in ("共振", "矛盾", "单边", "无信号"):
        s = res["buckets"].get(k, {"n": 0})
        if not s.get("n"):
            print("%-10s %6d %10s" % (k, 0, "—")); continue
        print("%-10s %6d %9.2f%% %9.2f%% %7.1f%%"
              % (k, s["n"], s["avg_ret"], s["median"], s["win_rate"]))
    print()
    for k in sorted(res["by_direction"]):
        s = res["by_direction"][k]
        if not s.get("n"):
            continue
        print("  %-18s n=%-4d 平均 %+6.2f%%  中位 %+6.2f%%  方向一致率 %.0f%%"
              % (k, s["n"], s["avg_ret"], s["median"], s["win_rate"]))


if __name__ == "__main__":
    main()

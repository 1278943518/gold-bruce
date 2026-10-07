# -*- coding: utf-8 -*-
"""回测 ④ COT Index（经典口径：净头寸 / 26 周 / 0~100）

触发：读数 ≥ TOP（默认 90，即他说的"干到顶部"）
  蓝线（商业 Producer/Merchant·产业套保）打顶 → 他＝行情衰减 / 看空
  绿线（管理基金 Managed Money·投机资金）打顶 → 他＝阶段底部 / 看多

⚠ 2026-10-08 修正：原先把规则挂反了（旧文写成"绿线＝商业"），
   截图反解已确认 蓝线＝商业、绿线＝管理基金，方向随之对调。

★ 三个必避的坑：
1. 必须有 base rate：2025-2026 黄金是大牛市，无脑看多胜率本来就高
2. 事件要去重：读数连续多周 ≥90 是同一波行情，连算＝重复计分
3. 分母统一：胜率 = 方向一致次数 / 全部事件（含亏损），与基准同口径
"""
import datetime, json, os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MKT = os.path.join(BASE, "data", "market")
OUT = os.path.join(MKT, "cot_speed_backtest.json")

HOLD_WEEKS = 8
TOP = 90        # 0~100 口径下的"打顶"阈值


def load(n):
    return json.load(open(os.path.join(MKT, n), encoding="utf-8"))


def fwd_return(dates, px, d, weeks=HOLD_WEEKS):
    base = max([x for x in dates if x <= d] or [dates[0]])
    target = (datetime.date.fromisoformat(d) + datetime.timedelta(days=weeks * 7)).isoformat()
    cand = [x for x in dates if x >= target]
    if not cand:
        return None
    return (px[cand[0]] / px[base] - 1) * 100


def cluster(idx, gap=4):
    out = []
    for i in idx:
        if out and i - out[-1] <= gap:
            continue
        out.append(i)
    return out


def main():
    sg = load("cot_speed_index.json")
    gc = load("gc_day.json")
    gdates = [x["d"] for x in gc]
    gpx = {x["d"]: x["c"] for x in gc}

    sdates = sg["dates"]
    valid_from = sg["valid_from"]
    valid = [i for i, d in enumerate(sdates) if d >= valid_from and sg["prod_idx"][i] is not None]

    base_idx = cluster(valid, gap=4)
    base_ret = [fwd_return(gdates, gpx, sdates[i]) for i in base_idx]
    base_ret = [r for r in base_ret if r is not None]
    base_up = sum(1 for r in base_ret if r > 0) / len(base_ret) * 100
    base_avg = sum(base_ret) / len(base_ret)

    res = {"hold_weeks": HOLD_WEEKS, "top": TOP,
           "params": sg["params"],
           "valid_from": valid_from,
           "base": {"n": len(base_ret), "up_rate": round(base_up, 1), "avg_ret": round(base_avg, 2)}}

    # 规则方向来自博主口播：蓝线(商业)打顶＝行情衰减→看空；绿线(管理基金)打顶＝底部→看多
    SPEC = (("prod", "蓝线·商业（Producer/Merchant）打顶", "他＝行情衰减/看空", False),
            ("mm", "绿线·管理基金（Managed Money）打顶", "他＝阶段底部/看多", True))

    for key, label, rule, want_up in SPEC:
        arr = sg[key + "_idx"]
        hit = [i for i in valid if (arr[i] or 0) >= TOP]
        hit = cluster(hit)
        rets = [(sdates[i], arr[i], fwd_return(gdates, gpx, sdates[i])) for i in hit]
        rets = [r for r in rets if r[2] is not None]
        if not rets:
            res[key] = {"label": label, "rule": rule, "n": 0}
            continue
        win = sum(1 for r in rets if (r[2] > 0) == want_up)
        avg = sum(r[2] for r in rets) / len(rets)
        base_dir = base_up if want_up else (100 - base_up)
        res[key] = {"label": label, "rule": rule, "n": len(rets),
                    "hit_rate": round(win / len(rets) * 100, 1),
                    "avg_ret": round(avg, 2),
                    "base_dir_rate": round(base_dir, 1),
                    "excess_pp": round(win / len(rets) * 100 - base_dir, 1),
                    "excess_ret": round(avg - base_avg, 2),
                    "events": [(r[0], round(r[1], 3), round(r[2], 2)) for r in rets]}

    # ---- 持有期敏感性：样本极少，单看 8 周易误判，必须横向对比 ----
    HOLDS = [4, 8, 13, 20, 26]
    sens = {"holds": [], "base_up": {}}
    for w in HOLDS:
        b = [fwd_return(gdates, gpx, sdates[i], w) for i in base_idx]
        b = [r for r in b if r is not None]
        sens["base_up"][str(w)] = round(sum(1 for r in b if r > 0) / len(b) * 100, 1)
        row = {"w": w}
        for key, _, _, _ in SPEC:
            arr = sg[key + "_idx"]
            hits = cluster([i for i in valid if (arr[i] or 0) >= TOP])
            ev = [(sdates[i], round(arr[i], 2), fwd_return(gdates, gpx, sdates[i], w)) for i in hits]
            row[key] = [list(e) for e in ev if e[2] is not None]
        sens["holds"].append(row)
    json.dump(sens, open(os.path.join(MKT, "cot_speed_sens.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("口径：%s | 打顶阈值 %.2f | 持有 %d 周" % (sg["params"], TOP, HOLD_WEEKS))
    print("有效区间 %s 起，基准 %d 次 | 上涨率 %.1f%% | 平均 %+.2f%%"
          % (valid_from, len(base_ret), base_up, base_avg))
    for key, _, _, _ in SPEC:
        r = res[key]
        if not r.get("n"):
            print("%s：无样本" % key); continue
        print("\n%s（%s）：事件 %d 次" % (r["label"], r["rule"], r["n"]))
        print("  命中率 %.1f%% vs 基准同向 %.1f%% → 超额 %+.1f pp"
              % (r["hit_rate"], r["base_dir_rate"], r["excess_pp"]))
        print("  平均收益 %+.2f%% vs 基准 %+.2f%% → 超额 %+.2f pp"
              % (r["avg_ret"], base_avg, r["excess_ret"]))
        print("  事件明细：", ", ".join("%s(%.2f)→%+.1f%%" % (a, b, c) for a, b, c in r["events"]))


if __name__ == "__main__":
    main()

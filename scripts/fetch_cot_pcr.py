# -*- coding: utf-8 -*-
"""接入布鲁斯体系里此前「未接入」的两层真实数据：
① CFTC COT 分类持仓（黄金）  ② 上期所黄金期权 PCR

数据源（均为官方免费、国内直连可用）：
- COT : https://www.cftc.gov/files/dea/history/fut_disagg_txt_{year}.zip
        （Disaggregated 分类报告：商业头寸 / 互换商 / 管理基金 / 其他可报告）
        也可用 GitHub 库 cot_reports / pycot-reports 简化，但直接拉 zip 更可控
- PCR : https://www.shfe.com.cn/data/tradedata/option/dailydata/kx{YYYYMMDD}.dat
        （上期所期权日行情，含 au 黄金期权逐合约成交量/持仓量，PCR 自己算）
        注意：非交易日返回 HTML 而非 JSON，需容错跳过

用法:
  python fetch_cot_pcr.py --cot           # 拉 COT（多年 zip）
  python fetch_cot_pcr.py --pcr           # 逐日拉期权算 PCR（按交易日并发）
  python fetch_cot_pcr.py --cot --pcr     # 都拉
"""
import argparse, concurrent.futures as cf, json, os, re, urllib.request, zipfile

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MKT = os.path.join(BASE, "data", "market")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36",
      "Referer": "https://www.shfe.com.cn/"}

GOLD_NAME = "GOLD - COMMODITY EXCHANGE INC."


def http(url, timeout=60, headers=None):
    req = urllib.request.Request(url, headers=headers or UA)
    return urllib.request.urlopen(req, timeout=timeout).read()


# ---------------- COT ----------------
def cot_year(year, report="fut_disagg_txt"):
    url = "https://www.cftc.gov/files/dea/history/%s_%d.zip" % (report, year)
    raw = http(url, timeout=180)
    p = os.path.join(MKT, "_cot_%s_%d.zip" % (report, year))
    open(p, "wb").write(raw)
    z = zipfile.ZipFile(p)
    name = z.namelist()[0]
    return z.read(name).decode("latin-1")


def parse_cot(text):
    lines = [l for l in text.split("\n") if l.strip()]
    header = [h.strip().strip('"') for h in lines[0].split(",")]
    idx = {h: i for i, h in enumerate(header)}
    out = []
    for l in lines[1:]:
        f = [x.strip().strip('"') for x in l.split(",")]
        if len(f) < 5:
            continue
        nm = f[idx.get("Market_and_Exchange_Names", 0)]
        if nm.upper() != GOLD_NAME.upper():
            continue
        def n(col):
            i = idx.get(col)
            if i is None or i >= len(f):
                return None
            try:
                return float(f[i])
            except ValueError:
                return None
        rec = {
            "date": f[idx.get("Report_Date_as_YYYY-MM-DD", 2)],
            "oi": n("Open_Interest_All"),
            "prod_long": n("Prod_Merc_Positions_Long_All"), "prod_short": n("Prod_Merc_Positions_Short_All"),
            "swap_long": n("Swap_Positions_Long_All"), "swap_short": n("Swap__Positions_Short_All"),
            "mm_long": n("M_Money_Positions_Long_All"), "mm_short": n("M_Money_Positions_Short_All"),
            "other_long": n("Other_Rept_Positions_Long_All"), "other_short": n("Other_Rept_Positions_Short_All"),
            # NonRept＝非报告头寸，官方口径里的「散户」。
            # ⚠ 列名是**大写 R** 的 NonRept_Positions_*，写成 Nonrept_* 会取不到（返回 None）。
            "nonrept_long": n("NonRept_Positions_Long_All"), "nonrept_short": n("NonRept_Positions_Short_All"),
        }
        for a, b in (("prod", ("prod_long", "prod_short")), ("swap", ("swap_long", "swap_short")),
                     ("mm", ("mm_long", "mm_short")), ("other", ("other_long", "other_short")),
                     ("nonrept", ("nonrept_long", "nonrept_short"))):
            v1, v2 = rec[b[0]], rec[b[1]]
            rec[a + "_net"] = None if (v1 is None or v2 is None) else v1 - v2
        out.append(rec)
    out.sort(key=lambda x: x["date"])
    return out


def do_cot(years=(2024, 2025, 2026)):
    all_rows = []
    for y in years:
        try:
            rows = parse_cot(cot_year(y))
        except Exception as e:
            print("  COT %d 失败: %s" % (y, e))
            continue
        print("  COT %d: %d 周 | %s ~ %s" % (y, len(rows), rows[0]["date"], rows[-1]["date"]))
        all_rows += rows
    # 去重
    seen, uniq = set(), []
    for r in sorted(all_rows, key=lambda x: x["date"]):
        if r["date"] in seen:
            continue
        seen.add(r["date"])
        uniq.append(r)
    json.dump(uniq, open(os.path.join(MKT, "cot_gold.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("COT 落盘: %d 周 -> data/market/cot_gold.json" % len(uniq))
    if uniq:
        r = uniq[-1]
        print("  最新 %s | 总持仓 %s | 管理基金净 %s | 商业净 %s"
              % (r["date"], r["oi"], r.get("mm_net"), r.get("prod_net")))


# ---------------- PCR ----------------
def pcr_one(d):
    """拉取单个交易日的上期所黄金期权，返回 (date, 成交量PCR, 持仓PCR, 明细)"""
    url = "https://www.shfe.com.cn/data/tradedata/option/dailydata/kx%s.dat" % d.replace("-", "")
    try:
        raw = http(url, timeout=40).decode("utf-8", "ignore")
        obj = json.loads(raw)
    except Exception:
        return None
    cur = obj.get("o_curinstrument") or []
    au = [x for x in cur if (x.get("PRODUCTGROUPID") or "").lower() == "au"]
    if not au:
        return None
    cv = pv = co = po = 0
    for x in au:
        iid = (x.get("INSTRUMENTID") or "").upper()
        m = re.match(r"^AU\d{4}([CP])\d+", iid)
        if not m:
            continue
        v = x.get("VOLUME") or 0
        oi = x.get("OPENINTEREST") or 0
        if m.group(1) == "C":
            cv += v; co += oi
        else:
            pv += v; po += oi
    return {"date": d,
            "call_vol": cv, "put_vol": pv,
            "call_oi": co, "put_oi": po,
            "pcr_vol": round(pv / cv, 4) if cv else None,
            "pcr_oi": round(po / co, 4) if co else None}


def do_pcr(start="2026-01-01", workers=8):
    au = json.load(open(os.path.join(MKT, "au2612_day.json"), encoding="utf-8"))
    dates = [x["d"] for x in au if x["d"] >= start]
    print("待拉 %d 个交易日，并发 %d ..." % (len(dates), workers))
    res = []
    with cf.ThreadPoolExecutor(max_workers=workers) as ex:
        for r in ex.map(pcr_one, dates):
            if r:
                res.append(r)
    res.sort(key=lambda x: x["date"])
    json.dump(res, open(os.path.join(MKT, "pcr_au.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    ok = [r for r in res if r["pcr_vol"] is not None]
    print("PCR 落盘: %d/%d 天有数据 -> data/market/pcr_au.json" % (len(ok), len(dates)))
    if ok:
        print("  区间 %s ~ %s" % (ok[0]["date"], ok[-1]["date"]))
        for r in ok[-5:]:
            print("   %s 成交量PCR=%.3f 持仓PCR=%.3f (call_vol=%d put_vol=%d)"
                  % (r["date"], r["pcr_vol"], r["pcr_oi"] or 0, r["call_vol"], r["put_vol"]))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cot", action="store_true")
    ap.add_argument("--pcr", action="store_true")
    ap.add_argument("--years", default="2024,2025,2026")
    args = ap.parse_args()
    os.makedirs(MKT, exist_ok=True)
    if args.cot:
        do_cot([int(y) for y in args.years.split(",")])
    if args.pcr:
        do_pcr()
    if not (args.cot or args.pcr):
        print("请指定 --cot 和/或 --pcr")

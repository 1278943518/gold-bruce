# -*- coding: utf-8 -*-
"""把上期所黄金期权 PCR 的历史拉长到 2024-01 起（原来只有 2026 年）

数据源：https://www.shfe.com.cn/data/tradedata/option/dailydata/kx{YYYYMMDD}.dat
交易日列表取自 AU0 连续合约的日 K（2008 起），筛 2024-01-01 之后。
已抓过的日期会与现有 pcr_au.json 合并，不重复请求。
"""
import json, os, re, urllib.request
import concurrent.futures as cf

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MKT = os.path.join(BASE, "data", "market")
START = "2024-01-01"
WORKERS = 8


def http(u, t=40):
    r = urllib.request.Request(u, headers={
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://www.shfe.com.cn/"})
    return urllib.request.urlopen(r, timeout=t).read()


def pcr_one(d):
    url = "https://www.shfe.com.cn/data/tradedata/option/dailydata/kx%s.dat" % d.replace("-", "")
    try:
        obj = json.loads(http(url).decode("utf-8", "ignore"))
    except Exception:
        return None
    cur = obj.get("o_curinstrument") or []
    au = [x for x in cur if (x.get("PRODUCTGROUPID") or "").lower() == "au"]
    if not au:
        return None
    cv = pv = co = po = 0
    for x in au:
        m = re.match(r"^AU\d{4}([CP])\d+", (x.get("INSTRUMENTID") or "").upper())
        if not m:
            continue
        v = x.get("VOLUME") or 0
        oi = x.get("OPENINTEREST") or 0
        if m.group(1) == "C":
            cv += v; co += oi
        else:
            pv += v; po += oi
    if not (cv or co):
        return None
    return {"date": d, "call_vol": cv, "put_vol": pv,
            "call_oi": co, "put_oi": po,
            "pcr_vol": round(pv / cv, 4) if cv else None,
            "pcr_oi": round(po / co, 4) if co else None}


def main():
    au0 = json.load(open(os.path.join(MKT, "au0_day.json"), encoding="utf-8"))
    dates = [x["d"] for x in au0 if x["d"] >= START]

    old_path = os.path.join(MKT, "pcr_au.json")
    have = {}
    if os.path.exists(old_path):
        for r in json.load(open(old_path, encoding="utf-8")):
            have[r["date"]] = r
    todo = [d for d in dates if d not in have]
    print("区间 %s ~ %s，共 %d 个交易日；已有 %d 天，待拉 %d 天"
          % (dates[0], dates[-1], len(dates), len(have), len(todo)))

    got = []
    with cf.ThreadPoolExecutor(max_workers=WORKERS) as ex:
        for i, r in enumerate(ex.map(pcr_one, todo)):
            if r:
                got.append(r)
            if (i + 1) % 100 == 0:
                print("  ... %d/%d" % (i + 1, len(todo)), flush=True)

    merged = dict(have)
    for r in got:
        merged[r["date"]] = r
    res = sorted(merged.values(), key=lambda x: x["date"])
    json.dump(res, open(old_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    ok = [r for r in res if r["pcr_oi"] is not None]
    print("落盘 %d 天（其中 %d 天有持仓 PCR）-> %s" % (len(res), len(ok), old_path))
    if ok:
        print("  区间 %s ~ %s" % (ok[0]["date"], ok[-1]["date"]))
        miss = [d for d in dates if d not in merged]
        print("  无数据交易日 %d 个（多为黄金期权未上市/停市）" % len(miss))


if __name__ == "__main__":
    main()

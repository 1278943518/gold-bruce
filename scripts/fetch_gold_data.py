# -*- coding: utf-8 -*-
"""抓取黄金可视化所需真实行情（新浪接口）
- 沪金连续 AU0 日线（元/克）
- 沪金单合约 AU2610 / AU2612 / AU2702 日线（算升贴水）
- COMEX 黄金 GC 日线（美元/盎司）
- 纽约金 / 伦敦金实时报价
"""
import json, os, re, urllib.request

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "data", "market")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36",
      "Referer": "https://finance.sina.com.cn/"}


def get(url, timeout=40):
    req = urllib.request.Request(url, headers=UA)
    return urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "ignore")


def jsonp(raw):
    """新浪返回 /*...*/ var _x=([...]);  —— 取出最外层数组"""
    m = re.search(r"=\s*\(?(\[.*\])\)?\s*;?\s*$", raw.strip(), re.S)
    if not m:
        raise ValueError("JSONP 解析失败: %s" % raw[:120])
    return json.loads(m.group(1))


def sina_futures(symbol):
    url = ("https://stock2.finance.sina.com.cn/futures/api/jsonp.php/var%%20_s=/"
           "InnerFuturesNewService.getDailyKLine?symbol=%s" % symbol)
    return jsonp(get(url))


def sina_global(symbol):
    url = ("https://stock2.finance.sina.com.cn/futures/api/jsonp.php/var%%20_g=/"
           "GlobalFuturesService.getGlobalFuturesDailyKLine?symbol=%s" % symbol)
    return jsonp(get(url))


def norm_fut(arr):
    return [{"d": x["d"], "o": float(x["o"]), "h": float(x["h"]),
             "l": float(x["l"]), "c": float(x["c"]), "v": float(x["v"] or 0)}
            for x in arr if x.get("c")]


def norm_gc(arr):
    return [{"d": x["date"], "o": float(x["open"]), "h": float(x["high"]),
             "l": float(x["low"]), "c": float(x["close"])}
            for x in arr if x.get("close")]


def main():
    os.makedirs(OUT, exist_ok=True)
    res = {}

    au0 = norm_fut(sina_futures("AU0"))
    json.dump(au0, open(os.path.join(OUT, "au0_day.json"), "w", encoding="utf-8"), ensure_ascii=False)
    res["au0"] = {"n": len(au0), "range": [au0[0]["d"], au0[-1]["d"]]}
    print("沪金连续 AU0 : %d 条 | %s ~ %s" % (len(au0), au0[0]["d"], au0[-1]["d"]))

    for sym in ("AU2610", "AU2612", "AU2702"):
        try:
            a = norm_fut(sina_futures(sym))
        except Exception as e:
            print("  %s 失败: %s" % (sym, e))
            continue
        json.dump(a, open(os.path.join(OUT, "%s_day.json" % sym.lower()), "w", encoding="utf-8"),
                  ensure_ascii=False)
        res[sym] = {"n": len(a), "range": [a[0]["d"], a[-1]["d"]]}
        print("合约 %s : %d 条 | %s ~ %s | 最新收盘 %.2f" % (sym, len(a), a[0]["d"], a[-1]["d"], a[-1]["c"]))

    try:
        gc = norm_gc(sina_global("GC"))
        json.dump(gc, open(os.path.join(OUT, "gc_day.json"), "w", encoding="utf-8"), ensure_ascii=False)
        res["GC"] = {"n": len(gc), "range": [gc[0]["d"], gc[-1]["d"]]}
        print("COMEX GC  : %d 条 | %s ~ %s" % (len(gc), gc[0]["d"], gc[-1]["d"]))
    except Exception as e:
        print("GC 失败:", e)

    try:
        live = get("https://hq.sinajs.cn/list=hf_GC,hf_XAU")
        live = live.encode("latin-1", "ignore").decode("gbk", "ignore")
        rows = {}
        for line in live.strip().split("\n"):
            m = re.search(r'hq_str_hf_(\w+)="([^"]*)"', line)
            if not m:
                continue
            f = m.group(2).split(",")
            rows[m.group(1)] = {"price": f[0], "prev_settle": f[7] if len(f) > 7 else "",
                                "time": f[6] if len(f) > 6 else "", "date": f[12] if len(f) > 12 else ""}
        json.dump(rows, open(os.path.join(OUT, "gold_live.json"), "w", encoding="utf-8"), ensure_ascii=False)
        print("实时:", {k: v["price"] for k, v in rows.items()})
    except Exception as e:
        print("实时报价失败:", e)

    json.dump(res, open(os.path.join(OUT, "gold_data_index.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("落盘完成 ->", OUT)


if __name__ == "__main__":
    main()

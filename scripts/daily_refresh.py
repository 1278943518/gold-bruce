# -*- coding: utf-8 -*-
"""每日刷新黄金看盘（手机版 + 桌面版）

链路：
1. fetch_gold_data.py     —— 沪金/AU2612/GC 日线 + 隔夜实时报价快照
2. fetch_pcr_long.py      —— 上期所 PCR 增量补抓（只拉缺失交易日，秒级）
3. COT 最新年抓取 + 合并  —— 只下载当年 zip，与 cot_gold.json 历史合并
                             （不能直接跑 fetch_cot_pcr.py --cot，它会覆盖整个文件！）
4. compute_cot_speed_index.py —— ④ 购买速度指数
5. backtest_cot_speed.py      —— 回测 + 持有期敏感性
6. crosscheck_cot_pcr.py      —— COT×PCR 共振/矛盾实证
7. build_gold_app.py          —— 手机版 outputs/gold_app/index.html
8. build_gold_dashboard.py    —— 桌面版（保持同源更新）

返回码 0 = 全部成功；输出最后一行 DATA_CHANGED=yes/no 供发布步骤判断。
"""
import hashlib, os, shutil, subprocess, sys

BASE = r"C:/Users/Leo/WorkBuddy/抖音博主蒸馏"
PY = r"C:/Users/Leo/.workbuddy/binaries/python/versions/3.13.12/python.exe"
APP = os.path.join(BASE, "outputs", "gold_app", "index.html")
# 黄金看盘有自己的工作区（避免与「王处合集」争同一个应用槽位），
# 每次重建后把成品同步过去，发布步骤指向该工作区。
SYNC_DIR = r"C:/Users/Leo/WorkBuddy/黄金看盘/gold_app"


def sync():
    src = os.path.join(BASE, "outputs", "gold_app")
    if not os.path.isdir(src):
        return
    os.makedirs(SYNC_DIR, exist_ok=True)
    shutil.copy2(os.path.join(src, "index.html"), os.path.join(SYNC_DIR, "index.html"))
    sa, da = os.path.join(src, "assets"), os.path.join(SYNC_DIR, "assets")
    os.makedirs(da, exist_ok=True)
    for f in os.listdir(sa):
        shutil.copy2(os.path.join(sa, f), os.path.join(da, f))
    print("已同步到独立工作区:", SYNC_DIR)


def run(script):
    print("\n====>", script, flush=True)
    r = subprocess.run([PY, os.path.join(BASE, "scripts", script)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=BASE)
    print(r.stdout[-2500:] if r.stdout else "", flush=True)
    if r.returncode != 0:
        print(r.stderr[-1500:], file=sys.stderr)
        raise SystemExit("%s 失败（exit %d）" % (script, r.returncode))


def sha(p):
    return hashlib.md5(open(p, "rb").read()).hexdigest() if os.path.exists(p) else None


def merge_cot():
    """只抓当年 COT zip，解析后与历史合并落盘"""
    sys.path.insert(0, os.path.join(BASE, "scripts"))
    import datetime
    from fetch_cot_pcr import cot_year, parse_cot, MKT
    path = os.path.join(MKT, "cot_gold.json")
    old = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else []
    year = datetime.date.today().year
    rows = parse_cot(cot_year(year))
    print("COT %d: %d 周（最新 %s）" % (year, len(rows), rows[-1]["date"] if rows else "-"))
    by_date = {r["date"]: r for r in old}
    n_new = 0
    for r in rows:
        if r["date"] not in by_date:
            n_new += 1
        by_date[r["date"]] = r
    merged = sorted(by_date.values(), key=lambda x: x["date"])
    json.dump(merged, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("COT 合并落盘: %d 周（新增 %d 周，历史保留 %d 周）" % (len(merged), n_new, len(old)))


import json

def main():
    before = sha(APP)
    run("fetch_gold_data.py")
    run("fetch_pcr_long.py")
    merge_cot()
    run("compute_cot_speed_index.py")
    run("backtest_cot_speed.py")
    run("crosscheck_cot_pcr.py")
    run("build_gold_app.py")
    run("build_gold_dashboard.py")
    sync()
    after = sha(APP)
    print("\nDATA_CHANGED=%s" % ("yes" if before != after else "no"))


if __name__ == "__main__":
    main()

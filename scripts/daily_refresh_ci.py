# -*- coding: utf-8 -*-
"""GitHub Actions 用的每日刷新脚本（可移植版）

与 Windows 版 daily_refresh.py 的区别：
- 路径按脚本位置推导，不硬编码 Windows 路径
- 子进程用 sys.executable，不写死 python.exe 路径
- 不做「同步到另一个工作区」的动作
- 只重建手机版，并把成品复制到仓库根目录 index.html（供 GitHub Pages 直接托管）

链路：
1. fetch_gold_data.py  沪金/AU2612/GC 日线 + 实时报价
2. fetch_pcr_long.py   上期所 PCR 增量补抓
3. merge_cot()         只抓当年 COT zip 与历史合并（不能直接跑 --cot，会覆盖！）
4. compute_cot_speed_index.py  ④ 购买速度指数
5. backtest_cot_speed.py       回测 + 持有期敏感性
6. crosscheck_cot_pcr.py       COT×PCR 共振/矛盾实证
7. build_gold_app.py           手机版页面
8. 复制到仓库根 index.html

只依赖 Python 标准库，无需 pip install。
"""
import datetime
import hashlib
import json
import os
import subprocess
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(BASE, "scripts")
MKT = os.path.join(BASE, "data", "market")
APP = os.path.join(BASE, "outputs", "gold_app", "index.html")
ROOT_HTML = os.path.join(BASE, "index.html")

if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)


def run(script):
    print("\n====>", script, flush=True)
    r = subprocess.run([sys.executable, os.path.join(SCRIPTS, script)],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", cwd=BASE)
    print((r.stdout or "")[-2500:], flush=True)
    if r.returncode != 0:
        print((r.stderr or "")[-1500:], file=sys.stderr)
        raise SystemExit("%s 失败（exit %d）" % (script, r.returncode))


def merge_cot():
    """只抓当年 COT zip，解析后与历史合并落盘"""
    from fetch_cot_pcr import cot_year, parse_cot
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
    with open(path, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=1)
    print("COT 合并落盘: %d 周（新增 %d 周，历史保留 %d 周）" % (len(merged), n_new, len(old)))


def sha(p):
    if not os.path.exists(p):
        return None
    with open(p, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()


def main():
    before = sha(APP)
    run("fetch_gold_data.py")
    run("fetch_pcr_long.py")
    merge_cot()
    run("compute_cot_speed_index.py")
    run("backtest_cot_speed.py")
    run("crosscheck_cot_pcr.py")
    run("build_gold_app.py")

    if not os.path.exists(APP):
        raise SystemExit("构建产物不存在: %s" % APP)
    with open(APP, "rb") as src, open(ROOT_HTML, "wb") as dst:
        dst.write(src.read())
    print("已复制到仓库根:", ROOT_HTML)

    after = sha(APP)
    print("\nDATA_CHANGED=%s" % ("yes" if before != after else "no"))


if __name__ == "__main__":
    main()

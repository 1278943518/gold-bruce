# -*- coding: utf-8 -*-
"""把远端 main 上「GitHub Actions 每天刷新」的数据文件同步到本地，再本地构建。

为什么需要它（2026-10-05 踩坑）：
CI 每天会提交新的 data/market/*.json；而本机 repo 里的那份是上次本地抓的、往往更旧。
如果直接本地 build + push，就会用旧数据重建 index.html / data.json 并推上去，
**把 CI 已经刷新的数据推回旧版**（实测：CI 已到 2026-10-05，本地还停在 10-02）。

正确顺序：  python _sync_remote_data.py  →  python scripts/build_gold_app.py  →  push
"""
import base64
import json
import os
import subprocess
import sys

OWNER = "1278943518"
REPO = "gold-bruce"
BASE = os.path.dirname(os.path.abspath(__file__))
MKT = os.path.join(BASE, "data", "market")


def gh(*args):
    r = subprocess.run(["gh"] + list(args), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise SystemExit("gh 失败: %s\n%s" % (" ".join(args), (r.stderr or r.stdout)[:400]))
    return r.stdout


def main():
    ref = sys.argv[1] if len(sys.argv) > 1 else "main"
    tree = json.loads(gh("api", "repos/%s/%s/contents/data/market?ref=%s" % (OWNER, REPO, ref)))
    names = sorted(x["name"] for x in tree if x["name"].endswith(".json"))
    print("远端 data/market 待同步 %d 个 json（ref=%s）" % (len(names), ref))

    changed = 0
    for n in names:
        raw = gh("api", "repos/%s/%s/contents/data/market/%s?ref=%s" % (OWNER, REPO, n, ref),
                 "--jq", ".content")
        data = base64.b64decode("".join(raw.split()))
        p = os.path.join(MKT, n)
        old = open(p, "rb").read() if os.path.exists(p) else None
        if old != data:
            open(p, "wb").write(data)
            changed += 1
            print("  ↑ %-32s %6.1f KB" % (n, len(data) / 1024.0))
    print("同步完成：%d/%d 个文件有更新" % (changed, len(names)))


if __name__ == "__main__":
    main()

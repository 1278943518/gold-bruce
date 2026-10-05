# -*- coding: utf-8 -*-
"""用 GitHub Git Data API 把本地文件打包成**一个干净提交**推到远端 main。

比 _push_via_api.py（Contents API，一文件一提交）更适合成批推送：
一次 commit，父提交接在远端当前头上，不产生分叉、不需要 force push。

用法: python _push_commit_api.py "提交信息" <file1> [file2 ...]
"""
import base64
import json
import os
import subprocess
import sys
import tempfile

OWNER = "1278943518"
REPO = "gold-bruce"


def gh(*args):
    r = subprocess.run(["gh"] + list(args), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise SystemExit("gh 失败: %s\n%s" % (" ".join(args), (r.stderr or r.stdout)[:500]))
    return r.stdout


def gh_json(*args):
    return json.loads(gh(*args))


def post(endpoint, payload):
    fd, tmp = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f)
    try:
        return gh_json("api", "-X", "POST", endpoint, "--input", tmp)
    finally:
        os.unlink(tmp)


def main():
    msg = sys.argv[1]
    files = sys.argv[2:]

    head = gh_json("api", "repos/%s/%s/commits/main" % (OWNER, REPO))
    parent = head["sha"]
    base_tree = head["commit"]["tree"]["sha"]
    print("远端当前头: %s" % parent[:7])

    entries = []
    for p in files:
        with open(p, "rb") as f:
            content = base64.b64encode(f.read()).decode()
        blob = post("repos/%s/%s/git/blobs" % (OWNER, REPO),
                    {"content": content, "encoding": "base64"})
        entries.append({"path": p.replace(os.sep, "/"), "mode": "100644",
                        "type": "blob", "sha": blob["sha"]})
        print("  blob %-42s %s" % (p.replace(os.sep, "/"), blob["sha"][:7]))

    tree = post("repos/%s/%s/git/trees" % (OWNER, REPO),
                {"base_tree": base_tree, "tree": entries})
    commit = post("repos/%s/%s/git/commits" % (OWNER, REPO),
                  {"message": msg, "tree": tree["sha"], "parents": [parent]})

    fd, tmp = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"sha": commit["sha"], "force": False}, f)
    try:
        gh("api", "-X", "PATCH", "repos/%s/%s/git/refs/heads/main" % (OWNER, REPO),
           "--input", tmp)
    finally:
        os.unlink(tmp)

    print("\n✓ 新提交: %s" % commit["sha"][:7])
    print("REFSHA=%s" % commit["sha"])


if __name__ == "__main__":
    main()

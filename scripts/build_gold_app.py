# -*- coding: utf-8 -*-
"""黄金 · 布鲁斯看盘【手机版 App 页面】

与桌面版仪表盘(build_gold_dashboard.py)的区别：
1. mobile-first：390px 宽设计，首页 = 顶部 logo 标题 + 6 个信息块 + 四张紧凑图，
   目标手机一屏（~844px）内看到四幅图
2. 页面底部「详细说明」：设计原因、逐图手册、④ 公式、共振/矛盾三原则、
   回测结论（全样本）、数据来源与更新机制、免责声明
3. 顶部嵌入透明 logo（base64，离线可用）
4. 单文件 index.html + assets/（logo 套装），发布目录 outputs/gold_app/
"""
import base64, json, os, shutil, datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MKT = os.path.join(BASE, "data", "market")
ASSETS = os.path.join(BASE, "outputs", "assets")
OUTDIR = os.path.join(BASE, "outputs", "gold_app")
OUT = os.path.join(OUTDIR, "index.html")

START = "2024-01-01"

SIGNALS = [
    ("2026-04-29", "触下轨", "多"), ("2026-05-22", "破上轨", "空"),
    ("2026-06-12", "触下轨", "多"), ("2026-06-24", "触下轨", "多"),
    ("2026-07-28", "触下轨", "多"), ("2026-08-25", "破上轨", "空"),
    ("2026-09-24", "触下轨", "多"),
]


def load(n):
    return json.load(open(os.path.join(MKT, n), encoding="utf-8"))


def bb(vals, n=20, k=2.0):
    mid, up, dn = [], [], []
    for i in range(len(vals)):
        if i < n - 1 or vals[i] is None:
            mid.append(None); up.append(None); dn.append(None); continue
        seg = vals[i - n + 1:i + 1]
        if any(v is None for v in seg):
            mid.append(None); up.append(None); dn.append(None); continue
        m = sum(seg) / n
        sd = (sum((x - m) ** 2 for x in seg) / n) ** 0.5
        mid.append(m); up.append(m + k * sd); dn.append(m - k * sd)
    return mid, up, dn


def build_view(rows, end):
    rows = [x for x in rows if x["d"] >= START and x["d"] <= end]
    c = [x["c"] for x in rows]
    mid, up, dn = bb(c)
    return {"dates": [x["d"] for x in rows],
            "o": [x["o"] for x in rows], "h": [x["h"] for x in rows],
            "l": [x["l"] for x in rows], "c": c,
            "mid": mid, "up": up, "dn": dn}


def main():
    gc = load("gc_day.json")
    pcr_rows = load("pcr_au.json")
    cot = load("cot_gold.json")
    cot.sort(key=lambda c: c["date"])
    live = load("gold_live.json")
    bt = load("cot_speed_backtest.json")
    sens = load("cot_speed_sens.json")
    cross = load("cot_pcr_crosscheck.json")

    pcr_end = max(x["date"] for x in pcr_rows if x.get("pcr_oi") is not None)
    view = build_view(gc, pcr_end)

    pcr = {x["date"]: {"oi": x.get("pcr_oi"), "vol": x.get("pcr_vol")}
           for x in pcr_rows if x.get("pcr_oi") is not None}

    w_dates = [c["date"] for c in cot]
    data = {"view": view, "pcr": pcr, "w_dates": w_dates,
            "signals": [{"date": d, "kind": k, "dir": dr} for d, k, dr in SIGNALS],
            "live": live, "cot_last": cot[-1]["date"],
            # 右上角两行时间戳：金价与 PCR 各自的数据最新日期（两者常常不同）
            "gold_last": max(x["d"] for x in gc), "pcr_last": pcr_end,
            "cot_n": len(w_dates), "cot_first": cot[0]["date"],
            "bt": bt, "sens": sens, "cross": cross,
            "valid_from": load("cot_speed_index.json")["valid_from"],
            "built_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")}
    # 只输出页面画的三条线（＝博主图上那三条，配色也照他）：
    # 绿＝M_Money 管理基金 / 蓝＝Prod_Merc 商业 / 红＝NonRept 散户
    # 互换商 Swap、其他可报告 Other_Rept 他图上没有，不画也不传。
    for cat in ("mm", "prod", "nonrept"):
        data["w_%s_net" % cat] = [c[cat + "_net"] for c in cot]

    # 净头寸的统计特征：用来在页面上回答「深灰线（商业）为什么长期为负」
    # —— 净头寸＝多−空，商业是产业套保盘，天然净空，是数据真相而非取数错误。
    def netstat(cat):
        v = [c[cat + "_net"] for c in cot]
        longs = [x[cat + "_long"] for x in cot]
        shorts = [x[cat + "_short"] for x in cot]
        return {"n": len(v),
                "neg_pct": round(100.0 * sum(1 for x in v if x < 0) / len(v), 1),
                "mean": round(sum(v) / len(v)), "min": round(min(v)), "max": round(max(v)),
                "long": round(longs[-1]), "short": round(shorts[-1]), "net": round(v[-1])}
    data["net_stats"] = {c: netstat(c) for c in ("mm", "prod", "nonrept")}

    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))

    def asset_b64(name):
        """优先读 PNG；仓库里只存了 base64 文本时（GitHub 纯文本推送）自动解码"""
        p = os.path.join(ASSETS, name)
        if os.path.exists(p):
            return base64.b64encode(open(p, "rb").read()).decode()
        pb = p + ".b64"
        if os.path.exists(pb):
            return open(pb, encoding="utf-8").read().strip()
        raise SystemExit("缺少资源文件: %s（或 %s.b64）" % (name, name))

    logo64 = asset_b64("logo-64.png")
    fav32 = asset_b64("favicon-32.png")

    HTML = r"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>布鲁斯黄金看盘 · COT × PCR × 价格</title>
<link rel="icon" href="data:image/png;base64,__FAV__">
<!-- iOS「添加到主屏幕」：必须用**不透明的 180×180 PNG 文件**（不能是 data URI、不能带 alpha）。
     图标由 scripts/make_ios_icons.py 用 logo 自身底色 #141418 填平透明区后生成。
     用相对路径 assets/… 是因为页面在 GitHub Pages 下位于子路径 /gold-bruce/，
     写 /apple-touch-icon.png 会 404。 -->
<link rel="apple-touch-icon" sizes="180x180" href="assets/apple-touch-icon.png">
<link rel="manifest" href="manifest.webmanifest">
<meta name="apple-mobile-web-app-title" content="布鲁斯黄金看盘">
<meta name="theme-color" content="#141418">
<style>
:root{--bg:#f5f6f8;--card:#fff;--ink:#1b1f24;--sub:#67717d;--line:#e6e9ee;--grid:#eef1f4;
--red:#c62828;--green:#1b7a4b;--amber:#a06a00;--blue:#1f5fbf;
--c-mm:#26a65b;--c-prod:#19b5fe;--c-nonrept:#cf000f}
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent;
-webkit-touch-callout:none;-webkit-user-select:none;-moz-user-select:none;-ms-user-select:none;user-select:none}
body{margin:0;background:var(--bg);color:var(--ink);
font:14px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif}
.wrap{max-width:560px;margin:0 auto;padding:10px 10px 40px}
.hd{display:flex;align-items:center;gap:9px;padding:4px 2px 8px}
.hd img{width:38px;height:38px;border-radius:9px}
.hd h1{font-size:16.5px;margin:0;line-height:1.25}
.hd .sub{font-size:11px;color:var(--sub)}
.upd{font-size:10.5px;color:var(--sub);text-align:right;margin-left:auto;line-height:1.45}
.upd span{display:block;white-space:nowrap}
.upd b{color:var(--blue);font-size:11px}
.upd i.dot{display:inline-block;width:6px;height:6px;border-radius:50%;margin-left:4px;vertical-align:1px;background:#c62828}
.upd i.dot.on{background:#0f7a52}
.grid6{display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin:2px 0 8px}
.kv{background:var(--card);border:1px solid var(--line);border-radius:9px;padding:6px 8px;min-width:0}
.kv .k{font-size:10px;color:var(--sub);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.kv .v{font-size:16px;font-weight:650;margin-top:1px;letter-spacing:-.2px}
.kv .v.small{font-size:13.5px;line-height:1.35}
.kv .x{font-size:9.5px;color:var(--sub);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.up{color:var(--red)}.down{color:var(--green)}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:7px 8px 4px;margin:7px 0}
.ct{display:flex;justify-content:space-between;align-items:baseline;font-size:11px;color:var(--sub);padding:0 2px 3px}
.ct b{color:var(--ink);font-size:11.5px}
svg{width:100%;height:auto;display:block}
.lg{font-size:10.5px;color:var(--sub);padding:2px 2px 4px}
.sw{display:inline-block;width:9px;height:3px;border-radius:2px;vertical-align:middle;margin:0 2px}
.verdict{border:1.5px solid var(--amber);background:var(--card);border-radius:10px;padding:8px 10px;font-size:12.5px;margin:8px 0}
.more{display:block;text-align:center;margin:12px 0 4px;font-size:12.5px;color:var(--blue);text-decoration:none;font-weight:600}
.detail{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 13px;margin:14px 0 0;font-size:13px}
.detail h2{font-size:15px;margin:14px 0 6px;padding-top:10px;border-top:1px dashed var(--line)}
.detail h2:first-child{margin-top:0;border-top:0;padding-top:0}
.detail p{margin:6px 0}
.warnnote{background:rgba(198,40,40,.06);border-left:3px solid #c62828;border-radius:0 8px 8px 0;padding:8px 10px;line-height:1.6}
.detail li{margin:4px 0}
.detail table{width:100%;border-collapse:collapse;font-size:11.5px;margin:7px 0}
.detail th,.detail td{border:1px solid var(--line);padding:4px 6px;text-align:left}
.detail th{background:var(--grid)}
.warn{background:var(--grid);border:1px solid var(--line);border-radius:9px;padding:8px 10px;font-size:12px;margin:8px 0}
.tag{display:inline-block;font-size:10.5px;padding:1px 6px;border-radius:5px;background:var(--grid)}
#tip{position:fixed;pointer-events:none;background:#fff;border:1px solid var(--line);
border-radius:8px;padding:6px 9px;font-size:12px;box-shadow:0 3px 12px rgba(0,0,0,.15);display:none;z-index:99;white-space:normal;max-width:76vw;line-height:1.55}
#tip .hint{color:var(--sub);font-size:10.5px;margin-top:2px}
.foot{text-align:center;color:var(--sub);font-size:10.5px;margin:16px 0 4px}
</style></head><body><div class="wrap">

<div class="hd">
<img src="data:image/png;base64,__LOGO__" alt="logo">
<div><h1>布鲁斯黄金看盘</h1><div class="sub">COT 持仓 × 期权 PCR × 价格通道 · 四维联动</div></div>
<div class="upd"><span>PCR <b id="updPcr">—</b><i class="dot" id="dotPcr"></i></span><span>金价 <b id="updGold">—</b><i class="dot" id="dotGold"></i></span></div>
</div>

<div class="grid6" id="cards"></div>
<div id="verdict"></div>

<div class="card"><div class="ct"><b>① COMEX 黄金 GC</b><span>蜡烛 + BB(20,2)　<span style="color:var(--red)">涨</span>/<span style="color:var(--green)">跌</span></span></div>
<svg id="s1" viewBox="0 0 750 150"></svg></div>

<div class="card"><div class="ct"><b>② 黄金期权 PCR</b><span>持仓量口径 + BB(20,2)（上期所）</span></div>
<svg id="s2" viewBox="0 0 750 140"></svg></div>

<div class="card"><div class="ct"><b>③ CFTC 分类净持仓</b><span>净头寸＝多−空·<b>可为负</b>　<span class="sw" style="background:var(--c-mm)"></span>管理基金 <span class="sw" style="background:var(--c-prod)"></span>商业 <span class="sw" style="background:var(--c-nonrept)"></span>散户</span></div>
<svg id="s3" viewBox="0 0 750 130"></svg></div>

<div class="card"><div class="ct"><b>④ COT Index（博主原版口径）</b><span>净头寸 26 周随机指标　0~100，≥90＝打顶</span></div>
<svg id="s4" viewBox="0 0 750 140"></svg></div>

<a class="more" href="#manual">▼ 详细说明 · 使用手册（怎么用 / 怎么看 / 口径溯源 / 已知缺口）</a>

<div class="detail" id="manual">
<p style="font-size:11.5px;color:var(--sub);line-height:2"><b>目录</b>：<a href="#m1" style="color:var(--sub)">这是什么</a> · <a href="#m2" style="color:var(--sub)">怎么用</a> · <a href="#m3" style="color:var(--sub)">四张图</a> · <a href="#m4" style="color:var(--sub)">六个信息块</a> · <a href="#m5" style="color:var(--sub)">COT×PCR</a> · <a href="#m6" style="color:var(--sub)">回测</a> · <a href="#m7" style="color:var(--sub)">数据来源</a> · <a href="#m8" style="color:var(--sub)">设计取舍</a> · <a href="#m9" style="color:var(--sub)">口径溯源</a> · <a href="#m10" style="color:var(--sub)">已知缺口</a></p>
<h2 id="m1">一、这是什么</h2>
<p>把抖音博主「布鲁斯」讲的中长线黄金分析框架做成可视化看板。他的优先级：<b>COT 持仓 ＞ 升贴水 ＞ 期权 PCR ＞ 技术分析</b>。其中<b>升贴水那一层还没接</b>（免费数据源不好找），本页先把他图上那三块（COT 净持仓、COT Index、期权 PCR＋价格通道）接入真实数据，四张图共用同一条日频时间轴。</p>

<h2 id="m2">二、怎么用这张页（交互说明）</h2>
<li><b>拖动看数</b>：鼠标移过（手机用手指按住滑动）任意一张图，会出现竖线与数据弹窗。<b>四张图共用同一条时间轴</b>，在任一图上移动，四图的竖线会同时联动，方便对齐同一时点。</li>
<li><b>弹窗不会自动消失</b>：松手 / 移开鼠标后弹窗<b>留着</b>，方便慢慢读数；点图表以外的空白处才收起。</li>
<li><b>弹窗里有什么</b>：当天日期（若落在某一 COT 周内，会加注「周报日」）、GC 收盘价与价格 %B、PCR 与 PCR %B，以及 ③④ 三条线各自的<b>净头寸</b>与 <b>COT Index（0~100）</b>。</li>
<li><b>右上角两个日期</b>：PCR 数据日 / 金价数据日，各自独立、互不影响。日期后的小圆点 <span style="color:#0f7a52">绿</span>＝该数据已更到今天，<span style="color:#c62828">红</span>＝还没更到今天。</li>
<li><b>你不需要管更新</b>：页面每次打开都会自己去拉最新的数据文件（多个源并发，谁先回来先用谁、后到的自动覆盖），失败会静默重试，从后台切回前台也会补一次。所以<b>收藏的链接永远是最新的，不需要重新部署</b>。</li>

<h2 id="m3">三、四张图怎么看（逐图手册）</h2>
<p><b>① 价格 + 布林通道 BB(20,2)</b>——蜡烛红涨绿跌（国内习惯）。他口播里的信号：<b>破上轨＝顶部（开空）、击穿下轨＝底部（做多）、通道内＝空仓等待</b>。图上的圆点是他视频里明确说过的信号位，可核对是否印证。</p>
<p><b>② 黄金期权 PCR（持仓量口径）</b>——看通道位置而不是绝对值：PCR %B 触到下轨（≤0）≈ 看多情绪极端，短中期易反弹；冲到上轨（≥100）≈ 偏空。橙线为成交量口径对照。注意 PCR 是<b>短中期</b>尺度（实证约 20 日兑现）。</p>
<p><b>③ CFTC 分类净持仓</b>——三类均为官方 Disaggregated 报告原始字段，配色直接照博主视频画面：<span style="color:var(--c-mm)"><b>绿线</b></span>＝管理基金 M_Money「投机资金」、<span style="color:var(--c-prod)"><b>蓝线</b></span>＝商业 Producer/Merchant「产业套保盘」、<span style="color:var(--c-nonrept)"><b>红线</b></span>＝散户 Non-Reportable「非报告头寸」。周频数据阶跃对齐到日轴。（互换商 Swap Dealers、其他可报告 Other Reportable 他图上没有，本页也不画。）</p>
<p id="netNote" class="warnnote"></p>
<p><b>④ COT Index（他图上第三栏那条，逐像素反解复原）</b>——
idx＝(净头寸<sub>t</sub> − 近 26 周最低) ÷ (近 26 周最高 − 最低) × 100，即最经典的 COT Index：
<b>净头寸口径、26 周窗口、不做任何速度差分</b>，输出 0~100（纵轴锁死 0~100，画三条参考线：
<b>90 打顶 / 50 中位 / 10 打底</b>，与他截图那张「0~100 + 中间 50 虚线」同款）。</p>
<p>三条线＝<span style="color:var(--c-prod)"><b>蓝线·商业</b></span>、<span style="color:var(--c-mm)"><b>绿线·管理基金</b></span>、<span style="color:var(--c-nonrept)"><b>红线·散户</b></span>，与 ③ 完全同色同名。<b>读数 ≥90 ＝ 已打顶，≤10 ＝ 打底，其余中性</b>。<b>规则方向（他 09-19 口播）</b>：<span style="color:var(--c-prod)"><b>蓝线（商业）干到顶 → 行情衰减、可横盘或直接回调，偏空</b></span>（2026-02-03 读数 100，金价随后从 5217 跌到 4021）；<span style="color:var(--c-mm)"><b>绿线（管理基金）干到顶 → 已到阶段底部，偏多</b></span>（2026-08-25 读数 100，其后 4021 涨到 4716）。</p>
<p><b>口径是怎么定下来的</b>：把 2026-09-19 视频截图里那条<span style="color:var(--c-prod)"><b>蓝线</b></span>逐列取出（1379 个有效列）与本地 CFTC 真实数据做滑动相关，153 种口径组合里 r=<b>0.886</b> 排第一的就是「商业 Producer/Merchant 净头寸 + 26 周 + 无差分」（前五名全是它，第二名 0.828；管理基金只有 0.402）。所以<b>他说的蓝线＝商业</b>，绿线＝管理基金。详细溯源见下方「九、口径溯源」。</p>

<h2 id="m4">四、顶部六个信息块</h2>
<li><b>现货金价（GC）</b>：COMEX 黄金最新报价快照，右侧为相对前一交易日结算价的涨跌幅。</li>
<li><b>价格 %B</b>：金价在 BB(20,2) 通道中的位置。<b>&gt;100 破上轨 → 偏空；&lt;0 破下轨 → 偏多；0~100 通道内 → 无信号</b>。</li>
<li><b>PCR·持仓量</b>：上期所黄金期权认沽/认购比，右下角是它在自身 BB(20,2) 里的 %B，读法同上。</li>
<li><b>④ 蓝线·商业</b>：商业（产业套保盘）的 COT Index 读数与状态。<b>他：打顶＝行情衰减</b>。</li>
<li><b>④ 绿线·管理基金</b>：管理基金（投机资金）的 COT Index 读数与状态。<b>他：打顶＝阶段底部</b>。</li>
<li><b>当下结论</b>：把 COT（中期）与 PCR（短期）两层信号按他的规则合成后的当前状态（共振 / 矛盾 / 单边 / 无信号）。</li>
<p style="font-size:11px;color:var(--sub)">注：金价与 PCR 是日频，COT 是周频——两个 ④ 卡片显示的是<b>最近一次已公布的 COT 周报</b>读数，一周内不会变。</p>

<h2 id="m5">五、COT × PCR 矛盾时怎么办（三条原则）</h2>
<p>① <b>先认时间尺度</b>：COT 是周频、看中期（实证 20 周才兑现），PCR 是日频、看短中期（约 20 个交易日兑现）。两者矛盾多半不是谁错，是节奏不同。</p>
<p>② <b>短期动作跟 PCR，中期仓位跟 COT</b>：他自己也是这么做的——「PCR 击穿下轨可开多接刀子，但不可重仓」。</p>
<p>③ <b>实在对不上就空仓</b>：「通道内＝空仓等待，不猜方向」。</p>
<p style="font-size:11px;color:var(--sub)">本页判定口径：COT 信号＝④ 读数 <b>≥90</b>（<b>绿线·管理基金打顶按 8 周有效、蓝线·商业打顶按 20 周有效</b>）；PCR 信号＝%B <b>≥100 或 ≤0</b>，按 <b>20 个交易日</b>有效。下表是 2024 年以来逐日切状态后的实证对照。</p>
<div id="crossTable"></div>

<h2 id="m6">六、④ 这套规则回测（全样本，别只看一条）</h2>
<p style="font-size:11px;color:var(--sub)">方法：④ 读数 <b>≥90</b> 记一次打顶信号、连续多周只算一次（按 4 周去重），再看之后各持有期的收益。关键是<b>必须跟基准比</b>——这两年黄金是大牛市，无脑看多胜率本来就高，只看绝对命中率会自欺。</p>
<div id="btBlock"></div>

<h2 id="m7">七、数据来源与每日更新</h2>
<li><b>COT</b>：美国 CFTC 官网 Disaggregated 报告（周频，每周六凌晨更新；__COTN__ 周，__COTFIRST__ 起）。官方五类（Prod_Merc / Swap / M_Money / Other_Rept / NonRept）<b>本地全部抓齐</b>，页面只画他图上有的三类（商业 / 管理基金 / 散户），其中「散户」用官方口径的 <b>NonRept（非报告头寸）</b>，不是拿其他可报告凑数。</li>
<li><b>PCR</b>：上期所黄金期权日行情（持仓量口径，2024-03-21 起；成交量口径作对照线）。</li>
<li><b>价格</b>：新浪财经 COMEX GC 日线 + 隔夜实时报价快照。</li>
<li><b>预热</b>：④ 需要 26 周历史窗口，所以 __VALIDFROM__ 起才有读数；主图用 COMEX（与 COT 同市场，口径自洽）。</li>
<li><b>自动更新</b>：后台每天自动重抓数据并重建页面（COT 每周一变，PCR 与价格每日变）。你手上的页面自己会去拉最新数据，因此<b>不需要重新部署</b>。</li>

<h2 id="m8">八、为什么这么设计</h2>
<li><b>四图同轴联动</b>：他的体系是「多层信号互相验证」，分开看容易漏掉共振/矛盾。</li>
<li><b>PCR 用持仓量而非成交量</b>：与他截图同款口径（经 2026-08-24 读数 0.7512 四位小数精确匹配确认）。</li>
<li><b>主图用 COMEX 而非沪金</b>：COT 是 COMEX 头寸，价格与持仓必须同市场；国内合约作副口径。</li>
<li><b>③④ 只画他图上有的三类</b>：互换商 Swap、其他可报告 Other_Rept 布鲁斯从来不看，画上去只会稀释注意力。</li>
<li><b>配色锚定他的视频画面，不是 tradingster</b>：常见财经站把商业画成深灰、互换商画成蓝；他的图里<b>蓝＝商业、绿＝管理基金、红＝散户</b>。本页跟他走——对读数时请<b>认类别名，不要只认颜色</b>。</li>
<li><b>④ 用「净头寸的 26 周相对位置」而非绝对值</b>：他口播讲的是"大资金抢着买"，但落到图上指标就是经典 COT Index；逐像素反解证明这条口径与他画面误差最小（r=0.886）。</li>
<li><b>④ 纵轴锁死 0~100</b>：这是固定量纲的指标，纵轴随数据自动缩放会让人误判"到底到没到顶"。</li>
<li><b>③ 与 ④ 同色同名，量纲却完全不同</b>：③ 是持仓<b>水平</b>（张数，可为负），④ 是<b>相对位置</b>（0~100）。③ 上「蓝线在下面、绿线在上面」是持仓结构本身，不代表 ④ 也会那样。</li>

<h2 id="m9">九、口径溯源：④ 是怎么一步一步定下来的</h2>
<p>这张图全网没有现成指标，只能<b>反解他的画面</b>。过程留在这里，方便你以后怀疑读数时回查：</p>
<li><b>① 先按口播试错</b>：早先照字面理解成「毛多头寸 13 周速度 → 52 周归一化」（0~1 口径），唯一的依据是 2026-08-25 画面读数 0.908 ≈ 商业毛多 0.9109。</li>
<li><b>② 卡住</b>：这样算不出「2026 年 2 月蓝线打顶」，而他图上的蓝线也找不到对应类别。</li>
<li><b>③ 关键证据</b>：2026-09-19 视频截图——第三栏指标名写着 <b>COT-index comm/large/specs</b>，Y 轴 0~100、中间 50 虚线。把那条蓝线逐列取像素（Y 轴 0@795px、100@657px → idx=(795−y)/1.38），得到 1379 个有效列。</li>
<li><b>④ 匹配</b>：用它与本地 CFTC 真实数据做滑动相关，在「5.4~6.6 px/周 × 13 种序列 × 4 种窗口 × 3 种算法」里逐一比：
  <table><tr><th>曲线</th><th>最佳匹配</th><th>相关系数 r</th></tr>
  <tr><td>蓝线</td><td><b>商业 prod_net + 26 周 + 无差分</b></td><td><b>0.886</b>（前五名全是它，第 2 名 0.828）</td></tr>
  <tr><td>红线</td><td>其他可报告 other_net + 52 周</td><td>0.445</td></tr>
  <tr><td>绿线</td><td>管理基金 mm_net + 26 周</td><td>0.402</td></tr></table></li>
<li><b>⑤ 验证</b>：2026-02-03 商业指数 = 100，其后金价 5217 → 4021（他说"跌了一大波"）；2026-08-25 管理基金 = 100，其后 4021 → 4716（他说"这位置是底部"）。两条因果链与他口播逐句吻合。</li>
<li><b>⑥ 结论</b>：旧口径唯一的证据「0.908 ≈ 0.9109」是<b>巧合</b>——正确口径下同一天商业 = 0、管理基金 = 100。真正的原因是<b>类别认错了</b>，不是窗口长短。旧口径已弃用。</li>

<h2 id="m10">十、已知缺口（还没做到的部分）</h2>
<li><b>升贴水没接</b>：他排第 2 优先级（COT ＞ 升贴水 ＞ 期权 PCR ＞ 技术分析），但免费稳定的数据源不好找，这一层暂时空缺。</li>
<li><b>缺国内「元/克」视角</b>：他第二期全程用沪金元/克讲价位，本页主图是 COMEX 美元/盎司，换算对照还没做。</li>
<li><b>样本有限</b>：COT 周报一周一条，打顶事件总共三四十次，单条结论随时会翻盘；回测用的是滚动重叠观测，n 不是独立事件数，<b>只看方向、不看精确胜率</b>。</li>

<div class="warn"><b>免责声明</b>：本页是对博主公开口播内容的量化复盘，全部数据来自公开官方渠道，仅作方法论研究，<b>不构成投资建议</b>。回测含重叠观测、样本有限，历史规律不代表未来。</div>
</div>

<div class="foot">布鲁斯黄金看盘 · 数据源 CFTC / SHFE / 新浪财经 · 构建 __BUILT__</div>
<div id="tip"></div>
</div>

<script>
var D=__DATA__;
const W=750,ML=42,MR=8,MT=8,MB=16;
const IDS=['s1','s2','s3','s4'];
const CATS=['mm','prod','nonrept'];
const tip=document.getElementById('tip');
let N=0,WMAP=[],PO=[],PO_UP=[],PO_DN=[],C4=null;
var V=D.view;

function fmt(v,d){return v==null?'—':Number(v).toFixed(d==null?1:d);}
function el(t,a){const e=document.createElementNS('http://www.w3.org/2000/svg',t);for(const k in a)e.setAttribute(k,a[k]);return e;}
function px2x(i){return ML+(W-ML-MR)*i/(N-1);}
function x2i(sx){let i=Math.round((sx-ML)/(W-ML-MR)*(N-1));return Math.max(0,Math.min(N-1,i));}
function rng(arrs){let lo=Infinity,hi=-Infinity;
  arrs.forEach(a=>a.forEach(v=>{if(v!=null){if(v<lo)lo=v;if(v>hi)hi=v;}}));
  if(!isFinite(lo)){lo=0;hi=1;}const p=(hi-lo)*0.08||1;return[lo-p,hi+p];}
function bbArr(v,n,k){const mid=[],up=[],dn=[];
  for(let i=0;i<v.length;i++){if(i<n-1||v[i]==null){mid.push(null);up.push(null);dn.push(null);continue;}
    const seg=v.slice(i-n+1,i+1);if(seg.some(x=>x==null)){mid.push(null);up.push(null);dn.push(null);continue;}
    const m=seg.reduce((a,b)=>a+b,0)/n;const sd=Math.sqrt(seg.reduce((a,b)=>a+(b-m)*(b-m),0)/n);
    mid.push(m);up.push(m+k*sd);dn.push(m-k*sd);}
  return[mid,up,dn];}
function toDaily(wk){const o=new Array(N);for(let i=0;i<N;i++){const j=WMAP[i];o[i]=(j<0)?null:wk[j];}return o;}
function stochW(v,n){const o=new Array(v.length).fill(null);
  for(let i=n-1;i<v.length;i++){const w=v.slice(i-n+1,i+1);
    if(w.some(x=>x==null)||v[i]==null)continue;
    const lo=Math.min(...w),hi=Math.max(...w);
    o[i]=(hi===lo)?null:(v[i]-lo)/(hi-lo);}
  return o;}
function catColor(c){return c==='mm'?'var(--c-mm)':(c==='prod'?'var(--c-prod)':'var(--c-nonrept)');}
const CATCN={mm:'管理基金',prod:'商业',nonrept:'散户'};
function iOfSig(d){let best=-1;for(let i=0;i<N;i++){if(V.dates[i]<=d)best=i;else break;}return best;}

function buildData(){
  N=V.dates.length;
  WMAP=new Array(N);let j=-1;
  for(let i=0;i<N;i++){while(j+1<D.w_dates.length&&D.w_dates[j+1]<=V.dates[i])j++;WMAP[i]=j;}
  // PCR 前向填充（上期所与 COMEX 日历不同）
  PO=new Array(N);let lo=null;
  for(let i=0;i<N;i++){const p=D.pcr[V.dates[i]];if(p)lo=p.oi;PO[i]=lo;}
  const B=bbArr(PO,20,2);PO_UP=B[1];PO_DN=B[2];
  /* ④ ＝博主图上第三栏那条 "COT-index"：经典 COT Index
       idx = (净头寸_t − 近 26 周最低) / (近 26 周最高 − 最低) × 100
     作用在【净头寸】上、26 周窗口、没有速度差分。
     2026-10-08 把 2026-09-19 视频截图里那条蓝线逐像素取出（1379 个有效列）
     与本地 CFTC 数据做滑动相关：153 种口径组合里排第一的是
     「商业 Producer/Merchant 净头寸 + 26 周 + 无差分」，r=0.886（前五名全是它）。
     所以蓝线＝商业。旧版 (毛多_t−毛多_{t−13})/13 再 52 周归一化已弃用。 */
  const N4=26,wk={};
  CATS.forEach(c=>wk[c]=stochW(D['w_'+c+'_net'],N4).map(v=>v==null?null:v*100));
  C4={wk:wk,dl:{}};
  CATS.forEach(c=>C4.dl[c]=toDaily(wk[c]));
}

function drawChart(id,h,cfg){
  const svg=document.getElementById(id);svg.innerHTML='';
  const all=[];cfg.candles&&cfg.candles.forEach(c=>all.push(c.h,c.l));
  cfg.lines.forEach(s=>all.push(s.data));
  if(cfg.band)all.push(cfg.band.up,cfg.band.dn);
  let[lo,hi]=rng(all);
  if(cfg.yfix){lo=cfg.yfix[0];hi=cfg.yfix[1];}   // ④ 是固定 0~100 的指标，锁死纵轴才和他画面一致
  const ph=h-MT-MB,Y=v=>MT+ph*(hi-v)/(hi-lo);
  for(let t=0;t<=3;t++){const v=lo+(hi-lo)*t/3,y=Y(v);
    svg.appendChild(el('line',{x1:ML,y1:y,x2:W-MR,y2:y,stroke:'var(--grid)'}));
    const tx=el('text',{x:ML-4,y:y+3,'font-size':8.5,fill:'var(--sub)','text-anchor':'end'});
    tx.textContent=cfg.yfmt(v);svg.appendChild(tx);}
  const step=Math.max(1,Math.floor(N/5));
  for(let i=0;i<N;i+=step){const tx=el('text',{x:px2x(i),y:h-4,'font-size':8.5,fill:'var(--sub)','text-anchor':'middle'});
    tx.textContent=V.dates[i].slice(2,7);svg.appendChild(tx);}
  if(cfg.band){const up=[],dn=[];
    for(let i=0;i<N;i++){if(cfg.band.up[i]==null)continue;up.push([px2x(i),Y(cfg.band.up[i])]);dn.push([px2x(i),Y(cfg.band.dn[i])]);}
    if(up.length){const pts=up.map(p=>p[0].toFixed(1)+','+p[1].toFixed(1)).join(' ')+' '+dn.slice().reverse().map(p=>p[0].toFixed(1)+','+p[1].toFixed(1)).join(' ');
      svg.appendChild(el('polygon',{points:pts,fill:cfg.band.fill,opacity:0.10}));}}
  const cw=Math.max(0.8,(W-ML-MR)/N*0.62);
  if(cfg.candles)cfg.candles.forEach(c=>{
    for(let i=0;i<N;i++){const o=c.o[i],cl=c.c[i],hh=c.h[i],ll=c.l[i];
      if(o==null||cl==null||hh==null||ll==null)continue;
      const x=px2x(i),u=cl>=o,col=u?'var(--red)':'var(--green)';
      svg.appendChild(el('line',{x1:x.toFixed(1),y1:Y(hh).toFixed(1),x2:x.toFixed(1),y2:Y(ll).toFixed(1),stroke:col,'stroke-width':0.6}));
      const yT=Y(Math.max(o,cl)),yB=Y(Math.min(o,cl));
      svg.appendChild(el('rect',{x:(x-cw/2).toFixed(1),y:yT.toFixed(1),width:cw.toFixed(1),
        height:Math.max(0.5,yB-yT).toFixed(1),fill:col}));}});
  cfg.lines.forEach(s=>{let d='',st=false;
    for(let i=0;i<N;i++){const v=s.data[i];if(v==null)continue;
      d+=(st?'L':'M')+px2x(i).toFixed(1)+' '+Y(v).toFixed(1)+' ';st=true;}
    svg.appendChild(el('path',{d:d,fill:'none',stroke:s.color,'stroke-width':s.w||1.3,opacity:s.op||1,'stroke-dasharray':s.dash||''}));});
  if(cfg.zero!=null){const y=Y(cfg.zero);
    svg.appendChild(el('line',{x1:ML,y1:y,x2:W-MR,y2:y,stroke:'var(--sub)','stroke-width':0.8,'stroke-dasharray':'2 3',opacity:.5}));}
  if(cfg.refs)cfg.refs.forEach(r=>{const y=Y(r.v);
    svg.appendChild(el('line',{x1:ML,y1:y,x2:W-MR,y2:y,stroke:r.color,'stroke-width':0.9,'stroke-dasharray':'4 3',opacity:0.5}));
    const tx=el('text',{x:W-MR-2,y:y-2.5,'font-size':8,fill:r.color,'text-anchor':'end',opacity:0.75});
    tx.textContent=r.label;svg.appendChild(tx);});
  if(cfg.sigAt)D.signals.forEach(g=>{const i=iOfSig(g.date);if(i<0)return;
    const v=cfg.sigAt(i);if(v==null)return;
    svg.appendChild(el('circle',{cx:px2x(i).toFixed(1),cy:Y(v).toFixed(1),r:3.4,fill:g.dir==='空'?'var(--red)':'var(--green)',stroke:'var(--card)','stroke-width':1.2}));});
  const hl=el('line',{x1:0,y1:MT,x2:0,y2:h-MB,stroke:'var(--blue)','stroke-width':0.9,opacity:0});
  svg.appendChild(hl);svg._hl=hl;
  const rect=el('rect',{x:ML,y:MT,width:W-ML-MR,height:ph,fill:'transparent'});
  svg.appendChild(rect);
  function mv(cx,cy){const bb=svg.getBoundingClientRect();
    const sx=(cx-bb.left)/bb.width*W;paint(x2i(sx),cy,cx);}
  rect.addEventListener('mousemove',e=>mv(e.clientX,e.clientY));
  rect.addEventListener('mouseleave',hideTip);
  rect.addEventListener('touchmove',e=>{mv(e.touches[0].clientX,e.touches[0].clientY);},{passive:true});
  // 触屏松手后弹窗保留，方便阅读；点图表以外的空白处才收起
  rect.addEventListener('touchend',()=>{});
}

function hideTip(){
  tip.style.display='none';
  IDS.forEach(id=>{const s=document.getElementById(id);if(s._hl)s._hl.setAttribute('opacity',0);});
}

function paint(i,cy,cx){
  if(i<0)return;
  IDS.forEach(id=>{const s=document.getElementById(id);
    if(s._hl){s._hl.setAttribute('x1',px2x(i));s._hl.setAttribute('x2',px2x(i));s._hl.setAttribute('opacity',0.5);}});
  const j=WMAP[i];
  // 价格 %B 与 PCR %B：都是在各自 20 日布林带里的位置（0%=下轨，100%=上轨）
  const pbI=(V.up[i]!=null&&V.dn[i]!=null)?((V.c[i]-V.dn[i])/(V.up[i]-V.dn[i])*100):null;
  const pbP=(PO_UP[i]!=null&&PO_DN[i]!=null)?((PO[i]-PO_DN[i])/(PO_UP[i]-PO_DN[i])*100):null;
  let cot='';CATS.forEach(c=>{const v=(j<0)?null:D['w_'+c+'_net'][j];
    cot+='<br><span style="color:'+catColor(c)+'">■</span>'+CATCN[c]+'净 '+
    (v==null?'—':Math.round(v).toLocaleString())+'　指数 '+fmt(C4.dl[c][i],0);});
  tip.innerHTML='<b>'+V.dates[i]+'</b>'+(j>=0?'（'+D.w_dates[j]+'周报）':'')+'<br>'
    +'GC 收 '+fmt(V.c[i],1)+' <span style="color:var(--sub)">价格 %B '+fmt(pbI,0)+'%</span>'
    +'<br>PCR '+fmt(PO[i],3)+' <span style="color:var(--sub)">PCR %B '+fmt(pbP,0)+'%</span>'
    +cot+'<div class="hint">点图表以外的空白处收起</div>';
  tip.style.display='block';
  const tw=tip.offsetWidth||200;
  tip.style.left=Math.max(4,Math.min(cx+10,window.innerWidth-tw-8))+'px';
  tip.style.top=Math.max(4,Math.min(cy-14,window.innerHeight-tip.offsetHeight-8))+'px';
}

function state4(v){return v==null?'—':(v>=90?'<span style="color:var(--c-nonrept)">已打顶</span>':(v<=10?'打底':'中性'));}
function last4(c){for(let k=N-1;k>=0;k--)if(C4.dl[c][k]!=null)return C4.dl[c][k];return null;}

function updateCards(){
  const i=N-1;
  const pb=(V.up[i]!=null&&V.dn[i]!=null)?(V.c[i]-V.dn[i])/(V.up[i]-V.dn[i])*100:null;
  const pob=(PO_UP[i]!=null&&PO_DN[i]!=null)?(PO[i]-PO_DN[i])/(PO_UP[i]-PO_DN[i])*100:null;
  const lp=last4('prod'),lm=last4('mm');
  const live=D.live.GC||{},chg=live.prev_settle?((+live.price-+live.prev_settle)/+live.prev_settle*100):null;
  const c=[
    ['现货金价（GC）','<span class="'+(chg>0?'up':(chg<0?'down':''))+'">'+(live.price?+live.price:'—')+'</span>',
     (chg==null?'':(chg>0?'+':'')+chg.toFixed(2)+'%')+'　'+(live.date||'')],
    ['价格 %B',fmt(pb,0)+'%',pb>100?'破上轨→偏空':(pb<0?'破下轨→偏多':'通道内')],
    ['PCR·持仓量',fmt(PO[i],3),'%B '+fmt(pob,0)+'%'],
    ['④ 蓝线·商业','<span style="color:var(--c-prod)">'+fmt(lp,0)+'</span>',state4(lp)+'（他：打顶＝行情衰减）'],
    ['④ 绿线·管理基金','<span style="color:var(--c-mm)">'+fmt(lm,0)+'</span>',state4(lm)+'（他：打顶＝阶段底部）'],
  ];
  // 当下结论
  /* 博主原话规则：蓝线（商业）干到顶 → 行情衰减/回调 → 看空；
     绿线（管理基金）干到顶 → 已到阶段底部 → 看多。 */
  let cotd=0;if(lp!=null&&lp>=90)cotd=-1;else if(lm!=null&&lm>=90)cotd=1;
  let pcrd=0;if(pob!=null){if(pob>=100)pcrd=-1;else if(pob<=0)pcrd=1;}
  let st,vc;
  if(cotd&&pcrd&&cotd===pcrd){st='<span class="tag" style="background:#e6f4ec;color:#1b7a4b">共振·'+(cotd>0?'看多':'看空')+'</span>';
    vc='<b>两者同向（'+(cotd>0?'看多':'看空')+'）＝共振，他的规则里胜率更高。短期动作照常，中期仓位方向一致可稍放重心。</b>';}
  else if(cotd&&pcrd){st='<span class="tag" style="background:#fdeaea;color:#c62828">矛盾</span>';
    vc='<b style="color:var(--c-nonrept)">COT '+(cotd>0?'看多':'看空')+'（中期）× PCR '+(pcrd>0?'看多':'看空')+'（短期）＝矛盾：短期动作跟 PCR，中期仓位跟 COT，不重仓、不恋战。</b>';}
  else if(cotd||pcrd){st='<span class="tag">单边信号</span>';
    vc='只有一层给信号（'+(cotd?'COT '+(cotd>0?'看多':'看空'):'PCR '+(pcrd>0?'看多':'看空'))+'），另一层观察中——单边＝轻仓试探或等共振。';}
  else{st='<span class="tag">无信号</span>';vc='<b>通道内＝空仓等待，不猜方向。</b>';}
  c.push(['当下结论',st,vc]);
  document.getElementById('cards').innerHTML=c.map(x=>'<div class="kv"><div class="k">'+x[0]+'</div><div class="v'+(x[0]==='当下结论'?' small':'')+'">'+x[1]+'</div><div class="x">'+x[2]+'</div></div>').join('');
  document.getElementById('verdict').innerHTML=vc
    +'<div style="font-size:10.5px;color:var(--sub);margin-top:3px">时间轴 '+V.dates[0]+' ~ '+V.dates[N-1]+'（'+N+' 个交易日）· 四图共用同轴，左右滑动任一图可联动查看</div>';
}

function drawAll(){
  drawChart('s1',150,{candles:[{o:V.o,h:V.h,l:V.l,c:V.c}],
    band:{up:V.up,dn:V.dn,fill:'var(--blue)'},lines:[],
    sigAt:i=>V.c[i],yfmt:v=>v.toFixed(0)});
  drawChart('s2',140,{candles:null,
    band:{up:PO_UP,dn:PO_DN,fill:'var(--amber)'},
    lines:[{data:PO,color:'var(--amber)',w:1.4}],
    sigAt:i=>PO[i],yfmt:v=>v.toFixed(2)});
  drawChart('s3',130,{candles:null,
    lines:[{data:toDaily(D.w_mm_net),color:'var(--c-mm)',w:1.5},
           {data:toDaily(D.w_prod_net),color:'var(--c-prod)',w:1.5},
           {data:toDaily(D.w_nonrept_net),color:'var(--c-nonrept)',w:1.4}],
    zero:0,yfmt:v=>Math.round(v/1000)+'k'});
  drawChart('s4',140,{candles:null,yfix:[0,100],
    refs:[{v:90,color:'var(--c-nonrept)',label:'90 打顶'},{v:50,color:'var(--sub)',label:'50'},
          {v:10,color:'var(--c-prod)',label:'10'}],
    lines:CATS.map(c=>({data:C4.dl[c],color:catColor(c),w:1.5})),
    yfmt:v=>v.toFixed(0)});
}

function fillDetail(){
  // ③ 净持仓：为什么蓝线（商业）长期为负 —— 用真实统计回答，避免被误当成取数错误
  const S=D.net_stats,NN=document.getElementById('netNote');
  if(S&&NN){const P=S.prod,M=S.mm,W=S.nonrept,th=x=>Math.round(x).toLocaleString();
    NN.innerHTML='<b>⚠ 蓝线（商业）为什么几乎一直在负区？这不是取数错误。</b><br>'
      +'「净头寸」＝多头 − 空头，<b>本身就可以是负数</b>。商业（Producer/Merchant）是<b>产业套保盘</b>'
      +'——金矿商、精炼商、贸易商、工业用户在期货上<b>卖出</b>来锁定未来的售价/成本，天生是空头。'
      +'最新一周（'+D.w_dates[D.w_dates.length-1]+'）商业 多 '+th(P.long)+' / 空 '+th(P.short)
      +' → 净 <b>'+th(P.net)+'</b>（空是多头的 '+(P.short/P.long).toFixed(1)+' 倍）。'
      +'自 '+D.cot_first+' 起共 '+P.n+' 周，商业净头寸 <b>'+P.neg_pct+'% 为负</b>，区间 '+th(P.min)+' ~ '+th(P.max)+'。'
      +'散户（Non-Reportable）结构相反，最新净 '+th(W.net)+'；管理基金（M_Money）是投机盘、长期净多，最新净 +'+th(M.net)+'。'
      +'<br><b>所以这张图天生就是「蓝线在下面、绿线在上面」——那是持仓结构本身，不是画错。</b>'
      +'它回答的是「谁站在哪一边」；要回答「谁在抢着买」，看 ④ 那张 0~100 的 COT Index。'
      +'③④ 两张图配色与类别完全一致，但<b>量纲完全不同（持仓水平 vs 相对位置），别混着比</b>。';}
  // 共振/矛盾实证表
  const BD=D.cross.by_direction;
  function xrow(k,label,hint){const s=BD[k];if(!s||!s.n)return '';
    return '<tr><td>'+label+'</td><td>'+s.n+'</td><td><b>'+(s.avg_ret>0?'+':'')+s.avg_ret+'%</b></td><td>'+s.win_rate+'%</td><td style="font-size:10.5px">'+hint+'</td></tr>';}
  document.getElementById('crossTable').innerHTML='<table><tr><th>组合</th><th>观测日</th><th>后'+D.cross.fwd_days+'日均收益</th><th>一致率</th><th>解读</th></tr>'
    +xrow('共振·看多','共振·看多','跟')+xrow('共振·看空','共振·看空','躲')
    +xrow('矛盾·COT多/PCR空','COT多/PCR空','听 PCR 短线')
    +xrow('矛盾·COT空/PCR多','COT空/PCR多','抢反弹不重仓')
    +'</table><p style="font-size:11px;color:var(--sub)">⚠ 重叠滚动观测，n 不是独立事件数，只看方向。</p>';
  // 回测块：所有数字都从 cot_speed_backtest.json / cot_speed_sens.json 现算，
  // 换口径（long↔net）时文字与数字自动跟随，杜绝旧版写死 −11.2pp/+25.5pp 过期的问题。
  const b=D.bt,B=b.params||{},avg=a=>a.length?a.reduce((s,x)=>s+x[2],0)/a.length:null;
  const BASIS_CN={long:'毛多头寸（多头买量）',net:'净头寸（多−空）',short:'毛空头寸'}[B.basis]||B.basis;
  const judge=e=>e>=10?'成立':(e>=3?'弱成立':(e>-3?'基本无效':'反向'));
  const sig=x=>x>0?'up':'down',sgn=(x,d)=>((x>0?'+':'')+Number(x).toFixed(d==null?1:d));
  // 每个持有期现算：事件 = [日期, 读数, 后 N 周收益]，命中率＝方向一致占比（含亏损，与基准同口径）
  function rowOf(r,w,key,wantUp){
    const ev=(r&&r[key])||[];if(!ev.length)return null;
    const bDir=wantUp?D.sens.base_up[w]:100-D.sens.base_up[w];
    const win=ev.filter(e=>(e[2]>0)===wantUp).length;
    return {n:ev.length,hit:win/ev.length*100,bDir:bDir,exc:win/ev.length*100-bDir,avg:avg(ev)};
  }
  const cell=x=>x?('<b>'+fmt(x.hit,0)+'%</b> <span class="'+sig(x.exc)+'">'+sgn(x.exc,1)+'pp</span>'
    +'<br><span style="font-size:10px;color:var(--sub)">均'+sgn(x.avg,2)+'%（n='+x.n+'）</span>'):'—';
  let sh='<table><tr><th>持有期</th><th>基准<br>上涨率</th><th>蓝线·商业<br>打顶后</th><th>绿线·管理基金<br>打顶后</th></tr>';
  D.sens.holds.forEach(r=>{sh+='<tr><td>'+r.w+' 周</td><td>'+D.sens.base_up[r.w]+'%</td>'
    +'<td>'+cell(rowOf(r,r.w,'prod',false))+'</td><td>'+cell(rowOf(r,r.w,'mm',true))+'</td></tr>';});
  sh+='</table>';
  const H=D.sens.holds,p0=rowOf(H[0],H[0].w,'prod',false),pL=rowOf(H[H.length-1],H[H.length-1].w,'prod',false);
  const m0=rowOf(H[0],H[0].w,'mm',true),mL=rowOf(H[H.length-1],H[H.length-1].w,'mm',true);
  const trend=(a,z)=>!a||!z?'':(z.exc>a.exc+3?'，且随持有期拉长走强':(z.exc<a.exc-3?'，且随持有期拉长走弱':'，各持有期基本一致'));
  document.getElementById('btBlock').innerHTML=
    '<p>口径：<b>'+BASIS_CN+'</b> / N='+B.norm_weeks+' 周窗口 / 无速度差分，打顶＝读数≥90，事件按 4 周去重。样本：COT '+D.cot_n+' 周，基准 '+b.base.n+' 次滚动观测（基准上涨率 '+b.base.up_rate+'% / 平均 '+sgn(b.base.avg_ret,2)+'%）。</p>'
    +'<table><tr><th>信号</th><th>事件</th><th>命中率</th><th>基准</th><th>超额</th></tr>'
    +'<tr><td>蓝线·商业打顶＝看空</td><td>'+b.prod.n+'</td><td><b>'+b.prod.hit_rate+'%</b></td><td>'+b.prod.base_dir_rate+'%</td><td class="'+sig(b.prod.excess_pp)+'">'+sgn(b.prod.excess_pp,1)+'pp → '+judge(b.prod.excess_pp)+'</td></tr>'
    +'<tr><td>绿线·管理基金打顶＝看多</td><td>'+b.mm.n+'</td><td><b>'+b.mm.hit_rate+'%</b></td><td>'+b.mm.base_dir_rate+'%</td><td class="'+sig(b.mm.excess_pp)+'">'+sgn(b.mm.excess_pp,1)+'pp → '+judge(b.mm.excess_pp)+'</td></tr></table>'
    +sh
    +'<p><b>结论（'+BASIS_CN+'）</b>：① 蓝线·商业打顶后 8 周命中率 '+b.prod.hit_rate+'%、较基准 '+sgn(b.prod.excess_pp,1)+'pp（<b>'+judge(b.prod.excess_pp)+'</b>）'+(trend(p0,pL)||'')+'；'
    +'② 绿线·管理基金打顶后 8 周命中率 '+b.mm.hit_rate+'%、较基准 '+sgn(b.mm.excess_pp,1)+'pp（<b>'+judge(b.mm.excess_pp)+'</b>）'+(trend(m0,mL)||'')+'；'
    +'③ 事件只有 '+b.prod.n+' / '+b.mm.n+' 个，单点差异随时会翻盘——这套指数<b>适合看形态，不宜单条当交易信号</b>。</p>'
    +'<p style="font-size:11px;color:var(--sub)">口径溯源（2026-10-08 由截图逐像素反解重定）：博主 09-19 那期画面第三栏写的是 <b>COT-index comm/large/specs</b>，Y 轴 0~100、中间一条 50 虚线。把那条<b>蓝线</b>逐列取出（1379 个有效列）与本地 CFTC 数据做滑动相关，153 种口径组合里排第一的是「<b>商业 Producer/Merchant 净头寸 + 26 周 + 无速度差分</b>」，相关系数 <b>r=0.886</b>（前五名全是它，第二名 0.828；管理基金(net,26) 只有 0.402，毛多/速度口径全部 &lt;0.70）。→ <b>他图上的蓝线＝商业、绿线＝管理基金</b>，公式就是最经典的 COT Index。旧版「毛多 13 周速度 + 52 周归一化」是拿 8/25 画面读数 0.908 去凑商业毛多 0.9109 才选中的，属于巧合，已弃用。</p>'
    +'<p style="font-size:11px;color:var(--sub)">「规则方向」依据他 09-19 口播：蓝线（商业）干到顶 → <b>行情衰减、可横盘或直接回调</b>（2026-02-03 商业 =100，金价随后从 5217 跌到 4021）；绿线（管理基金）干到顶 → <b>已到阶段底部</b>，可分批接。</p>';
}

buildData();
drawAll();
updateCards();
fillDetail();
/* 右上角两行时间戳：PCR 与金价各自的数据日期，互不影响，不显示任何同步状态 */
function todayStr(){const d=new Date(),p=x=>(x<10?'0':'')+x;
  return d.getFullYear()+'-'+p(d.getMonth()+1)+'-'+p(d.getDate());}
function stamps(){
  const tp=D.pcr_last||V.dates[N-1],tg=D.gold_last||V.dates[N-1],T=todayStr();
  document.getElementById('updPcr').textContent=tp;
  document.getElementById('updGold').textContent=tg;
  /* 绿点＝数据日期就是今天（当天已更新）；红点＝还没更到今天 */
  const dp=document.getElementById('dotPcr'),dg=document.getElementById('dotGold');
  if(dp)dp.className='dot'+(tp===T?' on':'');
  if(dg)dg.className='dot'+(tg===T?' on':'');
}
stamps();

/* 弹窗保留策略：点图表以外的区域才收起（触屏与鼠标都生效） */
document.addEventListener('touchstart',function(e){
  if(!e.target.closest||!e.target.closest('svg'))hideTip();
},{passive:true});
document.addEventListener('mousedown',function(e){
  if(!e.target.closest||!e.target.closest('svg'))hideTip();
});

/* 云端自更新：并发拉取多个源（同源 → GitHub Pages → 国内镜像 → CDN 兜底），
   谁先回来先用谁、后到的更新自动覆盖；全部失败则静默保留内置数据，
   并在页面停留期间按递增间隔自动重试，网络一恢复就更新。
   不再显示任何兜底状态字样——数据时间戳本身就是唯一的状态标识。 */
(function(){
  var RAW='https://raw.githubusercontent.com/1278943518/gold-bruce/main/data.json';
  var BATCH=[
    ['./data.json',
     'https://1278943518.github.io/gold-bruce/data.json',
     'https://ghfast.top/'+RAW],
    ['https://cdn.jsdelivr.net/gh/1278943518/gold-bruce@main/data.json',
     'https://fastly.jsdelivr.net/gh/1278943518/gold-bruce@main/data.json',
     'https://ghproxy.net/'+RAW]
  ];
  var RETRY=[30000,90000,180000,300000];   /* 全失败后的重试间隔(ms) */
  var applied=D.built_at,busy=false,round=0;

  function show(){stamps();}

  function apply(j){
    if(!j||!j.built_at||!j.view)return;
    if(j.built_at<=applied)return;
    applied=j.built_at;D=j;V=j.view;
    buildData();drawAll();updateCards();fillDetail();
    show();
  }

  function timedFetch(u,ms){
    return new Promise(function(res,rej){
      var done=false,ctl=null;
      var t=setTimeout(function(){
        if(done)return;done=true;
        if(ctl){try{ctl.abort();}catch(e){}}
        rej(0);
      },ms);
      var opt={cache:'no-store'};
      if(typeof AbortController!=='undefined'){ctl=new AbortController();opt.signal=ctl.signal;}
      fetch(u,opt).then(function(r){
        if(!r.ok)throw 0;return r.json();
      }).then(function(j){
        if(done)return;done=true;clearTimeout(t);res(j);
      }).catch(function(){
        if(done)return;done=true;clearTimeout(t);
        if(ctl){try{ctl.abort();}catch(e){}}
        rej(0);
      });
    });
  }

  function pull(list){
    return Promise.all(list.map(function(u){
      return timedFetch(u,8000).then(function(j){apply(j);return 1;},function(){return 0;});
    })).then(function(rs){
      var n=0;for(var k=0;k<rs.length;k++)n+=rs[k];return n;
    });
  }

  function run(){
    if(busy)return;busy=true;
    pull(BATCH[0]).then(function(n0){
      if(n0>0)return n0;
      return pull(BATCH[1]);
    }).then(function(n){
      busy=false;show();
      if(n>0){round=0;return;}
      if(round<RETRY.length){var d=RETRY[round];round++;setTimeout(run,d);}
    }).catch(function(){busy=false;show();});
  }

  /* 从后台切回前台时立刻补一次（手机常见的「放着不动→回来还是旧数据」） */
  document.addEventListener('visibilitychange',function(){
    if(!document.hidden&&!busy){round=0;run();}
  });

  show();
  run();
})();
</script></body></html>"""

    html = (HTML.replace("__DATA__", payload)
                .replace("__LOGO__", logo64)
                .replace("__FAV__", fav32)
                .replace("__COTN__", str(len(w_dates)))
                .replace("__COTFIRST__", cot[0]["date"])
                .replace("__VALIDFROM__", data["valid_from"])
                .replace("__BUILT__", data["built_at"]))
    os.makedirs(OUTDIR, exist_ok=True)
    open(OUT, "w", encoding="utf-8").write(html)

    # 同时产出一份 data.json，放在仓库根目录。
    # 页面会在加载时从这里拉最新数据（GitHub Pages / jsDelivr 都带 CORS），
    # 于是已发布的页面无需重新部署即可自己更新。
    data_json = os.path.join(BASE, "data.json")
    open(data_json, "w", encoding="utf-8").write(payload)
    print("  云端数据: %s | %.1f KB" % (data_json, len(payload) / 1024.0))

    # logo 套装复制到发布目录
    adir = os.path.join(OUTDIR, "assets")
    os.makedirs(adir, exist_ok=True)
    for f in ("logo.png", "logo-512.png", "logo-180.png", "logo-64.png",
              "favicon.ico", "favicon-32.png", "logo-square.png"):
        src = os.path.join(ASSETS, f)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(adir, f))

    # iOS「添加到主屏幕」图标 + web app manifest。
    # 页面在 GitHub Pages 上位于 /gold-bruce/ 子路径、在 WorkBuddy 上位于根路径，
    # 两处引用的都是相对路径 assets/xxx 与 manifest.webmanifest，
    # 所以**仓库根**与**发布目录**两边都要各放一份（否则有一边会 404）。
    manifest = {
        "name": "布鲁斯黄金看盘 · COT × PCR × 价格",
        "short_name": "布鲁斯黄金看盘",
        "description": "COT 持仓 · 期权 PCR · 价格通道三层合并的黄金中长线看板",
        "start_url": "./", "scope": "./",
        # display 用 browser：保留 Safari 地址栏与下拉刷新（数据每日变，能刷新很关键）。
        # 想要全屏应用感（无地址栏）把它改成 standalone 即可，但下拉刷新会失效。
        "display": "browser",
        "background_color": "#f5f6f8", "theme_color": "#141418",
        "icons": [{"src": "assets/icon-192.png", "sizes": "192x192", "type": "image/png"},
                  {"src": "assets/icon-512.png", "sizes": "512x512", "type": "image/png"}],
    }
    mf = json.dumps(manifest, ensure_ascii=False, indent=1)
    IOS_ASSETS = ("apple-touch-icon.png", "icon-192.png", "icon-512.png")
    for root in (BASE, OUTDIR):
        os.makedirs(os.path.join(root, "assets"), exist_ok=True)
        with open(os.path.join(root, "manifest.webmanifest"), "w", encoding="utf-8") as fh:
            fh.write(mf)
        for f in IOS_ASSETS:
            src = os.path.join(ASSETS, f)
            if not os.path.exists(src):
                raise SystemExit("缺少 iOS 图标资源: %s（先跑 scripts/make_ios_icons.py）" % f)
            shutil.copy2(src, os.path.join(root, "assets", f))
    print("  iOS 图标: apple-touch-icon.png / icon-192.png / icon-512.png + manifest.webmanifest")

    print("手机版已生成:", OUT, "| %.1f KB" % (os.path.getsize(OUT) / 1024.0))
    print("  时间轴 %s ~ %s（%d 交易日）| COT %d 周 | PCR %d 天"
          % (view["dates"][0], view["dates"][-1], len(view["dates"]), len(w_dates), len(pcr)))


if __name__ == "__main__":
    main()

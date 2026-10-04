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
            "cot_n": len(w_dates), "cot_first": cot[0]["date"],
            "bt": bt, "sens": sens, "cross": cross,
            "valid_from": load("cot_speed_index.json")["valid_from"],
            "built_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")}
    for cat in ("prod", "mm", "other", "swap"):
        for basis in ("net", "long", "short"):
            data["w_%s_%s" % (cat, basis)] = [c[cat + "_" + basis] for c in cot]

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
<style>
:root{--bg:#f5f6f8;--card:#fff;--ink:#1b1f24;--sub:#67717d;--line:#e6e9ee;--grid:#eef1f4;
--red:#c62828;--green:#1b7a4b;--amber:#a06a00;--blue:#1f5fbf;
--c-prod:#0f7a52;--c-mm:#1f5fbf;--c-other:#c62828;--c-swap:#8a94a0}
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
body{margin:0;background:var(--bg);color:var(--ink);
font:14px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif}
.wrap{max-width:560px;margin:0 auto;padding:10px 10px 40px}
.hd{display:flex;align-items:center;gap:9px;padding:4px 2px 8px}
.hd img{width:38px;height:38px;border-radius:9px}
.hd h1{font-size:16.5px;margin:0;line-height:1.25}
.hd .sub{font-size:11px;color:var(--sub)}
.upd{font-size:10.5px;color:var(--sub);text-align:right;margin-left:auto;line-height:1.4}
.upd b{color:var(--blue);font-size:11px;display:block}
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
.detail li{margin:4px 0}
.detail table{width:100%;border-collapse:collapse;font-size:11.5px;margin:7px 0}
.detail th,.detail td{border:1px solid var(--line);padding:4px 6px;text-align:left}
.detail th{background:var(--grid)}
.warn{background:var(--grid);border:1px solid var(--line);border-radius:9px;padding:8px 10px;font-size:12px;margin:8px 0}
.tag{display:inline-block;font-size:10.5px;padding:1px 6px;border-radius:5px;background:var(--grid)}
#tip{position:fixed;pointer-events:none;background:#fff;border:1px solid var(--line);
border-radius:8px;padding:5px 8px;font-size:10.5px;box-shadow:0 3px 12px rgba(0,0,0,.15);display:none;z-index:99;white-space:nowrap;line-height:1.5}
.foot{text-align:center;color:var(--sub);font-size:10.5px;margin:16px 0 4px}
</style></head><body><div class="wrap">

<div class="hd">
<img src="data:image/png;base64,__LOGO__" alt="logo">
<div><h1>布鲁斯黄金看盘</h1><div class="sub">COT 持仓 × 期权 PCR × 价格通道 · 四维联动</div></div>
<div class="upd">数据更新至<b id="updDate">—</b><span id="builtAt"></span></div>
</div>

<div class="grid6" id="cards"></div>
<div id="verdict"></div>

<div class="card"><div class="ct"><b>① COMEX 黄金 GC</b><span>蜡烛 + BB(20,2)　<span style="color:var(--red)">涨</span>/<span style="color:var(--green)">跌</span></span></div>
<svg id="s1" viewBox="0 0 750 150"></svg></div>

<div class="card"><div class="ct"><b>② 黄金期权 PCR</b><span>持仓量口径 + BB(20,2)（上期所）</span></div>
<svg id="s2" viewBox="0 0 750 140"></svg></div>

<div class="card"><div class="ct"><b>③ CFTC 分类净持仓</b><span>周频　<span class="sw" style="background:var(--c-prod)"></span>商业 <span class="sw" style="background:var(--c-mm)"></span>管理基金 <span class="sw" style="background:var(--c-other)"></span>散户</span></div>
<svg id="s3" viewBox="0 0 750 130"></svg></div>

<div class="card"><div class="ct"><b>④ COT「购买速度」指数</b><span>0~1，≥0.90＝打顶</span></div>
<svg id="s4" viewBox="0 0 750 140"></svg></div>

<a class="more" href="#manual">▼ 详细说明 · 使用手册（怎么看 / 为什么这么设计）</a>

<div class="detail" id="manual">
<h2>一、这是什么</h2>
<p>把抖音博主「布鲁斯」讲的中长线黄金分析框架做成可视化看板。他的优先级：<b>COT 持仓 ＞ 升贴水 ＞ 期权 PCR ＞ 技术分析</b>。本页把其中可量化、有免费官方数据源的三层（COT、PCR、价格通道）接入真实数据，四张图共用同一条日频时间轴。</p>

<h2>二、四张图怎么看（逐图手册）</h2>
<p><b>① 价格 + 布林通道 BB(20,2)</b>——蜡烛红涨绿跌（国内习惯）。他口播里的信号：<b>破上轨＝顶部（开空）、击穿下轨＝底部（做多）、通道内＝空仓等待</b>。图上的圆点是他视频里明确说过的信号位，可核对是否印证。</p>
<p><b>② 黄金期权 PCR（持仓量口径）</b>——看通道位置而不是绝对值：PCR %B 触到下轨（≤0）≈ 看多情绪极端，短中期易反弹；冲到上轨（≥100）≈ 偏空。橙线为成交量口径对照。注意 PCR 是<b>短中期</b>尺度（实证约 20 日兑现）。</p>
<p><b>③ CFTC 分类净持仓</b>——他 09-19 视频的口径：<span style="color:var(--c-prod)"><b>绿线</b></span>＝商业头寸「整个市场最大的资金」、<span style="color:var(--c-mm)"><b>蓝线</b></span>＝管理基金「华尔街大型投机机构」、<span style="color:var(--c-other)"><b>红线</b></span>＝其他可报告「散户小机构」、灰虚线＝互换商（他未指定颜色）。周频数据阶跃对齐到日轴。</p>
<p><b>④ COT「购买速度」指数（他自编公式的复原）</b>——
speed＝(买量<sub>t</sub> − 买量<sub>t−13</sub>) ÷ 13，再算 speed 在近 52 周中的相对位置（0~1）。
<span style="color:var(--c-prod)"><b>绿线打顶（≥0.90）</b></span>＝他说「最大资金加速买入到顶」；<span style="color:var(--c-mm)"><b>蓝线打顶</b></span>＝「投机资金加速衰减」。公式经他视频画面读数校准（2026-08-25 绿线 0.9109 vs 画面 0.908，差 0.3%）。</p>

<h2>三、顶部六个信息块</h2>
<li><b>现货金价</b>：COMEX GC 最新价（隔夜报价快照，每日构建时更新）与前一交易日收盘的涨跌。</li>
<li><b>价格 %B / PCR %B</b>：各自在 BB(20,2) 通道中的位置，&gt;100 破上轨、&lt;0 破下轨、通道内无信号。</li>
<li><b>④ 绿线 / 蓝线</b>：两条速度线最新读数与状态（已打顶 / 打底 / 中性）。</li>
<li><b>当下结论</b>：按他的规则综合给出的当前状态。</li>

<h2>四、COT × PCR 矛盾时怎么办（三条原则）</h2>
<p>① <b>先认时间尺度</b>：COT 周频＝中期（实证 20 周才兑现），PCR 日频＝短中期（20 日兑现）。矛盾多半不是谁错，是节奏不同。</p>
<p>② <b>短期动作跟 PCR，中期仓位跟 COT</b>：他自己也是这么做的——「PCR 击穿下轨可开多接刀子，但不可重仓」。</p>
<p>③ <b>实在对不上就空仓</b>：「通道内＝空仓等待，不猜方向」。</p>
<div id="crossTable"></div>

<h2>五、④ 这套规则回测（全样本，别只看一条）</h2>
<div id="btBlock"></div>

<h2>六、数据来源与每日更新</h2>
<li>COT：美国 CFTC 官网 Disaggregated 报告（周频，每周六凌晨更新，__COTN__ 周，__COTFIRST__ 起）。</li>
<li>PCR：上期所黄金期权日行情（持仓量口径，2024-03-21 起）。</li>
<li>价格：新浪财经 COMEX GC 日线 + 隔夜实时报价快照。</li>
<li>④ 需 64 周预热，__VALIDFROM__ 起有效；主图为 COMEX（与 COT 同市场，口径自洽）。</li>
<li>本页每日早上自动重抓数据并重新构建发布；COT 实际变化每周一次，PCR 与价格每日更新。</li>

<h2>七、为什么这么设计</h2>
<li><b>四图同轴联动</b>：他的体系是「多层信号互相验证」，分开看容易漏掉共振/矛盾。</li>
<li><b>PCR 用持仓量而非成交量</b>：与他截图同款口径（经 2026-08-24 读数 0.7512 四位小数精确匹配确认）。</li>
<li><b>主图用 COMEX 而非沪金</b>：COT 是 COMEX 头寸，价格与持仓必须同市场；国内合约作副口径。</li>
<li><b>④ 用「速度」而非「持仓多少」</b>：他反复强调"资金加速买入"而非"资金多"；随机指标化后与他画面读数误差最小。</li>

<div class="warn"><b>免责声明</b>：本页是对博主公开口播内容的量化复盘，全部数据来自公开官方渠道，仅作方法论研究，<b>不构成投资建议</b>。回测含重叠观测、样本有限，历史规律不代表未来。</div>
</div>

<div class="foot">布鲁斯黄金看盘 · 数据源 CFTC / SHFE / 新浪财经 · 构建 __BUILT__</div>
<div id="tip"></div>
</div>

<script>
var D=__DATA__;
const W=750,ML=42,MR=8,MT=8,MB=16;
const IDS=['s1','s2','s3','s4'];
const CATS=['prod','mm','other'];
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
function deltaW(v,k){const o=new Array(v.length).fill(null);
  for(let i=k;i<v.length;i++)o[i]=(v[i]-v[i-k])/k;return o;}
function stochW(v,n){const o=new Array(v.length).fill(null);
  for(let i=n-1;i<v.length;i++){const w=v.slice(i-n+1,i+1);
    if(w.some(x=>x==null)||v[i]==null)continue;
    const lo=Math.min(...w),hi=Math.max(...w);
    o[i]=(hi===lo)?null:(v[i]-lo)/(hi-lo);}
  return o;}
function catColor(c){return c==='prod'?'var(--c-prod)':(c==='mm'?'var(--c-mm)':'var(--c-other)');}
function iOfSig(d){let best=-1;for(let i=0;i<N;i++){if(V.dates[i]<=d)best=i;else break;}return best;}

function buildData(){
  N=V.dates.length;
  WMAP=new Array(N);let j=-1;
  for(let i=0;i<N;i++){while(j+1<D.w_dates.length&&D.w_dates[j+1]<=V.dates[i])j++;WMAP[i]=j;}
  // PCR 前向填充（上期所与 COMEX 日历不同）
  PO=new Array(N);let lo=null;
  for(let i=0;i<N;i++){const p=D.pcr[V.dates[i]];if(p)lo=p.oi;PO[i]=lo;}
  const B=bbArr(PO,20,2);PO_UP=B[1];PO_DN=B[2];
  const K=13,Nn=52,wk={};
  CATS.forEach(c=>wk[c]=stochW(deltaW(D['w_'+c+'_long'],K),Nn));
  const B4=bbArr(wk.mm,20,2);
  C4={wk:wk,dl:{},mid:toDaily(B4[0]),up:toDaily(B4[1]),dn:toDaily(B4[2])};
  CATS.forEach(c=>C4.dl[c]=toDaily(wk[c]));
}

function drawChart(id,h,cfg){
  const svg=document.getElementById(id);svg.innerHTML='';
  const all=[];cfg.candles&&cfg.candles.forEach(c=>all.push(c.h,c.l));
  cfg.lines.forEach(s=>all.push(s.data));
  if(cfg.band)all.push(cfg.band.up,cfg.band.dn);
  const[lo,hi]=rng(all);
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
  rect.addEventListener('mouseleave',()=>{IDS.forEach(id=>{const s=document.getElementById(id);if(s._hl)s._hl.setAttribute('opacity',0);});tip.style.display='none';});
  rect.addEventListener('touchmove',e=>{mv(e.touches[0].clientX,e.touches[0].clientY);},{passive:true});
  rect.addEventListener('touchend',()=>{setTimeout(()=>{tip.style.display='none';IDS.forEach(id=>{const s=document.getElementById(id);if(s._hl)s._hl.setAttribute('opacity',0);});},1600);});
}

function paint(i,cy,cx){
  if(i<0)return;
  IDS.forEach(id=>{const s=document.getElementById(id);
    if(s._hl){s._hl.setAttribute('x1',px2x(i));s._hl.setAttribute('x2',px2x(i));s._hl.setAttribute('opacity',0.5);}});
  const j=WMAP[i];
  let cot='';CATS.forEach(c=>{const v=(j<0)?null:D['w_'+c+'_net'][j];
    cot+='<br><span style="color:'+catColor(c)+'">■</span>'+(c==='prod'?'商业':(c==='mm'?'管理基金':'散户'))+'净 '+
    (v==null?'—':Math.round(v).toLocaleString())+'　速 '+fmt(C4.dl[c][i],2);});
  tip.innerHTML='<b>'+V.dates[i]+'</b>'+(j>=0?'（'+D.w_dates[j]+'周报）':'')+'<br>'
    +'GC 收 '+fmt(V.c[i],1)+'　PCR '+fmt(PO[i],3)+cot;
  tip.style.display='block';
  tip.style.left=Math.min(cx+10,window.innerWidth-170)+'px';
  tip.style.top=(cy-14)+'px';
}

function state4(v){return v==null?'—':(v>=0.90?'<span style="color:var(--c-other)">已打顶</span>':(v<=0.10?'打底':'中性'));}
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
    ['④ 绿线·最大资金','<span style="color:var(--c-prod)">'+fmt(lp,3)+'</span>',state4(lp)+'（打顶＝他判买点）'],
    ['④ 蓝线·投机资金','<span style="color:var(--c-mm)">'+fmt(lm,3)+'</span>',state4(lm)+'（打顶＝行情衰减）'],
  ];
  // 当下结论
  let cotd=0;if(lp!=null&&lp>=0.90)cotd=1;else if(lm!=null&&lm>=0.90)cotd=-1;
  let pcrd=0;if(pob!=null){if(pob>=100)pcrd=-1;else if(pob<=0)pcrd=1;}
  let st,vc;
  if(cotd&&pcrd&&cotd===pcrd){st='<span class="tag" style="background:#e6f4ec;color:#1b7a4b">共振·'+(cotd>0?'看多':'看空')+'</span>';
    vc='<b>两者同向（'+(cotd>0?'看多':'看空')+'）＝共振，他的规则里胜率更高。短期动作照常，中期仓位方向一致可稍放重心。</b>';}
  else if(cotd&&pcrd){st='<span class="tag" style="background:#fdeaea;color:#c62828">矛盾</span>';
    vc='<b style="color:var(--c-other)">COT '+(cotd>0?'看多':'看空')+'（中期）× PCR '+(pcrd>0?'看多':'看空')+'（短期）＝矛盾：短期动作跟 PCR，中期仓位跟 COT，不重仓、不恋战。</b>';}
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
    lines:[{data:toDaily(D.w_prod_net),color:'var(--c-prod)',w:1.4},
           {data:toDaily(D.w_mm_net),color:'var(--c-mm)',w:1.4},
           {data:toDaily(D.w_other_net),color:'var(--c-other)',w:1.1},
           {data:toDaily(D.w_swap_net),color:'var(--c-swap)',w:0.9,op:0.6,dash:'4 3'}],
    zero:0,yfmt:v=>Math.round(v/1000)+'k'});
  drawChart('s4',140,{candles:null,
    band:{up:C4.up,dn:C4.dn,fill:'var(--c-mm)'},
    refs:[{v:0.90,color:'var(--c-other)',label:'0.90 打顶'},{v:0.10,color:'var(--c-swap)',label:'0.10'}],
    lines:CATS.map(c=>({data:C4.dl[c],color:catColor(c),w:1.5})),
    yfmt:v=>v.toFixed(1)});
}

function fillDetail(){
  // 共振/矛盾实证表
  const BD=D.cross.by_direction;
  function xrow(k,label,hint){const s=BD[k];if(!s||!s.n)return '';
    return '<tr><td>'+label+'</td><td>'+s.n+'</td><td><b>'+(s.avg_ret>0?'+':'')+s.avg_ret+'%</b></td><td>'+s.win_rate+'%</td><td style="font-size:10.5px">'+hint+'</td></tr>';}
  document.getElementById('crossTable').innerHTML='<table><tr><th>组合</th><th>观测日</th><th>后'+D.cross.fwd_days+'日均收益</th><th>一致率</th><th>解读</th></tr>'
    +xrow('共振·看多','共振·看多','跟')+xrow('共振·看空','共振·看空','躲')
    +xrow('矛盾·COT多/PCR空','COT多/PCR空','听 PCR 短线')
    +xrow('矛盾·COT空/PCR多','COT空/PCR多','抢反弹不重仓')
    +'</table><p style="font-size:11px;color:var(--sub)">⚠ 重叠滚动观测，n 不是独立事件数，只看方向。</p>';
  // 回测块
  const b=D.bt,avg=a=>a.length?a.reduce((s,x)=>s+x[2],0)/a.length:null;
  let sh='<table><tr><th>持有期</th><th>基准上涨率</th><th>绿线打顶后</th><th>蓝线打顶后</th></tr>';
  D.sens.holds.forEach(r=>{const ap=avg(r.prod),am=avg(r.mm);
    sh+='<tr><td>'+r.w+' 周</td><td>'+D.sens.base_up[r.w]+'%</td>'
      +'<td class="'+(ap>0?'up':'down')+'">'+(ap>0?'+':'')+ap.toFixed(2)+'%（'+r.prod.length+'）</td>'
      +'<td class="'+(am>0?'up':'down')+'">'+(am>0?'+':'')+am.toFixed(2)+'%（'+r.mm.length+'）</td></tr>';});
  sh+='</table>';
  document.getElementById('btBlock').innerHTML=
    '<p>口径：多头买量 / K=13 / N=52，打顶＝读数≥0.90，事件按 4 周去重。样本：COT '+D.cot_n+' 周，基准 '+b.base.n+' 次滚动观测（基准上涨率 '+b.base.up_rate+'%）。</p>'
    +'<table><tr><th>信号</th><th>事件</th><th>命中率</th><th>基准</th><th>超额</th></tr>'
    +'<tr><td>绿线打顶＝买点</td><td>'+b.prod.n+'</td><td><b>'+b.prod.hit_rate+'%</b></td><td>'+b.prod.base_dir_rate+'%</td><td class="down">'+b.prod.excess_pp+'pp → 不成立</td></tr>'
    +'<tr><td>蓝线打顶＝衰减</td><td>'+b.mm.n+'</td><td><b>'+b.mm.hit_rate+'%</b></td><td>'+b.mm.base_dir_rate+'%</td><td class="up">+'+b.mm.excess_pp+'pp → 成立(短期)</td></tr></table>'
    +sh
    +'<p><b>结论</b>：① 绿线打顶后买入<b>跑输什么都不做</b>（−11.2pp）；② 蓝线打顶后短期（4~8 周）确实易跌易横（+25.5pp），但 20 周后回到正收益——是「牛市回调」不是反转；③ 上一版只有 1 个样本时结论正好相反——<b>小样本结论不可信</b>。</p>';
}

buildData();
drawAll();
updateCards();
fillDetail();
document.getElementById('updDate').textContent=V.dates[N-1];
document.getElementById('builtAt').textContent='构建 '+D.built_at;

/* 云端自更新：页面加载后去 GitHub 取最新数据，取到且比内置快照新就整体重绘。
   取不到（离线 / CDN 不通）就保留内置快照，页面永远有内容。 */
(function(){
  var SRC=[
    'https://1278943518.github.io/gold-bruce/data.json',
    'https://raw.githubusercontent.com/1278943518/gold-bruce/main/data.json',
    'https://cdn.jsdelivr.net/gh/1278943518/gold-bruce@main/data.json'
  ];
  var i=0;
  function next(){
    if(i>=SRC.length){
      document.getElementById('builtAt').textContent='构建 '+D.built_at+' · 离线快照';
      return;
    }
    var u=SRC[i++];
    fetch(u,{cache:'no-store'}).then(function(r){
      if(!r.ok)throw 0;return r.json();
    }).then(function(j){
      if(!j||!j.built_at||!j.view)throw 0;
      if(j.built_at<=D.built_at){
        document.getElementById('builtAt').textContent='构建 '+D.built_at+' · 已是最新';
        return;
      }
      D=j;V=j.view;
      buildData();drawAll();updateCards();fillDetail();
      document.getElementById('updDate').textContent=V.dates[N-1];
      document.getElementById('builtAt').textContent='云端更新 '+j.built_at;
    }).catch(next);
  }
  next();
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

    print("手机版已生成:", OUT, "| %.1f KB" % (os.path.getsize(OUT) / 1024.0))
    print("  时间轴 %s ~ %s（%d 交易日）| COT %d 周 | PCR %d 天"
          % (view["dates"][0], view["dates"][-1], len(view["dates"]), len(w_dates), len(pcr)))


if __name__ == "__main__":
    main()

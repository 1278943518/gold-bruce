# 布鲁斯黄金看盘 · COT × PCR × 价格

手机版单页看盘工具。**纯标准库 Python 构建，无第三方依赖。**

在线地址：https://1278943518.github.io/gold-bruce/

## 目录结构

```
index.html                 线上页面（由构建脚本生成，单文件自包含）
scripts/                   数据管道与页面构建
  daily_refresh_ci.py      每日刷新总入口
  fetch_gold_data.py       沪金/AU2612/GC 日线 + 实时报价（新浪）
  fetch_pcr_long.py        上期所期权 PCR 增量补抓
  fetch_cot_pcr.py         CFTC COT 抓取与解析
  compute_cot_speed_index.py  ④ 购买速度指数
  backtest_cot_speed.py    打顶信号回测 + 持有期敏感性
  crosscheck_cot_pcr.py    COT × PCR 共振/矛盾实证
  build_gold_app.py        生成手机版 index.html
data/market/               市场数据（COT 周度、PCR 日度、金价日线等）
outputs/assets/            logo 资源（仓库内以 base64 文本保存，便于纯文本推送）
```

## 每日刷新

`.github/workflows/refresh.yml` 每天 UTC 00:00（北京时间 08:00）自动运行：

金价 → 上期所 PCR 增量 → CFTC COT 当年合并 → ④指数 → 回测 → 共振实证 → 重建页面 → 有变化则提交。

页面地址固定不变，内容每天自动更新，不需要重新发布。也可在 Actions 页手动触发。

⚠ 注意：更新 COT 时**不能直接跑 `fetch_cot_pcr.py --cot`**，它会覆盖整个历史文件；
必须走 `daily_refresh_ci.py` 里的 `merge_cot()`，只抓当年 zip 再与历史合并。

## 本地运行

```bash
python scripts/daily_refresh_ci.py
```

## 免责声明

仅供个人研究参考，不构成任何投资建议。

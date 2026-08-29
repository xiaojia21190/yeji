# 自动业绩快报（GitHub Actions 定时扫描）

- 日期：2026-08-29
- 状态：已实现（山东黄金 600547 真实端到端验收，judge 视觉验收通过）

## 1. 目标

定时扫描 watchlist 内公司的财报披露，新披露自动生成「量化 + AI 撰写」的业绩快报，
发布到报告中心（GitHub Pages 自动更新），并开 issue 通知；深度六模块 AI 分析仍在本地跑 skill。

## 2. 架构与分工（v2：全市场监听）

```
cron (UTC 2/10/14 点 = 北京 10/18/22 点)
  └─ scan_and_brief.py
       ├─ scan_dev.scan_full_market()   # 巨潮预约披露表 1 次调用（当前季 ±1 期）
       │    → 回看窗口（3 天）内「实际披露」名单 → watchlist 优先、confirm_cap=300 截断
       ├─ auto_brief_dev.build_brief(period=日历期)   # 新浪未同步该期 → 跳过计数，下轮重试
       │    ├─ 脚本量化：单季拆解/同比、评分卡数值规则、反推对照（仅披露日前研报）、
       │    │   趋势、估值、同行（watchlist 配置才有）
       │    └─ AI 撰写（可选）：summary 文字 + 驱动维定性（重试 3 轮）
       ├─ save_payload → reports/{code}_{period}.json（viewer/Pages 直接渲染）
       └─ scan_result.json → workflow 建 issue 通知（含积压与未同步计数）

降级：日历接口整体失败 → 回退 watchlist 逐只扫描（摘要最新期判定）。
成本分层：AI 仅 watchlist（AI_ALL=1 可放开）；非 watchlist 纯量化，单次上限 60 份。
```

纪律：AI 只允许使用脚本算好的数据包数字（编造即触发 schema 校验降级）；
summary tone 与综合评级按 performance.md 合成规则可复算，AI 只写文字不定 tone；
AI 缺席时驱动维缺省、评级标注四维量化初判，管线绝不阻塞。

## 3. 配置

- `watchlist.json`：code/name/peers；港股不适用（取数链仅 A 股）
- 仓库 Secrets（Settings → Secrets and variables → Actions）：
  - `AI_API_KEY`（必需才启用 AI；不配则纯量化）
  - `AI_BASE_URL`（如 https://ai.huan666.de/v1）
  - `AI_MODEL`（如 deepseek-v4-flash）
- 手动触发：Actions 页 scan-earnings → Run workflow（调试入口）

## 4. 验收中发现并修复的坑

1. 摘要接口毛利率/ROE 是**百分数值**（24.43 = 24.43%），与自算小数混比产生 1801% 脏值——统一 ÷100
2. prev_cum_period 漏拼年份 → 单季退化成累计
3. scan() 未透传 peers → 同行模块静默消失
4. AI tone 覆盖合成规则 → 收紧为 AI 只写文字
5. 跨行字符串少 `+` 被解析为 str 调用（TypeError）
6. 巨潮期数参数「一季/三季」**不带「报」**（半年报/年报才带）
7. **负增长阈值守卫**：营收同比为负时，应收/存货「增速 ×1.5/×2」阈值为负形同虚设（存货 −4.5% 被判高增）——仅营收正增长时启用
8. **亏损期口径**：归母为负时净现比/非经常占比失真（分母为负），不参与质量打分并注明
9. cutoff 字符串二次 isoformat（TypeError）；日历整体失败自动降级 watchlist 逐只扫描

## 5. 全市场实跑记录（2026-08-29，中报季峰值）

日历命中 2958 家（回看 3 天）→ 待生成 299（confirm_cap 截断）→ 上限 2 份抽样：
000006 深振业Ａ（亏损地产，边界压力样本，judge 验收通过）、000007 全新好，均正确降级
（无可溯源预测 → 预期对照跳过；亏损 → 质量口径不适用）。
- 反推季节系数为公司上年历史节奏（无机构校准）；扫描仅覆盖 A 股正式披露（预告不触发）
- AI 无 WebSearch，快报不含前景与催化模块；免责声明固定标注「无人工复核」

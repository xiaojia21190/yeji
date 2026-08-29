# 自动业绩快报（GitHub Actions 定时扫描）

- 日期：2026-08-29
- 状态：已实现（山东黄金 600547 真实端到端验收，judge 视觉验收通过）

## 1. 目标

定时扫描 watchlist 内公司的财报披露，新披露自动生成「量化 + AI 撰写」的业绩快报，
发布到报告中心（GitHub Pages 自动更新），并开 issue 通知；深度六模块 AI 分析仍在本地跑 skill。

## 2. 架构与分工

```
cron (UTC 2/10/14 点 = 北京 10/18/22 点)
  └─ scan_and_brief.py
       ├─ scan_dev.scan()          # 财务摘要最新期 = 新披露；reports/ 目录即状态
       ├─ auto_brief_dev.build_brief()
       │    ├─ 脚本量化（可复现）：单季拆解/同比、评分卡数值规则、
       │    │   反推对照（仅披露日前研报，公告日期来自 statements）、趋势、估值、同行
       │    └─ AI 撰写（可选）：summary 文字 + 驱动维定性（deepseek-v4-flash，重试 3 轮）
       ├─ save_payload → reports/{code}_{period}.json（viewer/Pages 直接渲染）
       └─ scan_result.json → workflow 建 issue 通知
```

纪律：AI 只允许使用脚本算好的数据包数字（编造即触发 schema 校验降级）；
summary tone 与综合评级按 performance.md 合成规则可复算，AI 只写文字不定 tone；
AI 缺席（无 key）时驱动维缺省、评级标注四维量化初判，管线绝不阻塞。

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

## 5. 边界

- 反推季节系数为公司上年历史节奏（无机构校准）；扫描仅覆盖 A 股正式披露（预告不触发）
- AI 无 WebSearch，快报不含前景与催化模块；免责声明固定标注「无人工复核」

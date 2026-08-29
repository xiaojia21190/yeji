# 前景与催化模块（outlook）设计

- 日期：2026-08-29
- 状态：已实现（300308 实测 + 全量测试通过）
- 前置：完整业绩判断升级（2026-08-29，五维评分卡 + A/B/C/D 评级）

## 1. 问题

评分卡与预期对照都是「向后看」。用户要的第三类判断此前没有固化：公司的**核心优势**、
**订单前瞻**、以及业绩数字之外**影响走势的因素**（解禁减持/质押/政策/催化剂）。
只有腾讯报告里 ad hoc 写过 AI capex 一段。

## 2. 方案：第六模块「前景与催化」（outlook）

三张表 + 结论，每行必须挂量化证据或溯源出处：

1. **核心优势**：市占率/行业地位、技术产品壁垒、客户结构、供应链地位（应付账款/营收占款能力）、盈利相对优势（vs 同行表）
2. **订单与需求前瞻**：
   - 脚本：合同负债+预收（perf_math.advance_liabilities/advance_ratio）、存货备货方向、应付/预付变化
   - WebSearch：在手订单/重大合同/中标、大客户 capex、扩产投产时点
   - 行业口径：to B 长账期行业合同负债天然小（300308 仅占营收 0.05%），以在手订单/大客户 capex 为主
3. **影响走势因素**：checklist 逐项过（股权供给/筹码/资本运作/风险事件/行业景气/催化剂），
   无因素的项写「未发现」+检索词，不硬凑；方向=利好·利空·中性，只述共识逻辑不预测股价

模块 id `outlook`，顺序 scorecard → outlook → expectation。summary 增加前瞻一句。

## 3. 数据源决策

- 资产负债表新增订单前瞻字段：合同负债/预收款项/应付账款/预付款项（fetch_statements_dev 白名单，300308 实测通过）
- 股东户数 `stock_zh_a_gdhs` 需翻 876 页（约 5.5 分钟/只），全市场质押/解禁为分钟级大表——
  **不脚本化**，统一走 outlook.md 的 WebSearch 检索清单（与 skill 分工原则一致：脚本=稳定快数）
- 港股变通模式同样适用（财报原文 + WebSearch 溯源）

## 4. 改动与测试

- `finreport/fetch_statements_dev.py`：BALANCE_FIELDS +4 字段
- `finreport/perf_math.py`：+advance_liabilities/advance_ratio
- `skill_deploy/references/outlook.md`（新）+ SKILL.md 六模块流程 + metrics.md 口径表
- 测试：离线 56 通过（含 advance 4 例），网络冒烟 2 通过

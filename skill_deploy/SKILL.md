---
name: fin-report
description: A 股财报分析：业绩 vs 机构预期对照（反推算式可查）、财务趋势与质量、同行横向对比、估值水平。输入股票代码产出单文件 HTML 报告。触发词：/fin-report、财报分析、中报/年报/季报对照预期、业绩是否符合预期。
---

# 财报分析（fin-report）

输入 A 股代码，产出四模块单文件 HTML 报告。**声明：本次使用 fin-report skill。**

## 执行流程

### 0. 解析输入

- 参数：股票代码（6 位）必需；可选 `--period=YYYYMMDD`、`--modules=expectation,trend,peers,valuation`（默认全部）
- 代码有效性直接用财务摘要接口确认并取公司名（东财个股信息接口本机不可用，勿调）

### 1. 取数（脚本，稳定数据）

统一在当前工作目录建 `finreport_work/` 缓存：

```bash
python -X utf8 "C:/Users/35033/.claude/skills/fin-report/scripts/fetch_financial.py" 300308 --period 20260630 --out finreport_work/financial.json
python -X utf8 "C:/Users/35033/.claude/skills/fin-report/scripts/fetch_forecast.py" 300308 --out finreport_work/forecast.json
python -X utf8 "C:/Users/35033/.claude/skills/fin-report/scripts/fetch_market.py" 300308 --period 20260630 --out finreport_work/market.json
```

任一脚本失败：重试 1 次；仍失败则报告相应模块降级（预期对照缺 forecast → 该模块输出「无可靠预测，跳过」），绝不编数。

### 2. 补数（WebSearch，外资行与复核）

- 外资行（高盛/大摩/野村/瑞银/美银等）全年预测与目标价：搜「公司名+机构名+净利润 预测/目标价」，只收录有明确原文出处的，记录 URL
- 同行清单：WebSearch「公司名 同行业 可比上市公司」，结合研报列表行业字段定 3~6 家
- 两源冲突：并列列出，不取舍

### 3. 分析（AI，按 references/methodology.md）

- 单季拆解、季节系数、反推、达标判定：算式全部写进报告
- 逐机构对照表：机构/评级/全年预测/反推Q2/差额/判定
- 归母−扣非差额拆非经常性损益明细
- 趋势模块：近 8 期序列+单季环比+质量信号（references/metrics.md 信号表）
- 同行模块：增速/毛利率/ROE 对比表（同行数据同样用 fetch_financial.py 取）
- 估值模块：PE-TTM、PE-2026E/2027E 逐机构

### 4. 渲染（脚本）

payload 结构：meta{code,name,period_label,generated,disclaimer} + summary{text,tone,links[{id,label}]} + cards[] + sections[]{title,intro,tables[],conclusion{tone,text},notes[]}。
tone: good/bad/warn；表格 rows 与 row_tones 等长对齐。

**summary（顶部 AI 总结横幅，必填）**：3~5 句总评——四模块各一句 + 整体判断；tone 取四模块中最差与最好综合（整体偏差 bad / 喜忧参半 warn / 全面达标 good）；links 列出全部模块的 {id: section id, label: 模块简称}，点击跳转。summary 由分析阶段 AI 撰写，不写死模板。

```bash
python -X utf8 "C:/Users/35033/.claude/skills/fin-report/scripts/render_report.py" finreport_work/payload.json --out "300308_中际旭创_2026中报_财报分析_YYYYMMDD.html" --open
```

文件名：`{代码}_{公司名}_{报告期label}_财报分析_{当天YYYYMMDD}.html`，输出到当前目录。

### 5. 交付

- 报告路径 + 3~5 句核心结论（四模块各一句）
- 数据全部可溯源：机构数字标来源，反推算式在附录

## 硬性纪律

- 只列事实与数字，不构成投资建议（报告尾注固定声明）
- 无原文依据的机构预测一律剔除并注明
- 单位换算错误零容忍：脚本输出元，报告亿元，反推前先统一
- 东财 push2 系接口本机不可用，勿调 ak.stock_bid_ask_em / stock_individual_info_em / stock_board_industry_cons_em / stock_zh_a_hist

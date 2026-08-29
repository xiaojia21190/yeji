---
name: fin-report
description: A 股完整业绩判断：五维评分卡综合评级（成长/盈利/质量/健康/驱动，无机构覆盖也能判）+ 前景与催化（核心优势、订单前瞻、影响走势因素）+ 业绩 vs 机构预期对照（反推算式可查）、财务趋势与质量、同行对比、估值水平；行业画像特化（资源周期股商品价格联动等）。输入股票代码产出报告中心 HTML。触发词：/fin-report、财报分析、业绩分析、公司业绩怎么样、公司前景、中报/年报/季报对照预期、业绩是否符合预期、资源股分析。
---

# 财报分析（fin-report）

输入 A 股代码，产出六模块报告：**完整业绩判断（五维评分卡）**、**前景与催化**、业绩 vs 机构预期对照、财务趋势与质量、同行对比、估值。**声明：本次使用 fin-report skill。**

## 执行流程

### 0. 解析输入

- 参数：股票代码（6 位）必需；可选 `--period=YYYYMMDD`、`--modules=scorecard,outlook,expectation,trend,peers,valuation`（默认全部）
- 5 位港股代码（如 00700/09988）走「港股变通模式」，见下文
- **行业判定**：研报列表行业字段 + 主营构成判定行业属性；命中 `references/industries/` 画像（如资源周期：紫金矿业等金铜矿企）则加载画像——核心跟踪变量/驱动拆解/评分卡阈值/估值选型/走势因素按画像特化并在报告注明；多品种公司按主营占比取前两类并列
- 代码有效性直接用财务摘要接口确认并取公司名（东财个股信息接口本机不可用，勿调）

### 1. 取数（脚本，稳定数据）

统一在当前工作目录建 `finreport_work/` 缓存：

```bash
python -X utf8 "C:/Users/35033/.claude/skills/fin-report/scripts/fetch_financial.py" 300308 --period 20260630 --out finreport_work/financial.json
python -X utf8 "C:/Users/35033/.claude/skills/fin-report/scripts/fetch_statements.py" 300308 --out finreport_work/statements.json
python -X utf8 "C:/Users/35033/.claude/skills/fin-report/scripts/fetch_forecast.py" 300308 --out finreport_work/forecast.json
python -X utf8 "C:/Users/35033/.claude/skills/fin-report/scripts/fetch_market.py" 300308 --period 20260630 --out finreport_work/market.json
```

命中资源周期画像时加取商品价格（品种按主营商品选，AU0 沪金 / CU0 沪铜 / AG0 沪银 / SC0 原油等）：

```bash
python -X utf8 "C:/Users/35033/.claude/skills/fin-report/scripts/fetch_commodity.py" AU0 CU0 --out finreport_work/commodity.json
```

statements.json = 三大报表明细（利润表/资产负债表/现金流量表近 10 期，单位元；资产负债表含合同负债/预收/应付/预付等订单前瞻字段）+ 主营构成近两期（分部收入占比与毛利率），是评分卡与驱动拆解的数据底座。

任一脚本失败：重试 1 次；仍失败则相应模块降级——预期对照缺 forecast → 输出「无可靠预测，跳过」；评分卡缺 statements → 降级用 financial.json 摘要序列并在报告注明口径收窄。绝不编数。

### 2. 补数（WebSearch，外资行、前瞻与复核）

- 外资行（高盛/大摩/野村/瑞银/美银等）全年预测与目标价：搜「公司名+机构名+净利润 预测/目标价」，只收录有明确原文出处的，记录 URL
- 前景与催化深挖（references/outlook.md 检索清单）：在手订单/重大合同/中标、大客户 capex 计划、扩产投产、解禁/减持/回购/质押、行业政策与周期——逐项溯源记 URL，无出处的数字不写
- 同行清单：WebSearch「公司名 同行业 可比上市公司」，结合研报列表行业字段定 3~6 家
- 两源冲突：并列列出，不取舍

### 3. 分析（AI，按 references/）

- **评分卡（references/performance.md）**：成长性/盈利能力/盈利质量/财务健康/业绩驱动五维逐维判定，每维 tone 与量化依据表内可复算；综合评级 A/B/C/D 按 grade_from_tones 合成；驱动拆解必引用主营构成两期对照；一次性因素（非经常性占比、政府补助、处置收益）单列
- **前景与催化（references/outlook.md）**：核心优势逐条挂证据（市占率/客户结构/供应链占款/同行毛利率对照）；订单前瞻 = 合同负债与备货信号（脚本）+ 在手订单与大客户 capex（WebSearch）；影响走势因素 checklist 逐项过（解禁减持/质押/政策/催化剂），无因素写「未发现」不硬凑
- 单季拆解、季节系数、反推、达标判定：算式全部写进报告
- 逐机构对照表：机构/评级/全年预测/反推Q2/差额/判定
- 归母−扣非差额拆非经常性损益明细
- 趋势模块：近 8 期序列+单季环比+质量信号（references/metrics.md 信号表）；杜邦拆解用 TTM 口径（perf_math.ttm_metric）
- 同行模块：增速/毛利率/ROE 对比表（同行数据同样用 fetch_financial.py 取）
- 估值模块：PE-TTM、PE-2026E/2027E 逐机构，**必附「合理 PE 估算」小节**（按 references/metrics.md 的 PEG/利率锚/周期法选型，输出当前 PE vs 合理区间 vs 隐含市值，只说区间位置不给买卖建议）

### 4. 发布（脚本）

payload 结构：meta{code,name,period_label,generated,disclaimer} + summary{text,tone,links[{id,label}]} + cards[] + sections[]{title,intro,tables[],conclusion{tone,text},notes[]}。
tone: good/bad/warn；表格 rows 与 row_tones 等长对齐。

**summary（顶部 AI 总结横幅，必填）**：第一句必须给综合评级（如「综合评级 B：业绩良好——量价齐升但现金流承压」）；随后两面呈现：业绩本身（评分卡要点）与相对预期（达标/未达标家数），评级好但预期 miss（或反之）时两面都要说；前瞻一句（订单能见度或最大走势变量，来自 outlook 模块）。tone 按 references/performance.md 合成规则取（评级与预期对照 tone 取更差者）。links 列出全部模块的 {id: section id, label: 模块简称}。summary 由分析阶段 AI 撰写，不写死模板。

发布到本地报告中心（默认，不再生成散装 HTML）：

```bash
python -X utf8 "C:/Users/35033/.claude/skills/fin-report/scripts/render_report.py" finreport_work/payload.json
```

脚本会把 JSON 落盘到 `D:\code\yeji\reports\`、更新 index.json、自动起 8765 服务并打开 `http://localhost:8765/viewer.html`（列表点选查看，支持搜索与导出单文件 HTML）。

需要单发一份给他人时才导出静态版：

```bash
python -X utf8 "C:/Users/35033/.claude/skills/fin-report/scripts/render_report.py" finreport_work/payload.json --out "300308_中际旭创_2026中报_财报分析_YYYYMMDD.html"
```

### 5. 交付

- viewer 链接 `http://localhost:8765/viewer.html` + 报告文件名（reports/{code}_{period}.json）
- 3~5 句核心结论：第一句综合评级，之后评分卡最亮/最暗一维 + 前瞻一句（订单能见度或最大走势变量）+ 预期对照结论
- 数据全部可溯源：机构数字标来源，反推算式与评分卡依据在附录

## 港股变通模式（5 位代码）

fetch 脚本仅适用 A 股（新浪/东财 F10 源）。港股改走手工链路：

- 财务数据用公司业绩公告/年报 PDF + 雪球行情页，WebSearch 交叉核对，逐数字记录出处；分部、capex、合同负债从财报原文摘录
- 五维评分卡与前景与催化照常执行（数据来自财报原文 + WebSearch 溯源），预期对照只用 WebSearch 溯源到的机构预测
- payload meta.disclaimer 注明「港股财报分析（skill 港股变通模式）」；口径参照 00700/09988 两份既有报告

## 硬性纪律

- 只列事实与数字，不构成投资建议（报告尾注固定声明）
- 无原文依据的机构预测一律剔除并注明
- 单位换算错误零容忍：脚本输出元，报告亿元，反推前先统一；perf_math 算式层比率为小数，展示层转百分数
- 评分卡每维判定必须引用报告表内可复算的数字；行业阈值调整必须注明调整依据
- 综合评级与预期对照两面都要呈现，不允许只讲有利的一面
- 东财 push2 系接口本机不可用，勿调 ak.stock_bid_ask_em / stock_individual_info_em / stock_board_industry_cons_em / stock_zh_a_hist（东财 F10 主营构成 stock_zygc_em 非 push2 系，可用）

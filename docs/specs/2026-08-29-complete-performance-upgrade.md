# 完整业绩判断升级（五维评分卡）设计

- 日期：2026-08-29
- 状态：已实现（300308 实测取数 + 全量测试通过）
- 前置：fin-report skill v1（2026-08-22，四模块：预期对照/趋势/同行/估值）

## 1. 问题

v1 的判断核心是「业绩 vs 机构预期」，这带来两个盲区：

1. **无机构覆盖的公司没有业绩判断**——预期对照模块降级跳过后，报告剩下的模块都只是罗列
2. **预期 ≠ 业绩本身**——超预期可能是降幅收窄，miss 可能只是预期打得太满；「公司完整业绩怎么样」缺一个不依赖机构预测的独立判断

## 2. 方案：五维评分卡 + 综合评级

新增第一模块「完整业绩判断」，对业绩本身做独立判定，与预期对照互相独立：

| 维度 | 核心指标 | 数据底座 |
|---|---|---|
| 成长性 growth | 营收/归母单季同比、增速剪刀差、扣非口径增速 | financial.json 摘要序列 |
| 盈利能力 profitability | 毛利率 vs 近 8 期中位数、ROE-TTM、四费费率 | statements.json 利润表 |
| 盈利质量 quality | 净现比、非经常性占比、应收/存货预警 | statements.json 现金流量表 + 摘要 |
| 财务健康 health | 资产负债率、有息负债/货币资金、商誉占比 | statements.json 资产负债表 |
| 业绩驱动 drivers | 主营构成两期对照、驱动归类、capex 强度 | statements.json segments |

综合评级：good=+1/warn=0/bad=−1 五维求和 → A(≥3)/B(1~2)/C(−2~0)/D(≤−3)，
覆盖规则「成长性与质量同 bad 至多 C」。规则全部量化写在 `references/performance.md`，
可复算部分落在 `finreport/perf_math.py`（grade_from_tones 等），AI 只做定性维与行业阈值调整（须注明）。

预期对照模块原样保留。summary 第一句给综合评级，两面呈现（业绩本身 + 相对预期）。

## 3. 实现

```
finreport/
├── perf_math.py             # 新：增速/TTM/净现比/FCF/费用率/有息负债/评级合成（纯函数）
└── fetch_statements_dev.py  # 新：新浪三大报表白名单多期 + 东财 F10 主营构成近两期
skill_deploy/
├── SKILL.md                 # 五模块流程、summary 评级规范、港股变通模式小节
├── scripts/fetch_statements.py  # 薄 CLI 包装（同 fetch_financial 模式）
└── references/
    ├── performance.md       # 新：评分卡判定规则与合成规范
    ├── metrics.md           # 增三大报表明细字段口径表
    └── report-template.html # crumb/chips 更新（同步自安装版暗色模板）
```

- 数据源实测：新浪三大报表全字段可用；`stock_zygc_em`（东财 F10）非 push2 系，本机可用
- 主营构成保留分部间抵销/其他行（负收入），过滤交给分析层
- 港股：fetch 链不支持，本次把此前的变通做法正式写进 SKILL.md（财报 PDF/雪球 + WebSearch 溯源）
- 模板：评分卡复用现有 section/table/row_tones 渲染，无结构改动

## 4. 测试

- `tests/test_perf_math.py`（17 例，离线）：300308 真实披露值锚点，含评级合成的覆盖规则
- `tests/test_fetch_statements.py`：字段映射/降级/期数离线 4 例 + 300308 网络冒烟 2 例
- 全量 `pytest -m "not net"` 通过；`-m net` 冒烟通过

## 5. 边界与后续

- 评分卡阈值默认面向成长/制造类，稳态类靠 AI 按规则下调并注明——不做行业自动分类
- 金融/地产的负债率、金融业缺行处理依赖规则中的行业调整条款，非硬编码
- TTM 口径需要上年年报与上年同期累计，次新股（上市不足一年）ROE-TTM 缺失时该子项不计入

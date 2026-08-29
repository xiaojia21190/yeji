# yeji — 财报分析工作区

fin-report skill 的开发、测试与报告产出。

## 用法

任意目录对 Claude Code 说：`/fin-report 300308`（或「分析 300308 财报」「公司业绩怎么样」）。

skill 安装位置：`C:\Users\35033\.claude\skills\fin-report\`（镜像入库于 `skill_deploy/`）。

在线报告中心（GitHub Pages）：https://xiaojia21190.github.io/yeji/

## 能力

六模块报告，判断「公司完整业绩」而不只是「是否超预期」：

1. **完整业绩判断（五维评分卡）**：成长性 / 盈利能力 / 盈利质量 / 财务健康 / 业绩驱动逐维判定，综合评级 A/B/C/D——无机构覆盖也能出判断
2. **前景与催化**：核心优势逐条挂证据（市占率/客户结构/供应链占款）、订单与需求前瞻（合同负债备货信号 + 在手订单溯源）、影响走势因素 checklist（解禁减持/质押/政策/催化剂）；行业画像特化——资源周期股（紫金矿业等）自动加载金铜等商品价格联动、量价拆解、周期位置与 PE 失效估值
3. **业绩 vs 机构预期对照**：反推算式可查，逐机构达标判定（与评分卡互相独立，两面呈现）
4. **财务趋势与质量**：近 8 期序列 + 现金流/应收/存货质量信号 + 杜邦
5. **同行横向对比**
6. **估值水平**：PE 逐机构 + 合理 PE 估算

港股（5 位代码）走变通模式：财报 PDF/雪球 + WebSearch 溯源，评分卡照常。

## 结构

- `finreport/` 取数与分析纯函数库（skill 脚本依赖）
  - `fetch_dev.py` 财务摘要多期 / `fetch_statements_dev.py` 三大报表明细+主营构成 / `fetch_forecast_dev.py` 研报预测 / `fetch_market_dev.py` 行情股本 / `fetch_commodity_dev.py` 商品期货主力（金价铜价等）
  - `quarter_math.py` 单季拆解反推 / `perf_math.py` 评分卡算式与评级合成
- `skill_deploy/` skill 镜像（SKILL.md + scripts + references；`references/industries/` 行业画像插件，改完 cp 到安装位置）
- `tests/` pytest（`-m "not net"` 可离线跑纯函数与渲染）
- `reports/`、`finreport_work/` 产物目录
- `docs/` 设计文档与实现计划

## 已知约束

- 东财 push2 系接口本机代理下不可用（skill 已绕开，走新浪系；东财 F10 主营构成 `stock_zygc_em` 非 push2，可用）
- 申万成分明细接口有 bug，同行清单走 WebSearch 定夺
- 外资行预测仅收录可溯源新闻稿（高盛/大摩/野村 7 月预测已验证可溯源）
- 季节系数默认用公司上年历史节奏（如 300308 净利 37.0%），与参考报告的交银校准系数（39.2%）有口径差异，报告中并列注明
- 评分卡阈值默认面向成长/制造类，稳态类由 AI 按规则下调并注明；金融/地产行业负债率口径靠行业调整条款
- 股东户数（876 页翻页）/全市场质押/解禁等接口单次调用分钟级，过慢不脚本化，走势因素统一走 WebSearch 检索清单（references/outlook.md）

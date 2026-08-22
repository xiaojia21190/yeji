# yeji — 财报分析工作区

fin-report skill 的开发、测试与报告产出。

## 用法

任意目录对 Claude Code 说：`/fin-report 300308`（或「分析 300308 财报」）。

skill 安装位置：`C:\Users\35033\.claude\skills\fin-report\`（镜像入库于 `skill_deploy/`）。

## 结构

- `finreport/` 取数与分析纯函数库（skill 脚本依赖）
- `tests/` pytest（`-m "not net"` 可离线跑纯函数与渲染）
- `reports/`、`finreport_work/` 产物目录
- `docs/` 设计文档与实现计划
- `300308_*.html` 首份验收报告（2026-08-22，对照参考报告数字一致）

## 已知约束

- 东财 push2 系接口本机代理下不可用（skill 已绕开，走新浪系）
- 申万成分明细接口有 bug，同行清单走 WebSearch 定夺
- 外资行预测仅收录可溯源新闻稿（高盛/大摩/野村 7 月预测已验证可溯源）
- 季节系数默认用公司上年历史节奏（如 300308 净利 37.0%），与参考报告的交银校准系数（39.2%）有口径差异，报告中并列注明

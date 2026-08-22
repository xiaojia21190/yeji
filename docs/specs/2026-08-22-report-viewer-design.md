# 本地报告中心（viewer）设计文档

- 日期：2026-08-22
- 状态：待审阅
- 前置：fin-report skill 已交付（见 `2026-08-22-fin-report-skill-design.md`）
- 工作区：`D:\code\yeji`

## 1. 目标与边界

### 目标

把「每分析一家公司生成一个独立 HTML」改为「一个固定 viewer.html 报告中心」：

- 所有报告以 payload JSON 存于 `reports/`，viewer 左侧列表点选切换查看
- 新分析自动追加进清单，不再产生新 HTML 文件
- 列表带 tone 色点、搜索过滤，暗色主题沿用

### 边界（首版不做）

- 两家公司同屏对比（数据结构已可支撑，UI 后续加）
- 远程访问/鉴权（纯本地）
- 自动定时分析（仍由 Claude Code 会话触发）

## 2. 架构

```
D:\code\yeji\
├── viewer.html                 ← 报告中心（唯一入口）
├── reports\
│   ├── index.json              ← [{code, name, period_label, file, generated, tone}]
│   ├── 300308_2026中报.json    ← 现有 payload 结构原样
│   └── 002714_2026中报.json
└── finreport\
    ├── render_dev.py           ← 新增 save_payload()（JSON 落盘 + 更新 index）
    └── update_index.py         ← 清单维护纯函数
```

**数据流**：分析完成 → `save_payload()` 写 `reports/{code}_{period}.json` → `update_index()` 更新 `index.json` → viewer fetch 渲染。

**HTTP 服务**：`file://` 下 fetch 本地 JSON 被 CORS 拦截，viewer 需经 `python -m http.server 8765`（reports 上级目录）访问。skill 流程在渲染步骤自动检测 8765 端口并起服务（后台 nohup），SKILL.md 写死启动方式；直接双击打开时 viewer 顶部显示黄条提示启动命令。

## 3. 组件职责

| 组件 | 职责 | 依赖 |
|---|---|---|
| `viewer.html` | 清单加载/搜索过滤/报告渲染/导出单文件 HTML | reports/*.json |
| `finreport/update_index.py` | `add_entry(index, payload, filename) -> index`：新增/去重（同 code+period 覆盖）/按日期倒序 | 无（纯函数） |
| `finreport/render_dev.py` | 新增 `save_payload(payload, reports_dir)`：写 JSON + 调 update_index | update_index |
| skill `render_report.py` | 改为调 `save_payload`；保留 `--out xxx.html` 老路径导出静态版 | render_dev |

## 4. viewer 交互

- 左侧列表：公司名 + 代码徽章 + 报告期 + tone 色点（绿/黄/粉）+ 生成日期；按生成日期倒序
- 顶部搜索框：按代码/公司名/报告期过滤（前端 filter）
- 右侧报告区：现有暗色模板的完整复刻（CSS 原样搬运），summary 横幅 + 卡片 + sections + 锚点导航
- 「导出单文件 HTML」按钮：把当前渲染结果 `document.documentElement.outerHTML` 触发下载（发给别人的场景）
- 空状态：无 index.json 或清单空 → 引导语「运行 /fin-report 生成第一份报告」

## 5. 错误处理

- index.json 缺失 → 空状态引导
- fetch 报错（file:// 直开）→ 顶部黄条：「请用 `python -m http.server 8765` 启动后访问 http://localhost:8765/viewer.html」
- 单个报告 JSON 解析失败 → 列表项标红 + 点击提示损坏，不影响其他报告

## 6. 测试

- `update_index.py`：pytest 纯函数测试（新增、同 code+period 覆盖去重、倒序排序）
- `save_payload()`：tmp 目录写入 + index 更新断言
- viewer 渲染冒烟：Python `http.server` 起服务 + requests 抓 viewer 页面与 JSON，断言关键内容存在；JS 渲染函数不单测（无 Node 环境，靠冒烟 + 人眼验收）

## 7. 实施步骤概览（供 writing-plans 展开）

1. `update_index.py` 纯函数 + 测试
2. `save_payload()` 改造 + 测试；迁移现有两份 payload JSON 到 `reports/`
3. `viewer.html`（列表/搜索/渲染/导出/错误态）+ http.server 冒烟
4. skill `render_report.py` 切换到 save_payload + SKILL.md 更新（服务启动、报告中心入口）+ 镜像同步

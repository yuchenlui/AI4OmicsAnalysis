# Harness 架构图绘制提示词（README 用）

> 把本提示词交给任意绘图 agent（或人）即可复现/改编架构图。
> 参考实现：`ai4omics/make_architecture_svg.py`（改 NODES/STAGES 即可再生成）。
> 当前成品：`docs/harness_architecture.svg`，可直接被 GitHub README 的 `![]()` 引用。

## 目标

一张横向宽幅架构图（1440×830，白底），展示 ai4omics harness 的三层结构：
研究问题 → Supervisor 监督 → 六个专职 agent → 九阶段流水线 → 交付物，
外加「失败恢复策略」与「可审计与可证伪」两个说明块。

## 全局规范

- 画布 1440×830，背景 `#FFFFFF`，安全边距 40px。
- 字体 `Arial, Helvetica, sans-serif`（GitHub <img> 渲染 SVG 时外部字体不可用，只能用系统安全字体）。
- 文字色：主 `#111827`，次 `#6B7280`，说明块正文 `#374151`。
- 线与箭头 `#9CA3AF` / `#D1D5DB`，1.5px，开放箭头（V 形，非实心三角）。
- 方框：圆角 rx=10-14，浅色填充 + 深色描边 1.5px，内部不使用渐变/阴影。
- 中文正文 13-15px，标题 17-22px，页面主标题 30px（weight 600）。
- 禁止：emoji、渐变、阴影、旋转文字、11px 以下字号。

## 颜色令牌（按 agent 角色固定）

| 角色 | 填充 | 描边/标题 |
|---|---|---|
| Supervisor | `#FCEBEB` | `#A32D2D` |
| Omics Agent | `#E6F1FB` | `#185FA5` |
| Database Query | `#E1F5EE` | `#0F6E56` |
| Novelty Agent | `#EAF3DE` | `#3B6D11` |
| Plot Agent | `#FAEEDA` | `#854F0B` |
| Control Agent | `#EEEDFE` | `#534AB7` |
| 中性框 | `#F3F4F6` / `#F9FAFB` | `#D1D5DB` |

## 布局（自上而下五层）

### L1 标题（y≈40-100）
- 主标题：`YAP1 耐药候选筛选 · Agent Harness`（30px, 600）
- 副标题：`确定性流水线 + 监督门控 + 可选 LLM 判读 ｜ harness/run.py · pipeline.yaml · agents.py · supervisor.py`（16px, 次色）

### L2 主干（y≈128-234）
三个框横排，箭头 `→` 连接：
1. **研究问题**（中性框 210×82）：两行「研究问题 / 耐药候选基因」
2. **Supervisor（监督）**（620×106，角色色）：三行——
   `按 pipeline.yaml 调度 · 每阶段 QC 门控 · 失败分类重试 · 状态清单落盘`
   `harness/state.json 记录输入/脚本/产物哈希，未变则跳过`
3. **交付物**（中性框 420×82）：`候选基因表 · 创新性评分 · 复合图 · 报告`

### L3 agent 行（y≈292-396，六框等宽 220，间距 12）
每框：英文名（16px 600）→ 中文职责（13px）→ 2 行细节（12px）：

| 框 | 细节行 |
|---|---|
| Supervisor 监督与调度 | 阶段调度 · QC 门控 ／ 失败分类重试 · 状态清单 |
| Omics Agent 组学数据 | GEO/PRIDE 下载 ／ DEG · IP-MS · ChIP |
| Database Query 数据库检索 | GEO 数据集检索 ／ 数据集 → PMID |
| Novelty Agent 创新性评分 | PubMed 文献计数 ／ 新颖性 / 功能相关性 |
| Plot Agent 出图 | 按绘图提示词 ／ 花瓣图 · 四象限 · 峰图 |
| Control Agent 负对照 | 置换检验 ／ 多体系一致上调经验 p |

连线：Supervisor 底部中点垂直下行 28px → 水平贯穿线 → 六条垂直箭头分别落到各框顶。

### L4 流水线（y≈440-520）
小节标题：`流水线（pipeline.yaml）`+ 说明 `9 阶段 · 每阶段校验：产物存在 → 契约列名 → 行数区间 → 哈希落盘`。
九个 136×62 小框横排（间距 12），箭头串联，每框两行（中文 15px 600 / 英文 id 11px）：
检索 geo_search ｜ 下载 download ｜ 互作 ipms ｜ DEG deg ｜ ChIP chip ｜ 整合 integrate ｜ 负对照 negctrl ｜ 评分 novelty ｜ 出图 plots
（ipms/deg/chip 三框用 `#EFF6FF` 淡蓝底示意为计算密集阶段）

### L5 说明块（y≈556-732，两框各 660×176）
- **失败恢复：按类别处理，不用「重试 3 次」一刀切**（四行表格式）：
  `transient 网络限流SSL → 退避 2→8→20s 重试 3 次`
  `schema 缺文件缺列编码 → 重试 1 次后换解析或换数据源`
  `logic QC不达标断言失败 → 不重试，记录并中止等人工`
  `budget 超时超预算 → 不重试，调阈值或缩小规模`
- **可审计与可证伪**（四行圆点）：
  `state.json：输入/脚本/产物三方哈希，重跑可判定`
  `契约校验：产物缺列即失败，避免静默错数据`
  `负对照：置换 5000 次 + 多体系一致上调经验 p`
  `critic（规划中）：逐条质询证据同源性`

### 页脚（y≈770-800）
`运行：python -m ai4omics run ｜ --status 查看状态 ｜ --from integrate 续跑 ｜ --only novelty ｜ --force 忽略哈希`
`LLM 可选：设 LLM_BASE_URL / LLM_API_KEY 启用语义判读；未配置则全程规则模式，结果可复现。`

## 输出

- `docs/harness_architecture.svg`（README 直接 `![architecture](docs/harness_architecture.svg)` 引用）
- 可选 2x PNG（`--window-size=1440,830` 无头浏览器截图即可）
- 深色变体（可选）：背景 `#0D1117`、主文字 `#E6EDF3`、各角色填充用上表描边色、描边用填充色

## 验收清单

- [ ] 六个 agent 框全部在画布内、等宽等距、无文字溢出
- [ ] Supervisor 分发线到六个 agent 的箭头垂直对齐
- [ ] 流水线九框串联箭头连续无断
- [ ] 颜色严格按令牌表；无渐变/阴影/emoji
- [ ] SVG 无外部依赖（内联全部样式），GitHub 渲染正常

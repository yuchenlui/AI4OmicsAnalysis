# -*- coding: utf-8 -*-
"""make_architecture_svg.py — 生成 README 用的 harness 架构图（自包含 SVG）。

输出 docs/harness_architecture.svg：不依赖外部 CSS/字体变量，GitHub README 直接 <img> 可用。
改结构只需改下面的 NODES / STAGES 列表。
"""
import os

W, H = 1440, 830
INK, MUTED, LINE, SOFT = "#111827", "#6B7280", "#D1D5DB", "#F3F4F6"

AGENTS = [
    ("Supervisor", "监督与调度", ["阶段调度 · QC 门控", "失败分类重试 · 状态清单"], "#FCEBEB", "#A32D2D"),
    ("Omics Agent", "组学数据", ["GEO/PRIDE 下载", "DEG · IP-MS · ChIP"], "#E6F1FB", "#185FA5"),
    ("Database Query", "数据库检索", ["GEO 数据集检索", "数据集 → PMID"], "#E1F5EE", "#0F6E56"),
    ("Novelty Agent", "创新性评分", ["PubMed 文献计数", "新颖性 / 功能相关性"], "#EAF3DE", "#3B6D11"),
    ("Plot Agent", "出图", ["按绘图提示词", "花瓣图 · 四象限 · 峰图"], "#FAEEDA", "#854F0B"),
    ("Control Agent", "负对照", ["置换检验", "多体系一致上调经验 p"], "#EEEDFE", "#534AB7"),
]

STAGES = [
    ("检索", "geo_search"), ("下载", "download"), ("互作", "ipms"),
    ("DEG", "deg"), ("ChIP", "chip"), ("整合", "integrate"),
    ("负对照", "negctrl"), ("评分", "novelty"), ("出图", "plots"),
]


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def box(x, y, w, h, fill, stroke, rx=12, dash=None):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="1.5"{d}/>')


def text(x, y, s, size=15, color=INK, weight=400, anchor="start"):
    return (f'<text x="{x}" y="{y}" font-family="Arial, Helvetica, sans-serif" font-size="{size}" '
            f'fill="{color}" font-weight="{weight}" text-anchor="{anchor}">{esc(s)}</text>')


def arrow(x1, y1, x2, y2, color=LINE):
    return (f'<path d="M{x1} {y1} L{x2} {y2}" fill="none" stroke="{color}" stroke-width="1.5" '
            f'marker-end="url(#a)"/>')


def build():
    p = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="100%" '
         f'role="img" aria-label="YAP1 resistance screening agent harness architecture">',
         '<defs><marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
         'orient="auto-start-reverse"><path d="M1 1 L9 5 L1 9" fill="none" stroke="#9CA3AF" '
         'stroke-width="1.6" stroke-linecap="round"/></marker></defs>',
         f'<rect width="{W}" height="{H}" fill="#FFFFFF"/>']

    # 标题
    p += [text(40, 62, "YAP1 耐药候选筛选 · Agent Harness", 30, INK, 600),
          text(40, 94, "确定性流水线 + 监督门控 + 可选 LLM 判读 ｜ harness/run.py · pipeline.yaml · agents.py · supervisor.py", 16, MUTED)]

    # 入口 → Supervisor → 交付
    p += [box(40, 140, 200, 82, SOFT, LINE), text(140, 172, "研究问题", 17, INK, 600, "middle"),
          text(140, 196, "耐药候选基因", 14, MUTED, 400, "middle"),
          arrow(240, 181, 300, 181)]

    p += [box(300, 128, 620, 106, "#FCEBEB", "#A32D2D", 14),
          text(610, 164, "Supervisor（监督）", 22, "#7F1D1D", 600, "middle"),
          text(610, 192, "按 pipeline.yaml 调度 · 每阶段 QC 门控 · 失败分类重试 · 状态清单落盘", 15, "#7F1D1D", 400, "middle"),
          text(610, 216, "harness/state.json 记录输入/脚本/产物哈希，未变则跳过", 13, "#9B4A4A", 400, "middle")]
    p += [arrow(920, 181, 980, 181)]

    p += [box(980, 140, 420, 82, SOFT, LINE), text(1190, 172, "交付物", 17, INK, 600, "middle"),
          text(1190, 196, "候选基因表 · 创新性评分 · 复合图 · 报告", 14, MUTED, 400, "middle")]

    # 分发线（6 个 agent：w=220, gap=12, 起点 x=30）
    AW, AGAP, AX0 = 220, 12, 30
    cx = [AX0 + i * (AW + AGAP) + AW // 2 for i in range(6)]
    p += ['<path d="M610 234 L610 262" fill="none" stroke="#9CA3AF" stroke-width="1.5"/>',
          f'<path d="M{cx[0]} 262 L{cx[-1]} 262" fill="none" stroke="#9CA3AF" stroke-width="1.5"/>']
    for x in cx:
        p += [arrow(x, 262, x, 292)]

    # agents
    y = 292
    for i, (name, role, lines, fill, stroke) in enumerate(AGENTS):
        x = AX0 + i * (AW + AGAP)
        p += [box(x, y, AW, 104, fill, stroke),
              text(x + 14, y + 30, name, 16, stroke, 600),
              text(x + 14, y + 52, role, 13, stroke)]
        for j, ln in enumerate(lines):
            p += [text(x + 14, y + 74 + j * 18, ln, 12, "#374151")]

    # 流水线
    p += [text(40, 442, "流水线（pipeline.yaml）", 17, INK, 600),
          text(280, 442, "9 阶段 · 每阶段校验：产物存在 → 契约列名 → 行数区间 → 哈希落盘", 13, MUTED)]
    sy, sw, gap = 458, 136, 12
    for i, (cn, sid) in enumerate(STAGES):
        x = 40 + i * (sw + gap)
        fill = "#F9FAFB" if i not in (2, 3, 4) else "#EFF6FF"
        p += [box(x, sy, sw, 62, fill, LINE, 10),
              text(x + sw / 2, sy + 26, cn, 15, INK, 600, "middle"),
              text(x + sw / 2, sy + 46, sid, 11, MUTED, 400, "middle")]
        if i < len(STAGES) - 1:
            p += [arrow(x + sw + 1, sy + 31, x + sw + gap - 1, sy + 31, "#9CA3AF")]

    # 两个说明块
    by = 556
    p += [box(40, by, 660, 176, "#FFFFFF", LINE),
          text(60, by + 30, "失败恢复：按类别处理，不用「重试 3 次」一刀切", 16, INK, 600)]
    rows = [("transient", "网络/限流/SSL", "退避 2→8→20s 重试 3 次"),
            ("schema", "缺文件/缺列/编码", "重试 1 次，仍失败则换解析或换数据源"),
            ("logic", "QC 不达标/断言失败", "不重试，记录并中止等人工判断"),
            ("budget", "超时/超预算", "不重试，调阈值或缩小数据规模")]
    for i, (k, why, act) in enumerate(rows):
        yy = by + 58 + i * 28
        p += [text(60, yy, k, 13, "#7F1D1D", 600), text(150, yy, why, 13, MUTED),
              text(330, yy, act, 13, "#374151")]

    p += [box(740, by, 660, 176, "#FFFFFF", LINE),
          text(760, by + 30, "可审计与可证伪", 16, INK, 600)]
    rows2 = ["state.json：输入/脚本/产物三方哈希，重跑可判定" ,
             "契约校验：产物缺列即失败，避免静默错数据",
             "负对照：置换 5000 次 + 多体系一致上调经验 p",
             "critic（规划中）：逐条质询证据同源性"]
    for i, ln in enumerate(rows2):
        p += [text(760, by + 60 + i * 28, "· " + ln, 13, "#374151")]

    # 脚注
    p += [text(40, 774, "运行：python run.py ｜ --status 查看状态 ｜ --from integrate 续跑 ｜ --only novelty,negctrl ｜ --force 忽略哈希",
               13, MUTED),
          text(40, 800, "LLM 可选：设 LLM_BASE_URL / LLM_API_KEY 启用语义判读；未配置则全程规则模式，结果可复现。", 13, MUTED),
          '</svg>']
    return "\n".join(p)


if __name__ == "__main__":
    out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "docs", "harness_architecture.svg")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, "w", encoding="utf-8").write(build())
    print("written:", out)

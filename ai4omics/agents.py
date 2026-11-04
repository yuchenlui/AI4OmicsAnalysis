# -*- coding: utf-8 -*-
"""agents — 各角色 agent。每个 agent = 角色职责 + 工具集 + 可选 LLM 后端。

所有 agent 都能通过 pipeline.yaml 的 tools 字段执行脚本（本地或 SSH）；
NoveltyAgent / DatabaseQueryAgent 另有内置的在线查询能力。
"""
import json
import os
import time
import urllib.parse
import urllib.request

from .runner import make_runner, SSHRunner


def eutils_get(url, timeout=30):
    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    return json.loads(op.open(url, timeout=timeout).read())


class BaseAgent:
    name = "base"
    role = ""

    def __init__(self, supervisor):
        self.sup = supervisor
        self.runner = make_runner(supervisor.cfg)

    def log(self, msg):
        self.sup.log(f"[{self.name}] {msg}")

    def run_tool(self, script, timeout=3600):
        """执行工具：script 可为 str 或 [script, *args]（相对项目根），本地/远程由 execution 决定。"""
        args = script if isinstance(script, (list, tuple)) else [script]
        self.log(f"运行工具 {' '.join(args)}" + ("（远程）" if isinstance(self.runner, SSHRunner) else ""))
        py = self.sup.cfg.get("python", "python3")
        ok, tail = self.runner.run([py] + args, cwd=self.sup.cfg["base"],
                                   env=self.sup.env, timeout=timeout)
        if not ok:
            self.log(f"工具失败 {args[0]}:\n{tail}")
        return ok, tail


class OmicsAgent(BaseAgent):
    """组学数据 agent：下载 / DEG / IP-MS / ChIP / 整合等重计算工具。"""
    name = "omics"
    role = "组学数据处理：数据获取、差异分析、质谱互作、ChIP-seq、多组学整合"


class PlotAgent(BaseAgent):
    """绘图 agent：执行绘图脚本（规格见 docs/architecture-prompt.md 与绘图提示词）。"""
    name = "plotting"
    role = "按绘图提示词规格生成发表级复合图"


class DatabaseQueryAgent(BaseAgent):
    """数据库查询 agent：GEO 检索、数据集→PMID 解析。"""
    name = "dbquery"
    role = "外部数据库查询：GEO 检索、文献关联、ID 映射"
    EUT = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

    def gse_to_pmids(self, gse):
        d = eutils_get(f"{self.EUT}/esearch.fcgi?db=gds&term={gse}%5BACCN%5D&retmode=json")
        ids = d["esearchresult"]["idlist"]
        if not ids:
            return []
        time.sleep(0.4)
        s = eutils_get(f"{self.EUT}/esummary.fcgi?db=gds&id={ids[0]}&retmode=json")
        return s["result"][ids[0]].get("pubmedids", [])

    def search_datasets(self, term, retmax=30):
        q = urllib.parse.quote(term)
        d = eutils_get(f"{self.EUT}/esearch.fcgi?db=gds&term={q}&retmax={retmax}&retmode=json")
        return d["esearchresult"]["idlist"]


class NoveltyAgent(BaseAgent):
    """新颖性 agent：候选基因的文献新颖性 + 功能相关性评分。

    规则模式：gene+X 的 PubMed 计数组合；LLM 模式可叠加摘要语义判读。
    params（pipeline.yaml stage.params）：
      genes_from: 候选基因所在 CSV（默认第一列或 gene_column 指定列）
      out: 输出 CSV
      queries: {字段名: 查询模板}，模板中 {gene} 会被替换
    """
    name = "novelty"
    role = "候选创新性与功能相关性评估（PubMed 检索 + 语义判读）"
    EUT = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    DEFAULT_QUERIES = {
        "n_gene_YAP1": "{gene} AND YAP1",
        "n_resistance_breast": "{gene} AND (drug resistance OR chemoresistance) AND breast",
        "n_Hippo_TEAD": "{gene} AND (Hippo OR TEAD)",
    }

    def pubmed_count(self, query):
        q = urllib.parse.quote(query)
        d = eutils_get(f"{self.EUT}/esearch.fcgi?db=pubmed&term={q}&retmode=json")
        return int(d["esearchresult"]["count"])

    def score_gene(self, gene, queries):
        n = {k: self.pubmed_count(q.format(gene=gene)) for k, q in queries.items()}
        total_lit = sum(n.values())
        n_res = n.get("n_resistance_breast", 0)
        novelty = 1.0 if total_lit == 0 else max(0.0, 1 - total_lit / 30)
        relevance = min(1.0, 0.25 * (n_res > 0) + 0.5 * min(n_res, 10) / 10 +
                        0.25 * (total_lit > n_res))
        return {**{"gene": gene}, **n,
                "novelty": round(novelty, 3), "relevance": round(relevance, 3),
                "score": round(0.45 * novelty + 0.55 * relevance, 3)}

    def run(self, genes_from="results/priority_candidates.csv", gene_column=None,
            out="results/novelty_scores.csv", queries=None, sleep=0.5):
        import pandas as pd
        base = self.sup.cfg["base"]
        df = pd.read_csv(os.path.join(base, genes_from), encoding="utf-8-sig")
        col = gene_column or ("gene" if "gene" in df.columns else df.columns[0])
        genes = df[col].dropna().astype(str).unique().tolist()
        qs = queries or self.DEFAULT_QUERIES
        rows = []
        for g in genes:
            try:
                rows.append(self.score_gene(g, qs))
            except Exception as e:
                self.log(f"{g} 评分失败: {e}")
                rows.append({"gene": g})
            time.sleep(sleep)
        outdf = pd.DataFrame(rows).sort_values("score", ascending=False)
        outdf.to_csv(os.path.join(base, out), index=False, encoding="utf-8-sig")
        self.log(f"新颖性评分已写入 {out}（{len(outdf)} 基因）")
        return outdf


AGENTS = {a.name: a for a in (OmicsAgent, PlotAgent, DatabaseQueryAgent, NoveltyAgent)}

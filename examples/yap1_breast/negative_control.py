# -*- coding: utf-8 -*-
"""negative_control.py — 筛选结果的负对照与置换检验（示例随 YAP1 项目）。

回答审稿人必问的两个问题：
1. 观察到的命中数，打乱标签后还能剩多少？（置换检验）
2. "多体系一致上调"这种模式，随机基因出现频率多少？（经验 p 值）

判据与 examples/yap1_breast 的 scripts/34 保持一致；换项目时改 load_systems()。
"""
import argparse
import json
import os
import re
import numpy as np
import pandas as pd

CAND = ["ZNF462", "PLEKHA7", "ATXN2", "TEAD1", "AMOTL2", "PTPN14", "FHL2"]
LFC, P = 0.585, 0.05
BASE = None  # 由 --base 注入


def _r(*p):
    return os.path.join(BASE, "results", *p)


def _simple(path, fc="log2FC", pv="padj"):
    d = pd.read_csv(path)
    d = d[[c for c in (d.columns[0], fc, pv) if c in d.columns]]
    d.columns = ["gene", "log2FC", "p"]
    return d.dropna().sort_values("p").drop_duplicates("gene").set_index("gene")


def _grouped(path):
    """每 4 列一组（比较名, log2FC, PValue, FDR）的作者差异表。"""
    d = pd.read_csv(path)
    metric = re.compile(r"^(log2FC|PValue|FDR)(\.\d+)?$")
    groups, cur = {}, None
    for c in d.columns:
        if metric.match(c):
            if cur:
                groups[cur][metric.match(c).group(1)] = c
        else:
            cur = c.strip()
            groups[cur] = {}
    out = {}
    for name, m in groups.items():
        if "log2FC" in m and "PValue" in m:
            x = d[[d.columns[0], m["log2FC"], m["PValue"]]].copy()
            x.columns = ["gene", "log2FC", "p"]
            x = x.dropna().sort_values("p").drop_duplicates("gene")
            out[name] = x.set_index("gene")
    return out


def load_systems():
    """按项目改这里：返回 {体系名: DataFrame(gene, log2FC, p)}。"""
    sysd = {
        "Dox (GSE288840)": _simple(_r("GSE288840_DEG_doxorubicin.csv")),
        "Pac (GSE288840)": _simple(_r("GSE288840_DEG_paclitaxel.csv")),
        "PARPi (GSE297522)": _simple(_r("GSE297522_DEG_olaparib.csv")),
    }
    g = _grouped(os.path.join(BASE, "data/geo/GSE165914",
                              "GSE165914_M468P_OR_Diff_Expression_mshekhar.csv.gz"))
    for key, name in (("M468OR15Ola/Ctrl", "OlaR (GSE165914)"),
                      ("M468P2.5Cis/Ctrl", "Cis (GSE165914)")):
        if key in g:
            sysd[name] = g[key]
    return sysd


def run(b=5000, seed=42, out="results/negative_control.json"):
    rng = np.random.default_rng(seed)
    ip = pd.read_csv(_r("ipms_volcano_sorted.csv"))
    ip["log2FC"] = pd.to_numeric(ip.log2FC, errors="coerce")
    ip["padj"] = pd.to_numeric(ip.padj, errors="coerce")
    ip["is_ip"] = (ip.padj < P) & (ip.log2FC > 2)
    truthy = lambda v: str(v).strip().lower() == "true"
    ip["is_chip_up"] = ip.YAP1_ChIP_bound_and_resUP.apply(truthy)
    ip = ip.sort_values("log2FC", ascending=False).drop_duplicates("gene").set_index("gene")

    ups = pd.DataFrame({k: ((v.log2FC > LFC) & (v.p < P)).reindex(ip.index)
                        for k, v in load_systems().items()}).fillna(False).astype(bool)

    is_ip, chip_up = ip.is_ip.values, ip.is_chip_up.values
    obs = int((is_ip & chip_up).sum())
    null = np.array([int((rng.permutation(is_ip) & chip_up).sum()) for _ in range(b)])
    perm_p = (1 + int((null >= obs).sum())) / (1 + b)

    n_sys = ups.sum(axis=1)
    rows = []
    for g in CAND:
        if g not in n_sys.index:
            continue
        k = int(n_sys[g])
        p_emp = float((n_sys >= k).mean())
        rows.append({"gene": g, "n_systems_up": k, "n_systems_total": int(ups.shape[1]),
                     "empirical_p": round(p_emp, 5),
                     "expect_random_genes_at_least_k": round(p_emp * len(n_sys), 1),
                     "ip_percentile": round(float(ip.log2FC.rank(pct=True)[g]), 3)})

    res = {"n_background": int(len(ip)),
           "triple": {"observed": obs, "ip_enriched": int(is_ip.sum()),
                      "chip_and_resup": int(chip_up.sum()),
                      "expected_if_random": round(is_ip.mean() * chip_up.sum(), 2),
                      "null_p95": float(np.percentile(null, 95)),
                      "permutations": b, "perm_p": round(perm_p, 5)},
           "cross_system": sorted(rows, key=lambda r: -r["n_systems_up"])}
    op = os.path.join(BASE, out)
    json.dump(res, open(op, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"观察 {obs} vs 期望 {res['triple']['expected_if_random']} | perm p={perm_p:.4g}")
    for r in res["cross_system"]:
        print(f"  {r['gene']:8} {r['n_systems_up']}/{r['n_systems_total']} 体系  p={r['empirical_p']:.4g}")
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True, help="项目根目录")
    ap.add_argument("--perm", type=int, default=5000)
    a = ap.parse_args()
    BASE = a.base
    run(b=a.perm)

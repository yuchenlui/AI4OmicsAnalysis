# -*- coding: utf-8 -*-
"""Supervisor — 监督 agent：调度阶段、QC/契约验收、失败分类重试、状态清单、日志。

设计原则见 docs/design-principles.md：
  1. 每阶段的三方哈希（输入/脚本/产物）落盘 state.json，未变则跳过
  2. 失败按 transient/schema/logic/budget 四类走不同恢复策略
  3. 产物契约（列名）校验先于 QC 行数校验，杜绝静默错数据
"""
import io
import os
import sys
import time

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from . import errors as E
from .state import State, meta, sha256_file


class Supervisor:
    def __init__(self, cfg_path, force=False):
        self.cfg_path = os.path.abspath(cfg_path)
        self.cfg = yaml.safe_load(open(self.cfg_path, encoding="utf-8"))
        self.base = self.cfg["base"]
        self.force = force
        # state / 日志 与 pipeline.yaml 放在一起，一个项目一份运行档案
        pdir = os.path.dirname(self.cfg_path)
        os.makedirs(os.path.join(pdir, "logs"), exist_ok=True)
        self.logfile = os.path.join(pdir, "logs", "run.log")
        self.state = State(os.path.join(pdir, "state.json"), base=self.base)
        self.env = self.cfg.get("env") or {}
        self.llm = bool(os.environ.get("LLM_BASE_URL") and os.environ.get("LLM_API_KEY"))

    def log(self, msg):
        line = f"{time.strftime('%H:%M:%S')} {msg}"
        print(line, flush=True)
        with open(self.logfile, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    # ---------- 校验 ----------
    def _head(self, path):
        import pandas as pd
        for enc in ("utf-8-sig", "gbk"):
            try:
                return pd.read_csv(path, encoding=enc, nrows=5)
            except Exception:
                continue
        return None

    def check_contract(self, stage):
        bad = []
        for path, spec in (stage.get("contract") or {}).items():
            fp = os.path.join(self.base, path)
            if not os.path.exists(fp):
                bad.append(f"{path} 不存在")
                continue
            head = self._head(fp)
            if head is None:
                bad.append(f"{path} 无法按 CSV 读取")
                continue
            miss = [c for c in (spec.get("columns") or []) if c not in head.columns]
            if miss:
                bad.append(f"{path} 缺列 {miss}")
        return bad

    def qc(self, stage):
        import glob
        import pandas as pd
        ok, notes = True, []
        for p in stage.get("expect", []):
            if not os.path.exists(os.path.join(self.base, p)):
                ok = False
                notes.append(f"缺少产物 {p}")

        def rows(p):
            for enc in ("utf-8-sig", "gbk"):
                try:
                    return len(pd.read_csv(os.path.join(self.base, p), encoding=enc))
                except Exception:
                    continue
            return 0

        q = stage.get("qc", {})
        for p, lo in (q.get("min_rows") or {}).items():
            n = rows(p)
            if n < lo:
                ok = False
                notes.append(f"{p} 行数 {n} < {lo}")
        for p, (lo, hi) in (q.get("row_range") or {}).items():
            n = rows(p)
            if not (lo <= n <= hi):
                ok = False
                notes.append(f"{p} 行数 {n} 超出 [{lo},{hi}]")
        for d, lo in (q.get("min_files_in") or {}).items():
            n = len(os.listdir(os.path.join(self.base, d)))
            if n < lo:
                ok = False
                notes.append(f"{d} 文件数 {n} < {lo}")
        contract_bad = self.check_contract(stage)
        if contract_bad:
            ok = False
            notes += contract_bad
        return ok, notes

    # ---------- 调度 ----------
    def _script_hashes(self, stage):
        h = {}
        for t in stage.get("tools") or []:
            script = t[0] if isinstance(t, (list, tuple)) else t
            fp = os.path.join(self.base, script)
            if os.path.exists(fp):
                h[script] = sha256_file(fp)
        return h

    def run_stage(self, stage, agent):
        sid = stage["id"]
        sh = self._script_hashes(stage)
        if not self.force and self.state.is_fresh(sid, sh, []):
            self.log(f"阶段 {sid} 产物与脚本均未变，跳过（--force 强制重跑）")
            return True

        attempt, hits = 0, {"transient": 0, "schema": 0, "logic": 0, "budget": 0}
        t0 = time.time()
        while True:
            attempt += 1
            self.log(f"=== 阶段 {sid}（{stage['desc']}）agent={stage['agent']} 第 {attempt} 次 ===")
            try:
                if stage.get("tools"):
                    for t in stage["tools"]:
                        args = list(t) if isinstance(t, (list, tuple)) else [t]
                        args = [a.replace("{base}", self.base) for a in args]
                        ok, _ = agent.run_tool(args, timeout=stage.get("timeout", 3600))
                        if not ok:
                            raise E.LogicError(f"{args[0]} 退出码非 0")
                else:
                    import inspect
                    sig = inspect.signature(agent.run).parameters
                    agent.run(**{k: v for k, v in (stage.get("params") or {}).items() if k in sig})
                ok, notes = self.qc(stage)
                if not ok:
                    raise E.LogicError("QC 未通过: " + "; ".join(notes))
                # SSH 执行时把产物拉回本地
                if stage.get("tools") and hasattr(agent.runner, "pull"):
                    if stage.get("pull") and not agent.runner.pull(stage["pull"], self.base):
                        raise E.NetworkError("产物拉回失败（scp）")
                outs = [meta(p, self.base) for p in stage.get("expect", [])]
                self.state.record(sid, "ok", sh, [], outs,
                                  {"ok": True, "notes": notes}, attempt=attempt,
                                  elapsed=time.time() - t0)
                self.log(f"阶段 {sid} 通过 QC ✓ {('; '.join(notes))[:160]}")
                return True
            except Exception as e:
                kind, hint = E.classify(e)
                pol = E.RECOVERY[kind]
                self.log(f"阶段 {sid} 失败[{kind}] {hint} :: {str(e)[:300]}")
                hits[kind] += 1
                if hits[kind] > pol["retries"]:
                    self.state.record(sid, "failed", sh, [],
                                      [meta(p, self.base) for p in stage.get("expect", [])],
                                      {"ok": False}, error=f"[{kind}] {str(e)[:300]}",
                                      attempt=attempt, elapsed=time.time() - t0)
                    self.log(f"阶段 {sid} 按策略终止（{kind} → {pol['action']}）✗")
                    return False
                wait = pol["backoff"][min(hits[kind] - 1, len(pol["backoff"]) - 1)] if pol["backoff"] else 0
                self.log(f"  → {kind}：{pol['action']}，等待 {wait}s")
                time.sleep(wait)

    def run(self, only=None, from_stage=None):
        from .agents import AGENTS
        made = {}
        stages = self.cfg["stages"]
        if from_stage:
            stages = stages[[i for i, s in enumerate(stages) if s["id"] == from_stage][0]:]
        if only:
            stages = [s for s in stages if s["id"] in only]
        for stage in stages:
            a = stage["agent"]
            if a not in made:
                made[a] = AGENTS[a](self)
            if not self.run_stage(stage, made[a]):
                return False
        self.log("全部阶段完成 ✓")
        return True

# -*- coding: utf-8 -*-
"""ai4omics CLI。

用法（在项目根目录，pipeline.yaml 描述阶段）:
  python -m ai4omics run --pipeline pipeline.yaml                 # 全流程
  python -m ai4omics run --pipeline pipeline.yaml --only novelty  # 单阶段
  python -m ai4omics run --pipeline pipeline.yaml --from integrate
  python -m ai4omics run --pipeline pipeline.yaml --force         # 忽略哈希强制重跑
  python -m ai4omics status --pipeline pipeline.yaml              # 状态清单
  python -m ai4omics doctor                                       # 环境/远程自检
"""
import argparse
import os
import subprocess
import sys

from .supervisor import Supervisor


def cmd_run(a):
    sup = Supervisor(a.pipeline, force=a.force)
    if a.only:
        only = a.only.split(",")
    else:
        only = None
    sup.log(f"ai4omics 启动 LLM模式={sup.llm} force={a.force}")
    ok = sup.run(only=only, from_stage=a.frm)
    sys.exit(0 if ok else 1)


def cmd_status(a):
    sup = Supervisor(a.pipeline)
    print(sup.state.table())


def cmd_doctor(a):
    ok = True
    for mod in ("yaml", "pandas", "numpy", "matplotlib"):
        try:
            __import__(mod)
            print(f"  python 依赖 {mod:12} OK")
        except ImportError:
            ok = False
            print(f"  python 依赖 {mod:12} 缺失（pip install {mod}）")
    import yaml as _y
    cfg = _y.safe_load(open(a.pipeline, encoding="utf-8"))
    base = cfg["base"]
    print(f"  项目根 {base} {'OK' if os.path.isdir(base) else '不存在 ✗'}")
    if (cfg.get("execution") or "local") == "ssh":
        r = cfg.get("remote") or {}
        target = f"{r.get('user')}@{r['host']}" if r.get("user") else r["host"]
        p = subprocess.run(["ssh", "-p", str(r.get("port", 22)), "-o", "BatchMode=yes",
                            target, "echo ok"], capture_output=True, text=True, timeout=30)
        print(f"  SSH {target}: {'OK' if p.returncode == 0 else '失败（检查密钥/主机）'}")
        if p.returncode == 0:
            q = subprocess.run(["ssh", "-p", str(r.get("port", 22)), target,
                                f"cd '{r['workdir']}' && ls | head -3"],
                               capture_output=True, text=True, timeout=30)
            print(f"  远程工作目录 {r['workdir']}: {'OK' if q.returncode == 0 else '不存在'}")
    sys.exit(0 if ok else 1)


def main():
    ap = argparse.ArgumentParser(prog="ai4omics")
    sub = ap.add_subparsers(dest="cmd", required=True)

    for name in ("run", "status", "doctor"):
        s = sub.add_parser(name)
        s.add_argument("--pipeline", default="pipeline.yaml")
        if name == "run":
            s.add_argument("--only", help="逗号分隔的阶段 id")
            s.add_argument("--from", dest="frm", help="起始阶段 id")
            s.add_argument("--force", action="store_true")
    a = ap.parse_args()
    {"run": cmd_run, "status": cmd_status, "doctor": cmd_doctor}[a.cmd](a)


if __name__ == "__main__":
    main()

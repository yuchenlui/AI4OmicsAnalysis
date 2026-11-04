# -*- coding: utf-8 -*-
"""runner.py — 阶段执行器：本地或 SSH 远程。

组学分析（DESeq2/limma/Seurat、大矩阵 IO）在笔记本上又慢又吃内存，
生产建议在服务器上跑：pipeline.yaml 里配 execution: ssh 即可，阶段脚本
在远端执行，产物自动拉回本地 results/。

remote 配置示例：
  execution: ssh
  remote:
    host: sxycloud-x2          # 建议配 ~/.ssh/config 别名
    user: dsh
    port: 22
    workdir: /data/omics/myproject
    python: /opt/mambaforge/envs/omics/bin/python
"""
import os
import subprocess


class BaseRunner:
    def __init__(self, cfg):
        self.cfg = cfg

    def run(self, args, cwd, env=None, timeout=3600):
        raise NotImplementedError

    def pull(self, paths, cwd):
        """把远端产物拉回本地（SSH 执行器用）。"""
        return True


class LocalRunner(BaseRunner):
    def run(self, args, cwd, env=None, timeout=3600):
        p = subprocess.run(args, cwd=cwd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout,
                           env={**os.environ, **(env or {})})
        tail = "\n".join((p.stdout or "").splitlines()[-15:] +
                         (p.stderr or "").splitlines()[-8:])
        return p.returncode == 0, tail


class SSHRunner(BaseRunner):
    def __init__(self, cfg):
        super().__init__(cfg)
        r = cfg.get("remote") or {}
        self.host = r["host"]
        self.user = r.get("user")
        self.port = r.get("port", 22)
        self.workdir = r["workdir"]
        self.python = r.get("python", "python3")
        self.env = r.get("env", {})

    def _ssh(self, cmd, timeout):
        target = f"{self.user}@{self.host}" if self.user else self.host
        args = ["ssh", "-p", str(self.port), "-o", "BatchMode=yes",
                "-o", "StrictHostKeyChecking=accept-new", target, cmd]
        p = subprocess.run(args, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
        return p

    def run(self, args, cwd, env=None, timeout=3600):
        script = " ".join(a if " " not in a else f"'{a}'" for a in args)
        exports = " ".join(f"export {k}='{v}';" for k, v in {**(env or {}), **self.env}.items())
        cmd = f"cd '{self.workdir}' && {exports} {script}"
        p = self._ssh(cmd, timeout)
        tail = "\n".join((p.stdout or "").splitlines()[-15:] +
                         (p.stderr or "").splitlines()[-8:])
        return p.returncode == 0, tail

    def pull(self, paths, cwd):
        """scp 拉回产物（路径为项目相对路径）。"""
        target = f"{self.user}@{self.host}" if self.user else self.host
        ok = True
        for rel in paths:
            args = ["scp", "-P", str(self.port), "-o", "BatchMode=yes",
                    "-r", f"{target}:{self.workdir.rstrip('/')}/{rel}",
                    os.path.join(cwd, os.path.dirname(rel) or ".")]
            p = subprocess.run(args, capture_output=True, text=True)
            ok &= p.returncode == 0
        return ok


def make_runner(cfg):
    if (cfg.get("execution") or "local") == "ssh":
        return SSHRunner(cfg)
    return LocalRunner(cfg)

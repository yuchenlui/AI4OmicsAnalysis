# -*- coding: utf-8 -*-
"""state.py — 阶段状态与产物清单（manifest）。

每次运行把"这个阶段用了什么输入、跑了哪版脚本、产出了什么、QC 是否通过"
落盘到 harness/state.json。续跑时只认哈希一致的产物，避免"脚本改了但结果没变"
和"半成品被当成成品"两类静默错误。
"""
import hashlib, json, os, time

HARNESS = os.path.dirname(os.path.abspath(__file__))
STATE_PATH = os.path.join(HARNESS, "state.json")


def sha256_file(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()[:16]


def count_rows(path):
    """快速行数（CSV/TSV 减表头）；目录或二进制返回 None。"""
    if not os.path.isfile(path):
        return None
    if not path.lower().endswith((".csv", ".tsv", ".txt")):
        return None
    try:
        with open(path, "rb") as f:
            n = sum(1 for _ in f)
        return max(0, n - 1)
    except Exception:
        return None


def meta(path, base=None):
    """单个产物的元信息（相对路径按 base 解析）。"""
    ap = path if os.path.isabs(path) else os.path.join(base or os.getcwd(), path)
    if os.path.isdir(ap):
        files = sorted(os.listdir(ap))
        return {"path": path, "kind": "dir", "n_files": len(files),
                "sha256": sha256_file(os.path.join(ap, files[0])) if files else None}
    if not os.path.exists(ap):
        return {"path": path, "kind": "missing", "sha256": None}
    return {"path": path, "kind": "file", "size": os.path.getsize(ap),
            "sha256": sha256_file(ap), "rows": count_rows(ap)}


class State:
    def __init__(self, path=STATE_PATH, base=None):
        self.path = path
        self.base = base
        self.data = {}
        if os.path.exists(path):
            try:
                self.data = json.load(open(path, encoding="utf-8"))
            except Exception:
                self.data = {}

    def save(self):
        self.data["_updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
        json.dump(self.data, open(self.path, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)

    def get(self, sid):
        return self.data.get(sid)

    def is_fresh(self, sid, script_hashes, inputs):
        """产物哈希与脚本哈希都未变 → 可跳过。"""
        rec = self.get(sid)
        if not rec or rec.get("status") != "ok":
            return False
        if rec.get("script_hashes") != script_hashes:
            return False
        for i in rec.get("inputs", []):
            ap = i["path"] if os.path.isabs(i["path"]) else os.path.join(self.base or os.getcwd(), i["path"])
            if not os.path.exists(ap) or sha256_file(ap) != i["sha256"]:
                return False
        for o in rec.get("outputs", []):
            ap = o["path"] if os.path.isabs(o["path"]) else os.path.join(self.base or os.getcwd(), o["path"])
            if not os.path.exists(ap):
                return False
            if o.get("kind") == "file" and sha256_file(ap) != o.get("sha256"):
                return False
        return True

    def record(self, sid, status, script_hashes=None, inputs=None, outputs=None,
               qc=None, error=None, attempt=1, elapsed=None):
        self.data[sid] = {
            "status": status, "attempt": attempt,
            "started": (self.get(sid) or {}).get("started") or time.strftime("%Y-%m-%d %H:%M:%S"),
            "finished": time.strftime("%Y-%m-%d %H:%M:%S"),
            "elapsed_s": round(elapsed, 1) if elapsed else None,
            "script_hashes": script_hashes or {},
            "inputs": inputs or [],
            "outputs": outputs or [],
            "qc": qc or {},
            "error": error,
        }
        self.save()

    def table(self):
        lines = []
        for sid, r in self.data.items():
            if sid.startswith("_"):
                continue
            rows = max([o.get("rows") or 0 for o in r.get("outputs", [])] or [0])
            lines.append(f"{sid:12} {r.get('status','?'):6} {r.get('finished','')}  "
                         f"rows={rows:<7} err={r.get('error') or '-'}")
        return "\n".join(lines) or "(state.json 为空)"

# -*- coding: utf-8 -*-
"""冒烟测试：python tests/test_smoke.py（无 pytest 依赖）"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from ai4omics.errors import classify, RECOVERY
from ai4omics.state import State, sha256_file, meta


def test_errors():
    import urllib.error
    assert classify(urllib.error.HTTPError("u", 429, "x", None, None))[0] == "transient"
    assert classify(urllib.error.HTTPError("u", 404, "x", None, None))[0] == "schema"
    assert classify(FileNotFoundError("x"))[0] == "schema"
    assert classify(AssertionError("x"))[0] == "logic"
    assert RECOVERY["logic"]["retries"] == 0
    print("errors ✓")


def test_state():
    with tempfile.TemporaryDirectory() as d:
        f = os.path.join(d, "a.csv")
        open(f, "w", encoding="utf-8").write("gene,log2FC\nA,1\nB,2\n")
        m = meta("a.csv", base=d)
        assert m["rows"] == 2 and m["sha256"] == sha256_file(f)
        st = State(os.path.join(d, "s.json"), base=d)
        st.record("t", "ok", script_hashes={"x.py": "h1"},
                  outputs=[{"path": "a.csv", "kind": "file", "sha256": m["sha256"]}])
        assert st.is_fresh("t", {"x.py": "h1"}, [])
        open(f, "w", encoding="utf-8").write("gene,log2FC\nA,9\n")
        assert not st.is_fresh("t", {"x.py": "h1"}, [])   # 产物变了 → 不再新鲜
        assert not st.is_fresh("t", {"x.py": "h2"}, [])   # 脚本变了 → 不再新鲜
        print("state ✓")


def test_cli_import():
    from ai4omics import cli, runner, supervisor, agents  # noqa: F401
    r = runner.make_runner({"execution": "local"})
    ok, tail = r.run([sys.executable, "-c", "print('hi')"], cwd=".")
    assert ok and "hi" in tail
    print("cli/runner ✓")


if __name__ == "__main__":
    test_errors()
    test_state()
    test_cli_import()
    print("ALL PASS")

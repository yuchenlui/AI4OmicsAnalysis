# -*- coding: utf-8 -*-
"""errors.py — 失败分类与恢复策略。

不区分类别的"重试 3 次 + sleep 3s"是最常见的 harness 反模式：
网络抖动该退避重试，数据格式错重试一万次也没用，逻辑错重试只会扩大错误。
"""
import socket, ssl, subprocess, urllib.error

RECOVERY = {
    # 瞬时故障：退避重试
    "transient": {"retries": 3, "backoff": [2, 8, 20], "action": "指数退避后重试"},
    # 数据格式/缺失：最多重试 1 次，之后要求换数据源或修解析
    "schema": {"retries": 1, "backoff": [1], "action": "重试 1 次；仍失败则换解析/换数据源"},
    # 逻辑/QC 不达标：不重试，直接暴露问题
    "logic": {"retries": 0, "backoff": [], "action": "不重试；记录并中止，等待人工或 critic 判断"},
    # 超时/预算：不重试，需调参
    "budget": {"retries": 0, "backoff": [], "action": "不重试；检查超时阈值与数据规模"},
}


class StageError(Exception):
    kind = "logic"


class NetworkError(StageError):
    kind = "transient"


class DataSchemaError(StageError):
    kind = "schema"


class LogicError(StageError):
    kind = "logic"


class BudgetError(StageError):
    kind = "budget"


def classify(exc):
    """把异常映射到四类之一，并给出诊断线索。"""
    msg = str(exc)
    if isinstance(exc, (socket.timeout, TimeoutError, ConnectionError, ssl.SSLError)):
        return "transient", "网络/SSL 层失败，通常是限流或代理问题"
    if isinstance(exc, urllib.error.HTTPError):
        if exc.code in (429, 500, 502, 503, 504):
            return "transient", f"HTTP {exc.code}，服务端限流/不可用"
        return "schema", f"HTTP {exc.code}，请求本身不合法（URL/权限）"
    if isinstance(exc, urllib.error.URLError):
        return "transient", "URL 不可达（DNS/代理/证书）"
    if isinstance(exc, subprocess.TimeoutExpired):
        return "budget", "子进程超时"
    if isinstance(exc, FileNotFoundError):
        return "schema", "缺输入文件（下载未完成或路径变更）"
    if isinstance(exc, (KeyError, IndexError)):
        return "schema", "列名/索引不存在，数据结构与脚本假设不一致"
    if isinstance(exc, UnicodeDecodeError):
        return "schema", "编码不一致（GBK/UTF-8-BOM 常见）"
    if isinstance(exc, AssertionError):
        return "logic", "断言失败：结果不满足业务约束"
    return "logic", "未归类异常，需人工判读"

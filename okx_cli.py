#!/usr/bin/env python3
"""
OKX CLI 桥接 — 调用 okx-trade-cli 获取数据（167 个工具全可用）
CLI 不可用时自动回退到 REST API

安装 CLI：npm install -g @okx_ai/okx-trade-cli
配置：okx config init
"""

import json
import logging
import os
import subprocess
import shutil

log = logging.getLogger("btc_app")


def is_installed() -> bool:
    """检查 okx CLI 是否已安装。"""
    return shutil.which("okx") is not None


def is_configured() -> bool:
    """检查 okx CLI 是否已完成 API 配置。"""
    if not is_installed():
        return False
    try:
        result = _run(["okx", "account", "balance"], timeout=10)
        return "error" not in result.lower() and result.strip() != ""
    except Exception:
        return False


def get_install_guide() -> str:
    """返回安装指南文本。"""
    has_node = shutil.which("node") is not None
    guide = "需要安装 OKX CLI 工具包：\n\n"
    if not has_node:
        guide += "1. 安装 Node.js: https://nodejs.org (LTS 版本即可)\n"
    guide += (
        f"{'2' if not has_node else '1'}. 安装 CLI:\n"
        "   npm install -g @okx_ai/okx-trade-cli\n"
        f"{'3' if not has_node else '2'}. 配置 API Key:\n"
        "   okx config init\n"
    )
    return guide


def run_command(args: list, timeout: int = 15) -> dict:
    """运行 okx CLI 命令，返回 JSON 结果。失败返回 {"error": ...}"""
    if not is_installed():
        return {"error": "okx CLI 未安装，请运行: npm install -g @okx_ai/okx-trade-cli"}

    try:
        result = _run(["okx"] + args, timeout=timeout)
        # 尝试解析 JSON
        if result.strip().startswith("{"):
            return json.loads(result)
        if result.strip().startswith("["):
            return {"data": json.loads(result)}
        return {"text": result.strip()}
    except subprocess.TimeoutExpired:
        return {"error": f"命令超时 ({timeout}s): okx {' '.join(args)}"}
    except Exception as e:
        return {"error": str(e)}


# ── 工具方法（映射 agent-trade-kit 的核心工具）─────────────

def market_ticker(inst_id: str = "BTC-USDT") -> dict:
    return run_command(["market", "ticker", inst_id])


def market_candles(inst_id: str = "BTC-USDT-SWAP", bar: str = "15m",
                   limit: int = 60) -> dict:
    return run_command(["market", "candles", inst_id,
                       "--bar", bar, "--limit", str(limit)])


def market_indicator(inst_id: str = "BTC-USDT-SWAP", indicator: str = "rsi",
                     bar: str = "1H") -> dict:
    return run_command(["market", "indicator", inst_id,
                       "--indicator", indicator, "--bar", bar])


def account_balance() -> dict:
    return run_command(["account", "balance"])


def account_positions() -> dict:
    return run_command(["account", "positions"])


def news_latest(limit: int = 10) -> dict:
    return run_command(["news", "latest", "--limit", str(limit)])


def news_by_coin(coin: str = "BTC", limit: int = 10) -> dict:
    return run_command(["news", "by-coin", "--coins", coin,
                       "--limit", str(limit)])


def smartmoney_traders(period: str = "7", sort_by: str = "pnl",
                       limit: int = 10) -> dict:
    return run_command(["smartmoney", "traders",
                       "--period", period, "--sort-by", sort_by,
                       "--limit", str(limit)])


def smartmoney_signals(period: str = "7", sort_by: str = "pnl",
                       top_n: int = 5) -> dict:
    return run_command(["smartmoney", "signals",
                       "--period", period, "--sort-by", sort_by,
                       "--top-instruments", str(top_n)])


def smartmoney_trader_positions(author_id: str) -> dict:
    return run_command(["smartmoney", "trader-positions", author_id])


# ── 内部 ───────────────────────────────────────────────────

def _run(cmd: list, timeout: int = 15) -> str:
    env = os.environ.copy()
    env["NO_COLOR"] = "1"
    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout, env=env,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip()
        if "not logged in" in stderr.lower() or "unauthorized" in stderr.lower():
            raise RuntimeError("OKX CLI 未登录，请运行: okx config init")
        if "command not found" in stderr.lower():
            raise RuntimeError("命令无效，请检查 CLI 版本: npm update -g @okx_ai/okx-trade-cli")
        raise RuntimeError(stderr[:200])
    return result.stdout.strip()

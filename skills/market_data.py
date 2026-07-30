#!/usr/bin/env python3
"""
行情数据查询 — OKX 公开 REST API + 认证数据
使用 okx_client 统一接口，无 API Key 时自动回退公开 API
"""

import logging

log = logging.getLogger("btc_app")


def _get_client():
    """获取 OKX 客户端（延迟导入避免循环引用）。"""
    from okx_client import get_client
    return get_client("public")


def fetch_candles(inst_id: str = "BTC-USDT-SWAP", bar: str = "15m",
                  limit: int = 100) -> list[dict]:
    return _get_client().get_candles(inst_id, bar, limit)


def fetch_ticker(inst_id: str = "BTC-USDT-SWAP") -> dict:
    return _get_client().get_ticker(inst_id)


def fetch_funding_rate(inst_id: str = "BTC-USDT-SWAP") -> dict:
    return _get_client().get_funding_rate(inst_id)


def fetch_open_interest(inst_id: str = "BTC-USDT-SWAP") -> dict:
    return _get_client().get_open_interest(inst_id)


def fetch_all(inst_id: str = "BTC-USDT-SWAP") -> dict:
    """一次性获取所有公开行情数据。"""
    client = _get_client()
    ticker = client.get_ticker(inst_id)
    return {
        "price": ticker["last"],
        "high24h": ticker["high24h"],
        "low24h": ticker["low24h"],
        "vol24h": ticker["vol24h"],
        "bid": ticker["bid"],
        "ask": ticker["ask"],
    }

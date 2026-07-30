#!/usr/bin/env python3
"""
OKX 统一数据客户端
支持三种认证模式：public（免费公开）/ api_key（HMAC 签名）/ mcp（预留）

安全说明：所有请求仅发往 OKX 官方 API (https://www.okx.com)。
HMAC 签名在本地计算，Secret Key 不会离开本机。
"""

import base64
import hashlib
import hmac
import json
import logging
import time
from datetime import datetime, timezone

import requests

log = logging.getLogger("btc_app")

REST_URL = "https://www.okx.com"


class OKXClient:
    """OKX 数据客户端，自动根据认证模式选数据源。"""

    def __init__(self, auth_type: str = "public", credentials: dict = None):
        self.auth_type = auth_type  # "public" | "api_key" | "mcp"
        self.creds = credentials or {}
        self._cache = {}
        self._cache_ttl = {}

    # ── Public REST (no auth) ─────────────────────────────

    def get_candles(self, inst_id: str = "BTC-USDT-SWAP", bar: str = "15m",
                    limit: int = 100, history: bool = False) -> list[dict]:
        """获取 K 线数据。返回 [{ts, open, high, low, close, vol}, ...] 按时间升序。"""
        cache_key = f"candles_{inst_id}_{bar}_{limit}"
        if self._cache_hit(cache_key, 30):
            return self._cache[cache_key]

        url = f"{REST_URL}/api/v5/market/candles"
        params = {"instId": inst_id, "bar": bar, "limit": limit}
        data = self._get(url, params)
        candles = []
        for row in reversed(data.get("data", [])):
            candles.append({
                "ts": int(row[0]), "open": float(row[1]),
                "high": float(row[2]), "low": float(row[3]),
                "close": float(row[4]), "vol": float(row[5]),
            })
        self._cache_set(cache_key, candles, 30)
        return candles

    def get_ticker(self, inst_id: str = "BTC-USDT-SWAP") -> dict:
        """获取当前行情快照。"""
        cache_key = f"ticker_{inst_id}"
        if self._cache_hit(cache_key, 10):
            return self._cache[cache_key]

        url = f"{REST_URL}/api/v5/market/ticker"
        data = self._get(url, {"instId": inst_id})
        item = data["data"][0]
        result = {
            "last": float(item["last"]),
            "bid": float(item["bidPx"]),
            "ask": float(item["askPx"]),
            "high24h": float(item["high24h"]),
            "low24h": float(item["low24h"]),
            "vol24h": float(item["volCcy24h"]),
            "inst_id": item["instId"],
        }
        self._cache_set(cache_key, result, 10)
        return result

    def get_funding_rate(self, inst_id: str = "BTC-USDT-SWAP") -> dict:
        """获取当前资金费率。"""
        cache_key = f"fr_{inst_id}"
        if self._cache_hit(cache_key, 60):
            return self._cache[cache_key]

        url = f"{REST_URL}/api/v5/public/funding-rate"
        data = self._get(url, {"instId": inst_id})
        item = data["data"][0]
        result = {
            "funding_rate": float(item["fundingRate"]),
            "next_funding_time": int(item["nextFundingTime"]),
        }
        self._cache_set(cache_key, result, 60)
        return result

    def get_open_interest(self, inst_id: str = "BTC-USDT-SWAP") -> dict:
        """获取持仓量。"""
        cache_key = f"oi_{inst_id}"
        if self._cache_hit(cache_key, 30):
            return self._cache[cache_key]

        url = f"{REST_URL}/api/v5/public/open-interest"
        data = self._get(url, {"instId": inst_id})
        item = data["data"][0]
        result = {"oi": float(item["oi"]), "oi_ccy": float(item["oiCcy"]), "ts": int(item["ts"])}
        self._cache_set(cache_key, result, 30)
        return result

    def get_mark_price(self, inst_id: str = "BTC-USDT-SWAP") -> float:
        """获取标记价格。"""
        url = f"{REST_URL}/api/v5/public/mark-price"
        data = self._get(url, {"instType": "SWAP", "instId": inst_id})
        return float(data["data"][0]["markPx"])

    # ── Public: Indicators & Instruments ───────────────────

    def get_indicator(self, inst_id: str, indicator: str, bar: str = "1H",
                      params: list = None) -> dict | list:
        """获取技术指标值。支持 70+ 指标（MA/EMA/RSI/MACD/BB/KDJ/AHR999/BTCRAINBOW 等）。
        公开接口，无需认证。"""
        cache_key = f"ind_{inst_id}_{indicator}_{bar}"
        if self._cache_hit(cache_key, 30):
            return self._cache[cache_key]

        url = f"{REST_URL}/api/v5/market/indicator"
        req_params = {"instId": inst_id, "indicator": indicator, "bar": bar}
        if params:
            req_params["params"] = ",".join(str(p) for p in params)
        data = self._get(url, req_params)
        self._cache_set(cache_key, data["data"], 30)
        return data["data"]

    def get_instruments(self, inst_type: str = "SWAP",
                        inst_id: str = None) -> list[dict]:
        """获取交易产品列表及合约规格（最小下单量/面值/手续费等）。"""
        url = f"{REST_URL}/api/v5/public/instruments"
        params = {"instType": inst_type}
        if inst_id:
            params["instId"] = inst_id
        data = self._get(url, params)
        return data["data"]

    def get_index_candles(self, index: str = "BTC-USD", bar: str = "1H",
                          limit: int = 100) -> list[dict]:
        """获取指数 K 线（如 BTC-USD 指数）。"""
        cache_key = f"idx_{index}_{bar}_{limit}"
        if self._cache_hit(cache_key, 30):
            return self._cache[cache_key]

        url = f"{REST_URL}/api/v5/market/index-candles"
        data = self._get(url, {"instId": index, "bar": bar, "limit": limit})
        candles = []
        for row in reversed(data.get("data", [])):
            candles.append({"ts": int(row[0]), "open": float(row[1]),
                           "high": float(row[2]), "low": float(row[3]),
                           "close": float(row[4])})
        self._cache_set(cache_key, candles, 30)
        return candles

    # ── News (requires API Key) ─────────────────────────────

    def get_news_latest(self, limit: int = 10, language: str = "zh-CN") -> list[dict]:
        """获取最新加密货币新闻（需认证）。"""
        if self.auth_type != "api_key":
            return []

        url = f"{REST_URL}/api/v5/news/latest"
        try:
            data = self._signed_get(url, {"limit": limit, "language": language})
            articles = []
            for item in data.get("data", [])[:limit]:
                articles.append({
                    "title": item.get("title", ""),
                    "summary": item.get("summary", ""),
                    "time": item.get("publishTime", ""),
                    "source": item.get("source", ""),
                    "url": item.get("url", ""),
                })
            return articles
        except Exception as e:
            log.error(f"获取新闻失败: {e}")
            return []

    def get_news_by_coin(self, coin: str = "BTC",
                         limit: int = 10) -> list[dict]:
        """获取指定币种的新闻（需认证）。"""
        if self.auth_type != "api_key":
            return []

        url = f"{REST_URL}/api/v5/news/by-coin"
        try:
            data = self._signed_get(url, {"coins": coin, "limit": limit})
            articles = []
            for item in data.get("data", [])[:limit]:
                articles.append({
                    "title": item.get("title", ""),
                    "summary": item.get("summary", ""),
                    "time": item.get("publishTime", ""),
                    "source": item.get("source", ""),
                })
            return articles
        except Exception as e:
            log.error(f"获取{coin}新闻失败: {e}")
            return []

    # ── Smart Money (requires API Key) ──────────────────────

    def get_smart_money_traders(self, period: str = "7",
                                sort_by: str = "pnl",
                                limit: int = 10) -> list[dict]:
        """获取智能资金交易员排行榜（需认证）。"""
        if self.auth_type != "api_key":
            return []

        url = f"{REST_URL}/api/v5/trading-data/smart-money/traders"
        try:
            data = self._signed_get(
                url, {"period": period, "sortBy": sort_by, "limit": limit})
            traders = []
            for item in data.get("data", []):
                traders.append({
                    "nickname": item.get("nickName", ""),
                    "pnl": float(item.get("pnl", 0)),
                    "pnl_ratio": float(item.get("pnlRatio", 0)),
                    "win_rate": float(item.get("winRate", 0)),
                    "aum": float(item.get("aum", 0)),
                    "follower_count": int(item.get("followerCount", 0)),
                    "author_id": item.get("authorId", ""),
                })
            return traders
        except Exception as e:
            log.error(f"获取智能资金交易员失败: {e}")
            return []

    def get_smart_money_signals(self, period: str = "7",
                                sort_by: str = "pnl",
                                top_coins: int = 5) -> list[dict]:
        """获取智能资金共识信号（需认证）。"""
        if self.auth_type != "api_key":
            return []

        url = f"{REST_URL}/api/v5/trading-data/smart-money/overview"
        try:
            data = self._signed_get(
                url, {"period": period, "sortBy": sort_by,
                      "topInstruments": top_coins})
            signals = []
            for item in data.get("data", []):
                signals.append({
                    "inst_ccy": item.get("instCcy", ""),
                    "l_ratio": float(item.get("lRatio", 0)),
                    "s_ratio": float(item.get("sRatio", 0)),
                    "weighted_l_ratio": float(item.get("weightedLRatio", 0)),
                    "entry_px_dist": item.get("entryPxDist", ""),
                    "traders_qualified": int(item.get("tradersQualified", 0)),
                })
            return signals
        except Exception as e:
            log.error(f"获取智能资金信号失败: {e}")
            return []

    # ── Authenticated REST (requires API Key) ──────────────

    def get_balance(self) -> dict:
        """获取账户余额（需 API Key 认证）。"""
        if self.auth_type != "api_key":
            return {"error": "需要配置 API Key"}

        url = f"{REST_URL}/api/v5/account/balance"
        data = self._signed_get(url)
        if data.get("code") != "0":
            return {"error": data.get("msg", "未知错误")}

        balances = {}
        for item in data["data"][0].get("details", []):
            ccy = item["ccy"]
            avail = float(item["availBal"])
            frozen = float(item["frozenBal"])
            if avail > 0 or frozen > 0:
                balances[ccy] = {"可用": avail, "冻结": frozen,
                                 "总计": round(avail + frozen, 8)}
        return balances

    def get_positions(self, inst_id: str = None) -> list[dict]:
        """获取当前持仓（需 API Key 认证）。"""
        if self.auth_type != "api_key":
            return []

        url = f"{REST_URL}/api/v5/account/positions"
        params = {"instType": "SWAP"}
        if inst_id:
            params["instId"] = inst_id
        data = self._signed_get(url, params)
        if data.get("code") != "0":
            return []

        positions = []
        for item in data.get("data", []):
            pos = float(item["pos"])
            if pos == 0:
                continue
            positions.append({
                "inst_id": item["instId"],
                "pos": pos,
                "pos_side": item["posSide"],
                "avg_px": float(item["avgPx"]),
                "upl": float(item["upl"]),
                "upl_ratio": float(item["uplRatio"]),
                "lever": float(item["lever"]),
                "liq_px": float(item.get("liqPx", 0) or 0),
                "margin": float(item["margin"]),
                "mark_px": float(item["markPx"]),
            })
        return positions

    def get_account_config(self) -> dict | None:
        """获取账户配置（仓位模式、账户等级等）。"""
        if self.auth_type != "api_key":
            return None

        data = self._signed_get(f"{REST_URL}/api/v5/account/config")
        if data.get("code") != "0":
            return None
        item = data["data"][0]
        return {
            "pos_mode": item["posMode"],
            "acct_lv": item["acctLv"],
            "uid": item["uid"],
        }

    # ── HTTP helpers ───────────────────────────────────────

    def _request(self, method: str, url: str, params: dict = None,
                 headers: dict = None) -> dict:
        """发送请求，代理开/关自适应。
        先直连，失败后自动尝试系统代理。"""
        proxies_direct = {"http": None, "https": None}   # 不走代理
        proxies_system = None  # requests 默认走系统代理

        for label, proxies in [("直连", proxies_direct), ("代理", proxies_system)]:
            try:
                if method == "GET":
                    resp = requests.get(url, params=params, headers=headers,
                                        timeout=10, proxies=proxies)
                else:
                    resp = requests.request(method, url, params=params,
                                            headers=headers, timeout=10, proxies=proxies)
                resp.raise_for_status()
                data = resp.json()
                if data.get("code") != "0":
                    raise RuntimeError(f"OKX API: {data.get('msg', 'unknown')}")
                return data
            except requests.exceptions.ConnectionError:
                continue  # 直连失败，尝试代理
            except requests.exceptions.ProxyError:
                continue  # 代理不可用，等下直连会成功

        raise RuntimeError(f"OKX API 连接失败（直连和代理均不可用）: {url}")

    def _get(self, url: str, params: dict = None) -> dict:
        return self._request("GET", url, params=params)

    def _signed_get(self, url: str, params: dict = None) -> dict:
        """带签名的 GET 请求。"""
        if not params:
            params = {}
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.") + \
             str(datetime.now(timezone.utc).microsecond // 1000).zfill(3) + "Z"

        if "?" in url:
            path = url.split(REST_URL)[1]
        else:
            path = url.replace(REST_URL, "")
        qs = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
        if qs:
            path = path + "?" + qs

        sign_str = ts + "GET" + path
        sign = base64.b64encode(
            hmac.new(self.creds["secret_key"].encode(), sign_str.encode(),
                     hashlib.sha256).digest()
        ).decode()

        headers = {
            "OK-ACCESS-KEY": self.creds["api_key"],
            "OK-ACCESS-SIGN": sign,
            "OK-ACCESS-TIMESTAMP": ts,
            "OK-ACCESS-PASSPHRASE": self.creds["passphrase"],
            "Content-Type": "application/json",
        }
        return self._request("GET", url, params=params, headers=headers)

    def has_credentials(self) -> bool:
        """是否配置了 API Key 认证。"""
        if self.auth_type != "api_key":
            return False
        return all(self.creds.get(k) for k in ("api_key", "secret_key", "passphrase"))

    def test_connection(self) -> tuple[bool, str]:
        """测试 API 连接。返回 (成功, 消息)。"""
        if not self.has_credentials():
            return False, "请先填写 API Key / Secret Key / Passphrase"
        try:
            data = self.get_account_config()
            if data:
                return True, f"连接成功！账户 UID: {data.get('uid', '?')}"
            return False, "认证失败，请检查 API Key"
        except Exception as e:
            return False, f"连接失败: {e}"

    # ── Cache ──────────────────────────────────────────────

    def _cache_hit(self, key: str, max_age_s: int) -> bool:
        if key in self._cache and key in self._cache_ttl:
            if time.time() - self._cache_ttl[key] < max_age_s:
                return True
        return False

    def _cache_set(self, key: str, value, ttl_s: int = 30):
        self._cache[key] = value
        self._cache_ttl[key] = time.time()


# ── 模块级单例 ──────────────────────────────────────────────

_client: OKXClient | None = None


def get_client(auth_type: str = "public", credentials: dict = None) -> OKXClient:
    """获取 OKX 客户端实例（缓存）。"""
    global _client
    if _client is None or _client.auth_type != auth_type:
        _client = OKXClient(auth_type, credentials)
    return _client


def create_client_from_config(config: dict) -> OKXClient:
    """从应用配置创建 OKX 客户端。"""
    okx_cfg = config.get("okx", {})
    auth_type = okx_cfg.get("auth_type", "public")
    credentials = {
        "api_key": okx_cfg.get("api_key", ""),
        "secret_key": okx_cfg.get("secret_key", ""),
        "passphrase": okx_cfg.get("passphrase", ""),
    }
    if auth_type == "api_key" and all(credentials.values()):
        return OKXClient("api_key", credentials)
    return OKXClient("public")

#!/usr/bin/env python3
"""
新闻情绪 — BTC 市场情绪 + 恐惧贪婪指数
公开数据（恐惧贪婪指数）+ 可选 OKX 认证数据（账户/持仓）
"""

import requests
import logging

log = logging.getLogger("btc_app")


def _get_okx_client():
    """获取 OKX 客户端（如果已配置 API Key 则认证，否则公开）。"""
    try:
        from config_manager import load_config, get_okx_config
        from okx_client import OKXClient
        config = load_config()
        okx_cfg = get_okx_config(config)
        if okx_cfg.get("api_key") and okx_cfg.get("secret_key"):
            return OKXClient("api_key", {
                "api_key": okx_cfg["api_key"],
                "secret_key": okx_cfg["secret_key"],
                "passphrase": okx_cfg.get("passphrase", ""),
            })
    except Exception:
        pass
    return None


def fetch_fear_greed(limit: int = 7) -> list[dict]:
    """获取 BTC 恐惧贪婪指数（免费，无需 Key）。
    返回最近 N 天数据，value 0-100（0=极度恐惧, 100=极度贪婪）。
    """
    try:
        resp = requests.get(
            "https://api.alternative.me/fng/",
            params={"limit": limit, "format": "json"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        results = []
        for item in data.get("data", []):
            results.append({
                "value": int(item["value"]),
                "classification": item["value_classification"],
                "timestamp": int(item["timestamp"]),
            })
        return results
    except Exception as e:
        log.error(f"获取恐惧贪婪指数失败: {e}")
        return []


def fetch_btc_news(limit: int = 10) -> list[dict]:
    """
    获取 BTC 相关新闻。
    当前使用恐惧贪婪指数作为情绪指标。
    如需实时新闻，请在设置中配置 AI 供应商后使用「AI 情绪分析」。
    """
    fg = fetch_fear_greed(1)
    if fg:
        today = fg[0]
        return [{
            "title": f"BTC 恐惧贪婪指数: {today['value']} — {today['classification']}",
            "summary": f"当前市场情绪为 {today['classification']}，"
                       f"指数值 {today['value']}/100。"
                       f"0-25 极度恐惧 | 25-45 恐惧 | 45-55 中性 | 55-75 贪婪 | 75-100 极度贪婪。",
            "time": "",
            "source": "Alternative.me Fear & Greed Index",
            "url": "https://alternative.me/crypto/fear-and-greed-index/",
        }]
    return []


def fetch_btc_economic_calendar(limit: int = 5) -> list[dict]:
    """宏观经济事件需要 OKX 认证接口，公开 API 暂不可用。"""
    return []


def generate_sentiment_summary(ai_client=None) -> str:
    """
    生成市场情绪摘要。
    基于恐惧贪婪指数 + 可选 AI 分析。
    """
    fg = fetch_fear_greed(7)
    if not fg:
        return "暂无市场情绪数据。"

    current = fg[0]
    prev = fg[1] if len(fg) > 1 else None

    lines = [
        "=== BTC 市场情绪 ===",
        "",
        f"当前恐惧贪婪指数: {current['value']}/100 — {current['classification']}",
    ]

    if prev:
        change = current["value"] - prev["value"]
        direction = "上升" if change > 0 else ("下降" if change < 0 else "不变")
        lines.append(f"较昨日: {direction} {abs(change)} 点")

    # 历史趋势
    if len(fg) >= 7:
        vals = [d["value"] for d in fg]
        lines.append(f"7日均值: {sum(vals)//len(vals)}")
        lines.append(f"7日范围: {min(vals)} - {max(vals)}")

    lines += [
        "",
        "解读:",
        "  0-25  极度恐惧 → 市场可能超卖，历史上常是买入机会",
        "  25-45 恐惧      → 市场偏悲观",
        "  45-55 中性      → 市场方向不明",
        "  55-75 贪婪      → 市场偏乐观",
        "  75-100 极度贪婪 → 市场可能超买，注意回调风险",
    ]

    # 添加 OKX 认证数据（如有配置）
    okx = _get_okx_client()
    if okx and okx.has_credentials():
        try:
            balances = okx.get_balance()
            if balances and "error" not in balances:
                lines += ["", "─" * 30, "OKX 账户余额"]
                for ccy, b in balances.items():
                    if ccy in ("USDT", "BTC", "ETH"):
                        lines.append(f"  {ccy}: {b['可用']} (冻结 {b['冻结']})")
        except Exception:
            pass
        try:
            positions = okx.get_positions()
            if positions:
                lines += ["", "当前持仓:"]
                for p in positions:
                    lines.append(f"  {p['inst_id']} {p['pos_side']} "
                                 f"{p['pos']}张 @ {p['avg_px']:.1f} "
                                 f"盈亏: {p['upl']:.2f} ({p['upl_ratio']:.2%})")
        except Exception:
            pass

    if ai_client and ai_client.enabled:
        context = "\n".join(lines)
        prompt = f"""基于以下 BTC 市场数据，用中文做简短分析（50字以内）：

{context}

格式：情绪方向: bullish/bearish/neutral，一句话建议。"""
        result = ai_client.chat("你是加密货币分析师。", prompt)
        if result:
            lines.insert(0, f"AI 分析: {result}\n")

    return "\n".join(lines)


def generate_economic_summary() -> str:
    """宏观经济日历需要 OKX 认证接口。提示用户使用 MCP 工具。"""
    return ("宏观经济数据需要 OKX MCP 认证。\n"
            "如果你已配置 OKX CLI，可以使用 Claude Code 中的 "
            "okx-sentiment-tracker 技能获取完整数据。")

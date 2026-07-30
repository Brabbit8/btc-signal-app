#!/usr/bin/env python3
"""
交易计划生成 — 基于多维信号评分的结构化交易计划
参考 trading-plan-generator 的 6 维度评分框架
"""

import logging

log = logging.getLogger("btc_app")

# ── 评分维度权重 ────────────────────────────────────────────
DIMENSIONS = {
    "oi_trend":       {"name": "持仓量趋势",  "weight": 0.20},
    "ls_ratio":       {"name": "多空比",      "weight": 0.20},
    "funding_rate":   {"name": "资金费率",    "weight": 0.15},
    "liquidations":   {"name": "清算数据",    "weight": 0.15},
    "whale_position": {"name": "鲸鱼持仓",    "weight": 0.15},
    "signal_score":   {"name": "技术信号",    "weight": 0.15},
}


def score_to_signal(scores: dict) -> dict:
    """
    输入：各维度评分 (0-100, 50 中性)
    输出：综合信号 + 风险等级

    评分含义：> 50 = 偏多, < 50 = 偏空
    """
    if not scores:
        return {"signal": "neutral", "total_score": 50,
                "confidence": 0, "risk_level": "未知"}

    total = 0
    for key, dim in DIMENSIONS.items():
        s = scores.get(key, 50)
        total += s * dim["weight"]

    total = round(total, 1)

    if total >= 65:
        signal = "bullish"
    elif total >= 55:
        signal = "slightly_bullish"
    elif total <= 35:
        signal = "bearish"
    elif total <= 45:
        signal = "slightly_bearish"
    else:
        signal = "neutral"

    # 置信度：偏离 50 越远越高
    confidence = round(abs(total - 50) / 50, 2)

    # 风险等级
    if confidence >= 0.6:
        risk = "激进"
    elif confidence >= 0.3:
        risk = "中性"
    else:
        risk = "保守"

    return {
        "signal": signal,
        "total_score": total,
        "confidence": confidence,
        "risk_level": risk,
    }


def generate_plan(indicators: dict, sentiment: str = "",
                  scores: dict = None) -> str:
    """
    生成结构化交易计划。

    indicators: skills.technical.compute_all_indicators() 的返回值
    sentiment: 市场情绪摘要
    scores: 可选，各维度评分

    返回多档风险级别的交易计划文本。
    """
    if scores is None:
        # 基于指标自动生成简化评分
        scores = _auto_score_from_indicators(indicators)

    result = score_to_signal(scores)
    price = indicators.get("price", 0)

    signal_cn = {
        "bullish": "看多", "slightly_bullish": "偏多",
        "bearish": "看空", "slightly_bearish": "偏空",
        "neutral": "中性",
    }

    lines = [
        "=" * 50,
        "  BTC 交易计划",
        "=" * 50,
        "",
        f"综合评分: {result['total_score']}/100",
        f"信号方向: {signal_cn.get(result['signal'], result['signal'])}",
        f"置信度: {result['confidence']:.0%}",
        f"风险等级: {result['risk_level']}",
        "",
        "─" * 50,
        "  各维度评分",
        "─" * 50,
    ]

    for key, dim in DIMENSIONS.items():
        s = scores.get(key, 50)
        bar = "█" * int(s / 5) + "░" * (20 - int(s / 5))
        lines.append(f"  {dim['name']:<8} {bar} {s:.0f}")

    lines += [
        "",
        "─" * 50,
        "  风险级别建议",
        "─" * 50,
    ]

    atr = indicators.get("atr", 0)
    support = indicators.get("support", price * 0.95)
    resistance = indicators.get("resistance", price * 1.05)

    if result["signal"] in ("bullish", "slightly_bullish"):
        lines += [
            "",
            "  [保守] 等待回调至 $" + f"{support:,.1f} 附近做多",
            f"         止损: ${support - atr:,.1f}",
            f"         止盈: ${resistance:,.1f}",
            "",
            "  [中性] 当前价位分批建仓，仓位不超过 30%",
            f"         止损: ${price - atr * 1.5:,.1f}",
            f"         止盈: ${resistance:,.1f}",
            "",
            "  [激进] 现价直接做多，仓位不超过 50%",
            f"         止损: ${price - atr * 2:,.1f}",
            f"         止盈: ${resistance * 1.02:,.1f}",
        ]
    elif result["signal"] in ("bearish", "slightly_bearish"):
        lines += [
            "",
            "  [保守] 等待反弹至 $" + f"{resistance:,.1f} 附近做空",
            f"         止损: ${resistance + atr:,.1f}",
            f"         止盈: ${support:,.1f}",
            "",
            "  [中性] 当前价位分批建仓，仓位不超过 30%",
            f"         止损: ${price + atr * 1.5:,.1f}",
            f"         止盈: ${support:,.1f}",
            "",
            "  [激进] 现价直接做空，仓位不超过 50%",
            f"         止损: ${price + atr * 2:,.1f}",
            f"         止盈: ${support * 0.98:,.1f}",
        ]
    else:
        lines += [
            "",
            "  [保守] 观望为主，不建新仓",
            "",
            f"  [中性] 若价格触及 ${support:,.1f} 轻仓做多",
            f"         若价格触及 ${resistance:,.1f} 轻仓做空",
            "",
            "  [激进] 区间网格交易",
            f"         区间: ${support:,.1f} ~ ${resistance:,.1f}",
        ]

    lines += [
        "",
        "─" * 50,
        f"  生成时间: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "  免责声明: 本计划仅供学习参考，不构成投资建议。",
        "=" * 50,
    ]

    if sentiment:
        lines.insert(6, f"\n市场情绪: {sentiment}\n")

    return "\n".join(lines)


def _auto_score_from_indicators(indicators: dict) -> dict:
    """
    仅基于技术指标自动生成评分。
    实际使用时可替换为包含 OI、L/S 比率等多维数据的完整评分。
    """
    scores = {}
    rsi = indicators.get("rsi", 50) or 50
    trend = indicators.get("trend", "震荡")
    macd = indicators.get("macd", 0) or 0
    price = indicators.get("price", 0)
    bb_mid = indicators.get("bb_mid", price)

    # 持仓量趋势（简化：基于价格偏离中轨）
    if price and bb_mid:
        dev = (price - bb_mid) / bb_mid * 100
        scores["oi_trend"] = min(100, max(0, 50 + dev * 5))
    else:
        scores["oi_trend"] = 50

    # 多空比（简化：RSI 映射）
    scores["ls_ratio"] = min(100, max(0, rsi))

    # 资金费率（简化：中轨偏离度）
    scores["funding_rate"] = min(100, max(0, 50 + (rsi - 50) * 0.3))

    # 清算数据（简化：趋势强度映射）
    if trend == "上升":
        scores["liquidations"] = 65
    elif trend == "下降":
        scores["liquidations"] = 35
    else:
        scores["liquidations"] = 50

    # 鲸鱼持仓（简化：MACD 映射）
    scores["whale_position"] = min(100, max(0, 50 + macd * 5))

    # 技术信号（综合 RSI + 趋势 + BB）
    bb_score = 50
    if price and indicators.get("bb_lower") and indicators.get("bb_upper"):
        bb_range = indicators["bb_upper"] - indicators["bb_lower"]
        if bb_range > 0:
            bb_score = (price - indicators["bb_lower"]) / bb_range * 100
    scores["signal_score"] = round((rsi * 0.6 + bb_score * 0.4))

    return scores

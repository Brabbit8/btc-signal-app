#!/usr/bin/env python3
"""
技术分析 — 多指标计算 + Matplotlib K 线图
复用 btc_signal_bot 和 btc_strategy_adaptor 的计算函数
"""

import logging
from datetime import datetime

log = logging.getLogger("btc_app")

# 复用现有指标函数
from btc_signal_bot import calc_bb, calc_rsi, calc_atr, calc_sma
from btc_strategy_adaptor import calc_ema, calc_adx, calc_slope
from skills.market_data import fetch_candles


def compute_all_indicators(inst_id: str = "BTC-USDT-SWAP", bar: str = "15m",
                           limit: int = 100) -> dict:
    """计算所有技术指标，返回字典。"""
    candles = fetch_candles(inst_id, bar, limit)
    if not candles:
        return {}

    closes = [c["close"] for c in candles]
    price = closes[-1]

    upper, mid, lower = calc_bb(candles)
    rsi = calc_rsi(candles)
    atr = calc_atr(candles)

    result = {
        "price": price,
        "rsi": round(rsi, 1) if rsi else None,
        "atr": round(atr, 1) if atr else None,
        "bb_upper": round(upper, 1) if upper else None,
        "bb_mid": round(mid, 1) if mid else None,
        "bb_lower": round(lower, 1) if lower else None,
        "ema12": round(calc_ema(closes, 12), 1) if len(closes) >= 12 else None,
        "ema26": round(calc_ema(closes, 26), 1) if len(closes) >= 26 else None,
    }

    # MACD
    if result["ema12"] and result["ema26"]:
        result["macd"] = round(result["ema12"] - result["ema26"], 2)

    # ADX (需要更多数据)
    if len(candles) >= 28:
        result["adx"] = round((calc_adx(candles) or 0), 1)

    # 支撑/阻力位
    result["support"] = round(result["bb_lower"], 1) if result["bb_lower"] else None
    result["resistance"] = round(result["bb_upper"], 1) if result["bb_upper"] else None

    # 趋势判断
    if len(closes) >= 30:
        slope = calc_slope(closes[-20:])
        ema20 = calc_ema(closes, 20)
        ema50 = calc_ema(closes, 50) if len(closes) >= 50 else None
        if slope > 0.1 and ema20 and (ema50 is None or ema20 > ema50):
            result["trend"] = "上升"
        elif slope < -0.1 and ema20 and ema50 and ema20 < ema50:
            result["trend"] = "下降"
        else:
            result["trend"] = "震荡"

    return result


def format_analysis_text(indicators: dict) -> str:
    """将指标转为人可读的分析文本。"""
    if not indicators:
        return "暂无数据"

    lines = [
        f"当前价格: ${indicators.get('price', 0):,.1f}",
        f"趋势: {indicators.get('trend', '--')}",
        f"RSI(14): {indicators.get('rsi', '--')}",
        f"布林带: 上轨 {indicators.get('bb_upper', '--')} / "
        f"中轨 {indicators.get('bb_mid', '--')} / "
        f"下轨 {indicators.get('bb_lower', '--')}",
        f"ATR(14): {indicators.get('atr', '--')}",
    ]

    if indicators.get("macd") is not None:
        lines.append(f"MACD: {indicators['macd']}")
    if indicators.get("adx") is not None:
        adx = indicators["adx"]
        strength = "弱" if adx < 20 else ("强" if adx > 40 else "中")
        lines.append(f"ADX(14): {adx} (趋势{strength})")

    lines.append(f"\n支撑位: ${indicators.get('support', 0):,.1f}")
    lines.append(f"阻力位: ${indicators.get('resistance', 0):,.1f}")

    return "\n".join(lines)


def generate_chart_data(inst_id: str = "BTC-USDT-SWAP", bar: str = "1H",
                        limit: int = 60) -> dict:
    """生成图表数据——供 Matplotlib 绘图使用。"""
    candles = fetch_candles(inst_id, bar, limit)

    result = {
        "inst_id": inst_id,
        "bar": bar,
        "timestamps": [c["ts"] for c in candles],
        "opens": [c["open"] for c in candles],
        "highs": [c["high"] for c in candles],
        "lows": [c["low"] for c in candles],
        "closes": [c["close"] for c in candles],
        "volumes": [c["vol"] for c in candles],
    }

    # 计算叠加指标
    upper, mid, lower = calc_bb(candles)
    result["bb_upper"] = [upper] * len(candles) if upper else []
    result["bb_mid"] = [mid] * len(candles) if mid else []
    result["bb_lower"] = [lower] * len(candles) if lower else []

    rsi_vals = []
    for i in range(len(candles)):
        sub = candles[max(0, i - 20):i + 1]
        r = calc_rsi(sub)
        rsi_vals.append(r if r else 50)
    result["rsi"] = rsi_vals

    return result

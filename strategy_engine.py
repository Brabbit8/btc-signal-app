#!/usr/bin/env python3
"""
策略引擎 — 多种策略模式，AI 可根据市场状态自动切换

模式说明：
  mean_reversion  — BB+RSI 均值回归：价格触及布林带边界 + RSI 确认反转
  trend_following — EMA 交叉 + ADX 趋势跟随：顺势交易，趋势强时介入
  breakout        — 突破近期高/低点：价格突破前 N 根 K 线区间

所有函数返回 (action: str | None, reason: str)
action ∈ {ENTER_LONG, ENTER_SHORT, EXIT_LONG, EXIT_SHORT, None}
"""

from btc_signal_bot import calc_bb, calc_rsi, calc_atr, calc_sma
from btc_strategy_adaptor import calc_ema, calc_adx

# ── 策略注册表 ──────────────────────────────────────────────

STRATEGY_MODES = {
    "mean_reversion": {
        "name": "均值回归",
        "description": "BB+RSI：价格触及布林带边界 + RSI 超买/超卖确认，适合震荡行情",
        "best_regime": ["ranging"],
    },
    "trend_following": {
        "name": "趋势跟随",
        "description": "EMA 交叉 + ADX 确认：顺势入场，适合单边趋势行情",
        "best_regime": ["trending_up", "trending_down"],
    },
    "breakout": {
        "name": "突破交易",
        "description": "价格突破近 N 根 K 线高/低点 + 成交量放大，适合高波动行情",
        "best_regime": ["trending_up", "trending_down"],
    },
}


def check_signal(candles: list, config: dict, position: str) -> tuple:
    """
    根据当前策略模式检测信号。
    返回 (action, reason)
    """
    mode = config.get("strategy_mode", "mean_reversion")
    if mode == "trend_following":
        return _check_trend_following(candles, config, position)
    elif mode == "breakout":
        return _check_breakout(candles, config, position)
    else:
        return _check_mean_reversion(candles, config, position)


# ── 模式 1: 均值回归 (BB + RSI) ─────────────────────────────

def _check_mean_reversion(candles, config, position):
    price = candles[-1]["close"]
    upper, mid, lower = calc_bb(candles, config.get("bb_period", 20),
                                config.get("bb_mult", 2.0))
    rsi = calc_rsi(candles, config.get("rsi_period", 14))

    if upper is None or rsi is None:
        return None, ""

    long_entry = price <= lower * 1.003 and rsi < config.get("rsi_oversold", 35)
    short_entry = price >= upper * 0.997 and rsi > config.get("rsi_overbought", 65)
    long_exit = position == "LONG" and price >= mid
    short_exit = position == "SHORT" and price <= mid

    if position == "LONG" and long_exit:
        return "EXIT_LONG", f"价格 {price:.1f} >= 中轨 {mid:.1f}"
    elif position == "SHORT" and short_exit:
        return "EXIT_SHORT", f"价格 {price:.1f} <= 中轨 {mid:.1f}"
    elif position == "NONE":
        if long_entry:
            return "ENTER_LONG", f"价格 {price:.1f} 触及下轨 {lower:.1f}, RSI={rsi:.1f}"
        elif short_entry:
            return "ENTER_SHORT", f"价格 {price:.1f} 触及上轨 {upper:.1f}, RSI={rsi:.1f}"

    return None, ""


# ── 模式 2: 趋势跟随 (EMA 交叉 + ADX) ───────────────────────

def _check_trend_following(candles, config, position):
    price = candles[-1]["close"]
    closes = [c["close"] for c in candles]

    if len(closes) < 50:
        return None, ""

    ema9 = calc_ema(closes, 9)
    ema21 = calc_ema(closes, 21)
    adx = calc_adx(candles, 14) or 0
    atr = calc_atr(candles, 14) or 0
    slope = _calc_slope(closes[-20:])

    if ema9 is None or ema21 is None:
        return None, ""

    # 趋势条件：ADX > 20 确认有趋势，EMA 排列确认方向
    uptrend = adx > 20 and ema9 > ema21 and slope > 0
    downtrend = adx > 20 and ema9 < ema21 and slope < 0

    # 入场：趋势中回调到 EMA9 附近
    near_ema9_up = uptrend and abs(price - ema9) / price < 0.005
    near_ema9_down = downtrend and abs(price - ema9) / price < 0.005

    # 离场：EMA 反向交叉或趋势消失
    exit_long = position == "LONG" and (ema9 < ema21 or adx < 15)
    exit_short = position == "SHORT" and (ema9 > ema21 or adx < 15)

    if position == "LONG" and exit_long:
        return "EXIT_LONG", f"EMA 死叉或 ADX={adx:.1f} 趋势减弱"
    elif position == "SHORT" and exit_short:
        return "EXIT_SHORT", f"EMA 金叉或 ADX={adx:.1f} 趋势减弱"
    elif position == "NONE":
        if near_ema9_up:
            return "ENTER_LONG", f"上升趋势 ADX={adx:.1f}, 回调至 EMA9={ema9:.1f}"
        elif near_ema9_down:
            return "ENTER_SHORT", f"下降趋势 ADX={adx:.1f}, 反弹至 EMA9={ema9:.1f}"

    return None, ""


# ── 模式 3: 突破交易 (区间突破 + 成交量) ─────────────────────

def _check_breakout(candles, config, position):
    price = candles[-1]["close"]
    vol = candles[-1]["vol"]
    lookback = config.get("breakout_lookback", 20)

    if len(candles) < lookback + 1:
        return None, ""

    prev_candles = candles[-(lookback + 1):-1]
    prev_high = max(c["high"] for c in prev_candles)
    prev_low = min(c["low"] for c in prev_candles)
    avg_vol = sum(c["vol"] for c in prev_candles[-10:]) / 10

    # 成交量放大确认
    vol_surge = vol > avg_vol * config.get("breakout_vol_mult", 1.2)

    break_up = price > prev_high and vol_surge
    break_down = price < prev_low and vol_surge

    # 离场：回到区间内
    exit_long = position == "LONG" and price < prev_high
    exit_short = position == "SHORT" and price > prev_low

    if position == "LONG" and exit_long:
        return "EXIT_LONG", f"价格 {price:.1f} 回到区间内 (<{prev_high:.1f})"
    elif position == "SHORT" and exit_short:
        return "EXIT_SHORT", f"价格 {price:.1f} 回到区间内 (>{prev_low:.1f})"
    elif position == "NONE":
        if break_up:
            return "ENTER_LONG", f"突破 {lookback}K 高点 {prev_high:.1f}, 量放大 {vol/avg_vol:.1f}x"
        elif break_down:
            return "ENTER_SHORT", f"跌破 {lookback}K 低点 {prev_low:.1f}, 量放大 {vol/avg_vol:.1f}x"

    return None, ""


# ── 工具函数 ────────────────────────────────────────────────

def _calc_slope(values, lookback=5):
    if len(values) < lookback:
        return 0
    recent = values[-lookback:]
    n = len(recent)
    x_mean = (n - 1) / 2
    y_mean = sum(recent) / n
    num = sum((i - x_mean) * (recent[i] - y_mean) for i in range(n))
    den = sum((i - x_mean) ** 2 for i in range(n))
    return num / den if den != 0 else 0


def get_mode_info(mode: str) -> dict:
    """获取策略模式的显示信息。"""
    return STRATEGY_MODES.get(mode, STRATEGY_MODES["mean_reversion"])


def get_available_modes() -> dict:
    """获取所有可用策略模式。"""
    return STRATEGY_MODES

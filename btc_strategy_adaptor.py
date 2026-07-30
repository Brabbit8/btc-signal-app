#!/usr/bin/env python3
"""
BTC Strategy Adaptor — analyzes market regime across timeframes
and auto-adjusts btc_signal_config.json parameters.
Uses OKX public REST API + local indicator calculations only.
Run: python btc_strategy_adaptor.py
"""

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_PATH = SCRIPT_DIR / "btc_signal_config.json"
LOG_PATH = SCRIPT_DIR / "btc_signal.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [ADAPTOR] %(message)s",
    handlers=[logging.FileHandler(LOG_PATH, encoding="utf-8"), logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("btc_adaptor")


def fetch_candles(inst_id, bar, limit=50):
    url = "https://www.okx.com/api/v5/market/candles"
    resp = requests.get(url, params={"instId": inst_id, "bar": bar, "limit": limit}, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    if data["code"] != "0":
        raise RuntimeError(f"OKX API error: {data['msg']}")
    candles = []
    for row in reversed(data["data"]):
        candles.append({"ts": int(row[0]), "open": float(row[1]), "high": float(row[2]),
                        "low": float(row[3]), "close": float(row[4]), "vol": float(row[5])})
    return candles


def calc_sma(values, period):
    return sum(values[-period:]) / period if len(values) >= period else None


def calc_ema(values, period):
    if len(values) < period:
        return None
    k = 2 / (period + 1)
    ema = sum(values[:period]) / period
    for v in values[period:]:
        ema = v * k + ema * (1 - k)
    return ema


def calc_atr(candles, period=14):
    if len(candles) < period + 1:
        return None
    trs = [max(candles[i]["high"] - candles[i]["low"],
               abs(candles[i]["high"] - candles[i - 1]["close"]),
               abs(candles[i]["low"] - candles[i - 1]["close"]))
           for i in range(1, len(candles))]
    return sum(trs[-period:]) / period


def calc_adx(candles, period=14):
    """Average Directional Index — trend strength 0-100.
    < 20 = ranging, 20-25 = weak trend, 25-50 = strong trend, > 50 = extreme trend."""
    if len(candles) < period * 2:
        return None
    trs, pdms, ndms = [], [], []
    for i in range(1, len(candles)):
        high_diff = candles[i]["high"] - candles[i - 1]["high"]
        low_diff = candles[i - 1]["low"] - candles[i]["low"]
        tr = max(candles[i]["high"] - candles[i]["low"],
                 abs(candles[i]["high"] - candles[i - 1]["close"]),
                 abs(candles[i]["low"] - candles[i - 1]["close"]))
        trs.append(tr)
        pdms.append(high_diff if high_diff > 0 and high_diff > low_diff else 0)
        ndms.append(low_diff if low_diff > 0 and low_diff > high_diff else 0)

    atr_val = sum(trs[-period:]) / period
    if atr_val == 0:
        return None

    pdi = (sum(pdms[-period:]) / period) / atr_val * 100
    ndi = (sum(ndms[-period:]) / period) / atr_val * 100
    dx = abs(pdi - ndi) / (pdi + ndi) * 100 if (pdi + ndi) > 0 else 0
    return dx


def calc_slope(values, lookback=5):
    """Simple linear slope — positive = uptrend, negative = downtrend."""
    if len(values) < lookback:
        return 0
    recent = values[-lookback:]
    n = len(recent)
    x_mean = (n - 1) / 2
    y_mean = sum(recent) / n
    num = sum((i - x_mean) * (recent[i] - y_mean) for i in range(n))
    den = sum((i - x_mean) ** 2 for i in range(n))
    return num / den if den != 0 else 0


def detect_regime(candles_15m, candles_1h, candles_4h):
    """Classify market regime based on multi-timeframe analysis.
    Returns: (regime, confidence, detail_dict)"""

    # ADX on 4H for primary trend assessment
    adx_4h = calc_adx(candles_4h)
    closes_4h = [c["close"] for c in candles_4h]
    slope_4h = calc_slope(closes_4h, lookback=10)

    # ADX on 1H for shorter-term context
    adx_1h = calc_adx(candles_1h)

    # Volatility: ATR as % of price
    atr_15m = calc_atr(candles_15m)
    price = candles_15m[-1]["close"]
    vol_pct = (atr_15m / price * 100) if atr_15m else 0

    # EMA alignment
    closes_1h = [c["close"] for c in candles_1h]
    ema20_1h = calc_ema(closes_1h, 20)
    ema50_1h = calc_ema(closes_1h, 50) if len(closes_1h) >= 50 else None

    detail = {
        "price": round(price, 1),
        "adx_4h": round(adx_4h, 1) if adx_4h else None,
        "adx_1h": round(adx_1h, 1) if adx_1h else None,
        "slope_4h": round(slope_4h, 4),
        "vol_pct_15m": round(vol_pct, 3),
        "ema_alignment": "bullish" if ema20_1h and ema50_1h and ema20_1h > ema50_1h else "bearish",
    }

    if adx_4h is None:
        return "ranging", 0.3, detail

    # Ranging: ADX < 22
    if adx_4h < 22:
        return "ranging", round(1 - adx_4h / 22, 2), detail

    # Trending
    if slope_4h > 0 and detail["ema_alignment"] == "bullish":
        strength = min(adx_4h / 40, 1.0)
        return "trending_up", round(strength, 2), detail
    elif slope_4h < 0 and detail["ema_alignment"] == "bearish":
        strength = min(adx_4h / 40, 1.0)
        return "trending_down", round(strength, 2), detail
    else:
        # ADX high but direction unclear — chop/transition
        return "ranging", 0.5, detail


def adapt_config(config, regime, confidence, detail):
    """Adjust config parameters based on market regime."""
    changes = []

    if regime == "ranging":
        # Mean-reversion: wider BB sensitivity, tighter RSI thresholds
        new_rsi_os = min(40, config["rsi_oversold"] + int((1 - confidence) * 5))
        new_rsi_ob = max(60, config["rsi_overbought"] - int((1 - confidence) * 5))
        new_cooldown = max(30, config["cooldown_minutes"] - int(confidence * 60))
        new_bb_mult = min(2.5, config["bb_mult"] + 0.1)

        if config["rsi_oversold"] != new_rsi_os:
            changes.append(f"rsi_oversold: {config['rsi_oversold']} -> {new_rsi_os} (震荡放宽)")
            config["rsi_oversold"] = new_rsi_os
        if config["rsi_overbought"] != new_rsi_ob:
            changes.append(f"rsi_overbought: {config['rsi_overbought']} -> {new_rsi_ob} (震荡放宽)")
            config["rsi_overbought"] = new_rsi_ob
        if config["cooldown_minutes"] != new_cooldown:
            changes.append(f"cooldown_minutes: {config['cooldown_minutes']} -> {new_cooldown}")
            config["cooldown_minutes"] = new_cooldown

    elif regime in ("trending_up", "trending_down"):
        # Trend: tighter trigger, longer cooldown, directional bias
        new_rsi_os = max(25, config["rsi_oversold"] - int(confidence * 5))
        new_rsi_ob = min(75, config["rsi_overbought"] + int(confidence * 5))
        new_cooldown = min(240, config["cooldown_minutes"] + int(confidence * 60))
        new_bb_mult = max(1.8, config["bb_mult"] - 0.1)

        if config["rsi_oversold"] != new_rsi_os:
            changes.append(f"rsi_oversold: {config['rsi_oversold']} -> {new_rsi_os} (趋势收紧)")
            config["rsi_oversold"] = new_rsi_os
        if config["rsi_overbought"] != new_rsi_ob:
            changes.append(f"rsi_overbought: {config['rsi_overbought']} -> {new_rsi_ob} (趋势收紧)")
            config["rsi_overbought"] = new_rsi_ob
        if config["cooldown_minutes"] != new_cooldown:
            changes.append(f"cooldown_minutes: {config['cooldown_minutes']} -> {new_cooldown}")
            config["cooldown_minutes"] = new_cooldown

    config["bb_mult"] = round(new_bb_mult, 1)
    return changes


def main():
    config = json.load(open(CONFIG_PATH, "r", encoding="utf-8"))

    # Fetch multi-timeframe data
    candles_15m = fetch_candles("BTC-USDT-SWAP", "15m", limit=50)
    candles_1h = fetch_candles("BTC-USDT-SWAP", "1H", limit=60)
    candles_4h = fetch_candles("BTC-USDT-SWAP", "4H", limit=40)

    # Detect regime
    regime, confidence, detail = detect_regime(candles_15m, candles_1h, candles_4h)

    log.info(f"Regime: {regime} (confidence={confidence})")
    log.info(f"  ADX_4H={detail['adx_4h']} ADX_1H={detail['adx_1h']} "
             f"Price={detail['price']} Vol%={detail['vol_pct_15m']}% "
             f"EMA={detail['ema_alignment']}")

    # Adapt
    old_config = dict(config)
    changes = adapt_config(config, regime, confidence, detail)

    if changes:
        json.dump(config, open(CONFIG_PATH, "w", encoding="utf-8"), indent=2)
        log.info(f"Config updated: {'; '.join(changes)}")
    else:
        log.info("No config changes needed")

    # Summary
    log.info(f"Active params: BB_mult={config['bb_mult']} "
             f"RSI=[{config['rsi_oversold']},{config['rsi_overbought']}] "
             f"Cooldown={config['cooldown_minutes']}min")
    log.info("=== Adaptor Done ===\n")


if __name__ == "__main__":
    main()

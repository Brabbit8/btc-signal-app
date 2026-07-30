#!/usr/bin/env python3
"""
OKX BTC Signal Bot — BB(20,2) + RSI(14) Range Strategy
Detects ENTER_LONG / EXIT_LONG / ENTER_SHORT / EXIT_SHORT signals
and sends webhook to OKX Signal Bot for auto-execution.
Run: python btc_signal_bot.py
"""

import json
import time
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_PATH = SCRIPT_DIR / "btc_signal_config.json"
STATE_PATH = SCRIPT_DIR / "btc_signal_state.json"
LOG_PATH = SCRIPT_DIR / "btc_signal.log"
ALERT_PATH = SCRIPT_DIR / "btc_signal_alert.txt"
STATUS_PATH = SCRIPT_DIR / "btc_signal_status.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_PATH, encoding="utf-8"), logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("btc_signal")


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_state():
    if STATE_PATH.exists():
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"position": "NONE"}


def save_state(state):
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def fetch_candles(inst_id, bar, limit=30):
    url = "https://www.okx.com/api/v5/market/candles"
    params = {"instId": inst_id, "bar": bar, "limit": limit}
    resp = requests.get(url, params=params, timeout=10)
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


def calc_std(values, period):
    if len(values) < period:
        return None
    avg = calc_sma(values, period)
    return (sum((v - avg) ** 2 for v in values[-period:]) / period) ** 0.5


def calc_bb(candles, period=20, mult=2.0):
    closes = [c["close"] for c in candles]
    if len(closes) < period:
        return None, None, None
    mid = calc_sma(closes, period)
    std = calc_std(closes, period)
    return mid + std * mult, mid, mid - std * mult


def calc_rsi(candles, period=14):
    closes = [c["close"] for c in candles]
    if len(closes) < period + 1:
        return None
    gains, losses = [], []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        gains.append(diff if diff > 0 else 0)
        losses.append(-diff if diff < 0 else 0)
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100.0
    return 100.0 - (100.0 / (1.0 + avg_gain / avg_loss))


def calc_atr(candles, period=14):
    if len(candles) < period + 1:
        return None
    trs = [max(candles[i]["high"] - candles[i]["low"],
               abs(candles[i]["high"] - candles[i - 1]["close"]),
               abs(candles[i]["low"] - candles[i - 1]["close"]))
           for i in range(1, len(candles))]
    return sum(trs[-period:]) / period


def send_webhook(config, action):
    """Send signal to OKX webhook. Matches OKX Custom Signal template exactly."""
    is_entry = action.startswith("ENTER_")
    payload = {
        "action": action,
        "instrument": config["instrument"],
        "signalToken": config["signal_token"],
        "timestamp": str(int(time.time() * 1000)),
        "maxLag": "300",
        "orderType": "market",
        "orderPriceOffset": "",
        "investmentType": config["entry_investment_type"] if is_entry else config["exit_investment_type"],
        "amount": config["entry_amount"] if is_entry else config["exit_amount"],
    }
    log.info(f">>> WEBHOOK: {action}")
    log.info(f"    {json.dumps(payload)}")
    resp = requests.post(config["webhook_url"], json=payload, timeout=10)
    log.info(f"    Response: {resp.status_code} | {resp.text[:300]}")
    return resp.ok


def main():
    config = load_config()
    state = load_state()
    now = datetime.now(timezone.utc)

    if "PASTE" in config["signal_token"]:
        log.error("CONFIG NOT SET - edit btc_signal_config.json")
        return

    # Fetch
    candles = fetch_candles(config["instrument"], config["bar"], limit=30)
    last = candles[-1]
    price = last["close"]

    # Indicators
    upper, mid, lower = calc_bb(candles, config["bb_period"], config["bb_mult"])
    rsi = calc_rsi(candles, config["rsi_period"])
    atr = calc_atr(candles, 14)

    # Cooldown
    last_ts = state.get("last_signal_ts", 0)
    cooldown_ok = (now.timestamp() - last_ts) >= config["cooldown_minutes"] * 60
    position = state.get("position", "NONE")

    # === Signal Logic ===
    long_entry = price <= lower * 1.003 and rsi < config["rsi_oversold"]
    short_entry = price >= upper * 0.997 and rsi > config["rsi_overbought"]
    long_exit = position == "LONG" and price >= mid
    short_exit = position == "SHORT" and price <= mid

    action = None
    reason = ""

    # Exit always allowed (cooldown only restricts entry)
    if position == "LONG" and long_exit:
        action = "EXIT_LONG"
        reason = f"Price {price:.1f} >= mid BB {mid:.1f}, take profit"
    elif position == "SHORT" and short_exit:
        action = "EXIT_SHORT"
        reason = f"Price {price:.1f} <= mid BB {mid:.1f}, take profit"
    elif cooldown_ok and position == "NONE":
        if long_entry:
            action = "ENTER_LONG"
            reason = f"Price {price:.1f} at lower BB {lower:.1f}, RSI={rsi:.1f} oversold"
        elif short_entry:
            action = "ENTER_SHORT"
            reason = f"Price {price:.1f} at upper BB {upper:.1f}, RSI={rsi:.1f} overbought"

    # Status display
    status_parts = [
        f"Price={price:.1f}",
        f"BB[U={upper:.1f} M={mid:.1f} L={lower:.1f}]",
        f"RSI={rsi:.1f}",
        f"ATR={atr:.1f}" if atr else "",
        f"Position={position}",
    ]
    if not cooldown_ok:
        remaining = int(config["cooldown_minutes"] * 60 - (now.timestamp() - last_ts))
        status_parts.append(f"COOLDOWN({remaining}s)")

    log.info(" | ".join(p for p in status_parts if p))

    # Signal triggered — update state, write alert, attempt webhook
    if action:
        log.info(f"SIGNAL: {action} — {reason}")
        ok = send_webhook(config, action)
        if not ok:
            log.error("Webhook FAILED - check proxy/network")
        # Webhook may fail but we still record the signal
        state["last_signal_ts"] = now.timestamp()
        state["last_signal_action"] = action
        state["last_signal_price"] = price
        if action.startswith("ENTER_"):
            state["position"] = "LONG" if "LONG" in action else "SHORT"
            state["entry_price"] = price
        elif action.startswith("EXIT_"):
            entry_price = state.get("entry_price", "?")
            pnl = price - entry_price if "LONG" in action else entry_price - price
            log.info(f"TRADE CLOSED: Entry={entry_price} Exit={price:.1f} PnL={pnl:.1f}")
            state["position"] = "NONE"
        save_state(state)

        alert_msg = (
            f"[{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}]\n"
            f"SIGNAL: {action}\n"
            f"Price: {price:.1f}  |  RSI: {rsi:.1f}\n"
            f"BB: U={upper:.1f} M={mid:.1f} L={lower:.1f}\n"
            f"ATR: {atr:.1f}\n"
            f"Reason: {reason}\n"
            f"--- Open Claude Code and tell me: 'execute signal from alert file' ---\n"
        )
        with open(ALERT_PATH, "w", encoding="utf-8") as f:
            f.write(alert_msg)
        log.info(f"Alert written to {ALERT_PATH}")
    else:
        # Remove stale alert file
        if ALERT_PATH.exists():
            ALERT_PATH.unlink()
        long_ready = "READY" if long_entry else "-"
        short_ready = "READY" if short_entry else "-"
        log.info(f"No signal | Long:{long_ready} Short:{short_ready}")

    # Always write status file for quick check
    status = {
        "time_utc": datetime.now(timezone.utc).isoformat(),
        "price": price,
        "bb_upper": round(upper, 1) if upper else None,
        "bb_mid": round(mid, 1) if mid else None,
        "bb_lower": round(lower, 1) if lower else None,
        "rsi": round(rsi, 1) if rsi else None,
        "atr": round(atr, 1) if atr else None,
        "position": state.get("position", "NONE"),
        "entry_price": state.get("entry_price"),
        "cooldown_remaining_s": max(0, int(config["cooldown_minutes"] * 60 - (now.timestamp() - last_ts))) if not state.get("position", "NONE") == "NONE" or last_ts else 0,
        "signal": action,
    }
    with open(STATUS_PATH, "w", encoding="utf-8") as f:
        json.dump(status, f, indent=2)

    log.info("=== Done ===\n")


if __name__ == "__main__":
    loop_mode = "--loop" in sys.argv
    interval = 300  # 5 minutes

    log.info(f"=== BTC Signal Bot started (mode={'loop' if loop_mode else 'once'}) ===")
    if loop_mode:
        log.info(f"Checking every {interval}s. Press Ctrl+C to stop.")

    try:
        while True:
            try:
                main()
            except Exception as e:
                log.error(f"Run failed: {e}")
            if not loop_mode:
                break
            time.sleep(interval)
    except KeyboardInterrupt:
        log.info("Stopped by user.")

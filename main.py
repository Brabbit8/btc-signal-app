#!/usr/bin/env python3
"""
BTC Signal App — Auto signal detection + periodic AI analysis
Double-click to run, or: python main.py
"""

import json
import os
import sys
import time
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

# Import local modules
from btc_signal_bot import (
    fetch_candles, calc_bb, calc_rsi, calc_atr,
    load_config, load_state, save_state,
)
from btc_strategy_adaptor import fetch_candles as fetch_candles_adaptor
from btc_strategy_adaptor import calc_adx, calc_ema, calc_slope, calc_atr as adaptor_calc_atr

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(SCRIPT_DIR / "btc_signal.log", encoding="utf-8"), logging.StreamHandler()],
)
log = logging.getLogger("btc_app")

# ── App State ──────────────────────────────────────────────
CONFIG_PATH = SCRIPT_DIR / "btc_signal_config.json"
STATE_PATH = SCRIPT_DIR / "btc_signal_state.json"
ALERT_PATH = SCRIPT_DIR / "btc_signal_alert.txt"
STATUS_PATH = SCRIPT_DIR / "btc_signal_status.json"
APIKEY_PATH = SCRIPT_DIR / "apikey.txt"

app_state = {
    "running": True,
    "price": 0, "rsi": 0, "atr": 0,
    "bb_upper": 0, "bb_mid": 0, "bb_lower": 0,
    "position": "NONE", "signal": None,
    "cooldown_s": 0, "regime": "?", "regime_conf": 0,
    "last_ai": "never", "last_signal_time": "never",
    "status_msg": "Starting...",
}

lock = threading.Lock()


# ── AI Analysis ────────────────────────────────────────────
def get_api_key():
    if APIKEY_PATH.exists():
        return APIKEY_PATH.read_text(encoding="utf-8").strip()
    return None


def save_api_key(key):
    APIKEY_PATH.write_text(key.strip(), encoding="utf-8")


def call_ai_analysis(config):
    """Call DeepSeek API for market analysis. Returns dict with param adjustments or None."""
    api_key = get_api_key()
    if not api_key:
        return None

    try:
        from anthropic import Anthropic
    except ImportError:
        log.error("anthropic not installed. Run: pip install anthropic")
        return None

    # Fetch multi-timeframe data
    try:
        c_15m = fetch_candles("BTC-USDT-SWAP", "15m", limit=50)
        c_1h = fetch_candles("BTC-USDT-SWAP", "1H", limit=60)
        price = c_15m[-1]["close"]
    except Exception as e:
        log.error(f"Data fetch failed: {e}")
        return None

    # Calculate indicators
    upper, mid, lower = calc_bb(c_15m)
    rsi = calc_rsi(c_15m)
    atr = calc_atr(c_15m)
    adx = calc_adx(c_1h)
    closes_1h = [c["close"] for c in c_1h]
    ema20 = calc_ema(closes_1h, 20)
    ema50 = calc_ema(closes_1h, 50) if len(closes_1h) >= 50 else None

    ctx = f"""Current BTC market data (15m K-line):
Price: ${price:.1f}
BB: Upper=${upper:.1f} Mid=${mid:.1f} Lower=${lower:.1f} (mult={config['bb_mult']})
RSI(14,15m): {rsi:.1f}
ATR(14,15m): {atr:.1f}
ADX(14,1H): {adx:.1f}
EMA20(1H): {ema20:.1f}
EMA50(1H): {ema50:.1f}
Current config: rsi_oversold={config['rsi_oversold']}, rsi_overbought={config['rsi_overbought']}, cooldown_minutes={config['cooldown_minutes']}, bb_mult={config['bb_mult']}

Analyze the market regime (ranging / trending_up / trending_down). Then suggest parameter adjustments. Reply with ONLY this JSON, no other text:
{{"regime":"<ranging|trending_up|trending_down>","confidence":<0-1>,"rsi_oversold":<25-45>,"rsi_overbought":<55-75>,"cooldown_minutes":<30-240>,"bb_mult":<1.5-2.5>,"reason":"<one short sentence in English>"}}"""

    try:
        client = Anthropic(base_url="https://api.deepseek.com/anthropic", api_key=api_key)
        response = client.messages.create(
            model="deepseek-v4-pro",
            max_tokens=2000,
            messages=[{"role": "user", "content": ctx}],
        )
        text = ""
        for block in response.content:
            if hasattr(block, "text"):
                text += block.text
            elif hasattr(block, "thinking"):
                # DeepSeek reasoning model sometimes puts answer in thinking block
                text += block.thinking
        text = text.strip()
        if not text:
            log.error("AI returned empty text")
            return None
        # Extract JSON from response
        start = text.find("{")
        end = text.rfind("}") + 1
        if start != -1 and end > start:
            result = json.loads(text[start:end])
            log.info(f"AI Analysis: {result.get('regime')} conf={result.get('confidence')} — {result.get('reason')}")
            return result
    except Exception as e:
        log.error(f"AI API error: {e}")
    return None


def run_ai_analysis():
    """Periodic AI analysis thread target."""
    global app_state
    while app_state["running"]:
        try:
            with lock:
                app_state["status_msg"] = "AI analyzing..."
            config = load_config()
            result = call_ai_analysis(config)
            if result:
                # Apply AI suggestions to config
                config["rsi_oversold"] = int(result.get("rsi_oversold", config["rsi_oversold"]))
                config["rsi_overbought"] = int(result.get("rsi_overbought", config["rsi_overbought"]))
                config["cooldown_minutes"] = int(result.get("cooldown_minutes", config["cooldown_minutes"]))
                config["bb_mult"] = float(result.get("bb_mult", config["bb_mult"]))
                with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                    json.dump(config, f, indent=2)
                with lock:
                    app_state["regime"] = result.get("regime", "?")
                    app_state["regime_conf"] = result.get("confidence", 0)
                    app_state["last_ai"] = datetime.now().strftime("%H:%M")
                    app_state["status_msg"] = "AI analysis done"
            else:
                with lock:
                    app_state["status_msg"] = "AI skipped (no key or error)"
        except Exception as e:
            log.error(f"AI run failed: {e}")
            with lock:
                app_state["status_msg"] = f"AI error: {e}"

        # Sleep 2 hours between AI runs
        for _ in range(7200):
            if not app_state["running"]:
                return
            time.sleep(1)


# ── Signal Check ──────────────────────────────────────────
def run_signal_check():
    """Periodic signal detection thread target."""
    global app_state
    while app_state["running"]:
        try:
            config = load_config()
            state = load_state()
            now = datetime.now(timezone.utc)

            candles = fetch_candles(config["instrument"], config["bar"], limit=30)
            price = candles[-1]["close"]
            upper, mid, lower = calc_bb(candles, config["bb_period"], config["bb_mult"])
            rsi = calc_rsi(candles, config["rsi_period"])
            atr = calc_atr(candles, 14)

            last_ts = state.get("last_signal_ts", 0)
            cooldown_ok = (now.timestamp() - last_ts) >= config["cooldown_minutes"] * 60
            position = state.get("position", "NONE")

            long_entry = price <= lower * 1.003 and rsi < config["rsi_oversold"]
            short_entry = price >= upper * 0.997 and rsi > config["rsi_overbought"]
            long_exit = position == "LONG" and price >= mid
            short_exit = position == "SHORT" and price <= mid

            action = None
            reason = ""

            if position == "LONG" and long_exit:
                action = "EXIT_LONG"
                reason = f"Price {price:.1f} >= mid BB {mid:.1f}"
            elif position == "SHORT" and short_exit:
                action = "EXIT_SHORT"
                reason = f"Price {price:.1f} <= mid BB {mid:.1f}"
            elif cooldown_ok and position == "NONE":
                if long_entry:
                    action = "ENTER_LONG"
                    reason = f"Price {price:.1f} at lower BB {lower:.1f}, RSI={rsi:.1f}"
                elif short_entry:
                    action = "ENTER_SHORT"
                    reason = f"Price {price:.1f} at upper BB {upper:.1f}, RSI={rsi:.1f}"

            cooldown_s = max(0, int(config["cooldown_minutes"] * 60 - (now.timestamp() - last_ts)))

            with lock:
                app_state["price"] = price
                app_state["rsi"] = rsi or 0
                app_state["atr"] = atr or 0
                app_state["bb_upper"] = upper or 0
                app_state["bb_mid"] = mid or 0
                app_state["bb_lower"] = lower or 0
                app_state["position"] = position
                app_state["cooldown_s"] = cooldown_s
                app_state["status_msg"] = "Idle"

            if action:
                log.info(f"SIGNAL: {action} - {reason}")
                with lock:
                    app_state["signal"] = action
                    app_state["last_signal_time"] = datetime.now().strftime("%H:%M:%S")
                    app_state["status_msg"] = f"SIGNAL: {action}"

                # Write alert file
                alert_msg = (
                    f"[{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}]\n"
                    f"SIGNAL: {action}\n"
                    f"Price: {price:.1f}  |  RSI: {rsi:.1f}\n"
                    f"BB: U={upper:.1f} M={mid:.1f} L={lower:.1f}  |  ATR: {atr:.1f}\n"
                    f"Reason: {reason}\n"
                    f"--- Open Claude Code and say: 'execute signal from alert file' ---\n"
                )
                ALERT_PATH.write_text(alert_msg, encoding="utf-8")

                # Update state
                state["last_signal_ts"] = now.timestamp()
                state["last_signal_action"] = action
                state["last_signal_price"] = price
                if action.startswith("ENTER_"):
                    state["position"] = "LONG" if "LONG" in action else "SHORT"
                    state["entry_price"] = price
                elif action.startswith("EXIT_"):
                    entry_price = state.get("entry_price", "?")
                    pnl = price - entry_price if "LONG" in action else entry_price - price
                    log.info(f"TRADE CLOSED: PnL={pnl:.1f}")
                    state["position"] = "NONE"
                save_state(state)
            else:
                with lock:
                    app_state["signal"] = None
                if ALERT_PATH.exists():
                    ALERT_PATH.unlink()

            # Write status JSON
            status = {
                "time_utc": datetime.now(timezone.utc).isoformat(),
                "price": price, "rsi": round(rsi, 1) if rsi else None,
                "bb_upper": round(upper, 1) if upper else None,
                "bb_mid": round(mid, 1) if mid else None,
                "bb_lower": round(lower, 1) if lower else None,
                "atr": round(atr, 1) if atr else None,
                "position": position, "signal": action,
            }
            with open(STATUS_PATH, "w", encoding="utf-8") as f:
                json.dump(status, f, indent=2)

        except Exception as e:
            log.error(f"Signal check failed: {e}")
            with lock:
                app_state["status_msg"] = f"Error: {e}"

        for _ in range(300):
            if not app_state["running"]:
                return
            time.sleep(1)


# ── Console UI ─────────────────────────────────────────────
def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def render_ui():
    s = app_state
    bb_w = s["bb_upper"] - s["bb_lower"]
    price_pct = (s["price"] - s["bb_lower"]) / bb_w * 100 if bb_w > 0 else 50

    lines = [
        "╔══════════════════════════════════════════════════╗",
        "║        BTC Signal App v1.0                        ║",
        f"║        {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}                              ║",
        "╠══════════════════════════════════════════════════╣",
        f"║  Price:  ${s['price']:>10,.1f}                      ║",
        f"║  RSI:     {s['rsi']:>6.1f}    Position: {s['position']:<5}                  ║",
        f"║  BB:      U={s['bb_upper']:>8,.1f}  M={s['bb_mid']:>8,.1f}  L={s['bb_lower']:>8,.1f}  ║",
        f"║  ATR:     {s['atr']:>6.1f}                             ║",
        "╠══════════════════════════════════════════════════╣",
    ]

    if s["signal"]:
        lines.append(f"║  >>> SIGNAL: {s['signal']} @ {s['last_signal_time']}          ║")
    elif s["cooldown_s"] > 0:
        m, sec = divmod(s["cooldown_s"], 60)
        lines.append(f"║  Cooldown: {m}min {sec}s remaining                  ║")
    else:
        lines.append("║  Waiting for signal...                            ║")

    lines += [
        "╠══════════════════════════════════════════════════╣",
        f"║  AI: Last={s['last_ai']:<8}  Regime={s['regime']:<12} ({s['regime_conf']:.0%})     ║",
        f"║  Status: {s['status_msg'][:45]:<45} ║",
        "╠══════════════════════════════════════════════════╣",
        "║  [R] Refresh  [A] AI Analysis  [Q] Quit         ║",
        "╚══════════════════════════════════════════════════╝",
    ]
    return "\n".join(lines)


def keyboard_listener():
    """Listen for keyboard input on Windows."""
    global app_state
    try:
        import msvcrt
        while app_state["running"]:
            if msvcrt.kbhit():
                key = msvcrt.getch()
                if key in (b'q', b'Q'):
                    app_state["running"] = False
                    break
                elif key in (b'r', b'R'):
                    with lock:
                        app_state["status_msg"] = "Manual refresh..."
                elif key in (b'a', b'A'):
                    with lock:
                        app_state["status_msg"] = "Starting AI analysis..."
                    threading.Thread(target=run_ai_analysis_once, daemon=True).start()
            time.sleep(0.1)
    except ImportError:
        # Non-Windows fallback
        pass


def run_ai_analysis_once():
    global app_state
    config = load_config()
    result = call_ai_analysis(config)
    if result:
        config["rsi_oversold"] = int(result.get("rsi_oversold", config["rsi_oversold"]))
        config["rsi_overbought"] = int(result.get("rsi_overbought", config["rsi_overbought"]))
        config["cooldown_minutes"] = int(result.get("cooldown_minutes", config["cooldown_minutes"]))
        config["bb_mult"] = float(result.get("bb_mult", config["bb_mult"]))
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
        with lock:
            app_state["regime"] = result.get("regime", "?")
            app_state["regime_conf"] = result.get("confidence", 0)
            app_state["last_ai"] = datetime.now().strftime("%H:%M")
            app_state["status_msg"] = "AI analysis done"
    else:
        with lock:
            app_state["status_msg"] = "AI failed (no key or error)"


# ── Main ──────────────────────────────────────────────────
def main():
    print("BTC Signal App v1.0 starting...")

    # Auto-initialize config from example if missing
    if not CONFIG_PATH.exists():
        example = SCRIPT_DIR / "btc_signal_config.example.json"
        if example.exists():
            import shutil
            shutil.copy(example, CONFIG_PATH)
            print("Created btc_signal_config.json from example. Edit it to add your signal token.")

    # Check API key
    if not get_api_key():
        print("\nNo DeepSeek API key found.")
        key = input("Enter your DeepSeek API key (or press Enter to skip AI features): ").strip()
        if key:
            save_api_key(key)
            print("API key saved.")
        else:
            print("AI analysis disabled. Only signal detection will run.")

    # Run initial signal check immediately
    print("Running initial signal check...")
    try:
        config = load_config()
        candles = fetch_candles(config["instrument"], config["bar"], limit=30)
        price = candles[-1]["close"]
        upper, mid, lower = calc_bb(candles, config["bb_period"], config["bb_mult"])
        rsi = calc_rsi(candles, config["rsi_period"])
        atr = calc_atr(candles, 14)
        with lock:
            app_state["price"] = price
            app_state["rsi"] = rsi or 0
            app_state["atr"] = atr or 0
            app_state["bb_upper"] = upper or 0
            app_state["bb_mid"] = mid or 0
            app_state["bb_lower"] = lower or 0
            app_state["position"] = load_state().get("position", "NONE")
            app_state["status_msg"] = "Ready"
    except Exception as e:
        log.error(f"Initial check failed: {e}")

    # Start background threads
    signal_thread = threading.Thread(target=run_signal_check, daemon=True, name="signal")
    signal_thread.start()

    ai_thread = threading.Thread(target=run_ai_analysis, daemon=True, name="ai")
    ai_thread.start()

    kb_thread = threading.Thread(target=keyboard_listener, daemon=True, name="keyboard")
    kb_thread.start()

    # Main UI loop
    try:
        while app_state["running"]:
            clear_screen()
            print(render_ui())
            time.sleep(2)
    except KeyboardInterrupt:
        app_state["running"] = False

    clear_screen()
    print("BTC Signal App stopped.")
    log.info("App stopped by user.")


if __name__ == "__main__":
    main()

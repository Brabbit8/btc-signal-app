#!/usr/bin/env python3
"""
BTC Signal App v2.0 — 通用化桌面应用
支持多 AI 平台、内置技术分析/交易计划/新闻情绪等技能
启动: python main.py
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

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext

from config_manager import (
    load_config, save_config, get_ai_config, get_provider_models,
    AI_PROVIDERS, is_configured, init_config,
)
from ai_client import AIClient
from btc_signal_bot import (
    fetch_candles, calc_bb, calc_rsi, calc_atr, load_state, save_state,
)
from btc_strategy_adaptor import calc_adx, calc_ema, calc_slope
from skills import market_data, technical, sentiment, trading_plan

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(SCRIPT_DIR / "btc_signal.log", encoding="utf-8"),
              logging.StreamHandler()],
)
log = logging.getLogger("btc_app")

# ── Paths ──────────────────────────────────────────────────
CONFIG_PATH = SCRIPT_DIR / "btc_signal_config.json"
STATE_PATH = SCRIPT_DIR / "btc_signal_state.json"
ALERT_PATH = SCRIPT_DIR / "btc_signal_alert.txt"
STATUS_PATH = SCRIPT_DIR / "btc_signal_status.json"
APIKEY_PATH = SCRIPT_DIR / "apikey.txt"

# ── Shared State ───────────────────────────────────────────
app_state = {
    "running": True,
    "price": 0, "rsi": 0, "atr": 0,
    "bb_upper": 0, "bb_mid": 0, "bb_lower": 0,
    "position": "NONE", "signal": None,
    "cooldown_s": 0, "regime": "?", "regime_conf": 0,
    "last_ai": "从未", "last_signal_time": "从未",
    "status_msg": "启动中...",
}
lock = threading.Lock()

# ── Chinese Labels ─────────────────────────────────────────
REGIME_CN = {
    "ranging": "震荡", "trending_up": "上升趋势",
    "trending_down": "下降趋势", "?": "未知",
}
POSITION_CN = {"NONE": "无持仓", "LONG": "多头", "SHORT": "空头"}
SIGNAL_CN = {
    "ENTER_LONG": "做多信号", "ENTER_SHORT": "做空信号",
    "EXIT_LONG": "多头离场", "EXIT_SHORT": "空头离场",
}


# ── Background: AI Analysis ────────────────────────────────
def call_ai_analysis(config: dict):
    """调用 AI 进行市场分析。返回 regime 分析 dict 或 None。"""
    ai_config = get_ai_config(config)
    client = AIClient(ai_config)
    if not client.enabled:
        return None

    try:
        c_15m = fetch_candles("BTC-USDT-SWAP", "15m", limit=50)
        c_1h = fetch_candles("BTC-USDT-SWAP", "1H", limit=60)
        price = c_15m[-1]["close"]
    except Exception as e:
        log.error(f"数据获取失败: {e}")
        return None

    upper, mid, lower = calc_bb(c_15m)
    rsi = calc_rsi(c_15m)
    atr = calc_atr(c_15m)
    adx = calc_adx(c_1h)
    closes_1h = [c["close"] for c in c_1h]
    ema20 = calc_ema(closes_1h, 20)
    ema50 = calc_ema(closes_1h, 50) if len(closes_1h) >= 50 else None

    system_prompt = "You are a crypto market analyst. Reply with ONLY JSON."
    user_msg = f"""Current BTC data (15m):
Price: ${price:.1f} | RSI: {rsi:.1f} | ATR: {atr:.1f}
BB: U={upper:.1f} M={mid:.1f} L={lower:.1f} (mult={config['bb_mult']})
ADX(1H): {adx:.1f} | EMA20(1H): {ema20:.1f} | EMA50(1H): {ema50:.1f}
Config: rsi_os={config['rsi_oversold']}, rsi_ob={config['rsi_overbought']}, cooldown={config['cooldown_minutes']}min

Analyze regime (ranging/trending_up/trending_down). Suggest param adjustments. Reply ONLY JSON:
{{"regime":"<ranging|trending_up|trending_down>","confidence":<0-1>,"rsi_oversold":<25-45>,"rsi_overbought":<55-75>,"cooldown_minutes":<30-240>,"bb_mult":<1.5-2.5>,"reason":"<one short sentence>"}}"""

    result = client.chat_json(system_prompt, user_msg)
    if result:
        log.info(f"AI 分析: {result.get('regime')} conf={result.get('confidence')}")
    return result


def run_ai_analysis_loop():
    global app_state
    while app_state["running"]:
        try:
            with lock:
                app_state["status_msg"] = "AI 分析中..."
            config = load_config()
            result = call_ai_analysis(config)
            if result:
                config["rsi_oversold"] = int(result.get("rsi_oversold", config["rsi_oversold"]))
                config["rsi_overbought"] = int(result.get("rsi_overbought", config["rsi_overbought"]))
                config["cooldown_minutes"] = int(result.get("cooldown_minutes", config["cooldown_minutes"]))
                config["bb_mult"] = float(result.get("bb_mult", config["bb_mult"]))
                save_config(config)
                with lock:
                    app_state["regime"] = result.get("regime", "?")
                    app_state["regime_conf"] = result.get("confidence", 0)
                    app_state["last_ai"] = datetime.now().strftime("%H:%M")
                    app_state["status_msg"] = "AI 分析完成"
            else:
                with lock:
                    app_state["status_msg"] = "AI 跳过（未配置或出错）"
        except Exception as e:
            log.error(f"AI 运行失败: {e}")
            with lock:
                app_state["status_msg"] = f"AI 错误: {e}"
        for _ in range(7200):
            if not app_state["running"]:
                return
            time.sleep(1)


def run_ai_analysis_once():
    """手动触发一次 AI 分析。"""
    global app_state
    with lock:
        app_state["status_msg"] = "AI 分析中..."
    config = load_config()
    result = call_ai_analysis(config)
    if result:
        config["rsi_oversold"] = int(result.get("rsi_oversold", config["rsi_oversold"]))
        config["rsi_overbought"] = int(result.get("rsi_overbought", config["rsi_overbought"]))
        config["cooldown_minutes"] = int(result.get("cooldown_minutes", config["cooldown_minutes"]))
        config["bb_mult"] = float(result.get("bb_mult", config["bb_mult"]))
        save_config(config)
        with lock:
            app_state["regime"] = result.get("regime", "?")
            app_state["regime_conf"] = result.get("confidence", 0)
            app_state["last_ai"] = datetime.now().strftime("%H:%M")
            app_state["status_msg"] = "AI 分析完成"
    else:
        with lock:
            app_state["status_msg"] = "AI 失败（未配置或出错）"


# ── Background: Signal Check ───────────────────────────────
def run_signal_check():
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
                reason = f"价格 {price:.1f} >= 中轨 {mid:.1f}"
            elif position == "SHORT" and short_exit:
                action = "EXIT_SHORT"
                reason = f"价格 {price:.1f} <= 中轨 {mid:.1f}"
            elif cooldown_ok and position == "NONE":
                if long_entry:
                    action = "ENTER_LONG"
                    reason = f"价格 {price:.1f} 触及下轨 {lower:.1f}, RSI={rsi:.1f}"
                elif short_entry:
                    action = "ENTER_SHORT"
                    reason = f"价格 {price:.1f} 触及上轨 {upper:.1f}, RSI={rsi:.1f}"

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
                app_state["status_msg"] = "就绪"

            if action:
                log.info(f"信号: {action} - {reason}")
                with lock:
                    app_state["signal"] = action
                    app_state["last_signal_time"] = datetime.now().strftime("%H:%M:%S")
                    app_state["status_msg"] = f"信号: {action}"

                ALERT_PATH.write_text(
                    f"[{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}]\n"
                    f"信号: {action}\n"
                    f"价格: {price:.1f}  |  RSI: {rsi:.1f}\n"
                    f"布林带: U={upper:.1f} M={mid:.1f} L={lower:.1f}  |  ATR: {atr:.1f}\n"
                    f"原因: {reason}\n",
                    encoding="utf-8",
                )
                state["last_signal_ts"] = now.timestamp()
                state["last_signal_action"] = action
                state["last_signal_price"] = price
                if action.startswith("ENTER_"):
                    state["position"] = "LONG" if "LONG" in action else "SHORT"
                    state["entry_price"] = price
                elif action.startswith("EXIT_"):
                    entry_price = state.get("entry_price", "?")
                    pnl = price - entry_price if "LONG" in action else entry_price - price
                    log.info(f"交易平仓: PnL={pnl:.1f}")
                    state["position"] = "NONE"
                save_state(state)
            else:
                with lock:
                    app_state["signal"] = None
                if ALERT_PATH.exists():
                    ALERT_PATH.unlink()

            status = {
                "time_utc": datetime.now(timezone.utc).isoformat(),
                "price": price, "rsi": round(rsi, 1) if rsi else None,
                "bb_upper": round(upper, 1) if upper else None,
                "bb_mid": round(mid, 1) if mid else None,
                "bb_lower": round(lower, 1) if lower else None,
                "atr": round(atr, 1) if atr else None,
                "position": position, "signal": action,
            }
            STATUS_PATH.write_text(json.dumps(status, indent=2, ensure_ascii=False), encoding="utf-8")

        except Exception as e:
            log.error(f"信号检测失败: {e}")
            with lock:
                app_state["status_msg"] = f"错误: {e}"

        for _ in range(300):
            if not app_state["running"]:
                return
            time.sleep(1)


# ── Tkinter GUI ─────────────────────────────────────────────
class BTCSignalApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("BTC 信号机器人 v2.0")
        self.root.geometry("620x580")
        self.root.minsize(580, 500)
        self.root.configure(bg="#1a1a2e")

        self.bg = "#1a1a2e"
        self.card_bg = "#16213e"
        self.fg = "#e0e0e0"
        self.accent = "#0f3460"
        self.green = "#00e676"
        self.red = "#ff5252"
        self.yellow = "#ffd740"
        self.dim = "#888888"

        self._build_tabs()
        self._bind_keys()

        self._last_signal = None

        # 首次启动检测
        if not is_configured():
            self.root.after(500, lambda: self._show_setup_warning())

        self._update_display()

    # ── Tab Structure ─────────────────────────────────────
    def _build_tabs(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TNotebook", background=self.bg, borderwidth=0)
        style.configure("TNotebook.Tab", font=("Microsoft YaHei", 9, "bold"),
                        padding=[16, 6], background="#1e2d4a", foreground=self.fg)
        style.map("TNotebook.Tab", background=[("selected", self.accent)],
                  foreground=[("selected", "#ffffff")])

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        self.tab_monitor = tk.Frame(self.notebook, bg=self.bg)
        self.tab_tech = tk.Frame(self.notebook, bg=self.bg)
        self.tab_plan = tk.Frame(self.notebook, bg=self.bg)
        self.tab_news = tk.Frame(self.notebook, bg=self.bg)
        self.tab_settings = tk.Frame(self.notebook, bg=self.bg)

        self.notebook.add(self.tab_monitor, text=" 行情监控 ")
        self.notebook.add(self.tab_tech, text=" 技术分析 ")
        self.notebook.add(self.tab_plan, text=" 交易计划 ")
        self.notebook.add(self.tab_news, text=" 新闻情绪 ")
        self.notebook.add(self.tab_settings, text=" 设置 ")

        self._build_monitor_tab()
        self._build_tech_tab()
        self._build_plan_tab()
        self._build_news_tab()
        self._build_settings_tab()

    # ── Tab 1: Monitor ────────────────────────────────────
    def _build_monitor_tab(self):
        parent = self.tab_monitor

        # Header
        hf = tk.Frame(parent, bg=self.bg)
        hf.pack(fill=tk.X, padx=12, pady=(10, 4))
        tk.Label(hf, text="BTC 行情监控", font=("Microsoft YaHei", 13, "bold"),
                 fg="#ffffff", bg=self.bg).pack(side=tk.LEFT)
        self.lbl_time = tk.Label(hf, text="", font=("Consolas", 9),
                                  fg=self.dim, bg=self.bg)
        self.lbl_time.pack(side=tk.RIGHT)

        # Price card
        self._make_card(parent, "实时数据", [
            ("lbl_price", "当前价格"),
            ("lbl_rsi", "RSI(14)"),
            ("lbl_bb", "布林带"),
            ("lbl_atr", "ATR(14)"),
        ])

        # Signal card
        self._make_card(parent, "持仓与信号", [
            ("lbl_position", "持仓方向"),
            ("lbl_signal_status", "信号状态"),
        ])

        # AI card
        self._make_card(parent, "AI 策略分析", [
            ("lbl_ai_time", "上次分析"),
            ("lbl_regime", "市场状态"),
            ("lbl_status", "运行状态"),
        ])

        # Config bar
        self.lbl_config_bar = tk.Label(parent, text="", font=("Microsoft YaHei", 8),
                                        fg=self.dim, bg=self.bg, anchor=tk.W)
        self.lbl_config_bar.pack(fill=tk.X, padx=12, pady=(2, 8))

    def _make_card(self, parent, title, fields):
        frame = tk.Frame(parent, bg=self.card_bg)
        frame.pack(fill=tk.X, padx=12, pady=3)

        hdr = tk.Frame(frame, bg=self.accent)
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text=title, font=("Microsoft YaHei", 9, "bold"),
                 fg="#ffffff", bg=self.accent, anchor=tk.W, padx=10, pady=2).pack(fill=tk.X)

        content = tk.Frame(frame, bg=self.card_bg)
        content.pack(fill=tk.X, padx=10, pady=4)

        for i, (attr, label) in enumerate(fields):
            col = i % 2
            row = i // 2
            tk.Label(content, text=label + ":", font=("Microsoft YaHei", 9),
                     fg=self.dim, bg=self.card_bg).grid(
                row=row, column=col * 2, sticky=tk.W,
                padx=(0 if col == 0 else 20, 4), pady=1)
            lbl = tk.Label(content, text="--", font=("Consolas", 11, "bold"),
                           fg=self.fg, bg=self.card_bg)
            lbl.grid(row=row, column=col * 2 + 1, sticky=tk.W, pady=1)
            setattr(self, attr, lbl)

    # ── Tab 2: Technical Analysis ─────────────────────────
    def _build_tech_tab(self):
        parent = self.tab_tech

        # Controls
        ctrl = tk.Frame(parent, bg=self.bg)
        ctrl.pack(fill=tk.X, padx=12, pady=(10, 4))

        tk.Label(ctrl, text="K线周期:", font=("Microsoft YaHei", 9),
                 fg=self.fg, bg=self.bg).pack(side=tk.LEFT)
        self.tech_bar = ttk.Combobox(ctrl, values=["15m", "1H", "4H", "1D"],
                                      state="readonly", width=5)
        self.tech_bar.set("1H")
        self.tech_bar.pack(side=tk.LEFT, padx=4)
        ttk.Button(ctrl, text="刷新分析", command=self._run_tech_analysis).pack(side=tk.LEFT, padx=8)
        self.tech_status = tk.Label(ctrl, text="", font=("Microsoft YaHei", 8),
                                     fg=self.dim, bg=self.bg)
        self.tech_status.pack(side=tk.RIGHT)

        # Results text area
        self.tech_text = scrolledtext.ScrolledText(
            parent, font=("Consolas", 10), bg="#0d1b2a", fg=self.green,
            insertbackground=self.fg, relief=tk.FLAT, borderwidth=0,
            padx=10, pady=8, wrap=tk.WORD,
        )
        self.tech_text.pack(fill=tk.BOTH, expand=True, padx=12, pady=6)

    def _run_tech_analysis(self):
        bar = self.tech_bar.get()
        self.tech_status.config(text="分析中...")
        threading.Thread(target=self._do_tech_analysis, args=(bar,), daemon=True).start()

    def _do_tech_analysis(self, bar):
        try:
            ind = technical.compute_all_indicators("BTC-USDT-SWAP", bar, limit=100)
            text = technical.format_analysis_text(ind)
            self.root.after(0, lambda: self._show_tech_result(text, bar))
        except Exception as e:
            self.root.after(0, lambda: self._show_tech_result(f"分析失败: {e}", bar))

    def _show_tech_result(self, text, bar):
        self.tech_text.delete("1.0", tk.END)
        self.tech_text.insert("1.0", f"=== BTC 技术分析 ({bar}) ===\n\n{text}")
        self.tech_status.config(text=f"已完成 @ {datetime.now().strftime('%H:%M:%S')}")

    # ── Tab 3: Trading Plan ────────────────────────────────
    def _build_plan_tab(self):
        parent = self.tab_plan

        ctrl = tk.Frame(parent, bg=self.bg)
        ctrl.pack(fill=tk.X, padx=12, pady=(10, 4))

        tk.Label(ctrl, text="BTC 交易计划生成器", font=("Microsoft YaHei", 11, "bold"),
                 fg="#ffffff", bg=self.bg).pack(side=tk.LEFT)
        ttk.Button(ctrl, text="生成交易计划", command=self._run_trading_plan).pack(side=tk.LEFT, padx=12)
        self.plan_status = tk.Label(ctrl, text="", font=("Microsoft YaHei", 8),
                                     fg=self.dim, bg=self.bg)
        self.plan_status.pack(side=tk.RIGHT)

        # Scrollable result
        self.plan_text = scrolledtext.ScrolledText(
            parent, font=("Consolas", 10), bg="#0d1b2a", fg=self.yellow,
            relief=tk.FLAT, borderwidth=0, padx=10, pady=8, wrap=tk.WORD,
        )
        self.plan_text.pack(fill=tk.BOTH, expand=True, padx=12, pady=6)

    def _run_trading_plan(self):
        self.plan_status.config(text="生成中...")
        threading.Thread(target=self._do_trading_plan, daemon=True).start()

    def _do_trading_plan(self):
        try:
            ind = technical.compute_all_indicators("BTC-USDT-SWAP", "1H", limit=100)
            s = sentiment.generate_sentiment_summary() if True else ""
            plan = trading_plan.generate_plan(ind, s[:80] if s else "")
            self.root.after(0, lambda: self._show_plan_result(plan))
        except Exception as e:
            self.root.after(0, lambda: self._show_plan_result(f"生成失败: {e}"))

    def _show_plan_result(self, text):
        self.plan_text.delete("1.0", tk.END)
        self.plan_text.insert("1.0", text)
        self.plan_status.config(text=f"已完成 @ {datetime.now().strftime('%H:%M:%S')}")

    # ── Tab 4: News & Sentiment ────────────────────────────
    def _build_news_tab(self):
        parent = self.tab_news

        ctrl = tk.Frame(parent, bg=self.bg)
        ctrl.pack(fill=tk.X, padx=12, pady=(10, 4))
        tk.Label(ctrl, text="市场新闻与情绪", font=("Microsoft YaHei", 11, "bold"),
                 fg="#ffffff", bg=self.bg).pack(side=tk.LEFT)
        ttk.Button(ctrl, text="刷 新", command=self._run_news_fetch).pack(side=tk.LEFT, padx=12)
        ttk.Button(ctrl, text="AI 情绪分析", command=self._run_sentiment_ai).pack(side=tk.LEFT)
        self.news_status = tk.Label(ctrl, text="", font=("Microsoft YaHei", 8),
                                     fg=self.dim, bg=self.bg)
        self.news_status.pack(side=tk.RIGHT)

        self.news_text = scrolledtext.ScrolledText(
            parent, font=("Microsoft YaHei", 10), bg="#0d1b2a", fg=self.fg,
            relief=tk.FLAT, borderwidth=0, padx=10, pady=8, wrap=tk.WORD,
        )
        self.news_text.pack(fill=tk.BOTH, expand=True, padx=12, pady=6)

    def _run_news_fetch(self):
        self.news_status.config(text="获取中...")
        threading.Thread(target=self._do_news_fetch, daemon=True).start()

    def _do_news_fetch(self):
        try:
            news = sentiment.fetch_btc_news(15)
            lines = ["=== BTC 新闻 ===\n"]
            for n in news:
                lines.append(f"• {n['title']}")
                if n.get("summary"):
                    lines.append(f"  {n['summary'][:120]}")
                lines.append(f"  来源: {n.get('source', '?')}  |  {n.get('time', '?')}")
                lines.append("")
            text = "\n".join(lines) if len(lines) > 2 else "暂无新闻数据。"
            self.root.after(0, lambda: self._show_news_result(text))
        except Exception as e:
            self.root.after(0, lambda: self._show_news_result(f"获取失败: {e}"))

    def _show_news_result(self, text):
        self.news_text.delete("1.0", tk.END)
        self.news_text.insert("1.0", text)
        self.news_status.config(text=f"已更新 @ {datetime.now().strftime('%H:%M:%S')}")

    def _run_sentiment_ai(self):
        self.news_status.config(text="AI 分析中...")
        threading.Thread(target=self._do_sentiment_ai, daemon=True).start()

    def _do_sentiment_ai(self):
        try:
            config = load_config()
            ai_config = get_ai_config(config)
            client = AIClient(ai_config)
            result = sentiment.generate_sentiment_summary(client)
            eco = sentiment.generate_economic_summary()
            full = result + "\n\n" + eco
            self.root.after(0, lambda: self._show_news_result(full))
        except Exception as e:
            self.root.after(0, lambda: self._show_news_result(f"分析失败: {e}"))

    # ── Tab 5: Settings ────────────────────────────────────
    def _build_settings_tab(self):
        parent = self.tab_settings

        canvas = tk.Canvas(parent, bg=self.bg, highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=canvas.yview)
        scroll_frame = tk.Frame(canvas, bg=self.bg)
        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Bind mouse wheel
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        padx = 16
        pady = 4

        # ── AI Provider Section ──
        self._section_label(scroll_frame, "AI 平台配置", 0)

        row = tk.Frame(scroll_frame, bg=self.bg)
        row.pack(fill=tk.X, padx=padx, pady=pady)
        tk.Label(row, text="供应商:", font=("Microsoft YaHei", 9), fg=self.fg, bg=self.bg,
                 width=10, anchor=tk.W).pack(side=tk.LEFT)
        self.cfg_provider = ttk.Combobox(row, values=list(AI_PROVIDERS.keys()),
                                          state="readonly", width=18)
        self.cfg_provider.pack(side=tk.LEFT)
        self.cfg_provider.bind("<<ComboboxSelected>>", self._on_provider_change)

        row2 = tk.Frame(scroll_frame, bg=self.bg)
        row2.pack(fill=tk.X, padx=padx, pady=pady)
        tk.Label(row2, text="API Key:", font=("Microsoft YaHei", 9), fg=self.fg, bg=self.bg,
                 width=10, anchor=tk.W).pack(side=tk.LEFT)
        self.cfg_apikey = tk.Entry(row2, font=("Consolas", 10), show="*", width=35)
        self.cfg_apikey.pack(side=tk.LEFT)

        row3 = tk.Frame(scroll_frame, bg=self.bg)
        row3.pack(fill=tk.X, padx=padx, pady=pady)
        tk.Label(row3, text="模型:", font=("Microsoft YaHei", 9), fg=self.fg, bg=self.bg,
                 width=10, anchor=tk.W).pack(side=tk.LEFT)
        self.cfg_model = ttk.Combobox(row3, values=[], state="readonly", width=28)
        self.cfg_model.pack(side=tk.LEFT)

        row4 = tk.Frame(scroll_frame, bg=self.bg)
        row4.pack(fill=tk.X, padx=padx, pady=pady)
        tk.Label(row4, text="接口地址:", font=("Microsoft YaHei", 9), fg=self.fg, bg=self.bg,
                 width=10, anchor=tk.W).pack(side=tk.LEFT)
        self.cfg_baseurl = tk.Entry(row4, font=("Consolas", 9), width=45)
        self.cfg_baseurl.pack(side=tk.LEFT)

        # ── OKX Connection Section ──
        self._section_label(scroll_frame, "OKX 连接", 6)

        self._okx_help_text = (
            "OKX 提供两种连接方式：\n"
            "  方式一（推荐）：MCP OAuth — 点击下方按钮打开浏览器授权\n"
            "  MCP 地址: https://www.okx.com/api/v1/mcp/trading-oauth\n"
            "  方式二：API Key — 在 OKX 官网创建 API Key 后填入下方\n"
            "  (创建地址: https://www.okx.com/account/my-api)"
        )
        help_lbl = tk.Label(scroll_frame, text=self._okx_help_text,
                            font=("Microsoft YaHei", 8), fg=self.dim, bg=self.bg,
                            justify=tk.LEFT, anchor=tk.W)
        help_lbl.pack(fill=tk.X, padx=padx, pady=(0, 4))

        # Auth type selector
        auth_row = tk.Frame(scroll_frame, bg=self.bg)
        auth_row.pack(fill=tk.X, padx=padx, pady=pady)
        tk.Label(auth_row, text="认证方式:", font=("Microsoft YaHei", 9), fg=self.fg, bg=self.bg,
                 width=10, anchor=tk.W).pack(side=tk.LEFT)
        self.cfg_okx_auth = ttk.Combobox(auth_row, values=["public", "api_key"],
                                          state="readonly", width=12)
        self.cfg_okx_auth.pack(side=tk.LEFT)
        self.cfg_okx_auth.bind("<<ComboboxSelected>>", self._on_okx_auth_change)

        # API Key fields
        self.okx_key_frame = tk.Frame(scroll_frame, bg=self.bg)
        for i, (attr, label, show) in enumerate([
            ("cfg_okx_apikey", "API Key", "*"),
            ("cfg_okx_secret", "Secret Key", "*"),
            ("cfg_okx_pass", "Passphrase", "*"),
        ]):
            rf = tk.Frame(self.okx_key_frame, bg=self.bg)
            rf.pack(fill=tk.X, padx=0, pady=1)
            tk.Label(rf, text=label + ":", font=("Microsoft YaHei", 9), fg=self.fg, bg=self.bg,
                     width=10, anchor=tk.W).pack(side=tk.LEFT)
            e = tk.Entry(rf, font=("Consolas", 9), show=show, width=40)
            e.pack(side=tk.LEFT)
            setattr(self, attr, e)

        self.okx_key_frame.pack(fill=tk.X, padx=padx, pady=(2, 2))
        self.okx_key_frame.pack_forget()  # hidden by default

        # Test button
        okx_btn_row = tk.Frame(scroll_frame, bg=self.bg)
        okx_btn_row.pack(fill=tk.X, padx=padx, pady=(2, 4))
        ttk.Button(okx_btn_row, text="验证 OKX 连接", command=self._test_okx_connection).pack(
            side=tk.LEFT, padx=(80, 8))
        self.cfg_okx_status = tk.Label(okx_btn_row, text="", font=("Microsoft YaHei", 8),
                                        fg=self.dim, bg=self.bg)
        self.cfg_okx_status.pack(side=tk.LEFT)

        # Signal config
        self._section_label(scroll_frame, "OKX 信号配置", 8)

        row5 = tk.Frame(scroll_frame, bg=self.bg)
        row5.pack(fill=tk.X, padx=padx, pady=pady)
        tk.Label(row5, text="Signal Token:", font=("Microsoft YaHei", 9), fg=self.fg, bg=self.bg,
                 width=10, anchor=tk.W).pack(side=tk.LEFT)
        self.cfg_token = tk.Entry(row5, font=("Consolas", 10), width=40)
        self.cfg_token.pack(side=tk.LEFT)

        row6 = tk.Frame(scroll_frame, bg=self.bg)
        row6.pack(fill=tk.X, padx=padx, pady=pady)
        tk.Label(row6, text="交易对:", font=("Microsoft YaHei", 9), fg=self.fg, bg=self.bg,
                 width=10, anchor=tk.W).pack(side=tk.LEFT)
        self.cfg_instrument = ttk.Combobox(row6, values=["BTC-USDT-SWAP", "ETH-USDT-SWAP",
                                            "BTC-USDT", "ETH-USDT"], width=18)
        self.cfg_instrument.pack(side=tk.LEFT)

        # ── Strategy Section ──
        self._section_label(scroll_frame, "策略参数", 6)

        strat_fields = [
            ("cfg_bb_period", "BB 周期", "20"),
            ("cfg_bb_mult", "BB 乘数", "2.0"),
            ("cfg_rsi_period", "RSI 周期", "14"),
            ("cfg_rsi_os", "RSI 超卖", "35"),
            ("cfg_rsi_ob", "RSI 超买", "65"),
            ("cfg_cooldown", "冷却(分钟)", "120"),
        ]
        for i, (attr, label, default) in enumerate(strat_fields):
            rf = tk.Frame(scroll_frame, bg=self.bg)
            rf.pack(fill=tk.X, padx=padx, pady=pady)
            tk.Label(rf, text=label + ":", font=("Microsoft YaHei", 9), fg=self.fg, bg=self.bg,
                     width=10, anchor=tk.W).pack(side=tk.LEFT)
            e = tk.Entry(rf, font=("Consolas", 10), width=8)
            e.insert(0, default)
            e.pack(side=tk.LEFT)
            setattr(self, attr, e)

        # ── Buttons ──
        btn_frame = tk.Frame(scroll_frame, bg=self.bg)
        btn_frame.pack(fill=tk.X, padx=padx, pady=(12, 16))
        ttk.Button(btn_frame, text="保存设置", command=self._save_settings).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(btn_frame, text="测试 AI 连接", command=self._test_ai_connection).pack(side=tk.LEFT)

        self.cfg_status = tk.Label(scroll_frame, text="", font=("Microsoft YaHei", 8),
                                    fg=self.green, bg=self.bg)
        self.cfg_status.pack(fill=tk.X, padx=padx, pady=(0, 8))

        # ── Security Info ──
        self._section_label(scroll_frame, "安全信息", 6)
        sec_info = (
            "数据存储: 所有密钥仅保存在本地 btc_signal_config.json\n"
            "网络请求: 仅发往 OKX 官方 API (okx.com) 和你选择的 AI 供应商官方 API\n"
            "数据收集: 本应用无遥测、无统计、无第三方服务\n"
            "代码审计: 完全开源，查看 SECURITY.md 了解详情"
        )
        tk.Label(scroll_frame, text=sec_info, font=("Microsoft YaHei", 8),
                 fg=self.dim, bg=self.bg, justify=tk.LEFT, anchor=tk.W).pack(
            fill=tk.X, padx=padx, pady=(0, 8))

        # Load current config
        self._load_settings_to_form()

    def _section_label(self, parent, text, pady_top=12):
        tk.Label(parent, text="─ " + text, font=("Microsoft YaHei", 10, "bold"),
                 fg=self.accent, bg=self.bg, anchor=tk.W).pack(
            fill=tk.X, padx=16, pady=(pady_top, 2))

    # ── Settings Logic ─────────────────────────────────────
    def _load_settings_to_form(self):
        config = load_config()
        ai = config.get("ai", {})
        self.cfg_provider.set(ai.get("provider", "deepseek"))
        self.cfg_apikey.insert(0, ai.get("api_key", ""))
        self._refresh_model_list()
        self.cfg_model.set(ai.get("model", ""))
        self.cfg_baseurl.insert(0, ai.get("base_url", ""))
        self.cfg_token.insert(0, config.get("signal_token", ""))
        self.cfg_instrument.set(config.get("instrument", "BTC-USDT-SWAP"))

        # OKX connection
        okx = config.get("okx", {})
        self.cfg_okx_auth.set(okx.get("auth_type", "public"))
        self.cfg_okx_apikey.insert(0, okx.get("api_key", ""))
        self.cfg_okx_secret.insert(0, okx.get("secret_key", ""))
        self.cfg_okx_pass.insert(0, okx.get("passphrase", ""))
        self._on_okx_auth_change()
        self.cfg_bb_period.delete(0, tk.END)
        self.cfg_bb_period.insert(0, str(config.get("bb_period", 20)))
        self.cfg_bb_mult.delete(0, tk.END)
        self.cfg_bb_mult.insert(0, str(config.get("bb_mult", 2.0)))
        self.cfg_rsi_period.delete(0, tk.END)
        self.cfg_rsi_period.insert(0, str(config.get("rsi_period", 14)))
        self.cfg_rsi_os.delete(0, tk.END)
        self.cfg_rsi_os.insert(0, str(config.get("rsi_oversold", 35)))
        self.cfg_rsi_ob.delete(0, tk.END)
        self.cfg_rsi_ob.insert(0, str(config.get("rsi_overbought", 65)))
        self.cfg_cooldown.delete(0, tk.END)
        self.cfg_cooldown.insert(0, str(config.get("cooldown_minutes", 120)))

    def _on_provider_change(self, event=None):
        """供应商切换时更新 base_url 和模型列表。"""
        key = self.cfg_provider.get()
        preset = AI_PROVIDERS.get(key, {})
        self.cfg_baseurl.delete(0, tk.END)
        self.cfg_baseurl.insert(0, preset.get("base_url", ""))
        self._refresh_model_list()

    def _on_okx_auth_change(self, event=None):
        """认证方式切换时显示/隐藏 API Key 输入框。"""
        auth = self.cfg_okx_auth.get()
        if auth == "api_key":
            self.okx_key_frame.pack()
        else:
            self.okx_key_frame.pack_forget()

    def _refresh_model_list(self):
        key = self.cfg_provider.get()
        models = get_provider_models(key)
        self.cfg_model["values"] = models if models else ["(手动输入)"]
        if models:
            self.cfg_model.set(models[0])

    def _test_okx_connection(self):
        """测试 OKX API 连接。"""
        auth = self.cfg_okx_auth.get()
        if auth != "api_key":
            self.cfg_okx_status.config(text="请先选择 api_key 认证方式", fg=self.red)
            return

        api_key = self.cfg_okx_apikey.get()
        secret = self.cfg_okx_secret.get()
        passphrase = self.cfg_okx_pass.get()
        if not all([api_key, secret, passphrase]):
            self.cfg_okx_status.config(text="请填写完整的 API Key / Secret / Passphrase", fg=self.red)
            return

        self.cfg_okx_status.config(text="测试中...", fg=self.yellow)
        from okx_client import OKXClient
        client = OKXClient("api_key", {"api_key": api_key, "secret_key": secret, "passphrase": passphrase})
        ok, msg = client.test_connection()
        self.cfg_okx_status.config(text=msg, fg=self.green if ok else self.red)

    def _save_settings(self):
        config = load_config()

        config["ai"] = {
            "provider": self.cfg_provider.get(),
            "api_key": self.cfg_apikey.get(),
            "model": self.cfg_model.get(),
            "base_url": self.cfg_baseurl.get(),
            "api_format": AI_PROVIDERS.get(self.cfg_provider.get(), {}).get("api_format", "anthropic"),
            "enabled": bool(self.cfg_apikey.get()),
        }
        config["signal_token"] = self.cfg_token.get()
        config["instrument"] = self.cfg_instrument.get()

        config["okx"] = {
            "auth_type": self.cfg_okx_auth.get(),
            "api_key": self.cfg_okx_apikey.get(),
            "secret_key": self.cfg_okx_secret.get(),
            "passphrase": self.cfg_okx_pass.get(),
            "mcp_url": "https://www.okx.com/api/v1/mcp/trading-oauth",
            "signal_token": self.cfg_token.get(),
        }
        config["bb_period"] = int(self.cfg_bb_period.get())
        config["bb_mult"] = float(self.cfg_bb_mult.get())
        config["rsi_period"] = int(self.cfg_rsi_period.get())
        config["rsi_oversold"] = int(self.cfg_rsi_os.get())
        config["rsi_overbought"] = int(self.cfg_rsi_ob.get())
        config["cooldown_minutes"] = int(self.cfg_cooldown.get())

        save_config(config)
        self.cfg_status.config(text="设置已保存！", fg=self.green)

    def _test_ai_connection(self):
        self.cfg_status.config(text="测试中...", fg=self.yellow)
        provider = self.cfg_provider.get()
        api_key = self.cfg_apikey.get()
        model = self.cfg_model.get()
        base_url = self.cfg_baseurl.get()
        preset = AI_PROVIDERS.get(provider, {})

        ai_config = {
            "provider": provider, "api_key": api_key, "model": model,
            "base_url": base_url or preset.get("base_url", ""),
            "api_format": preset.get("api_format", "anthropic"),
            "enabled": bool(api_key),
        }
        threading.Thread(target=self._do_test_ai, args=(ai_config,), daemon=True).start()

    def _do_test_ai(self, ai_config):
        client = AIClient(ai_config)
        if not client.enabled:
            self.root.after(0, lambda: self.cfg_status.config(text="请先填写 API Key", fg=self.red))
            return
        result = client.chat("Reply with exactly 'OK'", "Hello")
        if result and "OK" in result:
            self.root.after(0, lambda: self.cfg_status.config(text="AI 连接成功！", fg=self.green))
        else:
            self.root.after(0, lambda: self.cfg_status.config(
                text=f"连接失败: {result[:80] if result else '无响应'}", fg=self.red))

    # ── Keyboard ───────────────────────────────────────────
    def _bind_keys(self):
        self.root.bind('<Key>', self._on_key)

    def _on_key(self, event):
        if event.char in ('r', 'R'):
            with lock:
                app_state["status_msg"] = "手动刷新..."
            threading.Thread(target=self._run_signal_once, daemon=True).start()
        elif event.char in ('a', 'A'):
            threading.Thread(target=run_ai_analysis_once, daemon=True).start()
        elif event.char in ('q', 'Q'):
            self._quit()
        elif event.char in ('1', '2', '3', '4', '5'):
            idx = int(event.char) - 1
            self.notebook.select(idx)

    def _run_signal_once(self):
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
                app_state["status_msg"] = "已刷新"
        except Exception as e:
            with lock:
                app_state["status_msg"] = f"刷新错误: {e}"

    # ── Periodic UI Update ─────────────────────────────────
    def _update_display(self):
        with lock:
            s = dict(app_state)

        self.lbl_time.config(text=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        # Price
        self.lbl_price.config(text=f"${s['price']:,.1f}" if s["price"] else "--")

        # RSI
        rsi_v = s["rsi"]
        rsi_color = self.red if rsi_v > 70 else (self.green if rsi_v < 30 else self.fg)
        self.lbl_rsi.config(text=f"{rsi_v:.1f}", fg=rsi_color)

        # BB
        self.lbl_bb.config(
            text=f"上 {s['bb_upper']:,.1f}  中 {s['bb_mid']:,.1f}  下 {s['bb_lower']:,.1f}")

        # ATR
        self.lbl_atr.config(text=f"{s['atr']:,.1f}" if s["atr"] else "--")

        # Position
        pos = s["position"]
        pos_color = (self.green if pos == "LONG" else
                     self.red if pos == "SHORT" else self.fg)
        self.lbl_position.config(text=POSITION_CN.get(pos, pos), fg=pos_color)

        # Signal
        signal = s["signal"]
        if signal:
            sig_cn = SIGNAL_CN.get(signal, signal)
            is_long = "LONG" in signal
            sig_color = self.green if is_long else self.red
            if "EXIT" in signal:
                sig_color = self.yellow
            self.lbl_signal_status.config(text=f"{sig_cn} @ {s['last_signal_time']}", fg=sig_color)
        elif s["cooldown_s"] > 0:
            m, sec = divmod(s["cooldown_s"], 60)
            self.lbl_signal_status.config(text=f"冷却中 {m}分{sec}秒", fg=self.yellow)
        else:
            self.lbl_signal_status.config(text="等待信号...", fg=self.dim)

        # AI
        self.lbl_ai_time.config(text=s["last_ai"])
        regime_cn = REGIME_CN.get(s["regime"], s["regime"])
        regime_color = (self.green if "up" in str(s["regime"]) else
                        self.red if "down" in str(s["regime"]) else self.yellow)
        self.lbl_regime.config(text=f"{regime_cn} ({s['regime_conf']:.0%})", fg=regime_color)
        self.lbl_status.config(text=s["status_msg"])

        # Config bar
        config = load_config()
        self.lbl_config_bar.config(
            text=f"参数: RSI [{config['rsi_oversold']},{config['rsi_overbought']}]  |  "
                 f"BB×{config['bb_mult']}  |  冷却 {config['cooldown_minutes']}分钟  |  "
                 f"K线 {config['bar']}  |  快捷键: 1-5=切换Tab  R=刷新  A=AI分析  Q=退出")

        self._last_signal = signal
        self.root.after(2000, self._update_display)

    # ── Setup Warning ──────────────────────────────────────
    def _show_setup_warning(self):
        """首次启动：安全声明 + 引导设置。"""
        security_msg = (
            "安全与隐私声明\n\n"
            "1. 所有密钥（API Key、Secret Key 等）仅存储在本地文件\n"
            "   btc_signal_config.json 中，不会上传到任何服务器\n\n"
            "2. 网络请求仅发往你主动配置的官方 API：\n"
            "   - OKX 官方 API (okx.com)\n"
            "   - AI 供应商官方 API（DeepSeek / OpenAI / Anthropic）\n"
            "   - 公开行情 API（恐惧贪婪指数等）\n\n"
            "3. 本应用不包含任何遥测、统计、或第三方数据收集\n\n"
            "4. 代码完全开源，所有网络请求可在源代码中审计\n\n"
            "详细信息请查看项目中的 SECURITY.md\n\n"
            "─" * 35 + "\n\n"
            "点击「是」前往设置页面配置 AI 和 OKX 连接"
        )
        if messagebox.askyesno("首次使用 — 安全声明", security_msg):
            self.notebook.select(4)

    # ── Quit ───────────────────────────────────────────────
    def _quit(self):
        if messagebox.askokcancel("退出", "确定要退出 BTC 信号机器人吗？"):
            app_state["running"] = False
            self.root.destroy()


# ── Main Entry ──────────────────────────────────────────────
def main():
    init_config()

    root = tk.Tk()
    app = BTCSignalApp(root)

    # Initial data fetch
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
            app_state["status_msg"] = "就绪"
    except Exception as e:
        log.error(f"初始数据获取失败: {e}")

    # Start background threads
    threading.Thread(target=run_signal_check, daemon=True, name="signal").start()
    threading.Thread(target=run_ai_analysis_loop, daemon=True, name="ai").start()

    root.protocol("WM_DELETE_WINDOW", app._quit)
    root.mainloop()
    log.info("应用已退出。")


if __name__ == "__main__":
    main()

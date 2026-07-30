#!/usr/bin/env python3
"""
BTC AI 分析中枢 — AI × 交易所的中间桥梁
用户只需连接 AI + 连接交易所，一键获得分析报告
启动: python main.py
"""

import json
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
    load_config, save_config, get_ai_config, get_okx_config,
    get_provider_models, AI_PROVIDERS, init_config, is_configured,
)
from ai_client import AIClient
from okx_client import OKXClient
from strategy_engine import check_signal, get_mode_info
from skill_registry import SKILLS, run_skill
from btc_signal_bot import fetch_candles, calc_bb, calc_rsi, calc_atr, load_state, save_state

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(SCRIPT_DIR / "btc_signal.log", encoding="utf-8"),
              logging.StreamHandler()],
)
log = logging.getLogger("btc_app")

CONFIG_PATH = SCRIPT_DIR / "btc_signal_config.json"
STATE_PATH = SCRIPT_DIR / "btc_signal_state.json"
ALERT_PATH = SCRIPT_DIR / "btc_signal_alert.txt"
STATUS_PATH = SCRIPT_DIR / "btc_signal_status.json"

app_state = {"running": True, "price": 0, "signal": None}
lock = threading.Lock()


# ── Background: Signal Monitor ──────────────────────────────
def run_signal_check():
    global app_state
    while app_state["running"]:
        try:
            config = load_config()
            state = load_state()
            now = datetime.now(timezone.utc)

            candles = fetch_candles(config.get("instrument", "BTC-USDT-SWAP"),
                                    config.get("bar", "15m"), limit=60)
            price = candles[-1]["close"]
            upper, mid, lower = calc_bb(candles, config.get("bb_period", 20),
                                        config.get("bb_mult", 2.0))
            rsi = calc_rsi(candles, config.get("rsi_period", 14))
            atr = calc_atr(candles, 14)

            last_ts = state.get("last_signal_ts", 0)
            cooldown_ok = (now.timestamp() - last_ts) >= config.get("cooldown_minutes", 120) * 60
            position = state.get("position", "NONE")

            action, reason = check_signal(candles, config, position)
            if action and action.startswith("ENTER_") and (not cooldown_ok or position != "NONE"):
                action, reason = None, ""
            if action and action.startswith("EXIT_") and position == "NONE":
                action, reason = None, ""

            with lock:
                app_state["price"] = price
                app_state["signal"] = action

            if action:
                log.info(f"信号: {action} - {reason}")
                ALERT_PATH.write_text(
                    f"[{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}]\n"
                    f"信号: {action}\n价格: {price:.1f} | RSI: {rsi:.1f}\n原因: {reason}\n",
                    encoding="utf-8")
                state["last_signal_ts"] = now.timestamp()
                state["last_signal_action"] = action
                if action.startswith("ENTER_"):
                    state["position"] = "LONG" if "LONG" in action else "SHORT"
                    state["entry_price"] = price
                elif action.startswith("EXIT_"):
                    state["position"] = "NONE"
                save_state(state)
            elif ALERT_PATH.exists():
                ALERT_PATH.unlink()

        except Exception as e:
            log.error(f"信号检测失败: {e}")

        for _ in range(300):
            if not app_state["running"]:
                return
            time.sleep(1)


# ── Tkinter GUI ─────────────────────────────────────────────
class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("BTC AI 分析中枢")
        self.root.geometry("580x520")
        self.root.minsize(480, 420)
        self.root.configure(bg="#0d1b2a")

        self.bg = "#0d1b2a"
        self.card_bg = "#162447"
        self.accent = "#1f4287"
        self.fg = "#e8e8e8"
        self.green = "#21bf73"
        self.red = "#fd5e53"
        self.yellow = "#f9a828"
        self.dim = "#6b7c93"

        # State
        self.current_page = None
        self.working = False

        self._build_pages()
        self.show_home()

        if not is_configured():
            self.root.after(500, self._show_first_launch)

        # Background signal monitor
        threading.Thread(target=run_signal_check, daemon=True, name="signal").start()

    # ── Pages ──────────────────────────────────────────────
    def _build_pages(self):
        self.page_home = tk.Frame(self.root, bg=self.bg)
        self.page_report = tk.Frame(self.root, bg=self.bg)
        self.page_settings = tk.Frame(self.root, bg=self.bg)

    def _clear(self):
        for page in [self.page_home, self.page_report, self.page_settings]:
            for w in page.winfo_children():
                w.destroy()
            page.pack_forget()

    # ── Page 1: Home ───────────────────────────────────────
    def show_home(self):
        self._clear()
        parent = self.page_home
        parent.pack(fill=tk.BOTH, expand=True)

        # Title
        tk.Label(parent, text="BTC AI 分析中枢", font=("Microsoft YaHei", 16, "bold"),
                 fg="#ffffff", bg=self.bg).pack(pady=(14, 2))
        tk.Label(parent, text="AI × 交易所的中间桥梁 — 一键分析，即刻报告",
                 font=("Microsoft YaHei", 9), fg=self.dim, bg=self.bg).pack()

        # Status bar
        self._build_status_bar(parent)

        tk.Label(parent, text="", bg=self.bg).pack(pady=2)  # spacer

        # Skill buttons grid
        grid = tk.Frame(parent, bg=self.bg)
        grid.pack(fill=tk.BOTH, padx=20, pady=6)

        for i, skill in enumerate(SKILLS):
            row, col = divmod(i, 3)
            self._make_skill_btn(grid, skill, row, col)

        for i in range(3):
            grid.grid_columnconfigure(i, weight=1)

        # Bottom
        bottom = tk.Frame(parent, bg=self.bg)
        bottom.pack(fill=tk.X, padx=20, pady=(8, 12))
        tk.Label(bottom, text="⚙ 设置 — 连接 AI 和交易所", font=("Microsoft YaHei", 9),
                 fg=self.accent, bg=self.bg, cursor="hand2").pack(side=tk.LEFT)
        tk.Label(bottom, text="", bg=self.bg).pack()
        # Make settings label clickable
        for child in bottom.winfo_children():
            if isinstance(child, tk.Label):
                child.bind("<Button-1>", lambda e: self.show_settings())

        self.current_page = "home"

    def _build_status_bar(self, parent):
        config = load_config()
        ai_cfg = get_ai_config(config)
        okx_cfg = get_okx_config(config)

        bar = tk.Frame(parent, bg=self.card_bg, bd=0)
        bar.pack(fill=tk.X, padx=20, pady=(4, 2))

        ai_status = f"AI: ✅ {ai_cfg['provider_name']}" if ai_cfg['enabled'] else "AI: ⚠️ 未配置"
        okx_status = "交易所: ✅ OKX" if (okx_cfg.get("api_key") or okx_cfg.get("signal_token")) else "交易所: ⚠️ 未配置"
        price = app_state.get("price", 0)
        signal = app_state.get("signal")

        status_text = f"  {ai_status}  |  {okx_status}  |  价格: ${price:,.1f}"
        if signal:
            status_text += f"  |  信号: {signal}"

        tk.Label(bar, text=status_text, font=("Microsoft YaHei", 9),
                 fg=self.fg, bg=self.card_bg, anchor=tk.W, padx=10, pady=4).pack(fill=tk.X)

        # Schedule refresh
        if self.current_page == "home":
            self.root.after(3000, self._refresh_status)

    def _refresh_status(self):
        if self.current_page == "home":
            self._clear_status_bar()
            self._build_status_bar(self.page_home)

    def _clear_status_bar(self):
        for w in self.page_home.winfo_children():
            if isinstance(w, tk.Frame) and w.cget("bg") == self.card_bg:
                w.destroy()

    def _make_skill_btn(self, parent, skill, row, col):
        frame = tk.Frame(parent, bg=self.card_bg, bd=0, relief=tk.FLAT)
        frame.grid(row=row, column=col, padx=4, pady=4, sticky="nsew")

        # Icon + name
        hdr = tk.Frame(frame, bg=self.card_bg)
        hdr.pack(pady=(10, 2))
        tk.Label(hdr, text=f"{skill['icon']} {skill['name']}",
                 font=("Microsoft YaHei", 11, "bold"), fg="#ffffff", bg=self.card_bg).pack()

        # Description
        tk.Label(frame, text=skill["description"], font=("Microsoft YaHei", 8),
                 fg=self.dim, bg=self.card_bg, wraplength=150, justify=tk.CENTER).pack(padx=8, pady=(2, 8))

        # Trigger area (entire card is clickable)
        for w in [frame, hdr] + list(hdr.winfo_children()) + list(frame.winfo_children()):
            if isinstance(w, tk.Label) or isinstance(w, tk.Frame):
                w.bind("<Button-1>", lambda e, sid=skill["id"]: self._trigger_skill(sid))
                w.configure(cursor="hand2")

    def _trigger_skill(self, skill_id):
        if self.working:
            return
        self.working = True

        skill = next((s for s in SKILLS if s["id"] == skill_id), None)
        if not skill:
            return

        self.show_report(skill["name"], f"⏳ 正在执行分析...\n\n请稍候，正在：\n① 从 OKX 拉取数据\n② 发送 AI 分析\n③ 生成报告...")

        threading.Thread(target=self._do_skill, args=(skill,), daemon=True).start()

    def _do_skill(self, skill):
        try:
            config = load_config()
            ai_cfg = get_ai_config(config)
            okx_cfg = get_okx_config(config)

            ai_client = AIClient(ai_cfg)
            okx_client = OKXClient(
                "api_key" if okx_cfg.get("api_key") else "public",
                {"api_key": okx_cfg.get("api_key", ""),
                 "secret_key": okx_cfg.get("secret_key", ""),
                 "passphrase": okx_cfg.get("passphrase", "")},
            )

            report = run_skill(skill["id"], ai_client, okx_client)
        except Exception as e:
            report = f"分析失败: {e}"
            log.error(f"技能执行失败 [{skill['id']}]: {e}")

        self.root.after(0, lambda: self._show_skill_result(skill["name"], report))

    def _show_skill_result(self, name, report):
        self.update_report_content(name, report)
        self.working = False

    # ── Page 2: Report ─────────────────────────────────────
    def show_report(self, title: str, content: str):
        self._clear()
        parent = self.page_report
        parent.pack(fill=tk.BOTH, expand=True)

        # Header with back button
        hdr = tk.Frame(parent, bg=self.bg)
        hdr.pack(fill=tk.X, padx=12, pady=(10, 4))

        back_btn = tk.Label(hdr, text="← 返回首页", font=("Microsoft YaHei", 9, "bold"),
                            fg=self.accent, bg=self.bg, cursor="hand2")
        back_btn.pack(side=tk.LEFT)
        back_btn.bind("<Button-1>", lambda e: self.show_home())

        self.report_title_lbl = tk.Label(hdr, text=title, font=("Microsoft YaHei", 12, "bold"),
                                          fg="#ffffff", bg=self.bg)
        self.report_title_lbl.pack(side=tk.LEFT, padx=16)

        # Copy button
        self.copy_btn = tk.Label(hdr, text="复制报告", font=("Microsoft YaHei", 9),
                                  fg=self.dim, bg=self.bg, cursor="hand2")
        self.copy_btn.pack(side=tk.RIGHT)
        self.copy_btn.bind("<Button-1>", lambda e: self._copy_report())

        # Separator
        tk.Frame(parent, bg=self.dim, height=1).pack(fill=tk.X, padx=12)

        # Report text
        self.report_text = scrolledtext.ScrolledText(
            parent, font=("Consolas", 10), bg="#0a1628", fg=self.fg,
            insertbackground=self.fg, relief=tk.FLAT, borderwidth=0,
            padx=14, pady=10, wrap=tk.WORD,
        )
        self.report_text.pack(fill=tk.BOTH, expand=True, padx=12, pady=6)
        self.report_text.insert("1.0", content)
        self.report_text.config(state=tk.DISABLED)

        self.current_page = "report"

    def update_report_content(self, title: str, content: str):
        self.report_title_lbl.config(text=title)
        self.report_text.config(state=tk.NORMAL)
        self.report_text.delete("1.0", tk.END)
        self.report_text.insert("1.0", content)
        self.report_text.config(state=tk.DISABLED)
        self.copy_btn.config(text="复制报告", fg=self.dim)

    def _copy_report(self):
        text = self.report_text.get("1.0", tk.END)
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.copy_btn.config(text="已复制!", fg=self.green)

    # ── Page 3: Settings ───────────────────────────────────
    def show_settings(self):
        self._clear()
        parent = self.page_settings
        parent.pack(fill=tk.BOTH, expand=True)

        # Header
        hdr = tk.Frame(parent, bg=self.bg)
        hdr.pack(fill=tk.X, padx=12, pady=(10, 4))
        back_btn = tk.Label(hdr, text="← 返回首页", font=("Microsoft YaHei", 9, "bold"),
                            fg=self.accent, bg=self.bg, cursor="hand2")
        back_btn.pack(side=tk.LEFT)
        back_btn.bind("<Button-1>", lambda e: self.show_home())
        tk.Label(hdr, text="⚙ 设置", font=("Microsoft YaHei", 12, "bold"),
                 fg="#ffffff", bg=self.bg).pack(side=tk.LEFT, padx=16)

        # Scrollable content
        canvas = tk.Canvas(parent, bg=self.bg, highlightthickness=0)
        scrollbar = tk.Scrollbar(parent, orient=tk.VERTICAL, command=canvas.yview)
        sf = tk.Frame(canvas, bg=self.bg)
        sf.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=sf, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))

        px, py = 16, 3

        # ── AI ──
        self._section(sf, "① AI 平台", 0)
        self._form_row(sf, "供应商:", px, py)
        self.cfg_provider = ttk.Combobox(sf, values=list(AI_PROVIDERS.keys()), state="readonly", width=22)
        self.cfg_provider.pack(fill=tk.X, padx=px, pady=py)
        self.cfg_provider.bind("<<ComboboxSelected>>", self._on_provider_change)

        self._form_row(sf, "API Key:", px, py)
        self.cfg_apikey = tk.Entry(sf, font=("Consolas", 10), show="*", width=42)
        self.cfg_apikey.pack(fill=tk.X, padx=px, pady=py)

        self._form_row(sf, "模型:", px, py)
        self.cfg_model = ttk.Combobox(sf, values=[], state="readonly", width=28)
        self.cfg_model.pack(fill=tk.X, padx=px, pady=py)

        self._form_row(sf, "接口地址:", px, py)
        self.cfg_baseurl = tk.Entry(sf, font=("Consolas", 9), width=42)
        self.cfg_baseurl.pack(fill=tk.X, padx=px, pady=py)

        test_frame = tk.Frame(sf, bg=self.bg)
        test_frame.pack(fill=tk.X, padx=px, pady=(4, 2))
        ttk.Button(test_frame, text="测试 AI 连接", command=self._test_ai).pack(side=tk.LEFT)
        self.ai_status_lbl = tk.Label(test_frame, text="", font=("Microsoft YaHei", 8), fg=self.dim, bg=self.bg)
        self.ai_status_lbl.pack(side=tk.LEFT, padx=8)

        # ── OKX ──
        self._section(sf, "② 交易所 (OKX)", 10)

        self._form_row(sf, "认证方式:", px, py)
        self.cfg_okx_auth = ttk.Combobox(sf, values=["public", "api_key"], state="readonly", width=10)
        self.cfg_okx_auth.pack(fill=tk.X, padx=px, pady=py)
        self.cfg_okx_auth.bind("<<ComboboxSelected>>", self._on_okx_auth_change)

        self.okx_key_frame = tk.Frame(sf, bg=self.bg)
        for label, attr in [("API Key", "cfg_okx_apikey"), ("Secret Key", "cfg_okx_secret"), ("Passphrase", "cfg_okx_pass")]:
            self._form_row(self.okx_key_frame, label + ":", 0, py)
            e = tk.Entry(self.okx_key_frame, font=("Consolas", 9), show="*", width=42)
            e.pack(fill=tk.X, padx=0, pady=py)
            setattr(self, attr, e)
        self.okx_key_frame.pack(fill=tk.X, padx=px, pady=(2, 2))
        self.okx_key_frame.pack_forget()

        self._form_row(sf, "交易模式:", px, py)
        self.cfg_okx_demo = ttk.Combobox(sf, values=["实盘", "模拟盘"], state="readonly", width=8)
        self.cfg_okx_demo.current(0)
        self.cfg_okx_demo.pack(fill=tk.X, padx=px, pady=py)

        test_okx = tk.Frame(sf, bg=self.bg)
        test_okx.pack(fill=tk.X, padx=px, pady=(4, 2))
        ttk.Button(test_okx, text="验证交易所连接", command=self._test_okx).pack(side=tk.LEFT)
        self.okx_status_lbl = tk.Label(test_okx, text="", font=("Microsoft YaHei", 8), fg=self.dim, bg=self.bg)
        self.okx_status_lbl.pack(side=tk.LEFT, padx=8)

        # ── Save ──
        self._section(sf, "", 8)
        ttk.Button(sf, text="保存设置", command=self._save_settings).pack(fill=tk.X, padx=px, pady=4)
        self.settings_status = tk.Label(sf, text="", font=("Microsoft YaHei", 8), fg=self.green, bg=self.bg)
        self.settings_status.pack(fill=tk.X, padx=px)

        # Security
        self._section(sf, "③ 安全与隐私", 8)
        tk.Label(sf, text="密钥仅本地存储 · 直连官方 API · 无中间服务器 · 开源可审计\n详见 SECURITY.md",
                 font=("Microsoft YaHei", 8), fg=self.dim, bg=self.bg, justify=tk.LEFT).pack(
            fill=tk.X, padx=px, pady=(0, 12))

        self._load_settings()
        self.current_page = "settings"

    def _section(self, parent, text, pady_top):
        if text:
            tk.Label(parent, text=text, font=("Microsoft YaHei", 10, "bold"),
                     fg=self.accent, bg=self.bg, anchor=tk.W).pack(
                fill=tk.X, padx=16, pady=(pady_top, 2))

    def _form_row(self, parent, label, px, py):
        tk.Label(parent, text=label, font=("Microsoft YaHei", 9), fg=self.fg, bg=self.bg,
                 anchor=tk.W).pack(fill=tk.X, padx=px, pady=(py + 2, 0))

    # ── Settings Logic ─────────────────────────────────────
    def _load_settings(self):
        config = load_config()
        ai = config.get("ai", {})
        okx = config.get("okx", {})

        self.cfg_provider.set(ai.get("provider", "deepseek"))
        self.cfg_apikey.insert(0, ai.get("api_key", ""))
        self._refresh_models()
        self.cfg_model.set(ai.get("model", ""))
        self.cfg_baseurl.insert(0, ai.get("base_url", ""))
        self.cfg_okx_auth.set(okx.get("auth_type", "public"))
        self.cfg_okx_apikey.insert(0, okx.get("api_key", ""))
        self.cfg_okx_secret.insert(0, okx.get("secret_key", ""))
        self.cfg_okx_pass.insert(0, okx.get("passphrase", ""))
        self._on_okx_auth_change()

    def _on_provider_change(self, e=None):
        key = self.cfg_provider.get()
        preset = AI_PROVIDERS.get(key, {})
        self.cfg_baseurl.delete(0, tk.END)
        self.cfg_baseurl.insert(0, preset.get("base_url", ""))
        self._refresh_models()

    def _refresh_models(self):
        key = self.cfg_provider.get()
        models = get_provider_models(key)
        self.cfg_model["values"] = models if models else ["(手动输入)"]
        if models:
            self.cfg_model.set(models[0])

    def _on_okx_auth_change(self, e=None):
        if self.cfg_okx_auth.get() == "api_key":
            self.okx_key_frame.pack()
        else:
            self.okx_key_frame.pack_forget()

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
        config["okx"] = {
            "auth_type": self.cfg_okx_auth.get(),
            "api_key": self.cfg_okx_apikey.get(),
            "secret_key": self.cfg_okx_secret.get(),
            "passphrase": self.cfg_okx_pass.get(),
            "demo": self.cfg_okx_demo.get() == "模拟盘",
            "signal_token": config.get("okx", {}).get("signal_token", ""),
        }
        save_config(config)
        self.settings_status.config(text="设置已保存！", fg=self.green)

    def _test_ai(self):
        self.ai_status_lbl.config(text="测试中...", fg=self.yellow)
        threading.Thread(target=self._do_test_ai, daemon=True).start()

    def _do_test_ai(self):
        ai_config = {
            "provider": self.cfg_provider.get(), "api_key": self.cfg_apikey.get(),
            "model": self.cfg_model.get(), "base_url": self.cfg_baseurl.get(),
            "api_format": AI_PROVIDERS.get(self.cfg_provider.get(), {}).get("api_format", "anthropic"),
            "enabled": bool(self.cfg_apikey.get()),
        }
        client = AIClient(ai_config)
        if not client.enabled:
            self.root.after(0, lambda: self.ai_status_lbl.config(text="请填写 API Key", fg=self.red))
            return
        result = client.chat("Reply with exactly 'OK'", "Hi")
        ok = result and "OK" in result
        self.root.after(0, lambda: self.ai_status_lbl.config(
            text="连接成功!" if ok else f"失败: {result[:60] if result else '无响应'}", fg=self.green if ok else self.red))

    def _test_okx(self):
        self.okx_status_lbl.config(text="测试中...", fg=self.yellow)
        threading.Thread(target=self._do_test_okx, daemon=True).start()

    def _do_test_okx(self):
        if self.cfg_okx_auth.get() != "api_key":
            self.root.after(0, lambda: self.okx_status_lbl.config(text="请选择 api_key 认证", fg=self.red))
            return
        ok, msg = OKXClient("api_key", {
            "api_key": self.cfg_okx_apikey.get(),
            "secret_key": self.cfg_okx_secret.get(),
            "passphrase": self.cfg_okx_pass.get(),
        }).test_connection()
        self.root.after(0, lambda: self.okx_status_lbl.config(
            text=msg, fg=self.green if ok else self.red))

    def _show_first_launch(self):
        msg = ("安全与隐私声明\n\n"
               "1. 所有密钥仅存储在本地，不会上传\n"
               "2. 网络请求仅发往你配置的官方 API\n"
               "3. 无遥测、无统计、无第三方收集\n\n"
               "点击「是」前往设置页面")
        if messagebox.askyesno("首次使用", msg):
            self.show_settings()

    def _quit(self):
        if messagebox.askokcancel("退出", "确定退出？"):
            app_state["running"] = False
            self.root.destroy()


# ── Main ────────────────────────────────────────────────────
def main():
    init_config()

    config = load_config()
    try:
        candles = fetch_candles(config.get("instrument", "BTC-USDT-SWAP"),
                                config.get("bar", "15m"), limit=60)
        price = candles[-1]["close"]
        with lock:
            app_state["price"] = price
    except Exception:
        pass

    threading.Thread(target=run_signal_check, daemon=True, name="signal").start()

    root = tk.Tk()
    app = App(root)
    root.protocol("WM_DELETE_WINDOW", app._quit)
    root.mainloop()
    log.info("应用已退出。")


if __name__ == "__main__":
    main()

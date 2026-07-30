#!/usr/bin/env python3
"""
配置管理器 — 统一管理 AI 供应商、OKX 连接、策略参数
首次启动自动从 btc_signal_config.example.json 复制模板

安全说明：
- 所有敏感数据（API Key、Secret 等）仅存储在本地 btc_signal_config.json
- 该文件已加入 .gitignore，不会被提交到版本控制
- 密钥仅在内存中使用，直接发往用户配置的官方 API，不经过任何中间服务器
"""

import json
import os
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_PATH = SCRIPT_DIR / "btc_signal_config.json"
APIKEY_PATH = SCRIPT_DIR / "apikey.txt"

# ── AI 供应商预设（参考 cc-switch 热门模型） ──────────────
AI_PROVIDERS: dict = {
    "deepseek": {
        "name": "DeepSeek",
        "base_url": "https://api.deepseek.com/anthropic",
        "api_format": "anthropic",
        "models": ["deepseek-v4-pro", "deepseek-v4-flash",
                   "deepseek-chat", "deepseek-reasoner"],
        "website": "https://platform.deepseek.com",
    },
    "openai": {
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "api_format": "openai_chat",
        "models": ["gpt-4.1", "gpt-4o", "gpt-4o-mini"],
        "website": "https://platform.openai.com",
    },
    "anthropic": {
        "name": "Anthropic Claude",
        "base_url": "https://api.anthropic.com",
        "api_format": "anthropic",
        "models": ["claude-sonnet-4-6", "claude-opus-4-7", "claude-haiku-4-5"],
        "website": "https://console.anthropic.com",
    },
    "ollama": {
        "name": "Ollama (本地)",
        "base_url": "http://localhost:11434/v1",
        "api_format": "openai_chat",
        "models": [],
        "website": "https://ollama.com",
    },
    "custom": {
        "name": "自定义",
        "base_url": "",
        "api_format": "anthropic",
        "models": [],
    },
}

DEFAULT_STRATEGY = {
    "webhook_url": "https://www.okx.com/pap/algo/signal/trigger",
    "signal_token": "",
    "instrument": "BTC-USDT-SWAP",
    "bar": "15m",
    "bb_period": 20,
    "bb_mult": 2.0,
    "rsi_period": 14,
    "rsi_oversold": 35,
    "rsi_overbought": 65,
    "cooldown_minutes": 120,
    "entry_investment_type": "percentage_balance",
    "entry_amount": "100",
    "exit_investment_type": "percentage_position",
    "exit_amount": "100",
    "strategy_mode": "mean_reversion",
    "breakout_lookback": 20,
    "breakout_vol_mult": 1.2,
}

DEFAULT_AI_CONFIG = {
    "provider": "deepseek",
    "api_key": "",
    "model": "deepseek-v4-pro",
    "base_url": "",
    "api_format": "anthropic",
    "enabled": False,
}

DEFAULT_OKX_CONFIG = {
    "auth_type": "public",
    "api_key": "",
    "secret_key": "",
    "passphrase": "",
    "mcp_url": "https://www.okx.com/api/v1/mcp/trading-oauth",
    "signal_token": "",
}


def init_config():
    """首次启动：从示例模板复制配置。返回 True 表示是新配置。"""
    if CONFIG_PATH.exists():
        return False
    example = SCRIPT_DIR / "btc_signal_config.example.json"
    if example.exists():
        import shutil
        shutil.copy(example, CONFIG_PATH)
    return True


def load_config() -> dict:
    """加载主配置，缺失字段自动补默认值。"""
    if not CONFIG_PATH.exists():
        init_config()

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)

    # 确保策略字段存在
    for k, v in DEFAULT_STRATEGY.items():
        config.setdefault(k, v)

    # 确保 AI 配置字段存在
    config.setdefault("ai", dict(DEFAULT_AI_CONFIG))
    for k, v in DEFAULT_AI_CONFIG.items():
        config["ai"].setdefault(k, v)

    # 确保 OKX 连接字段存在
    config.setdefault("okx", dict(DEFAULT_OKX_CONFIG))
    for k, v in DEFAULT_OKX_CONFIG.items():
        config["okx"].setdefault(k, v)

    # 兼容旧版：signal_token 在顶层 → 迁移到 okx.signal_token
    if config.get("signal_token") and not config["okx"]["signal_token"]:
        config["okx"]["signal_token"] = config["signal_token"]

    # 兼容旧版：从 apikey.txt 读取 DeepSeek key
    if not config["ai"]["api_key"] and APIKEY_PATH.exists():
        old_key = APIKEY_PATH.read_text(encoding="utf-8").strip()
        if old_key:
            config["ai"]["api_key"] = old_key
            config["ai"]["enabled"] = True
            save_config(config)

    return config


def save_config(config: dict):
    """保存主配置。"""
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def get_ai_config(config: dict = None) -> dict:
    """获取 AI 配置（含供应商预设信息合并）。"""
    if config is None:
        config = load_config()
    ai = config.get("ai", dict(DEFAULT_AI_CONFIG))
    provider_key = ai.get("provider", "deepseek")
    preset = AI_PROVIDERS.get(provider_key, AI_PROVIDERS["deepseek"])

    return {
        "provider": provider_key,
        "provider_name": preset["name"],
        "api_key": ai.get("api_key", ""),
        "model": ai.get("model", preset.get("models", [None])[0] or ""),
        "base_url": ai.get("base_url") or preset.get("base_url", ""),
        "api_format": ai.get("api_format") or preset.get("api_format", "anthropic"),
        "enabled": bool(ai.get("enabled") and ai.get("api_key")),
    }


def get_provider_models(provider_key: str) -> list:
    """获取指定供应商的模型列表。"""
    preset = AI_PROVIDERS.get(provider_key, AI_PROVIDERS["deepseek"])
    return preset.get("models", [])


def get_strategy_config(config: dict = None) -> dict:
    """获取策略参数。"""
    if config is None:
        config = load_config()
    return {k: config[k] for k in DEFAULT_STRATEGY if k in config}


def get_okx_config(config: dict = None) -> dict:
    """获取 OKX 连接配置。"""
    if config is None:
        config = load_config()
    okx = config.get("okx", dict(DEFAULT_OKX_CONFIG))
    return {
        "auth_type": okx.get("auth_type", "public"),
        "api_key": okx.get("api_key", ""),
        "secret_key": okx.get("secret_key", ""),
        "passphrase": okx.get("passphrase", ""),
        "mcp_url": okx.get("mcp_url", DEFAULT_OKX_CONFIG["mcp_url"]),
        "signal_token": okx.get("signal_token", "") or config.get("signal_token", ""),
    }


def is_configured(config: dict = None) -> bool:
    """检查是否已完成基本配置（至少 AI 或 OKX 已设置）。"""
    if config is None:
        config = load_config()
    ai_ok = bool(config.get("ai", {}).get("api_key"))
    okx_cfg = config.get("okx", {})
    okx_ok = bool(okx_cfg.get("api_key") or
                  (okx_cfg.get("signal_token") and
                   "PASTE" not in okx_cfg.get("signal_token", "")))
    return ai_ok or okx_ok

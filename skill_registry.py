#!/usr/bin/env python3
"""
技能注册中心 — 7 个内置分析技能
每个技能 = 数据获取 + Prompt 模板 + AI 分析 = 一键生成报告
"""

import logging
from datetime import datetime

log = logging.getLogger("btc_app")

# ── 技能定义 ────────────────────────────────────────────────

SKILLS = [
    {
        "id": "btc_full_report",
        "name": "BTC 综合报告",
        "icon": "📊",
        "description": "多维度综合分析：价格、指标、OI、资金费率、新闻、情绪",
        "data_fetcher": "_fetch_btc_full_data",
        "prompt_template": "_prompt_btc_full",
    },
    {
        "id": "technical_analysis",
        "name": "技术分析",
        "icon": "📈",
        "description": "70+ 技术指标分析，趋势、支撑阻力、形态研判",
        "data_fetcher": "_fetch_technical_data",
        "prompt_template": "_prompt_technical",
    },
    {
        "id": "trading_signal",
        "name": "交易信号",
        "icon": "💹",
        "description": "3 策略并行检测（均值回归/趋势跟随/突破），信号+置信度",
        "data_fetcher": "_fetch_signal_data",
        "prompt_template": "_prompt_signal",
    },
    {
        "id": "smart_money",
        "name": "智能资金",
        "icon": "🐋",
        "description": "交易员排行榜 + 共识信号 + 大户持仓动向",
        "data_fetcher": "_fetch_smart_money_data",
        "prompt_template": "_prompt_smart_money",
    },
    {
        "id": "market_sentiment",
        "name": "市场情绪",
        "icon": "📰",
        "description": "恐惧贪婪指数 + OKX 新闻 + AI 情绪分析",
        "data_fetcher": "_fetch_sentiment_data",
        "prompt_template": "_prompt_sentiment",
    },
    {
        "id": "risk_assessment",
        "name": "风险评估",
        "icon": "⚠️",
        "description": "持仓、杠杆、清算价、保证金率，风险评分+建议",
        "data_fetcher": "_fetch_risk_data",
        "prompt_template": "_prompt_risk",
    },
    {
        "id": "trading_plan",
        "name": "交易计划",
        "icon": "📋",
        "description": "OI/多空比/资金费率/清算/鲸鱼，三档风险计划",
        "data_fetcher": "_fetch_plan_data",
        "prompt_template": "_prompt_plan",
    },
]


def get_skill(skill_id: str) -> dict | None:
    """获取技能定义。"""
    for s in SKILLS:
        if s["id"] == skill_id:
            return s
    return None


def run_skill(skill_id: str, ai_client, okx_client) -> str:
    """
    执行技能：拉数据 → 组 prompt → 发 AI → 返回报告文本。

    ai_client: AIClient 实例
    okx_client: OKXClient 实例
    返回: 格式化报告字符串
    """
    skill = get_skill(skill_id)
    if not skill:
        return f"未知技能: {skill_id}"

    import report_engine as report

    # 1. 获取数据
    try:
        fetcher = globals().get(skill["data_fetcher"])
        if not fetcher:
            return report.generate_error_report(skill["name"], f"数据获取函数未找到: {skill['data_fetcher']}")
        data = fetcher(okx_client)
    except Exception as e:
        log.error(f"获取数据失败 [{skill_id}]: {e}")
        return report.generate_error_report(skill["name"], f"数据获取失败: {e}")

    # 2. 组装 prompt
    prompt_func = globals().get(skill["prompt_template"])
    if not prompt_func:
        return report.generate_error_report(skill["name"], f"Prompt 模板未找到: {skill['prompt_template']}")
    system_prompt, user_prompt = prompt_func(data)

    # 3. 调用 AI
    if not ai_client or not ai_client.enabled:
        # 无 AI 时直接返回数据
        return report.generate_report(
            skill["name"],
            f"数据已获取但未配置 AI 分析。请先在设置中配置 AI 平台。\n\n数据概要: {_summarize_data(data)}",
            _extract_key_metrics(data),
            skill["name"],
        )

    try:
        ai_result = ai_client.chat(system_prompt, user_prompt)
    except Exception as e:
        log.error(f"AI 调用失败 [{skill_id}]: {e}")
        return report.generate_error_report(skill["name"], f"AI 分析失败: {e}")

    if not ai_result:
        return report.generate_error_report(skill["name"], "AI 返回为空，请检查 API Key 和网络连接。")

    # 4. 生成报告
    return report.generate_report(
        skill["name"],
        ai_result,
        _extract_key_metrics(data),
        skill["name"],
    )


# ── Data Fetchers ───────────────────────────────────────────

def _fetch_btc_full_data(client) -> dict:
    from skills.sentiment import fetch_fear_greed
    candles = client.get_candles("BTC-USDT-SWAP", "15m", 60)
    ticker = client.get_ticker("BTC-USDT-SWAP")
    oi = client.get_open_interest("BTC-USDT-SWAP")
    fr = client.get_funding_rate("BTC-USDT-SWAP")
    fg = fetch_fear_greed(1)
    from strategy_engine import check_signal

    config = {"strategy_mode": "mean_reversion", "bb_period": 20, "bb_mult": 2.0,
              "rsi_period": 14, "rsi_oversold": 35, "rsi_overbought": 65}
    signal, reason = check_signal(candles, config, "NONE")

    news = client.get_news_latest(5) if client.has_credentials() else []
    traders = client.get_smart_money_traders("7", "pnl", 5) if client.has_credentials() else []
    signals = client.get_smart_money_signals("7", "pnl", 3) if client.has_credentials() else []

    return {
        "price": ticker["last"], "high24h": ticker["high24h"], "low24h": ticker["low24h"],
        "vol24h": ticker["vol24h"], "oi": oi["oi"], "funding_rate": fr["funding_rate"],
        "fear_greed": fg[0] if fg else {},
        "signal": signal, "signal_reason": reason,
        "news": news, "top_traders": traders, "consensus_signals": signals,
    }


def _fetch_technical_data(client) -> dict:
    candles = client.get_candles("BTC-USDT-SWAP", "1H", 100)
    ticker = client.get_ticker("BTC-USDT-SWAP")
    rsi_data = client.get_indicator("BTC-USDT-SWAP", "rsi", "1H")
    macd_data = client.get_indicator("BTC-USDT-SWAP", "macd", "1H")
    bb_data = client.get_indicator("BTC-USDT-SWAP", "bb", "1H")
    adx_data = client.get_indicator("BTC-USDT-SWAP", "adx", "1H")
    return {
        "price": ticker["last"], "high24h": ticker["high24h"], "low24h": ticker["low24h"],
        "candles_count": len(candles),
        "rsi": rsi_data[0] if rsi_data else {},
        "macd": macd_data[0] if macd_data else {},
        "bb": bb_data[0] if bb_data else {},
        "adx": adx_data[0] if adx_data else {},
    }


def _fetch_signal_data(client) -> dict:
    from strategy_engine import check_signal, get_available_modes
    candles = client.get_candles("BTC-USDT-SWAP", "15m", 60)
    ticker = client.get_ticker("BTC-USDT-SWAP")
    fr = client.get_funding_rate("BTC-USDT-SWAP")

    config_base = {"bb_period": 20, "bb_mult": 2.0, "rsi_period": 14,
                   "rsi_oversold": 35, "rsi_overbought": 65,
                   "breakout_lookback": 20, "breakout_vol_mult": 1.2}
    results = {}
    for mode in ["mean_reversion", "trend_following", "breakout"]:
        cfg = {**config_base, "strategy_mode": mode}
        action, reason = check_signal(candles, cfg, "NONE")
        results[mode] = {"action": action or "无信号", "reason": reason}

    return {"price": ticker["last"], "funding_rate": fr["funding_rate"],
            "signals": results, "modes": {k: v["name"] for k, v in get_available_modes().items()}}


def _fetch_smart_money_data(client) -> dict:
    traders = client.get_smart_money_traders("7", "pnl", 10)
    signals = client.get_smart_money_signals("7", "pnl", 5)
    return {"traders": traders, "signals": signals,
            "has_auth": client.has_credentials(),
            "note": "" if client.has_credentials() else "请配置 OKX API Key 后查看智能资金数据"}


def _fetch_sentiment_data(client) -> dict:
    from skills.sentiment import fetch_fear_greed
    fg = fetch_fear_greed(7)
    news = client.get_news_by_coin("BTC", 10) if client.has_credentials() else []
    return {"fear_greed": fg, "news": news,
            "has_auth": client.has_credentials(),
            "note": "" if client.has_credentials() else "请配置 OKX API Key 获取实时新闻"}


def _fetch_risk_data(client) -> dict:
    positions = client.get_positions() if client.has_credentials() else []
    balances = client.get_balance() if client.has_credentials() else {}
    return {"positions": positions, "balances": balances,
            "has_auth": client.has_credentials(),
            "note": "" if client.has_credentials() else "请配置 OKX API Key 查看持仓风险"}


def _fetch_plan_data(client) -> dict:
    from strategy_engine import check_signal, get_available_modes
    candles = client.get_candles("BTC-USDT-SWAP", "1H", 100)
    ticker = client.get_ticker("BTC-USDT-SWAP")
    oi = client.get_open_interest("BTC-USDT-SWAP")
    fr = client.get_funding_rate("BTC-USDT-SWAP")

    config_base = {"bb_period": 20, "bb_mult": 2.0, "rsi_period": 14,
                   "rsi_oversold": 35, "rsi_overbought": 65, "strategy_mode": "mean_reversion"}
    signal, reason = check_signal(candles, config_base, "NONE")

    smart = client.get_smart_money_signals("7", "pnl", 3) if client.has_credentials() else []
    traders = client.get_smart_money_traders("7", "pnl", 5) if client.has_credentials() else []

    return {"price": ticker["last"], "oi": oi["oi"], "funding_rate": fr["funding_rate"],
            "signal": signal, "signal_reason": reason,
            "smart_signals": smart, "top_traders": traders,
            "has_auth": client.has_credentials()}


# ── Prompt Templates ────────────────────────────────────────

def _prompt_btc_full(data: dict) -> tuple:
    sp = "你是加密货币分析师。用中文回答，输出结构化市场分析。"
    um = f"""请对 BTC 做多维度综合分析（200字以内）：

价格: ${data.get('price', 0):,.1f}
24h: ${data.get('high24h', 0):,.1f} / ${data.get('low24h', 0):,.1f}
OI: {data.get('oi', 0):,.0f} 合约
资金费率: {data.get('funding_rate', 0):.6f}
恐惧贪婪: {data.get('fear_greed', {}).get('value', '?')}/100 ({data.get('fear_greed', {}).get('classification', '?')})
当前信号: {data.get('signal') or '无'} — {data.get('signal_reason', '')}

新闻数: {len(data.get('news', []))}
大户信号数: {len(data.get('consensus_signals', []))}

请按此格式输出：
趋势判断: <上升/下降/震荡>
关键价位: 支撑 $xxx 阻力 $xxx
操作建议: <一句话>"""
    return sp, um


def _prompt_technical(data: dict) -> tuple:
    sp = "你是技术分析师。用中文输出技术分析，简洁专业。"
    rsi_info = data.get("rsi", {})
    macd_info = data.get("macd", {})
    bb_info = data.get("bb", {})
    adx_info = data.get("adx", {})

    um = f"""BTC 当前价格: ${data.get('price', 0):,.1f}

指标数据：
RSI(14,1H): {rsi_info}
MACD(1H): {macd_info}
布林带(1H): {bb_info}
ADX(1H): {adx_info}
24h 范围: ${data.get('high24h', 0):,.1f} / ${data.get('low24h', 0):,.1f}

请分析（150字以内）：
趋势: <方向>
支撑位/阻力位: <具体价位>
指标信号: RSI/MACD/ADX 各自给出的信号
操作建议: <一句话>"""
    return sp, um


def _prompt_signal(data: dict) -> tuple:
    sp = "你是交易信号分析师。用中文，简洁直接。"
    signals = data.get("signals", {})
    sig_lines = []
    for mode, info in signals.items():
        mode_name = data.get("modes", {}).get(mode, mode)
        sig_lines.append(f"{mode_name}: {info['action']} — {info['reason']}")

    um = f"""BTC 价格: ${data.get('price', 0):,.1f}
资金费率: {data.get('funding_rate', 0):.6f}

三策略并行检测结果：
{chr(10).join(sig_lines)}

请分析（100字以内）：
综合判断: 当前应做多/做空/观望？
置信度: 0-100%
建议: <一句话>"""
    return sp, um


def _prompt_smart_money(data: dict) -> tuple:
    sp = "你分析链上智能资金动向。用中文，简洁。"
    if data.get("note"):
        return sp, f"数据状态: {data['note']}"

    traders = data.get("traders", [])
    signals = data.get("signals", [])
    t_lines = [f"{t.get('nickname','?')}: PnL {t.get('pnl_ratio',0):.1%} 胜率 {t.get('win_rate',0):.0%}" for t in traders[:5]]
    s_lines = [f"{s.get('inst_ccy','?')}: 多{s.get('l_ratio',0):.0%} 空{s.get('s_ratio',0):.0%}" for s in signals[:5]]

    um = f"""智能资金数据：

顶级交易员（7天）：
{chr(10).join(t_lines) if t_lines else '无数据'}

共识信号：
{chr(10).join(s_lines) if s_lines else '无数据'}

请分析（150字以内）：
大户情绪: 偏多/偏空/中性
值得关注的方向: <方向>
操作建议: <一句话>"""
    return sp, um


def _prompt_sentiment(data: dict) -> tuple:
    sp = "你是市场情绪分析师。用中文，简洁。"
    fg_list = data.get("fear_greed", [])
    fg_now = fg_list[0] if fg_list else {}
    fg_trend = [d["value"] for d in fg_list] if len(fg_list) >= 3 else []

    news_text = ""
    for n in data.get("news", [])[:5]:
        news_text += f"- {n.get('title', '')}\n"

    um = f"""市场情绪数据：

恐惧贪婪指数: {fg_now.get('value', '?')}/100 ({fg_now.get('classification', '?')})
7日趋势: {fg_trend}
新闻数: {len(data.get('news', []))}

{news_text}

请分析（100字以内）：
情绪方向: bullish/bearish/neutral
一句话总结: <中文>"""
    return sp, um


def _prompt_risk(data: dict) -> tuple:
    sp = "你是风险管理分析师。用中文输出风险评估。"
    pos_list = data.get("positions", [])
    if not pos_list or data.get("note"):
        return sp, f"持仓状态: {data.get('note', '无持仓数据')}。请说明如何评估风险。"

    pos_lines = []
    for p in pos_list:
        pos_lines.append(f"{p['inst_id']} {p['pos_side']} {p['pos']}张 "
                        f"开仓价{p['avg_px']:.1f} 杠杆{p['lever']}x "
                        f"盈亏{p['upl']:.2f} ({p['upl_ratio']:.2%}) 强平价{p.get('liq_px',0):.1f}")

    um = f"""当前持仓风险：

{chr(10).join(pos_lines)}

请分析（150字以内）：
总体风险评分: 0-100
主要风险点: <描述>
调整建议: <一句话>"""
    return sp, um


def _prompt_plan(data: dict) -> tuple:
    sp = "你是交易策略师。生成结构化交易计划，用中文。"
    um = f"""BTC 数据：

价格: ${data.get('price', 0):,.1f}
OI: {data.get('oi', 0):,.0f} 合约
资金费率: {data.get('funding_rate', 0):.6f}
当前信号: {data.get('signal') or '无'} — {data.get('signal_reason', '')}
大户信号数: {len(data.get('smart_signals', []))}

请生成三档交易计划（200字以内）：

[保守]
入场: $xxx  止损: $xxx  止盈: $xxx  仓位: xx%

[中性]
入场: $xxx  止损: $xxx  止盈: $xxx  仓位: xx%

[激进]
入场: $xxx  止损: $xxx  止盈: $xxx  仓位: xx%"""
    return sp, um


# ── Utils ───────────────────────────────────────────────────

def _extract_key_metrics(data: dict) -> dict:
    """从原始数据提取关键指标作为报告摘要。"""
    metrics = {}
    if "price" in data:
        metrics["价格"] = f"${data['price']:,.1f}"
    if "funding_rate" in data and data["funding_rate"]:
        metrics["资金费率"] = f"{data['funding_rate']:.6f}"
    if "oi" in data and data["oi"]:
        metrics["OI"] = f"{data['oi']:,.0f} 合约"
    if "fear_greed" in data:
        fg = data["fear_greed"]
        if isinstance(fg, list) and fg:
            metrics["恐惧贪婪"] = f"{fg[0].get('value', '?')} ({fg[0].get('classification', '?')})"
        elif isinstance(fg, dict) and fg:
            metrics["恐惧贪婪"] = f"{fg.get('value', '?')} ({fg.get('classification', '?')})"
    if "signal" in data and data["signal"]:
        metrics["信号"] = data["signal"]
    if "candles_count" in data:
        metrics["K线数据"] = f"{data['candles_count']} 条"
    return metrics


def _summarize_data(data: dict) -> str:
    """将数据字典人可读化。"""
    parts = []
    for k, v in data.items():
        if isinstance(v, dict):
            parts.append(f"{k}: {len(v)} 项")
        elif isinstance(v, list):
            parts.append(f"{k}: {len(v)} 条")
        elif isinstance(v, (int, float)) and k not in ("funding_rate",):
            parts.append(f"{k}: {v:,.2f}" if isinstance(v, float) else f"{k}: {v}")
        else:
            parts.append(f"{k}: {v}")
    return "\n".join(parts[:20])

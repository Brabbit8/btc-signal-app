#!/usr/bin/env python3
"""
技能注册中心 — 7 个内置分析技能
每个技能 = 数据获取 + Prompt 模板 + AI 分析 = 一键生成报告

数据获取优先级：
  1. okx CLI (okx-cli) — 167 个工具全可用（需 npm install）
  2. OKX REST API (okx_client) — 公开 + 认证 API
  3. 回退提示 — 请配置 API Key 或安装 CLI
"""

import logging
from datetime import datetime

log = logging.getLogger("btc_app")


def _get_cli():
    """获取 OKX CLI 桥接（如果已安装）。"""
    try:
        import okx_cli
        if okx_cli.is_installed():
            return okx_cli
    except Exception:
        pass
    return None

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


# ── Data Fetchers — 尽最大努力使用所有可用工具 ─────────────

def _fetch_btc_full_data(client) -> dict:
    """综合报告：调用一切可用的工具获取最全面的数据。"""
    from skills.sentiment import fetch_fear_greed
    from strategy_engine import check_signal
    cli = _get_cli()

    # 行情数据（公开，永远可用）
    ticker = client.get_ticker("BTC-USDT-SWAP")
    candles_15m = client.get_candles("BTC-USDT-SWAP", "15m", 60)
    candles_1h = client.get_candles("BTC-USDT-SWAP", "1H", 60)
    oi = client.get_open_interest("BTC-USDT-SWAP")
    fr = client.get_funding_rate("BTC-USDT-SWAP")
    fg = fetch_fear_greed(7)

    # 技术指标（公开 API，永远可用）
    indicators = {}
    for ind in ["rsi", "macd", "bb", "adx", "ema", "supertrend"]:
        try:
            data = client.get_indicator("BTC-USDT-SWAP", ind, "1H")
            if data:
                indicators[ind] = data[0] if isinstance(data, list) and data else data
        except Exception:
            pass

    # 3 策略信号检测
    config = {"bb_period": 20, "bb_mult": 2.0, "rsi_period": 14,
              "rsi_oversold": 35, "rsi_overbought": 65,
              "breakout_lookback": 20, "breakout_vol_mult": 1.2}
    sig_results = {}
    for mode in ["mean_reversion", "trend_following", "breakout"]:
        action, reason = check_signal(candles_15m, {**config, "strategy_mode": mode}, "NONE")
        sig_results[mode] = {"action": action or "无信号", "reason": reason}

    # 新闻（CLI 优先 > REST API）
    news = []
    if cli:
        try:
            news_r = cli.news_by_coin("BTC", 10)
            news = news_r.get("data", []) if isinstance(news_r, dict) else []
        except Exception:
            pass
    if not news and client.has_credentials():
        news = client.get_news_by_coin("BTC", 10)

    # 智能资金（CLI 优先 > REST API）
    traders, signals = [], []
    if cli:
        try:
            t = cli.smartmoney_traders("7", "pnl", 10)
            s = cli.smartmoney_signals("7", "pnl", 5)
            traders = t.get("data", []) if isinstance(t, dict) else []
            signals = s.get("data", []) if isinstance(s, dict) else []
        except Exception:
            pass
    if not traders and client.has_credentials():
        traders = client.get_smart_money_traders("7", "pnl", 10)
        signals = client.get_smart_money_signals("7", "pnl", 5)

    # 账户数据（认证，可选）
    positions = []
    balances = {}
    if cli:
        try:
            pos_r = cli.account_positions()
            bal_r = cli.account_balance()
            positions = pos_r.get("data", []) if isinstance(pos_r, dict) else []
            balances = bal_r.get("data", {}) if isinstance(bal_r, dict) else {}
        except Exception:
            pass
    if not positions and client.has_credentials():
        positions = client.get_positions()
        balances = client.get_balance()

    return {
        "price": ticker["last"], "high24h": ticker["high24h"], "low24h": ticker["low24h"],
        "vol24h": ticker["vol24h"], "oi": oi["oi"], "funding_rate": fr["funding_rate"],
        "fear_greed": fg, "fear_greed_now": fg[0] if fg else {},
        "indicators": indicators, "signals": sig_results,
        "news": news, "news_count": len(news),
        "top_traders": traders, "consensus_signals": signals,
        "positions": positions, "balances": balances,
        "has_cli": cli is not None,
        "has_auth": client.has_credentials() or cli is not None,
        "data_sources": _list_sources(cli, client.has_credentials()),
    }


def _fetch_technical_data(client) -> dict:
    """技术分析：拉取 70+ 指标中最重要的 10+ 个。"""
    ticker = client.get_ticker("BTC-USDT-SWAP")
    candles = client.get_candles("BTC-USDT-SWAP", "1H", 100)

    # 批量拉取指标
    indicator_list = ["rsi", "macd", "bb", "adx", "ema", "ma",
                      "kdj", "supertrend", "atr", "cci", "wr", "mom"]
    indicators = {}
    for ind in indicator_list:
        try:
            data = client.get_indicator("BTC-USDT-SWAP", ind, "1H")
            if data:
                indicators[ind] = data[0] if isinstance(data, list) and data else data
        except Exception:
            pass

    return {
        "price": ticker["last"], "high24h": ticker["high24h"], "low24h": ticker["low24h"],
        "candles_count": len(candles), "indicators": indicators,
        "indicator_count": len(indicators),
    }


def _fetch_signal_data(client) -> dict:
    """交易信号：3 策略并行 + 多时间周期验证。"""
    from strategy_engine import check_signal, get_available_modes
    ticker = client.get_ticker("BTC-USDT-SWAP")
    fr = client.get_funding_rate("BTC-USDT-SWAP")

    config_base = {"bb_period": 20, "bb_mult": 2.0, "rsi_period": 14,
                   "rsi_oversold": 35, "rsi_overbought": 65,
                   "breakout_lookback": 20, "breakout_vol_mult": 1.2}

    # 多时间周期验证
    results = {}
    for bar_name, bar in [("15m", "15m"), ("1H", "1H"), ("4H", "4H")]:
        try:
            candles = client.get_candles("BTC-USDT-SWAP", bar, 60)
            bar_results = {}
            for mode in ["mean_reversion", "trend_following", "breakout"]:
                action, reason = check_signal(candles, {**config_base, "strategy_mode": mode}, "NONE")
                bar_results[mode] = action or "无信号"
            results[bar_name] = bar_results
        except Exception:
            results[bar_name] = {"error": "数据获取失败"}

    return {"price": ticker["last"], "funding_rate": fr["funding_rate"],
            "multi_timeframe": results,
            "modes": {k: v["name"] for k, v in get_available_modes().items()}}


def _fetch_smart_money_data(client) -> dict:
    """智能资金：交易员排行榜 + 多周期信号 + 个别交易员持仓。"""
    cli = _get_cli()

    traders_7d = traders_30d = signals_7d = signals_30d = []

    if cli:
        try:
            traders_7d = cli.smartmoney_traders("7", "pnl", 10)
            traders_7d = traders_7d.get("data", []) if isinstance(traders_7d, dict) else []
            traders_30d = cli.smartmoney_traders("30", "pnl", 10)
            traders_30d = traders_30d.get("data", []) if isinstance(traders_30d, dict) else []
            signals_7d = cli.smartmoney_signals("7", "pnl", 5)
            signals_7d = signals_7d.get("data", []) if isinstance(signals_7d, dict) else []
            signals_30d = cli.smartmoney_signals("30", "pnl", 5)
            signals_30d = signals_30d.get("data", []) if isinstance(signals_30d, dict) else []
        except Exception:
            pass

    if not traders_7d and client.has_credentials():
        traders_7d = client.get_smart_money_traders("7", "pnl", 10)
        signals_7d = client.get_smart_money_signals("7", "pnl", 5)

    return {
        "traders_7d": traders_7d[:5], "traders_30d": traders_30d[:5],
        "signals_7d": signals_7d, "signals_30d": signals_30d,
        "has_data": bool(traders_7d or traders_30d),
        "note": "" if (traders_7d or cli or client.has_credentials())
                else "请配置 OKX API Key 或安装 CLI",
    }


def _fetch_sentiment_data(client) -> dict:
    """市场情绪：恐惧贪婪 + 新闻 + 智能资金情绪。"""
    from skills.sentiment import fetch_fear_greed
    cli = _get_cli()

    fg = fetch_fear_greed(14)  # 14天趋势

    news = []
    if cli:
        try:
            r = cli.news_latest(15)
            news = r.get("data", []) if isinstance(r, dict) else []
        except Exception:
            pass
    if not news and client.has_credentials():
        news = client.get_news_latest(15)

    return {
        "fear_greed": fg, "fear_greed_now": fg[0] if fg else {},
        "fear_greed_trend_14d": [d["value"] for d in fg] if fg else [],
        "news": news[:15], "news_count": len(news),
        "has_auth": client.has_credentials() or cli is not None,
    }


def _fetch_risk_data(client) -> dict:
    """风险评估：持仓 + 余额 + 账户配置。"""
    cli = _get_cli()

    positions = balances = config_data = []
    if cli:
        try:
            positions = cli.account_positions()
            positions = positions.get("data", []) if isinstance(positions, dict) else []
            balances = cli.account_balance()
            balances = balances.get("data", {}) if isinstance(balances, dict) else {}
        except Exception:
            pass
    if not positions and client.has_credentials():
        positions = client.get_positions()
        balances = client.get_balance()
        config_data = client.get_account_config()

    return {
        "positions": positions, "balances": balances,
        "account_config": config_data,
        "position_count": len(positions) if isinstance(positions, list) else 0,
        "has_auth": client.has_credentials() or cli is not None,
        "note": "" if (positions or cli or client.has_credentials())
                else "请配置 OKX API Key 或安装 CLI 查看持仓",
    }


def _fetch_plan_data(client) -> dict:
    """交易计划：行情 + 信号 + 智能资金 + 情绪，全部数据综合。"""
    from strategy_engine import check_signal
    ticker = client.get_ticker("BTC-USDT-SWAP")
    candles = client.get_candles("BTC-USDT-SWAP", "1H", 100)
    oi = client.get_open_interest("BTC-USDT-SWAP")
    fr = client.get_funding_rate("BTC-USDT-SWAP")

    # 信号
    config = {"bb_period": 20, "bb_mult": 2.0, "rsi_period": 14,
              "rsi_oversold": 35, "rsi_overbought": 65,
              "breakout_lookback": 20, "breakout_vol_mult": 1.2}
    signals = {}
    for mode in ["mean_reversion", "trend_following", "breakout"]:
        action, reason = check_signal(candles, {**config, "strategy_mode": mode}, "NONE")
        signals[mode] = {"action": action or "无信号", "reason": reason}

    # 关键指标
    indicators = {}
    for ind in ["rsi", "macd", "bb", "adx", "supertrend"]:
        try:
            data = client.get_indicator("BTC-USDT-SWAP", ind, "1H")
            if data:
                indicators[ind] = data[0] if isinstance(data, list) and data else data
        except Exception:
            pass

    # 智能资金 + 恐惧贪婪
    cli = _get_cli()
    traders, smart_sigs = [], []
    if cli:
        try:
            traders = cli.smartmoney_traders("7", "pnl", 5)
            smart_sigs = cli.smartmoney_signals("7", "pnl", 3)
        except Exception:
            pass
    if not traders and client.has_credentials():
        traders = client.get_smart_money_traders("7", "pnl", 5)
        smart_sigs = client.get_smart_money_signals("7", "pnl", 3)
    from skills.sentiment import fetch_fear_greed
    fg = fetch_fear_greed(1)

    return {
        "price": ticker["last"], "high24h": ticker["high24h"], "low24h": ticker["low24h"],
        "oi": oi["oi"], "funding_rate": fr["funding_rate"],
        "indicators": indicators, "signals": signals,
        "smart_signals": smart_sigs, "top_traders": traders,
        "fear_greed": fg[0] if fg else {},
        "has_auth": client.has_credentials() or cli is not None,
        "data_sources": _list_sources(cli, client.has_credentials()),
    }


# ── Prompt Templates ────────────────────────────────────────

def _prompt_btc_full(data: dict) -> tuple:
    sp = "你是资深加密货币分析师。用中文输出精准的结构化市场分析报告。"
    fg = data.get("fear_greed_now", {})
    indicators = data.get("indicators", {})
    sigs = data.get("signals", {})
    traders = data.get("top_traders", [])
    cons = data.get("consensus_signals", [])

    # 格式化指标
    ind_lines = []
    for name, val in indicators.items():
        v = val.get("value") or val.get(list(val.keys())[0]) if isinstance(val, dict) and val else str(val)
        ind_lines.append(f"  {name.upper()}: {v}")
    ind_text = "\n".join(ind_lines[:15]) if ind_lines else "无"

    # 格式化信号
    sig_lines = []
    for mode, s in sigs.items():
        sig_lines.append(f"  {mode}: {s.get('action', '?')} — {s.get('reason', '')}")
    sig_text = "\n".join(sig_lines)

    # 格式化交易员
    t_lines = []
    for t in traders[:5]:
        t_lines.append(f"  {t.get('nickname', t.get('nickName', '?'))}: "
                      f"PnL {_pct(t.get('pnl_ratio', t.get('pnlRatio', 0)))}, "
                      f"胜率 {_pct(t.get('win_rate', t.get('winRate', 0)))}")
    t_text = "\n".join(t_lines) if t_lines else "无数据"

    # 共识信号
    c_lines = []
    for c in cons[:5]:
        c_lines.append(f"  {c.get('inst_ccy', c.get('instCcy', '?'))}: "
                      f"多{_pct(c.get('l_ratio', c.get('lRatio', 0)))} "
                      f"空{_pct(c.get('s_ratio', c.get('sRatio', 0)))}")
    c_text = "\n".join(c_lines) if c_lines else "无数据"

    # 数据源说明
    sources = data.get("data_sources", "")

    um = f"""BTC 综合数据 ({sources})：

【行情】
  价格: ${data.get('price', 0):,.1f}
  24h 范围: ${data.get('high24h', 0):,.1f} ~ ${data.get('low24h', 0):,.1f}
  成交量: ${data.get('vol24h', 0):,.0f}
  OI: {data.get('oi', 0):,.0f} 合约
  资金费率: {data.get('funding_rate', 0):.6f}

【技术指标】
{ind_text}

【策略信号】
{sig_text}

【恐惧贪婪】
  {fg.get('value', '?')}/100 — {fg.get('classification', '?')}
  7日趋势: {[d.get('value', 0) for d in data.get('fear_greed', [])[:7]]}

【大户动向 ({len(traders)}人)】
{t_text}

【共识信号】
{c_text}

【新闻】{data.get('news_count', 0)}条

请给出精准的 BTC 综合分析（300字以内）：

1. 趋势判断: <上升/下降/震荡>，置信度 xx%
2. 关键价位: 支撑 $xxx / 阻力 $xxx（基于 BB+EMA）
3. 资金面: 大户偏多/偏空，资金费率含义
4. 情绪面: 恐惧贪婪 + 新闻方向
5. 综合建议: 做多/做空/观望，具体理由"""
    return sp, um


def _prompt_technical(data: dict) -> tuple:
    sp = "你是专业的技术分析师。用中文输出精准的技术分析。"
    indicators = data.get("indicators", {})

    ind_lines = []
    for name, val in indicators.items():
        if isinstance(val, dict) and val:
            v = val.get("value") or val.get(list(val.keys())[0])
            ind_lines.append(f"  {name.upper()}: {v}")
        else:
            ind_lines.append(f"  {name.upper()}: {val}")
    ind_text = "\n".join(ind_lines)

    um = f"""BTC 当前价格: ${data.get('price', 0):,.1f}
24h: ${data.get('high24h', 0):,.1f} ~ ${data.get('low24h', 0):,.1f}
共获取 {data.get('indicator_count', 0)} 个指标：

{ind_text}

请给出精准的技术分析（200字）：
1. 趋势: 方向+强度(基于ADX/EMA排列/SUPERTREND)
2. RSI/MACD/KDJ 各自信号及含义
3. 布林带位置: 价格在带中的位置 + 带宽变化
4. 关键价位: 支撑位 + 阻力位（具体数值）
5. 操作建议: 方向+时机"""


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


def _pct(val) -> str:
    """格式化百分比。"""
    if isinstance(val, float):
        return f"{val:.1%}"
    try:
        return f"{float(val):.1%}"
    except (ValueError, TypeError):
        return str(val)


def _list_sources(cli, has_auth: bool) -> str:
    """列出当前可用的数据源。"""
    sources = ["公开API"]
    if has_auth:
        sources.append("认证API")
    if cli:
        sources.append("CLI")
    return " + ".join(sources)


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

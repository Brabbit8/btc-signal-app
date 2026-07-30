# BTC AI Analysis Hub

**The bridge between AI and Exchange** — connect your AI + connect your exchange, click once for precise analysis reports.

No MCP knowledge needed. No prompt writing. No API calls. Click → auto-fetch data → AI analysis → report.

## Data Flow

```
Click a skill button
    ↓
① OKX CLI (167 tools) → if not installed: REST API → fallback: public API
    ↓
② Data fills prompt → sent to AI (DeepSeek/OpenAI/Claude)
    ↓
③ AI interprets data → generates structured report
    ↓
④ Display (copyable)
```

## Interface

Three-page design (Tkinter):

| Page | Purpose |
|------|---------|
| Home | 7 skill buttons + AI/CLI/Exchange connection status |
| Report | Structured report (conclusion/data/AI analysis/disclaimer), copyable |
| Settings | AI platform + OKX exchange + CLI install guide + security |

## Quick Start

```bash
pip install -r requirements.txt
python main.py
```

First launch → security notice → settings page → fill in AI Key → (optional) configure OKX / install CLI → home page → click any button.

## Data Source Priority

| Priority | Source | Tools | Requires |
|----------|--------|-------|----------|
| 1 | OKX CLI (`okx-trade-cli`) | 167 | `npm install -g @okx_ai/okx-trade-cli` |
| 2 | OKX REST API (API Key) | ~30 | Enter API Key in settings |
| 3 | OKX Public API | ~15 | Nothing, free |

The app auto-detects the best available source on startup.

## 7 Built-in Skills

| Skill | Tools Automatically Called | AI Output |
|-------|--------------------------|-----------|
| BTC Full Report | Ticker+OI+Funding+12 Indicators+3 Strategy Signals+News+Smart Money+Fear & Greed | Multi-dimensional analysis |
| Technical Analysis | 12 Indicators (RSI/MACD/BB/ADX/EMA/MA/KDJ/SUPERTREND/ATR/CCI/WR/MOM) | Trend+S/R+Signal interpretation |
| Trading Signal | 3 Strategies × 3 Timeframes = 9 parallel checks | Multi-timeframe signal+confidence |
| Smart Money | 7-day+30-day trader leaderboards + consensus signals | Whale movement+capital flow |
| Market Sentiment | 14-day Fear & Greed + 15 news articles + AI sentiment | Sentiment direction+extremes |
| Risk Assessment | Positions+Leverage+Margin+Liquidation+P&L | Risk score+adjustment advice |
| Trading Plan | Price+Indicators+Signals+Smart Money+Sentiment | 3-tier (conservative/moderate/aggressive) |

## 3 Strategy Modes

| Mode | Logic | Best For |
|------|-------|----------|
| Mean Reversion | BB+RSI: price hits Bollinger Band + RSI confirmation | Ranging |
| Trend Following | EMA crossover + ADX confirmation | Trending |
| Breakout | Price breaks range + volume surge | High volatility |

## Supported AI Platforms

| Provider | Popular Models | API Format |
|----------|---------------|------------|
| DeepSeek | deepseek-v4-pro, deepseek-v4-flash | Anthropic-compatible |
| OpenAI | gpt-4.1, gpt-4o, gpt-4o-mini | OpenAI Chat |
| Anthropic | claude-sonnet-4-6, claude-opus-4-7 | Anthropic Messages |
| Ollama | Manual input | OpenAI-compatible (local) |
| Custom | Manual input | Anthropic / OpenAI format |

## Project Structure

```
main.py                       # Entry point, Tkinter GUI (Home/Report/Settings)
skill_registry.py             # 7 skills: auto-fetch data + Prompt + AI analysis
report_engine.py              # Standardized report format engine
config_manager.py             # Config + 5 AI provider presets
ai_client.py                  # Unified AI client (Anthropic/OpenAI SDK)
okx_client.py                 # OKX REST client (public + HMAC-signed)
okx_cli.py                    # OKX CLI bridge (167 tools, auto-detect)
strategy_engine.py            # Strategy engine (3 modes)
btc_signal_bot.py             # Signal detection engine (BB+RSI+ATR)
btc_strategy_adaptor.py       # Strategy adaptor (ADX trend detection)
skills/                       # Data fetching helper modules
btc_signal_config.json        # User config (gitignored)
SECURITY.md                   # Security & privacy info
```

## Build .exe

```bash
# Double-click build.bat, or manually:
pip install pyinstaller
pyinstaller --onefile --console --name btc-signal-app main.py
```

## Security & Privacy

- All credentials **stored locally only** in `btc_signal_config.json` (gitignored)
- Requests **only sent to** your configured official APIs (OKX / DeepSeek / OpenAI / Anthropic)
- **Zero telemetry, zero analytics, zero third-party data collection**
- Fully open source, all network calls auditable in source code
- See [SECURITY.md](SECURITY.md)

## Disclaimer

This tool is for educational purposes only. It does not constitute investment advice. Cryptocurrency trading carries extreme risk. Use at your own discretion.

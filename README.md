# BTC Signal App

Automated BTC trading signal detection with optional AI-powered market analysis.

## Features

- **Signal Detection**: BB(20,2) + RSI(14) strategy, checks every 5 minutes
- **AI Analysis**: Periodic DeepSeek AI analysis for market regime detection and auto parameter tuning (every 2 hours)
- **Alert System**: Writes `btc_signal_alert.txt` when signals trigger
- **Status Dashboard**: Real-time console display of price, indicators, position
- **Configurable**: All strategy parameters in `btc_signal_config.json`

## Quick Start

```bash
pip install -r requirements.txt
python main.py
```

On first run, you'll be prompted to enter your DeepSeek API key (optional — skip to use signal detection only).

## Console Controls

| Key | Action |
|-----|--------|
| R | Force refresh |
| A | Run AI analysis now |
| Q | Quit |

## Build .exe

```bash
build.bat
```

Or manually:

```bash
pip install pyinstaller
pyinstaller --onefile --console --name btc-signal-app main.py
```

Output: `dist/btc-signal-app.exe` (~15 MB, no Python required)

## Strategy Parameters

Configured in `btc_signal_config.json`:

| Parameter | Default | Description |
|-----------|---------|-------------|
| rsi_oversold | 35 | RSI threshold for long entry |
| rsi_overbought | 65 | RSI threshold for short entry |
| bb_mult | 2.0 | Bollinger Band standard deviation multiplier |
| cooldown_minutes | 120 | Minimum minutes between signals |
| instrument | BTC-USDT-SWAP | Trading pair |

AI analysis can auto-adjust these based on market regime.

## Architecture

```
main.py
├── btc_signal_bot.py       # Signal detection engine
├── btc_strategy_adaptor.py # Market regime classifier
└── AI module               # DeepSeek API integration
```

Data source: OKX public REST API (no API key required for market data).

## License

MIT

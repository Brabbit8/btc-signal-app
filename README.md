# BTC 信号机器人

基于 BB(20,2) + RSI(14) 策略的 BTC 自动信号检测工具，内置 DeepSeek AI 市场分析，实时控制台面板。

## 功能

| 功能 | 频率 | 说明 |
|------|------|------|
| 信号检测 | 每 5 分钟 | 布林带 + RSI 策略，自动判断做多/做空/离场 |
| AI 市场分析 | 每 2 小时 | 调用 DeepSeek API 判断市场状态（震荡/趋势），自动调整策略参数 |
| 信号提醒 | 实时 | 触发信号时生成 `btc_signal_alert.txt`，拿去让 Claude Code 帮你下单 |
| 控制台面板 | 实时刷新 | 显示价格、指标、持仓、信号状态 |

## 环境要求

- Python 3.11+
- Windows / macOS / Linux

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置文件
#    首次运行会自动从 btc_signal_config.example.json 复制一份配置
#    编辑 btc_signal_config.json，填入你的 OKX 信号策略 signalToken

# 3. 运行
python main.py
```

首次运行会提示输入 DeepSeek API Key。按回车跳过则只启用信号检测，不使用 AI 分析。

## 控制台操作

| 按键 | 功能 |
|------|------|
| `R` | 手动刷新 |
| `A` | 立即触发一次 AI 分析 |
| `Q` | 退出程序 |

## 打包为 .exe

```bash
# 方法一：双击 build.bat

# 方法二：手动执行
pip install pyinstaller
pyinstaller --onefile --console --name btc-signal-app main.py
```

生成的 `dist/btc-signal-app.exe` 约 15MB，无需安装 Python 即可在 Windows 上直接双击运行。

## 策略参数

在 `btc_signal_config.json` 中配置：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `rsi_oversold` | 35 | RSI 超卖阈值，低于此值考虑做多 |
| `rsi_overbought` | 65 | RSI 超买阈值，高于此值考虑做空 |
| `bb_period` | 20 | 布林带周期 |
| `bb_mult` | 2.0 | 布林带标准差倍数 |
| `cooldown_minutes` | 120 | 两次信号最小间隔（分钟） |
| `instrument` | BTC-USDT-SWAP | 交易对 |

AI 分析会根据市场状态自动调整以上参数——震荡行情放宽阈值、缩短冷却，趋势行情收紧阈值、延长冷却。

## 信号逻辑

```
做多：收盘价 ≤ 布林带下轨 × 1.003  且  RSI < rsi_oversold
做空：收盘价 ≥ 布林带上轨 × 0.997  且  RSI > rsi_overbought
离场（持多时）：收盘价 ≥ 布林带中轨
离场（持空时）：收盘价 ≤ 布林带中轨
```

离场不受冷却时间限制，任何时候达到条件都会触发。

## 工作流建议

1. 打开 VS Code 终端运行 `python main.py`
2. 程序在后台每 5 分钟检测信号，每 2 小时 AI 分析调参
3. 看到桌面多了 `btc_signal_alert.txt` → 打开 Claude Code → 说"执行信号"
4. Claude Code 通过 MCP 帮你下单
5. 你只需要在触发信号时看一眼，平时不用管

## 项目结构

```
main.py                       # 主入口，控制台界面 + 多线程调度
btc_signal_bot.py             # 信号检测引擎（BB+RSI+ATR）
btc_strategy_adaptor.py       # 策略适配器（ADX 趋势检测 + 自动调参）
btc_signal_config.json        # 策略参数配置（不上传 GitHub）
btc_signal_state.json         # 持仓状态记录
```

## 数据来源

- 行情数据：OKX 公开 REST API（免费，无需 API Key）
- AI 分析：DeepSeek API（可选，需自行申请 Key）

## 免责声明

本工具仅供学习参考，不构成投资建议。加密货币交易风险极高，请自行判断并承担风险。

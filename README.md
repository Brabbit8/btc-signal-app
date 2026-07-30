# BTC 信号机器人 v2.0

基于 BB(20,2) + RSI(14) 策略的 BTC 自动信号检测桌面应用，内置多 AI 平台支持、技术分析、交易计划生成和 OKX 连接。

## 界面预览

多 Tab 桌面应用（Tkinter），全中文界面：

| Tab | 功能 |
|-----|------|
| 行情监控 | BTC 实时价格、RSI、布林带、ATR、持仓方向、信号状态、AI 市场分析 |
| 技术分析 | 多周期 K 线指标分析（15m / 1H / 4H / 1D） |
| 交易计划 | 6 维评分 + 保守/中性/激进三档交易计划 |
| 新闻情绪 | 恐惧贪婪指数 + OKX 账户余额/持仓 + AI 市场情绪分析 |
| 设置 | AI 供应商配置 + OKX 连接 + 策略参数 |

## 环境要求

- Python 3.11+
- Windows / macOS / Linux

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 运行
python main.py
```

首次运行会弹出安全声明，确认后跳转到设置页面配置 AI 和 OKX 连接。不配置也能用——应用自动回退到公开 API 模式。

## 支持的 AI 平台

| 供应商 | 模型 | 接口 |
|--------|------|------|
| DeepSeek | deepseek-v4-pro, deepseek-v4-flash | Anthropic 兼容 |
| OpenAI | gpt-4.1, gpt-4o, gpt-4o-mini | OpenAI Chat |
| Anthropic | claude-sonnet-4-6, claude-opus-4-7, claude-haiku-4-5 | Anthropic Messages |
| Ollama | 手动输入 | OpenAI 兼容（本地） |
| 自定义 | 手动输入 | 可选 Anthropic / OpenAI 格式 |

## OKX 连接方式

| 方式 | 说明 |
|------|------|
| 公开 API | 默认，无需配置，行情数据免费使用 |
| API Key | 填入 Key/Secret/Passphrase，支持账户余额、持仓查询 |

OKX 官方 MCP 地址：`https://www.okx.com/api/v1/mcp/trading-oauth`（在 Claude Code 等 AI Agent 中使用）

## 操作快捷键

| 按键 | 功能 |
|------|------|
| `1` - `5` | 切换 Tab |
| `R` | 手动刷新行情 |
| `A` | 触发 AI 分析 |
| `Q` | 退出程序 |

## 信号逻辑

```
做多：收盘价 ≤ 布林带下轨 × 1.003  且  RSI < rsi_oversold
做空：收盘价 ≥ 布林带上轨 × 0.997  且  RSI > rsi_overbought
离场（持多时）：收盘价 ≥ 布林带中轨
离场（持空时）：收盘价 ≤ 布林带中轨
```

离场不受冷却时间限制。AI 分析每 2 小时根据市场状态自动调整参数。

## 策略参数

在设置 Tab 中直接修改，保存到 `btc_signal_config.json`：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `rsi_oversold` | 35 | RSI 超卖阈值 |
| `rsi_overbought` | 65 | RSI 超买阈值 |
| `bb_period` | 20 | 布林带周期 |
| `bb_mult` | 2.0 | 布林带标准差倍数 |
| `cooldown_minutes` | 120 | 两次信号最小间隔（分钟） |

## 交易计划评分维度

| 维度 | 权重 | 说明 |
|------|------|------|
| 持仓量趋势 | 20% | OI 变化方向 |
| 多空比 | 20% | 市场情绪偏向 |
| 资金费率 | 15% | 多头成本 |
| 清算数据 | 15% | 爆仓方向 |
| 鲸鱼持仓 | 15% | 大资金动向 |
| 技术信号 | 15% | RSI + BB 综合 |

## 项目结构

```
main.py                       # 主入口，Tkinter 多 Tab GUI
main_console.py               # v1 控制台版本（备用）
config_manager.py             # 配置管理 + AI 供应商预设
ai_client.py                  # 统一 AI 调用（Anthropic/OpenAI SDK）
okx_client.py                 # OKX 客户端（公开 API + HMAC 签名认证）
btc_signal_bot.py             # 信号检测引擎（BB+RSI+ATR）
btc_strategy_adaptor.py       # 策略适配器（ADX 趋势检测 + 自动调参）
skills/                       # 内置技能模块
  market_data.py              # OKX 行情数据
  technical.py                # 技术分析 + 多指标计算
  sentiment.py                # 市场情绪 + 恐惧贪婪指数
  trading_plan.py             # 交易计划生成器
btc_signal_config.json        # 用户配置（gitignore，不上传）
btc_signal_state.json         # 持仓状态（gitignore）
```

## 打包为 .exe

```bash
# 双击 build.bat，或手动：
pip install pyinstaller
pyinstaller --onefile --console --name btc-signal-app main.py
```

## 安全与隐私

- 所有密钥仅存储在本地 `btc_signal_config.json`，已加入 `.gitignore`
- 网络请求仅发往用户主动配置的官方 API（OKX / DeepSeek / OpenAI / Anthropic）
- 无遥测、无统计、无第三方数据收集
- 详见 [SECURITY.md](SECURITY.md)

## 数据来源

- 行情数据：OKX 公开 REST API（免费，无需 Key）
- 恐惧贪婪指数：[Alternative.me](https://alternative.me/crypto/fear-and-greed-index/)（免费）
- AI 分析：DeepSeek / OpenAI / Anthropic API（可选）
- OKX 账户数据：需配置 API Key

## 免责声明

本工具仅供学习参考，不构成投资建议。加密货币交易风险极高，请自行判断并承担风险。

# BTC AI 分析中枢

**AI × 交易所的中间桥梁** — 连接 AI + 连接交易所，一键获得分析报告。

不需要懂 MCP、不需要写 Prompt、不需要调 API。点击按钮 → 自动拉数据 → AI 分析 → 出报告。

## 界面

三页设计（Tkinter），全中文界面：

| 页面 | 功能 |
|------|------|
| 首页 | 7 个分析技能按钮 + AI/交易所连接状态 |
| 报告 | 标准化分析报告（结论/数据/AI分析/风险提示），可复制 |
| 设置 | 连接 AI 平台 + 连接 OKX 交易所 + 安全信息 |

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 运行
python main.py
```

首次运行弹出安全声明 → 进入设置页 → 填写 AI 的 API Key → 选填 OKX API Key → 回到首页点击任意分析按钮。

不配置 AI Key 也能看原始数据，配置后获得 AI 分析报告。

## 7 个内置技能

| 技能 | 说明 | 数据源 |
|------|------|--------|
| BTC 综合报告 | 价格/指标/OI/资金费率/新闻/情绪，多维度综合分析 | OKX + 恐惧贪婪 + AI |
| 技术分析 | 70+ 技术指标，趋势/支撑阻力/形态分析 | OKX indicator API |
| 交易信号 | 3 策略并行（均值回归/趋势跟随/突破），信号+置信度 | OKX 行情 + 策略引擎 |
| 智能资金 | 交易员排行榜 + 共识信号 + 大户持仓动向 | OKX smart money API |
| 市场情绪 | 恐惧贪婪指数 + OKX 新闻 + AI 情绪解读 | Alternative.me + OKX |
| 风险评估 | 持仓/杠杆/清算价/保证金率，风险评分+建议 | OKX 账户 API |
| 交易计划 | OI/多空比/资金费率/清算/鲸鱼，三档风险计划 | OKX + 策略引擎 |

## 3 种策略模式

AI 可根据市场状态自动切换策略：

| 模式 | 逻辑 | 最佳行情 |
|------|------|----------|
| 均值回归 | BB+RSI：价格触及布林带边界 + RSI 确认 | 震荡 |
| 趋势跟随 | EMA 交叉 + ADX 确认：顺势入场 | 趋势 |
| 突破交易 | 价格突破区间 + 成交量放大 | 高波动 |

## 支持的 AI 平台

| 供应商 | 模型 | 接口 |
|--------|------|------|
| DeepSeek | deepseek-v4-pro, deepseek-v4-flash | Anthropic 兼容 |
| OpenAI | gpt-4.1, gpt-4o, gpt-4o-mini | OpenAI Chat |
| Anthropic | claude-sonnet-4-6, claude-opus-4-7, claude-haiku-4-5 | Anthropic Messages |
| Ollama | 手动输入 | OpenAI 兼容（本地） |
| 自定义 | 手动输入 | Anthropic / OpenAI 格式可选 |

## OKX 连接方式

| 方式 | 说明 |
|------|------|
| 公开 API | 默认，无需配置，行情数据免费使用 |
| API Key | 填入 Key/Secret/Passphrase，解锁智能资金/新闻/账户数据 |

## 项目结构

```
main.py                       # 主入口，Tkinter GUI（首页/报告/设置）
skill_registry.py             # 7 个技能：数据获取 + Prompt + AI 调用
report_engine.py              # 标准化报告格式引擎
config_manager.py             # 配置管理 + 5 个 AI 供应商预设
ai_client.py                  # 统一 AI 客户端（Anthropic/OpenAI SDK）
okx_client.py                 # OKX 客户端（公开 API + 签名认证）
strategy_engine.py            # 策略引擎（均值回归/趋势跟随/突破）
btc_signal_bot.py             # 信号检测引擎（BB+RSI+ATR 计算）
btc_strategy_adaptor.py       # 策略适配器（ADX 趋势检测）
skills/                       # 数据获取模块
btc_signal_config.json        # 用户配置（gitignore）
SECURITY.md                   # 安全与隐私说明
```

## 打包为 .exe

```bash
# 双击 build.bat，或手动：
pip install pyinstaller
pyinstaller --onefile --console --name btc-signal-app main.py
```

## 安全与隐私

- 所有密钥**仅存储在本地** `btc_signal_config.json`，已加入 `.gitignore`
- 网络请求**仅发往**你主动配置的官方 API（OKX / DeepSeek / OpenAI / Anthropic）
- **无遥测、无统计、无第三方数据收集**
- 完全开源，所有网络请求可在源代码中审计
- 详见 [SECURITY.md](SECURITY.md)

## 免责声明

本工具仅供学习参考，不构成投资建议。加密货���交易风险极高，请自行判断并承担风险。

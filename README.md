# BTC AI 分析中枢

**AI × 交易所的中间桥梁** — 连接 AI + 连接交易所，一键获得精准分析报告。

不需要懂 MCP、不需要写 Prompt、不需要调 API。点击按钮 → 自动调用所有可用工具拉数据 → AI 实时分析 → 出报告。

## 数据流

```
点击技能按钮
    ↓
① OKX CLI (167个工具) → 没装则 REST API → 都没有则公开API
    ↓
② 数据填充到 Prompt → 发给 AI (DeepSeek/OpenAI/Claude)
    ↓
③ AI 解读数据 → 生成结构化报告
    ↓
④ 展示 (可复制)
```

## 界面

三页设计（Tkinter），全中文：

| 页面 | 功能 |
|------|------|
| 首页 | 7 个技能按钮 + AI/CLI/交易所连接状态实时显示 |
| 报告 | 标准化报告（结论/数据/AI分析/风险提示），一键复制 |
| 设置 | AI 平台 + OKX 交易所 + CLI 安装引导 + 安全信息 |

## 快速开始

```bash
pip install -r requirements.txt
python main.py
```

首次启动 → 安全声明 → 设置页 → 填写 AI Key → （可选）配 OKX / 装 CLI → 回到首页 → 点击按钮。

## 数据源优先级

| 优先级 | 数据源 | 工具数 | 需要 |
|--------|--------|--------|------|
| 1 | OKX CLI (`okx-trade-cli`) | 167 | `npm install -g @okx_ai/okx-trade-cli` |
| 2 | OKX REST API (API Key) | ~30 | 在设置页填 API Key |
| 3 | OKX 公开 API | ~15 | 无需配置，免费 |

应用启动时自动检测，优先使用可用的最佳数据源。

## 7 个内置技能

| 技能 | 自动调用的工具 | AI 输出 |
|------|---------------|---------|
| BTC 综合报告 | 行情+OI+资金费率+12指标+3策略信号+新闻+智能资金+恐惧贪婪 | 多维度综合分析 |
| 技术分析 | 12 个指标 (RSI/MACD/BB/ADX/EMA/MA/KDJ/SUPERTREND/ATR/CCI/WR/MOM) | 趋势+支撑阻力+信号解读 |
| 交易信号 | 3策略 × 3时间周期 = 9路并行检测 | 多周期综合信号+置信度 |
| 智能资金 | 7日+30日交易员排行榜 + 共识信号 | 大户动向+资金流向 |
| 市场情绪 | 14日恐惧贪婪 + 15条新闻 + AI情绪 | 情绪方向+极端信号检测 |
| 风险评估 | 持仓+杠杆+保证金+强平价+盈亏 | 风险评分+调整建议 |
| 交易计划 | 行情+指标+信号+智能资金+情绪全数据 | 三档风险入场/止盈/止损 |

## 3 种策略模式

| 模式 | 逻辑 | 适用行情 |
|------|------|----------|
| 均值回归 | BB+RSI：价格触及布林带边界 + RSI 确认 | 震荡 |
| 趋势跟随 | EMA 交叉 + ADX 确认 | 单边趋势 |
| 突破交易 | 价格突破区间 + 成交量放大 | 高波动 |

## 支持的 AI 平台

| 供应商 | 热门模型 | 接口格式 |
|--------|---------|----------|
| DeepSeek | deepseek-v4-pro, deepseek-v4-flash | Anthropic 兼容 |
| OpenAI | gpt-4.1, gpt-4o, gpt-4o-mini | OpenAI Chat |
| Anthropic | claude-sonnet-4-6, claude-opus-4-7 | Anthropic Messages |
| Ollama | 手动输入 | OpenAI 兼容（本地） |
| 自定义 | 手动输入 | 可选 Anthropic / OpenAI |

## 项目结构

```
main.py                       # 主入口，Tkinter GUI（首页/报告/设置）
skill_registry.py             # 7 技能：自动拉数据 + Prompt + AI 分析
report_engine.py              # 标准化报告格式引擎
config_manager.py             # 配置管理 + 5 AI 供应商预设
ai_client.py                  # 统一 AI 客户端 (Anthropic/OpenAI SDK)
okx_client.py                 # OKX REST 客户端 (公开 + HMAC 签名)
okx_cli.py                    # OKX CLI 桥接 (167工具, 自动检测)
strategy_engine.py            # 策略引擎 (3 种模式)
btc_signal_bot.py             # 信号检测引擎 (BB+RSI+ATR)
btc_strategy_adaptor.py       # 策略适配器 (ADX 趋势检测)
skills/                       # 数据获取辅助模块
btc_signal_config.json        # 用户配置 (gitignore)
SECURITY.md                   # 安全与隐私说明
```

## 打包为 .exe

```bash
# 双击 build.bat，或手动：
pip install pyinstaller
pyinstaller --onefile --console --name btc-signal-app main.py
```

## 安全与隐私

- 所有密钥**仅存储在本地** `btc_signal_config.json` (gitignore)
- 请求**仅发往**你配置的官方 API (OKX / DeepSeek / OpenAI / Anthropic)
- **零遥测、零统计、零第三方收集**
- 完全开源，所有网络请求可审计
- 详见 [SECURITY.md](SECURITY.md)

## 免责声明

本工具仅供学习参考，不构成投资建议。加密货币交易风险极高，请自行判断并承担风险。

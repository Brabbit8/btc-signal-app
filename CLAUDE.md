# CLAUDE.md

本文件为 Claude Code (claude.ai/code) 在此仓库中工作时提供指导。

## 常用命令

```bash
pip install -r requirements.txt   # 安装依赖 (requests, anthropic)
python main.py                    # 启动完整应用（控制台界面 + 信号检测 + AI 分析）
python btc_signal_bot.py          # 执行一次信号检测
python btc_signal_bot.py --loop   # 独立运行信号检测循环（每 5 分钟一次）
python btc_strategy_adaptor.py    # 执行一次策略适配（市场状态检测 + 配置更新）
build.bat                         # Windows: 通过 PyInstaller 打包为 .exe
```

## 架构

三个模块，依赖链清晰：

**`main.py`** — 应用入口。负责实时控制台 UI（`render_ui` / `clear_screen`），三个守护线程（每 5 分钟信号检测、每 2 小时 AI 分析、键盘监听 R/A/Q 快捷键），通过 `threading.Lock` 管理共享的应用状态。分别从 `btc_signal_bot` 和 `btc_strategy_adaptor` 导入指标计算函数。

**`btc_signal_bot.py`** — 核心信号检测引擎。从 OKX 公开 REST API 获取 K 线数据，计算 BB(20,2) + RSI(14) + ATR(14)，判断入场/离场信号，将持仓状态持久化到 JSON，触发信号时生成 `btc_signal_alert.txt`，并向 OKX Signal Bot 发送 webhook 实现自动下单。可独立运行（`--loop`），也可由 `main.py` 驱动。

**`btc_strategy_adaptor.py`** — 市场状态分类与自动调参模块。分析多时间周期数据（15m/1H/4H），使用 ADX、EMA 排列和线性斜率将市场分类为 `ranging` / `trending_up` / `trending_down` 并附带置信度。直接覆写 `btc_signal_config.json`，根据市场状态调整 RSI 阈值、冷却时间和 BB 乘数（震荡行情放宽阈值，趋势行情收紧阈值）。其 `adapt_config()` 原地修改配置字典并写入磁盘。

## 关键细节

- **OKX 数据来源**：公开 REST API `https://www.okx.com/api/v5/market/candles` — 无需认证。原始 K 线数组已反转，索引 0 为最早的数据。
- **AI 分析**：通过 Anthropic Python SDK 调用 DeepSeek API，使用 `base_url="https://api.deepseek.com/anthropic"`。API Key 存储在 `apikey.txt`（已 gitignore）。AI 返回包含市场状态和参数建议的 JSON。针对 DeepSeek 推理模型做了特殊处理——答案可能出现在 `block.thinking` 而非 `block.text`。
- **有意的代码重复**：`fetch_candles`、`calc_sma`、`calc_atr` 在 `btc_signal_bot.py` 和 `btc_strategy_adaptor.py` 中均有定义。这是有意为之——每个模块都设计为可独立运行。请勿在未询问的情况下将其提取为共享工具函数。
- **配置流程**：首次运行自动从 `btc_signal_config.example.json` 复制生成 `btc_signal_config.json`。策略适配器或 AI 分析会在运行时覆写此配置。
- **本项目无测试套件**。
- **信号逻辑**：离场信号不受冷却时间限制（随时触发）。入场信号需冷却时间已过且当前无持仓。无活跃信号时会清除告警文件（`ALERT_PATH.unlink()`）。

# 安全与隐私说明

## 你的数据在哪里

**所有敏感数据仅存储在你本地的 `btc_signal_config.json` 文件中**，包括：
- AI 平台 API Key
- OKX API Key / Secret / Passphrase
- OKX Signal Token
- 策略参数

该文件已加入 `.gitignore`，不会被提交到 Git。

## 数据流向

```
你的输入 → btc_signal_config.json (本地文件)
                ↓
          应用内存 (RAM)
                ↓
   ┌───────────┼───────────┐
   ↓           ↓           ↓
OKX 官方    DeepSeek    OpenAI/Anthropic
API 服务器    API 服务器   API 服务器
```

**本应用：**
- ✅ 请求仅发往你主动配置的 AI 供应商和 OKX 官方 API
- ✅ 不运行任何中间代理服务器
- ✅ 不连接任何第三方分析/遥测服务
- ✅ 所有网络请求可在源代码中审计

**本应用不会：**
- ❌ 将你的 API Key 发送到任何非官方服务器
- ❌ 上传你的持仓、交易记录到云端
- ❌ 收集任何使用数据或统计信息
- ❌ 连接任何第三方广告或追踪服务

## 审计代码

本项目完全开源。所有网络请求集中在以下文件中：

| 文件 | 请求目标 |
|------|----------|
| `okx_client.py` | `https://www.okx.com` — OKX 官方 REST API |
| `ai_client.py` | 你在设置中选择的 AI 供应商 API |
| `skills/sentiment.py` | `https://api.alternative.me` — 恐惧贪婪指数（公开免费） |

## 安全建议

1. **使用 OKX API Key 时**，建议创建仅具有「读取」和「交易」权限的 Key，**不要**授予「提现」权限
2. **定期更换** API Key
3. **不要**将 `btc_signal_config.json` 分享给他人
4. 如果你使用打包后的 `.exe`，确保它来自可信来源

## 报告安全问题

如果你发现安全漏洞，请在 GitHub 提交 Issue（标注 `security`），或发送邮件到项目维护者。

请不要在公开 Issue 中暴露你的 API Key 或个人信息。

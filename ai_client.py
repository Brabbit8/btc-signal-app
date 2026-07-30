#!/usr/bin/env python3
"""
统一 AI 客户端 — 支持 DeepSeek / OpenAI / Anthropic / Ollama
根据配置自动选择 SDK 和 API 格式

安全说明：API Key 仅在请求时通过 HTTPS 发往所选 AI 供应商的官方 API。
不会发送到任何其他服务器。
"""

import json
import logging

log = logging.getLogger("btc_app")


class AIClient:
    """统一的 AI 调用接口。"""

    def __init__(self, ai_config: dict):
        """
        ai_config: get_ai_config() 返回的字典，包含:
          provider, api_key, model, base_url, api_format
        """
        self.provider = ai_config["provider"]
        self.api_key = ai_config["api_key"]
        self.model = ai_config["model"]
        self.base_url = ai_config["base_url"]
        self.api_format = ai_config.get("api_format", "anthropic")
        self.enabled = ai_config.get("enabled", False)

    def chat(self, system_prompt: str, user_message: str) -> str | None:
        """发送对话请求，返回模型回复文本。失败返回 None。"""
        if not self.enabled:
            return None

        if self.api_format == "anthropic":
            return self._call_anthropic(system_prompt, user_message)
        else:
            return self._call_openai(system_prompt, user_message)

    def chat_json(self, system_prompt: str, user_message: str) -> dict | None:
        """发送对话请求，返回解析后的 JSON。"""
        text = self.chat(system_prompt, user_message)
        if not text:
            return None
        try:
            start = text.find("{")
            end = text.rfind("}") + 1
            if start != -1 and end > start:
                return json.loads(text[start:end])
        except json.JSONDecodeError:
            log.error(f"AI 返回非 JSON: {text[:200]}")
        return None

    def _call_anthropic(self, system_prompt: str, user_message: str) -> str | None:
        """通过 Anthropic SDK 调用（DeepSeek / Anthropic / 自定义兼容接口）。"""
        try:
            from anthropic import Anthropic
        except ImportError:
            log.error("anthropic 未安装: pip install anthropic")
            return None

        try:
            client = Anthropic(base_url=self.base_url, api_key=self.api_key)
            response = client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            )
            text = ""
            for block in response.content:
                if hasattr(block, "text"):
                    text += block.text
                elif hasattr(block, "thinking"):
                    text += block.thinking
            return text.strip() or None
        except Exception as e:
            log.error(f"AI (Anthropic) 调用失败: {e}")
            return None

    def _call_openai(self, system_prompt: str, user_message: str) -> str | None:
        """通过 OpenAI SDK 调用（OpenAI / Ollama）。"""
        try:
            from openai import OpenAI
        except ImportError:
            log.error("openai 未安装: pip install openai")
            return None

        try:
            client = OpenAI(base_url=self.base_url, api_key=self.api_key)
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ]
            response = client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=4096,
            )
            return response.choices[0].message.content.strip() or None
        except Exception as e:
            log.error(f"AI (OpenAI) 调用失败: {e}")
            return None


# ── 快捷函数 ────────────────────────────────────────────────

def create_client(config: dict = None) -> AIClient:
    """从配置创建 AI 客户端。"""
    from config_manager import get_ai_config
    return AIClient(get_ai_config(config))


def quick_chat(system_prompt: str, user_message: str) -> str | None:
    """快捷对话 — 自动从配置加载。"""
    client = create_client()
    return client.chat(system_prompt, user_message)

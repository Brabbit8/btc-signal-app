#!/usr/bin/env python3
"""
报告引擎 — 标准化分析报告格式
每个技能输出统一格式的报告：标题 / 核心结论 / 关键数据 / AI分析 / 风险提示
"""

from datetime import datetime


def generate_report(title: str, ai_result: str, data: dict = None,
                    skill_name: str = "") -> str:
    """
    生成标准格式报告。

    title: 报告标题
    ai_result: AI 分析结果文本
    data: 关键数据字典，如 {"价格": "$64,292", "RSI": "66"}
    skill_name: 技能名称（用于日志）
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sep = "=" * 50

    lines = [
        sep,
        f"  {title}",
        f"  {now}",
        sep,
        "",
    ]

    # 提取核心结论（AI 返回的前 80 字）
    if ai_result:
        conclusion = _extract_conclusion(ai_result)
        lines.append("【核心结论】")
        lines.append(conclusion)
        lines.append("")

    # 关键数据
    if data:
        lines.append("【关键数据】")
        for k, v in data.items():
            lines.append(f"  {k}: {v}")
        lines.append("")

    # AI 分析
    if ai_result:
        lines.append("【AI 分析】")
        for line in ai_result.strip().split("\n"):
            lines.append(f"  {line}")
        lines.append("")

    # 风险提示
    lines.append("【风险提示】")
    lines.append("  本报告由 AI 生成，仅供学习参考，不构成投资建议。")
    lines.append("  加密货币交易风险极高，请自行判断并承担风险。")
    lines.append("")
    lines.append(sep)

    return "\n".join(lines)


def _extract_conclusion(text: str, max_len: int = 100) -> str:
    """从 AI 分析文本提取核心结论（第一段前 max_len 字）。"""
    text = text.strip()
    if not text:
        return "暂无结论"

    # 取第一段
    first_para = text.split("\n\n")[0].split("\n")[0]
    if len(first_para) <= max_len:
        return first_para
    return first_para[:max_len - 3] + "..."


def format_report_for_tk(text: str) -> str:
    """将报告文本转为 Tkinter Text widget 可用的格式。"""
    return text


def generate_error_report(title: str, error: str) -> str:
    """生成错误报告。"""
    sep = "=" * 50
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return f"{sep}\n  {title}\n  {now}\n{sep}\n\n【错误】\n  {error}\n\n{sep}"


def generate_loading_text(skill_name: str) -> str:
    """生成加载中的提示文本。"""
    return f"⏳ 正在执行「{skill_name}」分析...\n\n正在从 OKX 获取数据 → 发送给 AI 分析 → 生成报告..."

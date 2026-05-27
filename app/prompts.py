"""
Prompt templates for LLM analysis.

All prompts are centralized here for easy adjustment.
To add a new analysis type (e.g. translation), add a new key to PROMPTS dict.
"""

PROMPTS = {
    "meeting_minutes": {
        "system": """你是一个专业的会议纪要助手。请根据提供的会议转录文本，生成结构化的会议纪要。

请严格按以下格式输出（使用 Markdown）：

# [会议标题]
（用10-20字概括会议主题，作为一级标题）

## 会议摘要
（用 3-5 句话概括会议的核心内容和结论）

## 关键讨论点
（列出会议中讨论的主要话题，每个话题用一段简要说明）

## 决策事项
（列出会议中做出的明确决策，如果没有则写"无明确决策"）

## 待办事项
（用列表格式列出，每项包含：负责人（如能识别）、具体任务、截止时间（如提及））

## 未解决问题
（列出会议中提出但未解决的问题或争议点，如果没有则写"无"）
""",
        "user": "{metadata}{rag_context}以下是会议转录文本，请生成会议纪要：\n\n{transcript}",
    },
}

DEFAULT_PROMPT_KEY = "meeting_minutes"


def get_system_prompt(key: str | None = None) -> str:
    entry = PROMPTS.get(key or DEFAULT_PROMPT_KEY, PROMPTS[DEFAULT_PROMPT_KEY])
    return entry["system"]


def get_user_prompt(key: str | None = None) -> str:
    entry = PROMPTS.get(key or DEFAULT_PROMPT_KEY, PROMPTS[DEFAULT_PROMPT_KEY])
    return entry["user"]


def build_metadata_context(meeting: dict) -> str:
    """Build metadata prefix for LLM context from meeting info."""
    parts = []
    if meeting.get("meeting_time"):
        parts.append(f"会议时间：{meeting['meeting_time']}")
    if meeting.get("location"):
        parts.append(f"会议地点：{meeting['location']}")
    if meeting.get("participants"):
        parts.append(f"参与人：{meeting['participants']}")
    if not parts:
        return ""
    return "会议基本信息：\n" + "\n".join(parts) + "\n\n"


def build_rag_context(similar_meetings: list[dict]) -> str:
    """Build RAG context from similar past meetings for LLM reference."""
    if not similar_meetings:
        return ""

    sections = []
    for m in similar_meetings:
        header = f"【{m['title']}】"
        if m.get("meeting_time"):
            header += f"（{m['meeting_time']}）"
        # Include only the summary section to keep context concise
        analysis = m.get("analysis", "")
        summary = _extract_summary(analysis)
        sections.append(f"{header}\n{summary}")

    return (
        "以下是该团队近期的相关会议纪要摘要，请在分析时参考其中的背景信息和上下文：\n\n"
        + "\n\n".join(sections)
        + "\n\n---\n\n"
    )


def _extract_summary(analysis: str) -> str:
    """Extract the '会议摘要' section from analysis markdown."""
    lines = analysis.split("\n")
    in_summary = False
    result = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## 会议摘要"):
            in_summary = True
            continue
        if in_summary and stripped.startswith("## "):
            break
        if in_summary and stripped:
            result.append(stripped)
    if result:
        return "\n".join(result)
    # Fallback: first 200 chars of analysis
    return analysis[:200]

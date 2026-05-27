"""
Prompt templates for LLM analysis.

All prompts are centralized here for easy adjustment.
To add a new analysis type (e.g. translation), add a new key to PROMPTS dict.
"""

PROMPTS = {
    "meeting_minutes": {
        "system": """你是一个专业的会议纪要助手。请根据提供的会议转录文本，生成结构化的会议纪要。

请按以下格式输出（使用 Markdown）：

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
        "user": "{metadata}以下是会议转录文本，请生成会议纪要：\n\n{transcript}",
    },

    "generate_title": {
        "system": "你是一个标题生成助手。请根据会议转录内容，生成一个简洁准确的会议标题（10-20字）。只输出标题本身，不要加引号或其他格式。",
        "user": "请为以下会议内容生成标题：\n\n{transcript}",
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

"""LLM-based meeting analysis using Qwen via OpenAI-compatible API."""

import re
import logging
from openai import OpenAI
from app.config import DASHSCOPE_API_KEY, QWEN_BASE_URL, QWEN_MODEL, LLM_TEMPERATURE, LLM_MAX_TOKENS
from app.prompts import get_system_prompt, get_user_prompt, build_metadata_context

logger = logging.getLogger(__name__)


def _get_client() -> OpenAI:
    if not DASHSCOPE_API_KEY:
        raise RuntimeError("未配置 QWEN_API_KEY，请在 .env 文件中设置。")
    return OpenAI(api_key=DASHSCOPE_API_KEY, base_url=QWEN_BASE_URL)


def analyze_meeting(
    transcript: str,
    custom_prompt: str | None = None,
    meeting: dict | None = None,
    need_title: bool = False,
) -> dict | str:
    """Analyze meeting transcript with LLM.

    Returns:
        If need_title=True: {"title": str, "analysis": str}
        Otherwise: str (analysis markdown)
    """
    client = _get_client()

    system = custom_prompt or get_system_prompt()
    user_template = get_user_prompt()

    metadata = build_metadata_context(meeting) if meeting else ""
    user_message = user_template.format(transcript=transcript, metadata=metadata)

    response = client.chat.completions.create(
        model=QWEN_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_message},
        ],
        temperature=LLM_TEMPERATURE,
        max_tokens=LLM_MAX_TOKENS,
    )
    content = response.choices[0].message.content or "分析结果为空"

    if need_title:
        title, analysis = _extract_title(content)
        return {"title": title, "analysis": analysis}

    return content


def _extract_title(markdown: str) -> tuple[str, str]:
    """Extract H1 title from markdown, return (title, remaining_markdown)."""
    lines = markdown.strip().split("\n")

    for i, line in enumerate(lines):
        stripped = line.strip()
        # Match "# xxx" but not "## xxx"
        m = re.match(r"^#\s+(.+)$", stripped)
        if m and not stripped.startswith("## "):
            title = m.group(1).strip().strip("[]")
            remaining = "\n".join(lines[i + 1:]).strip()
            return title, remaining

    return "未命名会议", markdown

"""LLM-based meeting analysis using Qwen via OpenAI-compatible API."""

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
) -> str:
    """Analyze meeting transcript with LLM. Returns markdown analysis text."""
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
    return response.choices[0].message.content or "分析结果为空"


def generate_title(transcript: str) -> str:
    """Generate a concise meeting title from transcript using LLM."""
    client = _get_client()

    system = get_system_prompt("generate_title")
    user_template = get_user_prompt("generate_title")
    # Use first ~500 chars for speed and cost
    snippet = transcript[:500]
    user_message = user_template.format(transcript=snippet)

    response = client.chat.completions.create(
        model=QWEN_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_message},
        ],
        temperature=0.3,
        max_tokens=64,
    )
    title = (response.choices[0].message.content or "").strip().strip('"\'')
    return title or "未命名会议"

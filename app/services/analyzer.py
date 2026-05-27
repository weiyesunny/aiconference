"""LLM-based meeting analysis using Qwen via OpenAI-compatible API."""

import logging
from openai import OpenAI
from app.config import DASHSCOPE_API_KEY, QWEN_BASE_URL, QWEN_MODEL, LLM_TEMPERATURE, LLM_MAX_TOKENS
from app.prompts import get_system_prompt, get_user_prompt

logger = logging.getLogger(__name__)


def analyze_meeting(transcript: str, custom_prompt: str | None = None) -> str:
    """Analyze meeting transcript with LLM. Returns markdown analysis text."""
    if not DASHSCOPE_API_KEY:
        raise RuntimeError("未配置 QWEN_API_KEY，请在 .env 文件中设置。")

    client = OpenAI(api_key=DASHSCOPE_API_KEY, base_url=QWEN_BASE_URL)

    system = custom_prompt or get_system_prompt()
    user_template = get_user_prompt()
    user_message = user_template.format(transcript=transcript)

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

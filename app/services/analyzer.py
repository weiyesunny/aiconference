import logging
from openai import OpenAI
from app.config import DASHSCOPE_API_KEY, QWEN_BASE_URL, QWEN_MODEL

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是一个专业的会议纪要助手。请根据提供的会议转录文本，生成结构化的会议纪要。

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
"""


def analyze_meeting(transcript: str, custom_prompt: str | None = None) -> str:
    """Call Qwen API to analyze meeting transcript."""
    if not DASHSCOPE_API_KEY:
        return "错误：未配置 QWEN_API_KEY，请在 .env 文件中设置。"

    client = OpenAI(api_key=DASHSCOPE_API_KEY, base_url=QWEN_BASE_URL)

    system = custom_prompt or SYSTEM_PROMPT
    user_message = f"以下是会议转录文本，请生成会议纪要：\n\n{transcript}"

    try:
        response = client.chat.completions.create(
            model=QWEN_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_message},
            ],
            temperature=0.3,
            max_tokens=4096,
        )
        return response.choices[0].message.content or "分析结果为空"
    except Exception as e:
        logger.exception("Qwen API call failed")
        return f"分析失败：{e}"

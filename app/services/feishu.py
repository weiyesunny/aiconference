"""Send meeting minutes to Feishu group via Incoming Webhook."""
import logging
import httpx

from app.config import FEISHU_WEBHOOK_URL

logger = logging.getLogger(__name__)


def push_to_feishu(title: str, analysis: str) -> bool:
    """Push meeting minutes to Feishu group chat. Returns True on success."""
    if not FEISHU_WEBHOOK_URL:
        return False

    content = _build_post(title, analysis)

    try:
        resp = httpx.post(FEISHU_WEBHOOK_URL, json=content, timeout=15)
        data = resp.json()
        if data.get("code") == 0:
            logger.info("Pushed meeting minutes to Feishu: %s", title)
            return True
        else:
            logger.error("Feishu webhook error: %s", data)
            return False
    except Exception:
        logger.exception("Failed to push to Feishu")
        return False


def _build_post(title: str, markdown_text: str) -> dict:
    """Build Feishu rich text (post) message from markdown-like text."""
    lines = markdown_text.strip().split("\n")
    content_lines = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("## "):
            content_lines.append([{"tag": "text", "text": "\n"}])
            content_lines.append([{"tag": "text", "text": f"📌 {stripped[3:]}", "style": ["bold"]}])
        elif stripped.startswith("### "):
            content_lines.append([{"tag": "text", "text": stripped[4:], "style": ["bold"]}])
        elif stripped.startswith("- ") or stripped.startswith("* "):
            content_lines.append([{"tag": "text", "text": f"  • {stripped[2:]}"}])
        elif stripped.startswith("**") and stripped.endswith("**"):
            content_lines.append([{"tag": "text", "text": stripped.strip("*"), "style": ["bold"]}])
        else:
            content_lines.append([{"tag": "text", "text": stripped}])

    if not content_lines:
        content_lines = [[{"tag": "text", "text": markdown_text[:2000]}]]

    return {
        "msg_type": "post",
        "content": {
            "post": {
                "zh_cn": {
                    "title": f"📋 会议纪要: {title}",
                    "content": content_lines,
                }
            }
        }
    }

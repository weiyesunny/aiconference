"""Send meeting minutes to Feishu group via Incoming Webhook (card message)."""
import logging
import httpx

from app.config import FEISHU_WEBHOOK_URL

logger = logging.getLogger(__name__)

CARD_HEADER_COLOR = "blue"


def push_to_feishu(title: str, analysis: str) -> bool:
    """Push meeting minutes to Feishu group chat as a card message."""
    if not FEISHU_WEBHOOK_URL:
        return False

    card = _build_card(title, analysis)

    try:
        resp = httpx.post(FEISHU_WEBHOOK_URL, json=card, timeout=15)
        data = resp.json()
        if data.get("code") == 0:
            logger.info("Pushed meeting minutes to Feishu: %s", title)
            return True

        # Card message may fail keyword check; fall back to post format
        if data.get("code") == 19024:
            logger.warning("Card blocked by keyword filter, falling back to post format")
            post = _build_post(title, analysis)
            resp2 = httpx.post(FEISHU_WEBHOOK_URL, json=post, timeout=15)
            data2 = resp2.json()
            if data2.get("code") == 0:
                logger.info("Pushed meeting minutes via post fallback: %s", title)
                return True
            logger.error("Feishu post fallback also failed: %s", data2)

        logger.error("Feishu webhook error: %s", data)
        return False
    except Exception:
        logger.exception("Failed to push to Feishu")
        return False


def _build_card(title: str, markdown_text: str) -> dict:
    """Build a Feishu interactive card from analysis markdown."""
    elements = []
    current_section = []

    for line in markdown_text.strip().split("\n"):
        stripped = line.strip()
        if not stripped:
            continue

        if stripped.startswith("## "):
            if current_section:
                elements.append({"tag": "markdown", "content": "\n".join(current_section)})
                current_section = []
            elements.append({"tag": "hr"})
            section_title = stripped[3:].strip()
            elements.append({
                "tag": "markdown",
                "content": f"**📌 {section_title}**",
            })
        elif stripped.startswith("### "):
            current_section.append(f"**{stripped[4:].strip()}**")
        elif stripped.startswith("- ") or stripped.startswith("* "):
            current_section.append(f"• {stripped[2:]}")
        elif stripped.startswith("**") and stripped.endswith("**"):
            current_section.append(stripped)
        else:
            current_section.append(stripped)

    if current_section:
        elements.append({"tag": "markdown", "content": "\n".join(current_section)})

    elements.append({"tag": "hr"})
    elements.append({
        "tag": "note",
        "elements": [{"tag": "plain_text", "content": "American First Investment · AI会议助手"}],
    })

    return {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": f"📋 会议纪要: {title}"},
                "template": CARD_HEADER_COLOR,
            },
            "elements": elements,
        }
    }


def _build_post(title: str, markdown_text: str) -> dict:
    """Build a Feishu post (rich text) message with keyword included."""
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
        else:
            content_lines.append([{"tag": "text", "text": stripped}])

    content_lines.append([{"tag": "text", "text": "\n———\nAmerican First Investment · AI会议助手"}])

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

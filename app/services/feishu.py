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
        else:
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

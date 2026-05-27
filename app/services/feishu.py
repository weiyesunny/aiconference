"""Feishu (Lark) bot integration: receive audio files, process, reply with minutes."""
import time
import logging
import hashlib
import hmac
import httpx

logger = logging.getLogger(__name__)

_token_cache = {"token": "", "expires": 0}


def _get_tenant_token(app_id: str, app_secret: str) -> str:
    """Get or refresh tenant_access_token with caching."""
    now = time.time()
    if _token_cache["token"] and _token_cache["expires"] > now + 60:
        return _token_cache["token"]

    resp = httpx.post(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        json={"app_id": app_id, "app_secret": app_secret},
        timeout=10,
    )
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"Failed to get tenant token: {data}")

    token = data["tenant_access_token"]
    _token_cache["token"] = token
    _token_cache["expires"] = now + data.get("expire", 7200)
    logger.info("Feishu tenant token refreshed")
    return token


def verify_signature(timestamp: str, nonce: str, body: str, encrypt_key: str) -> str:
    """Generate verification signature for Feishu events."""
    content = timestamp + nonce + encrypt_key + body
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def download_audio(message_id: str, file_key: str, app_id: str, app_secret: str) -> bytes:
    """Download audio/file resource from Feishu."""
    token = _get_tenant_token(app_id, app_secret)
    headers = {"Authorization": f"Bearer {token}"}

    url = f"https://open.feishu.cn/open-apis/im/v1/messages/{message_id}/resources/{file_key}"
    resp = httpx.get(url, headers=headers, params={"type": "file"}, timeout=120, follow_redirects=True)

    if resp.status_code != 200:
        raise RuntimeError(f"Download failed: HTTP {resp.status_code}, {resp.text[:200]}")

    logger.info("Downloaded audio from Feishu: %d bytes", len(resp.content))
    return resp.content


def download_file(message_id: str, file_key: str, app_id: str, app_secret: str) -> tuple[bytes, str]:
    """Download file message from Feishu, returns (content, filename)."""
    token = _get_tenant_token(app_id, app_secret)
    headers = {"Authorization": f"Bearer {token}"}

    url = f"https://open.feishu.cn/open-apis/im/v1/messages/{message_id}/resources/{file_key}"
    resp = httpx.get(url, headers=headers, params={"type": "file"}, timeout=120, follow_redirects=True)

    if resp.status_code != 200:
        raise RuntimeError(f"Download failed: HTTP {resp.status_code}, {resp.text[:200]}")

    filename = "audio.m4a"
    if "content-disposition" in resp.headers:
        cd = resp.headers["content-disposition"]
        if "filename=" in cd:
            filename = cd.split("filename=")[-1].strip('" ')

    logger.info("Downloaded file from Feishu: %s (%d bytes)", filename, len(resp.content))
    return resp.content, filename


def send_message(chat_id: str, text: str, app_id: str, app_secret: str, msg_type: str = "text"):
    """Send a text or post message to a Feishu chat."""
    token = _get_tenant_token(app_id, app_secret)
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    if msg_type == "post":
        content = _build_post_content(text)
    else:
        content = f'{{"text": {_json_escape(text)}}}'

    resp = httpx.post(
        "https://open.feishu.cn/open-apis/im/v1/messages",
        headers=headers,
        params={"receive_id_type": "chat_id"},
        json={"receive_id": chat_id, "msg_type": msg_type, "content": content},
        timeout=30,
    )
    data = resp.json()
    if data.get("code") != 0:
        logger.error("Send message failed: %s", data)
    else:
        logger.info("Sent message to chat %s", chat_id)


def reply_message(message_id: str, text: str, app_id: str, app_secret: str, msg_type: str = "post"):
    """Reply to a specific message in Feishu."""
    token = _get_tenant_token(app_id, app_secret)
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    if msg_type == "post":
        content = _build_post_content(text)
    else:
        content = f'{{"text": {_json_escape(text)}}}'

    resp = httpx.post(
        f"https://open.feishu.cn/open-apis/im/v1/messages/{message_id}/reply",
        headers=headers,
        json={"msg_type": msg_type, "content": content},
        timeout=30,
    )
    data = resp.json()
    if data.get("code") != 0:
        logger.error("Reply failed: %s", data)
    else:
        logger.info("Replied to message %s", message_id)


def _json_escape(s: str) -> str:
    import json
    return json.dumps(s, ensure_ascii=False)


def _build_post_content(markdown_text: str) -> str:
    """Convert markdown-like text to Feishu post format (rich text)."""
    import json
    lines = markdown_text.strip().split("\n")
    title = ""
    content_lines = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## "):
            if not title:
                title = stripped[3:].strip()
            else:
                content_lines.append([{"tag": "text", "text": "\n"}])
                content_lines.append([{"tag": "text", "text": f"{'─' * 20}", "style": ["bold"]}])
                content_lines.append([{"tag": "text", "text": stripped[3:].strip(), "style": ["bold"]}])
        elif stripped.startswith("### "):
            content_lines.append([{"tag": "text", "text": stripped[4:].strip(), "style": ["bold"]}])
        elif stripped.startswith("- ") or stripped.startswith("* "):
            content_lines.append([{"tag": "text", "text": f"• {stripped[2:]}"}])
        elif stripped.startswith("**") and stripped.endswith("**"):
            content_lines.append([{"tag": "text", "text": stripped.strip("*"), "style": ["bold"]}])
        elif stripped:
            content_lines.append([{"tag": "text", "text": stripped}])

    post = {
        "zh_cn": {
            "title": title or "会议纪要",
            "content": content_lines if content_lines else [[{"tag": "text", "text": markdown_text[:2000]}]],
        }
    }
    return json.dumps(post, ensure_ascii=False)

import json
import uuid
import logging
import hashlib
import threading
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form, Request, BackgroundTasks, Cookie, Response
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import (
    UPLOAD_DIR, QWEN_MODEL, ACCESS_PASSWORD,
    FEISHU_APP_ID, FEISHU_APP_SECRET, FEISHU_VERIFICATION_TOKEN,
)
from app.database import init_db, create_meeting, update_meeting, get_meeting, list_meetings, delete_meeting
from app.services.asr import transcribe
from app.services.analyzer import analyze_meeting

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="美国第一投资 AI帮助中心 - AI会议助手")

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")

ALLOWED_EXTENSIONS = {".mp3", ".m4a", ".wav", ".flac", ".ogg", ".mp4", ".webm", ".aac", ".opus"}

_feishu_processed = set()
_feishu_lock = threading.Lock()


@app.on_event("startup")
def startup():
    init_db()
    logger.info("Database initialized. LLM model: %s", QWEN_MODEL)
    if FEISHU_APP_ID:
        logger.info("Feishu bot enabled (app_id=%s...)", FEISHU_APP_ID[:8])


# ==================== 密码保护 ====================

def _check_auth(request: Request) -> bool:
    if not ACCESS_PASSWORD:
        return True
    token = request.cookies.get("auth_token", "")
    expected = hashlib.sha256(ACCESS_PASSWORD.encode()).hexdigest()[:32]
    return token == expected


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = ""):
    if not ACCESS_PASSWORD:
        return RedirectResponse(url="/")
    return templates.TemplateResponse("login.html", {"request": request, "error": error})


@app.post("/login")
async def login_submit(request: Request, password: str = Form(...)):
    if password == ACCESS_PASSWORD:
        token = hashlib.sha256(ACCESS_PASSWORD.encode()).hexdigest()[:32]
        resp = RedirectResponse(url="/", status_code=303)
        resp.set_cookie("auth_token", token, httponly=True, max_age=86400 * 30)
        return resp
    return templates.TemplateResponse("login.html", {"request": request, "error": "密码错误"})


# ==================== Web 页面路由 ====================

def process_meeting(meeting_id: int):
    """Background task: transcribe audio then analyze with LLM."""
    meeting = get_meeting(meeting_id)
    if not meeting:
        return

    update_meeting(meeting_id, status="transcribing")
    logger.info("Transcribing meeting #%d: %s", meeting_id, meeting["filename"])

    try:
        result = transcribe(meeting["audio_path"])
        update_meeting(
            meeting_id,
            status="analyzing",
            transcript=result["full_text"],
            segments=json.dumps(result["segments"], ensure_ascii=False),
            duration=result["duration"],
            language=result["language"],
        )
        logger.info("Transcription done for #%d (%.1fs, lang=%s). Starting analysis...",
                     meeting_id, result["duration"], result["language"])

        analysis = analyze_meeting(result["full_text"])
        update_meeting(meeting_id, status="completed", analysis=analysis)
        logger.info("Analysis done for meeting #%d", meeting_id)

    except Exception:
        logger.exception("Processing failed for meeting #%d", meeting_id)
        update_meeting(meeting_id, status="failed")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    if not _check_auth(request):
        return RedirectResponse(url="/login")
    meetings = list_meetings()
    return templates.TemplateResponse("index.html", {"request": request, "meetings": meetings})


@app.post("/upload")
async def upload(
    background_tasks: BackgroundTasks,
    request: Request,
    file: UploadFile = File(...),
    title: str = Form(""),
):
    if not _check_auth(request):
        return RedirectResponse(url="/login")

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        meetings = list_meetings()
        return templates.TemplateResponse("index.html", {
            "request": request, "meetings": meetings,
            "error": f"不支持的文件格式: {ext}，支持: {', '.join(ALLOWED_EXTENSIONS)}"
        })

    safe_name = f"{uuid.uuid4().hex}{ext}"
    save_path = UPLOAD_DIR / safe_name
    with open(save_path, "wb") as f:
        content = await file.read()
        f.write(content)

    meeting_title = title.strip() or Path(file.filename).stem
    meeting_id = create_meeting(meeting_title, file.filename, str(save_path))
    logger.info("Uploaded meeting #%d: %s -> %s", meeting_id, file.filename, safe_name)

    background_tasks.add_task(process_meeting, meeting_id)

    return RedirectResponse(url=f"/meeting/{meeting_id}", status_code=303)


@app.get("/meeting/{meeting_id}", response_class=HTMLResponse)
async def meeting_detail(request: Request, meeting_id: int):
    if not _check_auth(request):
        return RedirectResponse(url="/login")
    meeting = get_meeting(meeting_id)
    if not meeting:
        return RedirectResponse(url="/")
    return templates.TemplateResponse("meeting.html", {"request": request, "meeting": meeting})


@app.get("/api/meeting/{meeting_id}/status")
async def meeting_status(meeting_id: int):
    meeting = get_meeting(meeting_id)
    if not meeting:
        return {"error": "not found"}
    return {"id": meeting_id, "status": meeting["status"]}


@app.post("/meeting/{meeting_id}/delete")
async def meeting_delete(request: Request, meeting_id: int):
    if not _check_auth(request):
        return RedirectResponse(url="/login")
    delete_meeting(meeting_id)
    return RedirectResponse(url="/", status_code=303)


@app.post("/meeting/{meeting_id}/reanalyze")
async def reanalyze(background_tasks: BackgroundTasks, request: Request, meeting_id: int, custom_prompt: str = Form(None)):
    if not _check_auth(request):
        return RedirectResponse(url="/login")
    meeting = get_meeting(meeting_id)
    if not meeting or not meeting.get("transcript"):
        return RedirectResponse(url=f"/meeting/{meeting_id}", status_code=303)

    def do_reanalyze():
        update_meeting(meeting_id, status="analyzing")
        analysis = analyze_meeting(meeting["transcript"], custom_prompt=custom_prompt or None)
        update_meeting(meeting_id, status="completed", analysis=analysis)

    background_tasks.add_task(do_reanalyze)
    return RedirectResponse(url=f"/meeting/{meeting_id}", status_code=303)


# ==================== 飞书 Webhook ====================

@app.post("/feishu/webhook")
async def feishu_webhook(request: Request):
    """Handle Feishu bot event callbacks."""
    body = await request.json()

    # URL verification challenge
    if "challenge" in body:
        return {"challenge": body["challenge"]}

    # Event v2 format
    header = body.get("header", {})
    event = body.get("event", {})

    # Verify token
    if FEISHU_VERIFICATION_TOKEN:
        token = header.get("token", "")
        if token != FEISHU_VERIFICATION_TOKEN:
            logger.warning("Feishu webhook: invalid token")
            return JSONResponse({"code": 1, "msg": "invalid token"}, status_code=403)

    event_type = header.get("event_type", "")
    if event_type != "im.message.receive_v1":
        return {"code": 0}

    # Deduplicate events (Feishu may retry)
    event_id = header.get("event_id", "")
    with _feishu_lock:
        if event_id in _feishu_processed:
            return {"code": 0}
        _feishu_processed.add(event_id)
        if len(_feishu_processed) > 1000:
            _feishu_processed.clear()

    msg = event.get("message", {})
    msg_type = msg.get("message_type", "")
    chat_id = msg.get("chat_id", "")
    message_id = msg.get("message_id", "")

    # Only handle audio and file messages
    if msg_type not in ("audio", "file"):
        logger.info("Feishu: ignoring message type '%s'", msg_type)
        return {"code": 0}

    # Parse content to get file_key
    try:
        content = json.loads(msg.get("content", "{}"))
        file_key = content.get("file_key") or content.get("file_key", "")
        filename = content.get("file_name", "audio.m4a")
    except (json.JSONDecodeError, KeyError):
        logger.error("Feishu: failed to parse message content")
        return {"code": 0}

    if not file_key:
        return {"code": 0}

    logger.info("Feishu: received %s from chat %s, file_key=%s", msg_type, chat_id, file_key)

    # Process in background thread
    thread = threading.Thread(
        target=_process_feishu_audio,
        args=(message_id, chat_id, file_key, filename),
        daemon=True,
    )
    thread.start()

    return {"code": 0}


def _process_feishu_audio(message_id: str, chat_id: str, file_key: str, filename: str):
    """Download audio from Feishu, transcribe, analyze, reply."""
    from app.services.feishu import download_file, reply_message

    try:
        # Notify: processing started
        reply_message(
            message_id, "收到录音文件，正在处理中...\n转录 + 分析通常需要 2-5 分钟，请稍候。",
            FEISHU_APP_ID, FEISHU_APP_SECRET, msg_type="text",
        )

        # Download file from Feishu
        audio_data, dl_filename = download_file(message_id, file_key, FEISHU_APP_ID, FEISHU_APP_SECRET)
        actual_filename = dl_filename or filename

        # Determine extension
        ext = Path(actual_filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            ext = ".m4a"

        # Save to temp file
        safe_name = f"feishu_{uuid.uuid4().hex}{ext}"
        save_path = UPLOAD_DIR / safe_name
        with open(save_path, "wb") as f:
            f.write(audio_data)

        # Create meeting record
        meeting_title = f"飞书录音: {Path(actual_filename).stem}"
        meeting_id = create_meeting(meeting_title, actual_filename, str(save_path))
        logger.info("Feishu: created meeting #%d from %s (%d bytes)", meeting_id, actual_filename, len(audio_data))

        # Transcribe
        update_meeting(meeting_id, status="transcribing")
        result = transcribe(str(save_path))
        update_meeting(
            meeting_id,
            status="analyzing",
            transcript=result["full_text"],
            segments=json.dumps(result["segments"], ensure_ascii=False),
            duration=result["duration"],
            language=result["language"],
        )
        logger.info("Feishu: transcription done for #%d (%.1fs)", meeting_id, result["duration"])

        # Analyze
        analysis = analyze_meeting(result["full_text"])
        update_meeting(meeting_id, status="completed", analysis=analysis)
        logger.info("Feishu: analysis done for #%d", meeting_id)

        # Reply with result
        reply_message(
            message_id, analysis,
            FEISHU_APP_ID, FEISHU_APP_SECRET, msg_type="post",
        )

    except Exception as e:
        logger.exception("Feishu: processing failed")
        try:
            from app.services.feishu import reply_message as _reply
            _reply(
                message_id, f"处理失败: {e}",
                FEISHU_APP_ID, FEISHU_APP_SECRET, msg_type="text",
            )
        except Exception:
            logger.exception("Feishu: failed to send error reply")

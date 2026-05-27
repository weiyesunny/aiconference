import json
import uuid
import logging
import hashlib
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import UPLOAD_DIR, QWEN_MODEL, ACCESS_PASSWORD, FEISHU_WEBHOOK_URL
from app.database import init_db, create_meeting, update_meeting, get_meeting, list_meetings, delete_meeting
from app.services.asr import transcribe
from app.services.analyzer import analyze_meeting

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="美国第一投资 AI帮助中心 - AI会议助手")

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")

ALLOWED_EXTENSIONS = {".mp3", ".m4a", ".wav", ".flac", ".ogg", ".mp4", ".webm", ".aac", ".opus"}


@app.on_event("startup")
def startup():
    init_db()
    logger.info("Database initialized. LLM model: %s", QWEN_MODEL)
    if FEISHU_WEBHOOK_URL:
        logger.info("Feishu webhook push enabled")


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


# ==================== 核心处理 ====================

def process_meeting(meeting_id: int):
    """Background task: transcribe audio, analyze with LLM, push to Feishu."""
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

        # 推送到飞书群
        if FEISHU_WEBHOOK_URL:
            from app.services.feishu import push_to_feishu
            push_to_feishu(meeting["title"], analysis)

    except Exception:
        logger.exception("Processing failed for meeting #%d", meeting_id)
        update_meeting(meeting_id, status="failed")


# ==================== Web 路由 ====================

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
        if FEISHU_WEBHOOK_URL:
            from app.services.feishu import push_to_feishu
            push_to_feishu(meeting["title"], analysis)

    background_tasks.add_task(do_reanalyze)
    return RedirectResponse(url=f"/meeting/{meeting_id}", status_code=303)

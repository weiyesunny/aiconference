"""Meeting CRUD and processing routes — mounted under /minutes/ prefix."""

import json
import uuid
import logging
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, UploadFile, File, Form, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse

from app.config import UPLOAD_DIR, FEISHU_WEBHOOK_URL
from app.constants import MeetingStatus, ALLOWED_AUDIO_EXTENSIONS
from app.database import create_meeting, update_meeting, get_meeting, list_meetings, delete_meeting
from app.services.asr import transcribe
from app.services.analyzer import analyze_meeting
from app.services.embedding import search_similar, store_embedding
from app.routes.auth import check_auth

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/minutes")


def _get_templates():
    from app.main import templates
    return templates


def process_meeting(meeting_id: int):
    """Background task: transcribe audio, analyze with LLM, push to Feishu."""
    meeting = get_meeting(meeting_id)
    if not meeting:
        return

    update_meeting(meeting_id, status=MeetingStatus.TRANSCRIBING)
    logger.info("Transcribing meeting #%d: %s", meeting_id, meeting["filename"])

    try:
        result = transcribe(meeting["audio_path"])
        update_meeting(
            meeting_id,
            status=MeetingStatus.ANALYZING,
            transcript=result["full_text"],
            segments=json.dumps(result["segments"], ensure_ascii=False),
            duration=result["duration"],
            language=result["language"],
        )
        logger.info(
            "Transcription done for #%d (%.1fs, lang=%s). Starting analysis...",
            meeting_id, result["duration"], result["language"],
        )

        # RAG: search similar past meetings for context
        similar = search_similar(result["full_text"], exclude_id=meeting_id)

        needs_title = meeting["title"].startswith("_auto_")
        result_obj = analyze_meeting(
            result["full_text"], meeting=meeting,
            need_title=needs_title, similar_meetings=similar,
        )

        if needs_title:
            ai_title = result_obj["title"]
            analysis = result_obj["analysis"]
            update_meeting(meeting_id, status=MeetingStatus.COMPLETED, analysis=analysis, title=ai_title)
            meeting["title"] = ai_title
            logger.info("AI generated title for #%d: %s", meeting_id, ai_title)
        else:
            analysis = result_obj
            update_meeting(meeting_id, status=MeetingStatus.COMPLETED, analysis=analysis)

        # Store embedding for future RAG searches
        store_embedding(meeting_id, analysis)

        meeting = get_meeting(meeting_id)
        logger.info("Analysis done for meeting #%d", meeting_id)

        if FEISHU_WEBHOOK_URL and meeting.get("push_feishu"):
            from app.services.feishu import push_to_feishu
            push_to_feishu(meeting, analysis)

    except Exception as exc:
        logger.exception("Processing failed for meeting #%d", meeting_id)
        update_meeting(meeting_id, status=MeetingStatus.FAILED, error_message=str(exc))


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    if not check_auth(request):
        return RedirectResponse(url="/login")
    meetings = list_meetings()
    return _get_templates().TemplateResponse("minutes.html", {"request": request, "meetings": meetings})


@router.post("/upload")
async def upload(
    background_tasks: BackgroundTasks,
    request: Request,
    file: UploadFile = File(...),
    title: str = Form(""),
    meeting_time: str = Form(""),
    location: str = Form(""),
    participants: str = Form(""),
    push_feishu: str = Form(""),
):
    if not check_auth(request):
        return RedirectResponse(url="/login")

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_AUDIO_EXTENSIONS:
        meetings = list_meetings()
        return _get_templates().TemplateResponse("minutes.html", {
            "request": request, "meetings": meetings,
            "error": f"不支持的文件格式: {ext}，支持: {', '.join(sorted(ALLOWED_AUDIO_EXTENSIONS))}"
        })

    safe_name = f"{uuid.uuid4().hex}{ext}"
    save_path = UPLOAD_DIR / safe_name
    with open(save_path, "wb") as f:
        content = await file.read()
        f.write(content)

    meeting_title = title.strip() or f"_auto_{uuid.uuid4().hex[:8]}"
    should_push = push_feishu == "on"

    meeting_id = create_meeting(
        meeting_title, file.filename, str(save_path),
        meeting_time=meeting_time.strip(),
        location=location.strip(),
        participants=participants.strip(),
        push_feishu=should_push,
    )
    logger.info("Uploaded meeting #%d: %s -> %s", meeting_id, file.filename, safe_name)

    background_tasks.add_task(process_meeting, meeting_id)

    return RedirectResponse(url=f"/minutes/{meeting_id}", status_code=303)


@router.get("/{meeting_id}", response_class=HTMLResponse)
async def meeting_detail(request: Request, meeting_id: int):
    if not check_auth(request):
        return RedirectResponse(url="/login")
    meeting = get_meeting(meeting_id)
    if not meeting:
        return RedirectResponse(url="/minutes/")
    return _get_templates().TemplateResponse("meeting.html", {"request": request, "meeting": meeting})


@router.get("/api/{meeting_id}/status")
async def meeting_status(request: Request, meeting_id: int):
    if not check_auth(request):
        return {"error": "unauthorized"}
    meeting = get_meeting(meeting_id)
    if not meeting:
        return {"error": "not found"}
    return {"id": meeting_id, "status": meeting["status"], "title": meeting["title"]}


@router.get("/{meeting_id}/download")
async def download_docx(request: Request, meeting_id: int):
    if not check_auth(request):
        return RedirectResponse(url="/login")
    meeting = get_meeting(meeting_id)
    if not meeting or not meeting.get("analysis"):
        return RedirectResponse(url=f"/minutes/{meeting_id}", status_code=303)

    from app.services.export import markdown_to_docx
    buf = markdown_to_docx(meeting["analysis"], meeting)

    title = meeting["title"]
    if title.startswith("_auto_"):
        title = "会议纪要"
    safe_title = title[:50].strip() or "meeting"
    filename = f"{safe_title}.docx"
    encoded = quote(filename)

    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded}"},
    )


@router.post("/{meeting_id}/delete")
async def meeting_delete(request: Request, meeting_id: int):
    if not check_auth(request):
        return RedirectResponse(url="/login")
    delete_meeting(meeting_id)
    return RedirectResponse(url="/minutes/", status_code=303)


@router.post("/{meeting_id}/reanalyze")
async def reanalyze(
    background_tasks: BackgroundTasks,
    request: Request,
    meeting_id: int,
    custom_prompt: str = Form(None),
):
    if not check_auth(request):
        return RedirectResponse(url="/login")
    meeting = get_meeting(meeting_id)
    if not meeting or not meeting.get("transcript"):
        return RedirectResponse(url=f"/minutes/{meeting_id}", status_code=303)

    def do_reanalyze():
        try:
            update_meeting(meeting_id, status=MeetingStatus.ANALYZING)
            similar = search_similar(meeting["transcript"], exclude_id=meeting_id)
            analysis = analyze_meeting(
                meeting["transcript"],
                custom_prompt=custom_prompt or None,
                meeting=meeting,
                similar_meetings=similar,
            )
            update_meeting(meeting_id, status=MeetingStatus.COMPLETED, analysis=analysis)
            store_embedding(meeting_id, analysis)
            if FEISHU_WEBHOOK_URL:
                from app.services.feishu import push_to_feishu
                push_to_feishu(meeting, analysis)
        except Exception as exc:
            logger.exception("Re-analysis failed for meeting #%d", meeting_id)
            update_meeting(meeting_id, status=MeetingStatus.FAILED, error_message=str(exc))

    background_tasks.add_task(do_reanalyze)
    return RedirectResponse(url=f"/minutes/{meeting_id}", status_code=303)

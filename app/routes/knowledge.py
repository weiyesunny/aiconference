"""Knowledge base routes — separate password protection."""

import hashlib
import uuid
import logging
import threading
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Form, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, RedirectResponse

from app.config import KNOWLEDGE_PASSWORD, UPLOAD_DIR
from app.constants import KB_COOKIE_NAME, AUTH_COOKIE_MAX_AGE, ALLOWED_DOC_EXTENSIONS
from app.database import (
    list_completed_meetings, list_knowledge_docs,
    create_knowledge_doc, delete_knowledge_doc, get_knowledge_doc,
)
from app.routes.auth import check_auth

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/knowledge")

DOCS_DIR = UPLOAD_DIR.parent / "knowledge_docs"
DOCS_DIR.mkdir(parents=True, exist_ok=True)


def _get_templates():
    from app.main import templates
    return templates


def _check_kb_auth(request: Request) -> bool:
    """Knowledge base has its own password layer on top of main auth."""
    if not check_auth(request):
        return False
    if not KNOWLEDGE_PASSWORD:
        return True
    token = request.cookies.get(KB_COOKIE_NAME, "")
    expected = hashlib.sha256(KNOWLEDGE_PASSWORD.encode()).hexdigest()[:32]
    return token == expected


@router.get("/login", response_class=HTMLResponse)
async def kb_login_page(request: Request, error: str = ""):
    if not check_auth(request):
        return RedirectResponse(url="/login")
    if not KNOWLEDGE_PASSWORD:
        return RedirectResponse(url="/knowledge/")
    return _get_templates().TemplateResponse(
        "kb_login.html", {"request": request, "error": error},
    )


@router.post("/login")
async def kb_login_submit(request: Request, password: str = Form(...)):
    if not check_auth(request):
        return RedirectResponse(url="/login")
    if password == KNOWLEDGE_PASSWORD:
        token = hashlib.sha256(KNOWLEDGE_PASSWORD.encode()).hexdigest()[:32]
        resp = RedirectResponse(url="/knowledge/", status_code=303)
        resp.set_cookie(
            KB_COOKIE_NAME, token,
            httponly=True, samesite="lax",
            max_age=AUTH_COOKIE_MAX_AGE,
        )
        return resp
    return _get_templates().TemplateResponse(
        "kb_login.html", {"request": request, "error": "密码错误"},
    )


@router.get("/", response_class=HTMLResponse)
async def kb_index(request: Request):
    if not _check_kb_auth(request):
        return RedirectResponse(url="/knowledge/login")
    meetings = list_completed_meetings()
    docs = list_knowledge_docs()
    return _get_templates().TemplateResponse(
        "knowledge.html",
        {"request": request, "meetings": meetings, "docs": docs},
    )


@router.post("/upload")
async def kb_upload(
    request: Request,
    file: UploadFile = File(...),
    title: str = Form(""),
):
    if not _check_kb_auth(request):
        return RedirectResponse(url="/knowledge/login")

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_DOC_EXTENSIONS:
        meetings = list_completed_meetings()
        docs = list_knowledge_docs()
        return _get_templates().TemplateResponse("knowledge.html", {
            "request": request, "meetings": meetings, "docs": docs,
            "error": f"不支持的文件格式: {ext}，支持: {', '.join(sorted(ALLOWED_DOC_EXTENSIONS))}",
        })

    safe_name = f"{uuid.uuid4().hex}{ext}"
    save_path = DOCS_DIR / safe_name
    with open(save_path, "wb") as f:
        content = await file.read()
        f.write(content)

    doc_title = title.strip() or Path(file.filename).stem

    from app.services.docparse import extract_text
    try:
        text_content = extract_text(str(save_path))
    except Exception as exc:
        logger.exception("Failed to extract text from %s", file.filename)
        save_path.unlink(missing_ok=True)
        meetings = list_completed_meetings()
        docs = list_knowledge_docs()
        return _get_templates().TemplateResponse("knowledge.html", {
            "request": request, "meetings": meetings, "docs": docs,
            "error": f"文件解析失败: {exc}",
        })

    if not text_content.strip():
        save_path.unlink(missing_ok=True)
        meetings = list_completed_meetings()
        docs = list_knowledge_docs()
        return _get_templates().TemplateResponse("knowledge.html", {
            "request": request, "meetings": meetings, "docs": docs,
            "error": "文件内容为空，无法处理",
        })

    doc_id = create_knowledge_doc(
        doc_title, file.filename, str(save_path), text_content, ext.lstrip("."),
    )
    logger.info("Knowledge doc #%d uploaded: %s (%d chars)", doc_id, file.filename, len(text_content))

    def _embed():
        from app.services.embedding import store_doc_embedding
        store_doc_embedding(doc_id, text_content)

    thread = threading.Thread(target=_embed, daemon=True)
    thread.start()

    return RedirectResponse(url="/knowledge/", status_code=303)


@router.post("/{doc_id}/delete")
async def kb_delete(request: Request, doc_id: int):
    if not _check_kb_auth(request):
        return RedirectResponse(url="/knowledge/login")
    delete_knowledge_doc(doc_id)
    return RedirectResponse(url="/knowledge/", status_code=303)

"""Dashboard home page — module entry points."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.routes.auth import check_auth

router = APIRouter()


def _get_templates():
    from app.main import templates
    return templates


MODULES = [
    {
        "id": "minutes",
        "icon": "📋",
        "title": "AI 会议纪要",
        "desc": "上传录音文件，AI 自动转录并生成结构化会议纪要，支持飞书群推送",
        "url": "/minutes/",
        "active": True,
        "color": "blue",
    },
    {
        "id": "translate",
        "icon": "🌐",
        "title": "AI 翻译",
        "desc": "智能文档翻译，支持中英双向，保留格式与术语一致性",
        "url": "#",
        "active": False,
        "color": "emerald",
    },
    {
        "id": "summary",
        "icon": "📄",
        "title": "AI 文档助手",
        "desc": "快速阅读、摘要长文档，提取关键信息与行动要点",
        "url": "#",
        "active": False,
        "color": "violet",
    },
    {
        "id": "knowledge",
        "icon": "🧠",
        "title": "知识库",
        "desc": "会议纪要归档与文档管理，构建 AI 驱动的团队知识体系",
        "url": "/knowledge/",
        "active": True,
        "color": "amber",
    },
]


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    if not check_auth(request):
        return RedirectResponse(url="/login")
    return _get_templates().TemplateResponse(
        "dashboard.html",
        {"request": request, "modules": MODULES},
    )

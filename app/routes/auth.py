"""Authentication routes and helpers."""

import hashlib

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.config import ACCESS_PASSWORD
from app.constants import AUTH_COOKIE_NAME, AUTH_COOKIE_MAX_AGE

router = APIRouter()


def _get_templates() -> Jinja2Templates:
    from app.main import templates
    return templates


def check_auth(request: Request) -> bool:
    if not ACCESS_PASSWORD:
        return True
    token = request.cookies.get(AUTH_COOKIE_NAME, "")
    expected = hashlib.sha256(ACCESS_PASSWORD.encode()).hexdigest()[:32]
    return token == expected


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = ""):
    if not ACCESS_PASSWORD:
        return RedirectResponse(url="/")
    return _get_templates().TemplateResponse("login.html", {"request": request, "error": error})


@router.post("/login")
async def login_submit(request: Request, password: str = Form(...)):
    if password == ACCESS_PASSWORD:
        token = hashlib.sha256(ACCESS_PASSWORD.encode()).hexdigest()[:32]
        resp = RedirectResponse(url="/", status_code=303)
        resp.set_cookie(
            AUTH_COOKIE_NAME, token,
            httponly=True, samesite="lax",
            max_age=AUTH_COOKIE_MAX_AGE,
        )
        return resp
    return _get_templates().TemplateResponse("login.html", {"request": request, "error": "密码错误"})

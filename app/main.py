"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import QWEN_MODEL, FEISHU_WEBHOOK_URL
from app.constants import BRAND_NAME, BRAND_SUB
from app.database import init_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logger.info("Database initialized. LLM model: %s", QWEN_MODEL)
    if FEISHU_WEBHOOK_URL:
        logger.info("Feishu webhook push enabled")
    yield


app = FastAPI(title=f"{BRAND_NAME} - {BRAND_SUB}", lifespan=lifespan)

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")

from app.routes.auth import router as auth_router            # noqa: E402
from app.routes.dashboard import router as dashboard_router   # noqa: E402
from app.routes.meeting import router as meeting_router       # noqa: E402

app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(meeting_router)

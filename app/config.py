import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# DashScope API (同时用于 LLM 和 ASR)
DASHSCOPE_API_KEY = os.getenv("QWEN_API_KEY", "")
QWEN_BASE_URL = os.getenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
QWEN_MODEL = os.getenv("QWEN_MODEL", "qwen-plus")

# ASR 配置
ASR_MODEL = os.getenv("ASR_MODEL", "paraformer-realtime-v2")

# 飞书 Incoming Webhook（处理完成后推送纪要到群）
FEISHU_WEBHOOK_URL = os.getenv("FEISHU_WEBHOOK_URL", "")

# 网页访问密码（留空则不启用）
ACCESS_PASSWORD = os.getenv("ACCESS_PASSWORD", "")

UPLOAD_DIR = BASE_DIR / os.getenv("UPLOAD_DIR", "uploads")
DATABASE_PATH = BASE_DIR / os.getenv("DATABASE_PATH", "data/meetings.db")

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

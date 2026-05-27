"""Application configuration — loaded from .env file."""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# DashScope API (LLM + ASR share the same key)
DASHSCOPE_API_KEY = os.getenv("QWEN_API_KEY", "")
QWEN_BASE_URL = os.getenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
QWEN_MODEL = os.getenv("QWEN_MODEL", "qwen-plus")

# LLM generation parameters
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.3"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "4096"))

# ASR
ASR_MODEL = os.getenv("ASR_MODEL", "paraformer-realtime-v2")

# Embedding + RAG
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-v3")
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "3"))
RAG_MIN_SCORE = float(os.getenv("RAG_MIN_SCORE", "0.3"))

# Feishu Incoming Webhook
FEISHU_WEBHOOK_URL = os.getenv("FEISHU_WEBHOOK_URL", "")

# Web access password (empty = no auth)
ACCESS_PASSWORD = os.getenv("ACCESS_PASSWORD", "")

# Knowledge base password (separate access control)
KNOWLEDGE_PASSWORD = os.getenv("KNOWLEDGE_PASSWORD", "")

# Storage paths
UPLOAD_DIR = BASE_DIR / os.getenv("UPLOAD_DIR", "uploads")
DATABASE_PATH = BASE_DIR / os.getenv("DATABASE_PATH", "data/meetings.db")

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

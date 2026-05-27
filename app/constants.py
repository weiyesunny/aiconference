"""Centralized constants — statuses, brand text, allowed formats, etc."""

from enum import StrEnum


class MeetingStatus(StrEnum):
    UPLOADED = "uploaded"
    TRANSCRIBING = "transcribing"
    ANALYZING = "analyzing"
    COMPLETED = "completed"
    FAILED = "failed"


ALLOWED_AUDIO_EXTENSIONS = {
    ".mp3", ".m4a", ".wav", ".flac", ".ogg",
    ".mp4", ".webm", ".aac", ".opus",
}

BRAND_NAME = "美国第一投资 AI帮助中心"
BRAND_SUB = "AI会议助手"
BRAND_EN = "American First Investment"

AUTH_COOKIE_NAME = "auth_token"
AUTH_COOKIE_MAX_AGE = 86400 * 30  # 30 days

ASR_SAMPLE_RATE = 16000
ASR_CHANNELS = 1

STATUS_LABELS = {
    MeetingStatus.UPLOADED: "已上传",
    MeetingStatus.TRANSCRIBING: "转录中",
    MeetingStatus.ANALYZING: "分析中",
    MeetingStatus.COMPLETED: "已完成",
    MeetingStatus.FAILED: "失败",
}

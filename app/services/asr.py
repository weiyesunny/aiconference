import os
import logging
import subprocess
from pathlib import Path

import dashscope
from dashscope.audio.asr import Recognition

from app.config import DASHSCOPE_API_KEY, ASR_MODEL

logger = logging.getLogger(__name__)


def _get_duration(audio_path: Path) -> float:
    probe = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(audio_path)],
        capture_output=True, text=True,
    )
    return float(probe.stdout.strip())


def _convert_to_wav(audio_path: Path) -> Path:
    """Convert audio to 16kHz mono WAV for best compatibility."""
    wav_path = audio_path.with_suffix(".tmp.wav")
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(audio_path), "-ar", "16000", "-ac", "1",
         "-loglevel", "error", str(wav_path)],
        check=True,
    )
    return wav_path


def transcribe(audio_path: str | Path) -> dict:
    """Transcribe audio using DashScope Paraformer via Recognition SDK."""
    audio_path = Path(audio_path)

    if not DASHSCOPE_API_KEY:
        raise RuntimeError("未配置 QWEN_API_KEY（DASHSCOPE_API_KEY），请在 .env 文件中设置。")

    dashscope.api_key = DASHSCOPE_API_KEY

    duration = _get_duration(audio_path)
    logger.info("Audio duration: %.1fs, converting to WAV...", duration)

    wav_path = _convert_to_wav(audio_path)

    try:
        return _do_transcribe(wav_path, duration)
    finally:
        if wav_path.exists() and wav_path != audio_path:
            wav_path.unlink(missing_ok=True)


def _do_transcribe(wav_path: Path, duration: float) -> dict:
    """Run the actual transcription."""
    logger.info("Starting Paraformer recognition...")

    from dashscope.audio.asr import RecognitionCallback

    class _NoopCallback(RecognitionCallback):
        def on_event(self, result): pass
        def on_complete(self): pass
        def on_error(self, result):
            logger.error("ASR stream error: %s", result)

    rec = Recognition(
        model=ASR_MODEL,
        format="wav",
        sample_rate=16000,
        callback=_NoopCallback(),
    )
    result = rec.call(file=str(wav_path))

    if result.status_code != 200:
        raise RuntimeError(f"ASR failed: status={result.status_code}, message={result.message}")

    sentences = result.get_sentence()
    if not sentences:
        raise RuntimeError("ASR returned no sentences")

    segments = []
    full_text_parts = []

    for sen in sentences:
        text = sen.get("text", "").strip()
        if not text:
            continue

        begin_ms = sen.get("begin_time", 0)
        end_ms = sen.get("end_time", 0)
        speaker_id = sen.get("speaker_id")

        seg = {
            "start": round(begin_ms / 1000, 2),
            "end": round(end_ms / 1000, 2),
            "text": text,
        }
        if speaker_id is not None:
            seg["speaker"] = f"说话人{speaker_id + 1}"

        segments.append(seg)
        full_text_parts.append(text)

    full_text = "\n".join(full_text_parts)
    logger.info("Transcription done: %d segments, %d chars", len(segments), len(full_text))

    return {
        "language": "zh",
        "language_probability": 0.99,
        "duration": round(duration, 1),
        "segments": segments,
        "full_text": full_text,
    }

"""Standalone test script for DashScope Paraformer ASR."""
import os
import subprocess
import sys

from dotenv import load_dotenv
import dashscope
from dashscope.audio.asr import Recognition, RecognitionCallback

load_dotenv()

api_key = os.getenv("QWEN_API_KEY")
if not api_key:
    print("ERROR: QWEN_API_KEY not set in .env")
    sys.exit(1)

dashscope.api_key = api_key

src = "uploads/1fec37b137864303bcf1592106e6f007.m4a"
clip = "/tmp/test_asr_clip.wav"
subprocess.run(
    ["ffmpeg", "-y", "-i", src, "-t", "20", "-ar", "16000", "-ac", "1",
     "-loglevel", "error", clip],
    check=True,
)
print(f"Test clip created: {clip}")

events = []


class CB(RecognitionCallback):
    def on_event(self, result):
        sen = result.get_sentence()
        events.append(sen)
        if sen:
            print(f"  [EVENT] sentence={sen}")

    def on_complete(self):
        print("  [COMPLETE]")

    def on_error(self, result):
        print(f"  [ERROR] {result}")


print("Starting recognition...")
rec = Recognition(
    model="paraformer-realtime-v2", format="wav",
    sample_rate=16000, callback=CB(),
)
result = rec.call(file=clip)

print(f"\n=== {len(events)} events received ===")
print(f"status_code: {result.status_code}")
if hasattr(result, "get_sentence"):
    print(f"result.get_sentence(): {repr(result.get_sentence())[:500]}")

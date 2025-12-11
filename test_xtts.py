#!/usr/bin/env python3
from TTS.api import TTS
import torch

# Check device
if torch.backends.mps.is_available():
    device = "mps"
else:
    device = "cpu"

print(f"Using device: {device}")

# Load XTTS model
print("Loading XTTS model...")
xtts_tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)

# Test with jesus_custom.mp3
speaker_path = "voices/jesus_custom.mp3"
print(f"\nTesting with speaker: {speaker_path}")

try:
    wav = xtts_tts.tts(
        text="Hello world, this is a test.",
        speaker_wav=speaker_path,
        language="en",
    )
    print(f"Success! Generated audio with shape: {len(wav)}")
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()

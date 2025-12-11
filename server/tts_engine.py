from pathlib import Path
from typing import List
from pydub import AudioSegment
from TTS.api import TTS
import math

# Load XTTS-v2 once (zero-shot cloning via reference WAVs)
# This avoids full fine-tuning and works great locally.
_tts = None

def get_tts():
    global _tts
    if _tts is None:
        _tts = TTS(model_name="tts_models/multilingual/multi-dataset/xtts_v2")
    return _tts

# Split long text into safe chunks for generation

def chunk_text(text: str, max_chars: int = 400):
    parts = []
    buf = []
    count = 0
    for tok in text.replace("\r", "").split():
        if count + len(tok) + 1 > max_chars:
            parts.append(" ".join(buf))
            buf, count = [tok], len(tok)
        else:
            buf.append(tok)
            count += len(tok) + 1
    if buf:
        parts.append(" ".join(buf))
    return parts

# Merge list of wav paths into a single mp3

def merge_to_mp3(wav_paths: List[Path], out_mp3: Path):
    combined = AudioSegment.silent(duration=0)
    for w in wav_paths:
        seg = AudioSegment.from_file(w)
        combined += seg
    out_mp3.parent.mkdir(parents=True, exist_ok=True)
    combined.export(out_mp3, format="mp3")
    return str(out_mp3)

# Synthesize a chunk to wav path using given reference wavs

def synth_chunk(text: str, ref_wavs: List[str], out_wav: Path, language: str = "en"):
    tts = get_tts()
    # For XTTS, pass a single reference file path OR list. We'll pass the first for stability.
    speaker_wav = ref_wavs[0] if ref_wavs else None
    assert speaker_wav, "No reference wavs provided for this voice."
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    tts.tts_to_file(text=text, speaker_wav=speaker_wav, language=language, file_path=str(out_wav))
    return str(out_wav)
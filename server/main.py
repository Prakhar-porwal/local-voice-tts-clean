import os

# --- CRITICAL FIX: FORCE TTS CACHE PATH ---
# Must be set BEFORE importing TTS
os.environ["TTS_HOME"] = "/app/tts_cache"
os.environ["XDG_DATA_HOME"] = "/app/tts_cache"
print("!!! NUCLEAR DEPLOYMENT ACTIVE - REV 9 - TTS PATH ENFORCED !!!")
print(f"DEBUG: Enforced TTS Cache Path: {os.environ.get('TTS_HOME')}")
# ------------------------------------------

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel

from TTS.api import TTS
import torch
import io
import soundfile as sf
from pathlib import Path
from uuid import uuid4
import json
import os
import shutil
import numpy as np  # for concatenating chunks

# ---- Paths ----
BASE_DIR = Path(__file__).parent
VOICES_DIR = BASE_DIR / "voices"
VOICES_DIR.mkdir(exist_ok=True)
VOICES_DB_PATH = BASE_DIR / "custom_voices.json"


def load_custom_voices() -> dict:
    if VOICES_DB_PATH.exists():
        try:
            return json.loads(VOICES_DB_PATH.read_text())
        except Exception:
            return {}
    return {}


def save_custom_voices(data: dict) -> None:
    VOICES_DB_PATH.write_text(json.dumps(data, indent=2))


# ---- Built-in + stored custom voices ----

# Voices already created earlier and stored on disk
_loaded_custom = load_custom_voices()

# Your permanent built-in custom voices (XTTS voice cloning)
# Make sure these files exist under server/voices/
#   - voices/deep_story_female.wav       (optional)
#   - voices/deep_story_male.mp3         (optional)
#   - voices/jesus.mp3                   (your custom Jesus voice)
BUILTIN_CUSTOM_VOICES = {
    "custom_deep_story_female": {
        "file_path": "voices/deep_story_female.wav",
        "name": "Deep Story Female",
        "language": "en",
    },
    "custom_deep_story_male": {
        "file_path": "voices/deep_story_male.mp3",
        "name": "Deep Story Male",
        "language": "en",
    },
    "custom_jesus_voice": {
        "file_path": "voices/jesus_custom.mp3",
        "name": "Jesus Style Voice",
        "language": "en",
    },
}

# Merge built-in and previously saved voices
CUSTOM_VOICES = {**BUILTIN_CUSTOM_VOICES, **_loaded_custom}
save_custom_voices(CUSTOM_VOICES)

# ---- Simple progress tracker ----
# The UI can poll /tts/progress to show "chunk X / Y"
TTS_PROGRESS = {
    "current": 0,
    "total": 0,
}


def reset_progress():
    TTS_PROGRESS["current"] = 0
    TTS_PROGRESS["total"] = 0


# ---- Models ----

# We force CPU for stability (XTTS + MPS is unstable)
device = "cpu"
print(f"Using device: {device}")

# Preset voices use VCTK (English multi-speaker)
VCTK_MODEL = "tts_models/en/vctk/vits"

# Cloned voices use XTTS v2 (multilingual, voice cloning via speaker_wav)
XTTS_MODEL = "tts_models/multilingual/multi-dataset/xtts_v2"

print("Loading VCTK model for preset voices...")
vctk_tts = TTS(VCTK_MODEL).to(device)

print("Loading XTTS model for cloned voices...")
xtts_tts = TTS(XTTS_MODEL).to(device)

# Map our front-end preset voice IDs -> actual VCTK speaker IDs
PRESET_VOICES = {
    "gentleman_deep": "p236",
    "gentleman_soft": "p230",
    "boy_casual": "p253",
    "boy_energy": "p243",
    "girl_warm": "p276",
    "girl_story": "p280",
    "girl_crisp": "p294",
    "girl_friendly": "p345",
    "radio_host": "p270",
    "movie_trailer": "p262",
    "soft_whisper": "p248",
    "news_anchor": "p283",
}

DEFAULT_VOICE_ID = "gentleman_deep"


def split_text(text: str, max_chars: int = 450) -> list[str]:
    """
    Split text into small chunks that are safe for XTTS.

    - First split by double newlines (paragraphs)
    - Then further split long paragraphs on sentence boundaries
    """
    text = text.strip()
    if not text:
        return []

    # Split into paragraphs first
    raw_paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []

    for para in raw_paragraphs:
        if len(para) <= max_chars:
            chunks.append(para)
            continue

        # Try to split by sentence-ish endings
        current = ""
        # Normalize sentence boundaries a bit
        normalized = (
            para.replace("?", "?.")
            .replace("!", "!.")
            .replace("…", "...")
        )
        sentences = [s.strip() for s in normalized.split(".") if s.strip()]

        for sentence in sentences:
            candidate = (current + " " + sentence).strip()
            if len(candidate) > max_chars:
                if current:
                    chunks.append(current.strip())
                current = sentence
            else:
                current = candidate

        if current:
            chunks.append(current.strip())

    # As a final safeguard, hard cut any monster chunk
    final_chunks: list[str] = []
    for ch in chunks:
        if len(ch) <= max_chars:
            final_chunks.append(ch)
        else:
            for i in range(0, len(ch), max_chars):
                piece = ch[i : i + max_chars].strip()
                if piece:
                    final_chunks.append(piece)

    return final_chunks


# ---- FastAPI app ----

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for simplicity in this hybrid setup
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
@app.get("/")
def home():
    return {"status": "running", "message": "VERSION 2.0 - UPDATED!", "files": str(list(VOICES_DIR.glob("*")))}



class TTSRequest(BaseModel):
    text: str
    language: str = "en"             # 'en', 'hi', 'es', etc.
    voice_id: str = DEFAULT_VOICE_ID # preset_xxx or custom_xxx


@app.get("/tts/progress")
def get_tts_progress():
    """
    UI can poll this endpoint to display progress like 'chunk 3 / 120'.
    """
    return {
        "current": TTS_PROGRESS["current"],
        "total": TTS_PROGRESS["total"],
    }


@app.post("/tts")
def tts_endpoint(body: TTSRequest):
    text = body.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Text is empty.")

    lang = body.language.lower().strip() or "en"
    voice_id = body.voice_id.strip() or DEFAULT_VOICE_ID

    # Reset progress for this new generation
    reset_progress()

    # -------- 1) Custom / cloned voices → XTTS (multilingual, supports Hindi etc.) --------
    if voice_id.startswith("custom_") or voice_id in CUSTOM_VOICES:
        voice_info = CUSTOM_VOICES.get(voice_id)
        if not voice_info:
            raise HTTPException(status_code=404, detail="Custom voice not found.")

        speaker_path = BASE_DIR / voice_info["file_path"]
        if not speaker_path.exists():
            # DEBUG: List actual files to see what's wrong
            try:
                found = list(VOICES_DIR.glob("*"))
                found_names = [f.name for f in found]
            except Exception:
                found_names = ["(Error listing files)"]
            
            raise HTTPException(
                status_code=404,
                detail=f"Reference audio missing: {speaker_path}. Found in dir: {found_names}",
            )

        print(f"Generating XTTS audio with cloned/custom voice {voice_id}, language={lang}")

        try:
            # Optimization: Smaller chunks (200 chars) for faster first-byte latency
            chunks = split_text(text, max_chars=200)
            if not chunks:
                raise HTTPException(status_code=400, detail="Text is empty after processing.")

            TTS_PROGRESS["total"] = len(chunks)
            audio_segments = []

            for idx, chunk in enumerate(chunks, start=1):
                TTS_PROGRESS["current"] = idx
                print(f"   [XTTS] chunk {idx}/{len(chunks)} (len={len(chunk)})")
                seg = xtts_tts.tts(
                    text=chunk,
                    speaker_wav=str(speaker_path),
                    language=lang,
                    speed=1.3,  # Optimization: Increase playback speed by 30%
                )
                audio_segments.append(seg)

            wav = np.concatenate(audio_segments)
            sample_rate = xtts_tts.synthesizer.output_sample_rate

            buf = io.BytesIO()
            sf.write(buf, wav, sample_rate, format="WAV")
            buf.seek(0)

            # Mark progress as done
            TTS_PROGRESS["current"] = TTS_PROGRESS["total"]

            return StreamingResponse(buf, media_type="audio/wav")
        except HTTPException:
            raise
        except Exception as e:
            print("Error in /tts (cloned/custom voice):", repr(e))
            raise HTTPException(
                status_code=500,
                detail="Error generating TTS for cloned/custom voice.",
            )

    # -------- 2) Preset voices → VCTK (English only) --------
    if lang != "en":
        raise HTTPException(
            status_code=400,
            detail=(
                "Preset voices currently support only English (en). "
                "Select a cloned/custom voice if you want Hindi or other languages."
            ),
        )

    speaker_id = PRESET_VOICES.get(voice_id, PRESET_VOICES[DEFAULT_VOICE_ID])
    print(f"Generating VCTK audio with preset voice_id={voice_id}, speaker={speaker_id}")

    try:
        chunks = split_text(text, max_chars=450)
        if not chunks:
            raise HTTPException(status_code=400, detail="Text is empty after processing.")

        TTS_PROGRESS["total"] = len(chunks)
        audio_segments = []

        for idx, chunk in enumerate(chunks, start=1):
            TTS_PROGRESS["current"] = idx
            print(f"   [VCTK] chunk {idx}/{len(chunks)} (len={len(chunk)})")
            seg = vctk_tts.tts(
                text=chunk,
                speaker=speaker_id,
            )
            audio_segments.append(seg)

        wav = np.concatenate(audio_segments)
        sample_rate = vctk_tts.synthesizer.output_sample_rate

        buf = io.BytesIO()
        sf.write(buf, wav, sample_rate, format="WAV")
        buf.seek(0)

        # Mark progress as done
        TTS_PROGRESS["current"] = TTS_PROGRESS["total"]

        return StreamingResponse(buf, media_type="audio/wav")
    except HTTPException:
        raise
    except Exception as e:
        print("Error in /tts (preset voice):", repr(e))
        raise HTTPException(
            status_code=500,
            detail="Error generating TTS for preset voice.",
        )


@app.post("/voices/clone")
async def clone_voice(
    audio: UploadFile = File(...),
    name: str = Form(None),
    language: str = Form("en"),
):
    """
    Upload an audio sample (10-30s clean speech) to create a new cloned voice.
    Returns a voice_id like 'custom_ab12cd34' that you can use in /tts.
    """
    if not audio.filename:
        raise HTTPException(status_code=400, detail="No audio file uploaded.")

    original_name = audio.filename
    ext = os.path.splitext(original_name)[1].lower() or ".wav"
    if ext not in [".wav", ".mp3", ".flac", ".ogg"]:
        ext = ".wav"

    voice_id = f"custom_{uuid4().hex[:8]}"
    dest_path = VOICES_DIR / f"{voice_id}{ext}"

    # Save uploaded file
    try:
        with dest_path.open("wb") as f:
            shutil.copyfileobj(audio.file, f)
    except Exception as e:
        print("Error saving uploaded audio:", e)
        raise HTTPException(status_code=500, detail="Failed to save uploaded audio file.")

    display_name = name or original_name or voice_id

    rel_path = str(dest_path.relative_to(BASE_DIR))
    CUSTOM_VOICES[voice_id] = {
        "file_path": rel_path,
        "name": display_name,
        "language": language.lower().strip() or "en",
    }
    save_custom_voices(CUSTOM_VOICES)

    print(f"New cloned voice created: {voice_id} -> {rel_path}")

    return JSONResponse(
        {
            "voice_id": voice_id,
            "name": display_name,
            "language": language.lower().strip() or "en",
        }
    )


@app.get("/voices")
def list_voices():
    """Helper endpoint to list all voices (preset + custom)."""
    return {
        "presets": list(PRESET_VOICES.keys()),
        "custom": CUSTOM_VOICES,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=False)

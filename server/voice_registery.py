from pathlib import Path
import json, uuid

BASE = Path(__file__).resolve().parent
DATA = BASE.parent / "data"
VOICES = DATA / "voices"
VOICES.mkdir(parents=True, exist_ok=True)

REG_PATH = VOICES / "registry.json"
if not REG_PATH.exists():
    REG_PATH.write_text(json.dumps({}))

def _read():
    return json.loads(REG_PATH.read_text())

def _write(obj):
    REG_PATH.write_text(json.dumps(obj, indent=2))

# Public API

def list_voices():
    return _read()


def create_voice(display_name: str):
    vid = str(uuid.uuid4())
    voices = _read()
    voices[vid] = {"id": vid, "name": display_name, "refs": []}
    (VOICES / vid).mkdir(parents=True, exist_ok=True)
    _write(voices)
    return voices[vid]


def add_reference_wav(voice_id: str, wav_path: Path):
    voices = _read()
    assert voice_id in voices, "voice not found"
    # Copy/normalize path into voice folder
    import shutil
    dst = VOICES / voice_id / wav_path.name
    shutil.copy2(wav_path, dst)
    voices[voice_id]["refs"].append(str(dst))
    _write(voices)
    return str(dst)
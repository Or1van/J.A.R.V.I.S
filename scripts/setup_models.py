"""Завантажує офлайн-моделі мовлення в %LOCALAPPDATA%\\Jarvis\\models (~200 МБ архівами)."""
import shutil
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # щоб знайти пакет jarvis

from jarvis.paths import MODELS_DIR, PIPER_MODEL, VOSK_MODEL

VOSK_URL = f"https://alphacephei.com/vosk/models/{VOSK_MODEL.name}.zip"
PIPER_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/main/uk/uk_UA/ukrainian_tts/medium/"


def download(url: str, dest: Path) -> None:
    print(f"Завантажую {url}")
    with urllib.request.urlopen(url) as resp, open(dest, "wb") as f:
        shutil.copyfileobj(resp, f)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    if VOSK_MODEL.exists():
        print("Модель розпізнавання вже є.")
    else:
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "vosk.zip"
            download(VOSK_URL, archive)
            with zipfile.ZipFile(archive) as z:
                z.extractall(MODELS_DIR)

    if PIPER_MODEL.exists():
        print("Офлайн-голос уже є.")
    else:
        PIPER_MODEL.parent.mkdir(parents=True, exist_ok=True)
        for suffix in ("", ".json"):
            download(PIPER_URL + PIPER_MODEL.name + suffix, PIPER_MODEL.with_name(PIPER_MODEL.name + suffix))

    print(f"Готово: {MODELS_DIR}")


if __name__ == "__main__":
    main()

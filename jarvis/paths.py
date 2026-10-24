"""Шляхи до файлів Джарвіса.

Код лежить у папці проєкту, а моделі та налаштування — у %LOCALAPPDATA%\\Jarvis,
щоб важкі файли не синхронізувались через OneDrive і не потрапляли в git.
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Jarvis"
MODELS_DIR = DATA_DIR / "models"
SETTINGS_FILE = DATA_DIR / "settings.json"

VOSK_MODEL = MODELS_DIR / "vosk-model-small-uk-v3-small"
PIPER_MODEL = MODELS_DIR / "piper" / "uk_UA-ukrainian_tts-medium.onnx"

DATA_DIR.mkdir(parents=True, exist_ok=True)

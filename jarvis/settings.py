"""Налаштування, які зберігаються між запусками (%LOCALAPPDATA%\\Jarvis\\settings.json)."""
import json
from dataclasses import asdict, dataclass, field, fields

from .paths import SETTINGS_FILE


@dataclass
class Settings:
    # Локальна модель в Ollama (мозок для запитів, які Джарвіс не розуміє сам) і адреса Ollama.
    local_model: str = "qwen3:4b"
    ollama_url: str = "http://127.0.0.1:11434"

    # Коли Джарвіс слухає: hotkey — лише після натискання гарячої клавіші; wake_word — завжди чекає слово "Джарвіс".
    activation: str = "hotkey"
    # Гаряча клавіша: клавіші через "+", натиснуті разом. Напр. "-+=", "ctrl+alt+j", "f9".
    hotkey: str = "-+="
    # Скільки секунд чекати команду після натискання гарячої клавіші.
    listen_seconds: int = 8
    # Скільки секунд тиші означає "фразу закінчено". Більше — Джарвіс не перебиває, коли ви робите паузу.
    pause_seconds: float = 1.3

    # Браузер для сайтів і пошуку: chrome | default (браузер Windows за замовчуванням) | повний шлях до .exe
    browser: str = "chrome"

    wake_words: list[str] = field(default_factory=lambda: [
        "джарвіс", "джарвис", "джервіс", "джервис", "jarvis", "жарвіс", "чарвіс",
    ])
    # Скільки секунд після відповіді Джарвіс ще слухає наступну команду (без клавіші й слова "Джарвіс").
    followup_seconds: int = 8
    # Після скількох хвилин тиші розмова з локальною моделлю починається спочатку.
    idle_reset_minutes: int = 10
    # Номер мікрофона (python main.py --list-mics). null = системний за замовчуванням.
    mic_index: int | None = None

    # Голос: auto (онлайн — edge, офлайн — piper) | edge | piper
    tts_engine: str = "auto"
    edge_voice: str = "uk-UA-OstapNeural"
    edge_rate: str = "+0%"
    # Диктор офлайн-голосу: 0 — Лада, 1 — Микита, 2 — Тетяна.
    piper_speaker: int = 1

    # Чи зачитувати початок відповіді Claude Code, коли він закінчив роботу.
    claude_code_summary: bool = True
    # Порт, на який Claude Code та інші програми надсилають події Джарвісу.
    event_port: int = 8765

    # Власні назви: "як кажу" -> шлях. Напр. {"сайт": "C:/Projects/my-site"}.
    projects: dict[str, str] = field(default_factory=dict)
    apps: dict[str, str] = field(default_factory=dict)

    @classmethod
    def load(cls) -> "Settings":
        data = {}
        if SETTINGS_FILE.exists():
            data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        known = {f.name for f in fields(cls)}
        settings = cls(**{k: v for k, v in data.items() if k in known})
        settings.save()  # дописує у файл нові параметри, що з'явились в оновленнях
        return settings

    def save(self) -> None:
        SETTINGS_FILE.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")

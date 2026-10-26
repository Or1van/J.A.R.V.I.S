"""Голос Джарвіса: edge-tts (онлайн, найприродніший) або Piper (офлайн).

Короткі фрази зберігаються в кеші (%LOCALAPPDATA%\\Jarvis\\tts_cache): повторні "Слухаю, сер",
"Відкриваю Telegram" звучать миттєво й без інтернету.
"""
import asyncio
import hashlib
import logging
import os
import shutil
import tempfile
import time
import wave

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import edge_tts
import pygame

from jarvis.net import is_online
from jarvis.paths import DATA_DIR, PIPER_MODEL
from jarvis.settings import Settings

logging.getLogger("piper").setLevel(logging.ERROR)

CACHE_DIR = DATA_DIR / "tts_cache"
CACHE_MAX_CHARS = 120  # довші відповіді (новини, нотатки) рідко повторюються — їх не кешуємо
CACHE_MAX_FILES = 400


class Mouth:
    def __init__(self, settings: Settings, ears=None, muted: bool = False):
        self.settings = settings
        self.ears = ears
        self.muted = muted
        self._piper = None
        if not muted:
            pygame.mixer.init()
            CACHE_DIR.mkdir(exist_ok=True)
            _prune_cache()

    def say(self, text: str) -> None:
        text = text.strip()
        if not text or self.muted:
            return
        path, temporary = None, True
        try:
            path, temporary = self._synthesize(text)
            if self.ears:
                self.ears.mute()
            pygame.mixer.music.load(path)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                time.sleep(0.05)
            pygame.mixer.music.unload()
        except Exception as e:
            print(f"[озвучення не вдалося: {e}]")
        finally:
            if self.ears:
                self.ears.unmute()
            if path and temporary:
                try:
                    os.remove(path)
                except OSError:
                    pass

    def _synthesize(self, text: str) -> tuple[str, bool]:
        """Повертає (шлях до аудіо, чи це тимчасовий файл, який треба видалити після відтворення)."""
        engine = self.settings.tts_engine
        s = self.settings
        edge_cached = _cached(f"edge|{s.edge_voice}|{s.speech_speed}|{text}", ".mp3")
        piper_cached = _cached(f"piper|{s.piper_speaker}|{s.speech_speed}|{text}", ".wav")
        cacheable = len(text) <= CACHE_MAX_CHARS
        if engine != "piper" and edge_cached.exists():
            return _hit(edge_cached)
        if engine != "edge" and piper_cached.exists() and not (engine == "auto" and is_online()):
            return _hit(piper_cached)
        if engine == "edge" or (engine == "auto" and is_online()):
            path = _temp_file(".mp3")
            try:
                rate = f"{self.settings.speech_speed:+d}%"
                communicate = edge_tts.Communicate(text, self.settings.edge_voice, rate=rate)
                asyncio.run(communicate.save(path))
                return _keep(path, edge_cached) if cacheable else (path, True)
            except Exception as e:
                os.remove(path)
                print(f"[онлайн-голос недоступний ({e}), говорю офлайн]")
        path = self._synthesize_piper(text)
        return _keep(path, piper_cached) if cacheable else (path, True)

    def _synthesize_piper(self, text: str) -> str:
        from piper import PiperVoice, SynthesisConfig

        if self._piper is None:
            self._piper = PiperVoice.load(str(PIPER_MODEL))
        path = _temp_file(".wav")
        with wave.open(path, "wb") as wav:
            config = SynthesisConfig(
                speaker_id=self.settings.piper_speaker,
                length_scale=1 / (1 + self.settings.speech_speed / 100),  # менше — швидше
            )
            self._piper.synthesize_wav(text, wav, syn_config=config)
        return path


def _cached(key: str, suffix: str):
    return CACHE_DIR / (hashlib.sha1(key.encode("utf-8")).hexdigest()[:20] + suffix)


def _hit(cached) -> tuple[str, bool]:
    os.utime(cached)  # свіжа дата — щоб часті фрази не видалялись із кешу
    return str(cached), False


def _keep(path: str, cached) -> tuple[str, bool]:
    """Переносить щойно озвучену фразу в кеш."""
    try:
        shutil.move(path, cached)
        return str(cached), False
    except OSError:
        return path, True


def _prune_cache() -> None:
    """Лишає в кеші лише фрази, які звучали найнедавніше."""
    files = sorted(CACHE_DIR.glob("*.*"), key=lambda f: f.stat().st_mtime, reverse=True)
    for f in files[CACHE_MAX_FILES:]:
        try:
            f.unlink()
        except OSError:
            pass


def _temp_file(suffix: str) -> str:
    fd, path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    return path

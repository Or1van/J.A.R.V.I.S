"""Голос Джарвіса: edge-tts (онлайн, найприродніший) або Piper (офлайн)."""
import asyncio
import logging
import os
import tempfile
import time
import wave

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import edge_tts
import pygame

from jarvis.net import is_online
from jarvis.paths import PIPER_MODEL
from jarvis.settings import Settings

logging.getLogger("piper").setLevel(logging.ERROR)


class Mouth:
    def __init__(self, settings: Settings, ears=None, muted: bool = False):
        self.settings = settings
        self.ears = ears
        self.muted = muted
        self._piper = None
        if not muted:
            pygame.mixer.init()

    def say(self, text: str) -> None:
        text = text.strip()
        if not text or self.muted:
            return
        path = None
        try:
            path = self._synthesize(text)
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
            if path:
                try:
                    os.remove(path)
                except OSError:
                    pass

    def _synthesize(self, text: str) -> str:
        engine = self.settings.tts_engine
        if engine == "edge" or (engine == "auto" and is_online()):
            path = _temp_file(".mp3")
            try:
                communicate = edge_tts.Communicate(text, self.settings.edge_voice, rate=self.settings.edge_rate)
                asyncio.run(communicate.save(path))
                return path
            except Exception as e:
                os.remove(path)
                print(f"[онлайн-голос недоступний ({e}), говорю офлайн]")
        return self._synthesize_piper(text)

    def _synthesize_piper(self, text: str) -> str:
        from piper import PiperVoice, SynthesisConfig

        if self._piper is None:
            self._piper = PiperVoice.load(str(PIPER_MODEL))
        path = _temp_file(".wav")
        with wave.open(path, "wb") as wav:
            self._piper.synthesize_wav(text, wav, syn_config=SynthesisConfig(speaker_id=self.settings.piper_speaker))
        return path


def _temp_file(suffix: str) -> str:
    fd, path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    return path

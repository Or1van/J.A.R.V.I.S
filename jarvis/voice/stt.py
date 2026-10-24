"""Вуха Джарвіса.

Мікрофон відкритий у фоні, але фрази обробляються лише коли Джарвіс "слухає".
Якщо є інтернет — фразу розпізнає Google (точніше), інакше — офлайн-модель Vosk.
"""
import json
import queue
import threading
import time
from typing import Callable

import speech_recognition as sr
from vosk import KaldiRecognizer, Model, SetLogLevel

from jarvis.net import is_online
from jarvis.paths import VOSK_MODEL


class Utterance:
    """Одна почута фраза."""

    def __init__(self, text: str, audio: sr.AudioData | None = None, language: str = "uk-UA",
                 accurate: str | None = None, offline: Callable[[], str] | None = None):
        self.text = text
        self.audio = audio
        self.language = language
        self._accurate = accurate
        self._offline = offline  # як отримати офлайн-варіант тексту (рахується лише за потреби)

    def alternatives(self) -> list[str]:
        """Інші варіанти розпізнавання тієї ж фрази — щоб спробувати їх, якщо основний не схожий на команду."""
        options = [self.accurate()]
        if self._offline is not None:
            options.append(self._offline())
        return [o for i, o in enumerate(options) if o and o != self.text and o not in options[:i]]

    def accurate(self) -> str:
        """Точніший текст (Google), якщо є інтернет; інакше — офлайн-варіант."""
        if self._accurate is None:
            self._accurate = self.text
            if self.audio is not None and is_online():
                try:
                    self._accurate = sr.Recognizer().recognize_google(self.audio, language=self.language)
                except (sr.UnknownValueError, sr.RequestError):
                    pass
        return self._accurate


class VoiceEars:
    requires_wake_word = True
    closed = False
    # Мікрофон відкритий постійно, але фрази розпізнаються лише коли active=True
    # (після гарячої клавіші, у режимі диктування або в режимі слова-активатора).
    active = False

    def __init__(self, mic_index: int | None = None, language: str = "uk-UA", pause_seconds: float = 1.3):
        self.language = language
        print("Завантажую офлайн-модель розпізнавання мовлення...")
        SetLogLevel(-1)
        self.model = Model(str(VOSK_MODEL))
        self.online_recognizer = sr.Recognizer()
        self.online_recognizer.operation_timeout = 6

        self.recognizer = sr.Recognizer()
        self.recognizer.pause_threshold = pause_seconds
        self.recognizer.dynamic_energy_threshold = True
        self.mic = sr.Microphone(device_index=mic_index)
        print("Калібрую мікрофон під фоновий шум, секунду тиші...")
        with self.mic as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=1)

        self.queue: queue.Queue[sr.AudioData] = queue.Queue()
        self._muted = False
        self._unmuted_at = 0.0  # коли Джарвіс востаннє замовк
        self._stop =self.recognizer.listen_in_background(self.mic, self._on_audio, phrase_time_limit=30)

    def _on_audio(self, _recognizer, audio: sr.AudioData) -> None:
        """Мікрофон чує й самого Джарвіса. Фраза "закінчується" лише після паузи (pause_threshold),
        тож відлуння його голосу приходить уже після того, як він замовк. Тому дивимось, коли фраза
        ПОЧАЛАСЬ: якщо ще під час його мовлення — це його ж голос (напр. "...скажіть так або ні")."""
        if not self.active or self._muted:
            return
        r = self.recognizer
        duration = len(audio.frame_data) / (audio.sample_rate * audio.sample_width)
        speech_end = time.time() - r.pause_threshold
        speech_start = speech_end - (duration - 2 * r.non_speaking_duration)
        if speech_start < self._unmuted_at - 0.2:
            return
        self.queue.put(audio)

    def set_active(self, on: bool) -> None:
        self.active = on
        if not on:
            while not self.queue.empty():
                self.queue.get_nowait()

    def mute(self) -> None:
        self._muted = True

    def unmute(self) -> None:
        self._unmuted_at = time.time()
        self._muted = False
        while not self.queue.empty():
            self.queue.get_nowait()

    def next(self, timeout: float) -> Utterance | None:
        deadline = time.time() + timeout
        while (remaining := deadline - time.time()) > 0:
            try:
                audio = self.queue.get(timeout=remaining)
            except queue.Empty:
                return None
            utterance = self._recognize(audio)
            if utterance is not None:
                return utterance
        return None

    def _recognize(self, audio: sr.AudioData) -> Utterance | None:
        if is_online():
            try:
                text = self.online_recognizer.recognize_google(audio, language=self.language)
                return Utterance(text, audio, self.language, accurate=text,
                                 offline=lambda: self._recognize_offline(audio))
            except sr.UnknownValueError:
                return None  # Google нічого не розібрав — найімовірніше, це був шум
            except sr.RequestError:
                pass  # сервіс недоступний — розпізнаємо офлайн
        text = self._recognize_offline(audio)
        if len(text) > 1:  # окремі "а", "і" — зазвичай шум
            return Utterance(text, audio, self.language)
        return None

    def _recognize_offline(self, audio: sr.AudioData) -> str:
        rec = KaldiRecognizer(self.model, 16000)
        rec.AcceptWaveform(audio.get_raw_data(convert_rate=16000, convert_width=2))
        return json.loads(rec.FinalResult()).get("text", "").strip()

    def close(self) -> None:
        self._stop(wait_for_stop=False)


class TextEars:
    """Клавіатура замість мікрофона (режим --text)."""
    requires_wake_word = False
    active = True

    def __init__(self):
        self.queue: queue.Queue[str | None] = queue.Queue()
        self.closed = False
        print("Текстовий режим: пишіть команди й натискайте Enter. Порожній рядок — вихід.")
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self) -> None:
        while True:
            try:
                line = input()
            except EOFError:
                line = ""
            self.queue.put(line.strip() or None)
            if not line.strip():
                return

    def next(self, timeout: float) -> Utterance | None:
        try:
            line = self.queue.get(timeout=timeout)
        except queue.Empty:
            return None
        if line is None:
            self.closed = True
            return None
        return Utterance(line)

    def set_active(self, on: bool) -> None:
        pass

    def mute(self) -> None:
        pass

    def unmute(self) -> None:
        pass

    def close(self) -> None:
        pass

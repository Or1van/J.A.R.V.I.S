"""Ядро Джарвіса: слухає, вирішує, хто виконає команду, і відповідає.

Коли слухати:
  - activation = "hotkey": лише після гарячої клавіші (або кнопки "Говорити"), ще кілька секунд
    після відповіді та весь час, поки активний режим (напр. диктування);
  - activation = "wake_word": завжди, але реагує лише на фрази зі словом "Джарвіс".

Порядок обробки фрази:
  1. активний режим (напр. диктування для Claude Code) отримує фразу першим;
  2. локальні команди — виконуються миттєво, без ШІ та інтернету;
  3. якщо є інтернет — фраза ще раз розпізнається точніше (Google) і знову перевіряється локально;
  4. усе інше йде локальній моделі (Ollama), якщо вона встановлена.
"""
import queue
import time
import traceback
import winsound
from typing import Protocol

from jarvis.core import registry, runtime
from jarvis.core.text import is_yes, normalize, split_wake_word
from jarvis.settings import Settings
from jarvis.voice.stt import Utterance

NOT_UNDERSTOOD = "Цього я поки не вмію. Можу відкрити Claude Code — скажіть «Джарвіс, відкрий Claude Code»."


class Mode(Protocol):
    """Режим, який перехоплює всі фрази без слова "Джарвіс" (напр. диктування)."""
    def handle(self, text: str, utterance) -> None: ...


class Assistant:
    def __init__(self, settings: Settings, ears, mouth, brain, ui):
        self.settings = settings
        self.ears = ears
        self.mouth = mouth
        self.brain = brain
        self.ui = ui
        self.events: queue.Queue = queue.Queue()
        self.mode: Mode | None = None
        self.running = True
        self.listening = False
        self.armed_until = 0.0
        self.followup_until = 0.0
        self.last_said = ""
        self._utterance = None
        self._command_raw = ""
        runtime.bind(self)

    # ---------- API для навичок ----------

    def say(self, text: str) -> None:
        if text and text.strip():
            self.last_said = text
            self.ui.log("Джарвіс", text)
            self.ui.status("speak")
            self.mouth.say(text)
            self.ui.status("listen" if self.listening else "sleep")

    def listen(self, timeout: float = 8.0) -> str | None:
        utterance = self._next_utterance(timeout)
        return utterance.accurate() if utterance else None

    def confirm(self, question: str) -> bool:
        self.say(f"{question} Скажіть «так» або «ні».")
        return is_yes(self.listen(8))

    def command_text(self) -> str:
        if self._utterance is None:
            return self._command_raw
        _, rest = split_wake_word(self._utterance.accurate(), self.settings.wake_words)
        return rest

    def activate(self) -> None:
        """Гаряча клавіша / кнопка: почати слухати. Повторне натискання — перестати."""
        if self.listening and self.mode is None and self.settings.activation == "hotkey":
            self.armed_until = self.followup_until = 0.0
        else:
            self.armed_until = time.time() + self.settings.listen_seconds

    def stop(self) -> None:
        self.running = False

    # ---------- Головний цикл ----------

    def run(self) -> None:
        status = "підключена" if self.brain.available() else "не встановлена (лише вбудовані команди)"
        print(f"Локальна модель {self.settings.local_model}: {status}.")
        if self.settings.activation == "hotkey" and self.ears.requires_wake_word:
            keys = " і ".join(self.settings.hotkey.split("+"))
            self.say(f"Джарвіс на зв'язку. Щоб я слухав, натисніть {keys}.")
        else:
            self.say("Джарвіс на зв'язку.")
        while self.running and not self.ears.closed:
            self._set_listening(self._wants_to_listen())
            utterance = self.ears.next(timeout=0.25)
            if utterance is not None:
                self._on_utterance(utterance)
            self._process_events()

    def _wants_to_listen(self) -> bool:
        if self.settings.activation != "hotkey" or not self.ears.requires_wake_word:
            return True
        return self.mode is not None or time.time() < max(self.armed_until, self.followup_until)

    def _set_listening(self, on: bool) -> None:
        if on == self.listening:
            return
        self.listening = on
        if self.ears.requires_wake_word and self.settings.activation == "hotkey":
            winsound.Beep(1000 if on else 600, 80)  # короткий сигнал: почав / перестав слухати
        self.ears.set_active(on)
        self.ui.status("listen" if on else "sleep")

    def _next_utterance(self, timeout: float) -> Utterance | None:
        """Слухає наступну фразу (навіть якщо зараз режим "не слухаю")."""
        self.armed_until = max(self.armed_until, time.time() + timeout)
        self._set_listening(True)
        utterance = self.ears.next(timeout)
        if utterance is not None:
            self.ui.log("Ви", utterance.text)
        return utterance

    def _process_events(self) -> None:
        while True:
            try:
                kind, payload = self.events.get_nowait()
            except queue.Empty:
                return
            try:
                if kind == "jarvis.activate":
                    self.activate()
                elif kind == "jarvis.show":  # повторний запуск (Ctrl+Alt+J), коли Джарвіс уже працює
                    self.ui.show()
                    if not self.listening:
                        self.activate()
                elif kind == "ui.text":
                    self._on_utterance(Utterance(payload["text"]), typed=True)
                for handler in runtime.EVENT_HANDLERS.get(kind, []):
                    handler(payload)
            except Exception:
                traceback.print_exc()

    def _on_utterance(self, utterance: Utterance, typed: bool = False) -> None:
        has_wake, rest = split_wake_word(utterance.text, self.settings.wake_words)
        rest = normalize(rest)
        self.ui.log("Ви", utterance.text)

        if self.mode is not None:
            # "Джарвіс, гучніше" працює і в режимі; решта — для режиму
            if has_wake and rest and self._try_local(rest, utterance):
                return
            self.mode.handle(rest if has_wake else normalize(utterance.text), utterance)
            return

        awake = (has_wake or typed or not self.ears.requires_wake_word
                 or self.settings.activation == "hotkey" or time.time() < self.followup_until)
        if not awake:
            return

        if has_wake and not rest:
            self.say("Слухаю, сер.")
            utterance = self._next_utterance(8)
            if utterance is None:
                return
            rest = normalize(utterance.text)

        self.armed_until = 0.0
        self.ui.status("busy")
        self.execute(rest, utterance)
        self.ui.status("listen" if self.listening else "sleep")
        if not typed:  # після голосової команди ще трохи слухаємо наступну
            self.followup_until = time.time() + self.settings.followup_seconds

    def execute(self, text: str, utterance=None) -> None:
        """Виконує команду: спочатку локально, потім через локальну модель."""
        if self._try_local(text, utterance):
            return

        raw = text
        if utterance is not None:
            # Інший розпізнавач міг почути фразу інакше — може, це все ж вбудована команда
            for alternative in utterance.alternatives():
                _, alt = split_wake_word(alternative, self.settings.wake_words)
                if normalize(alt) != text:
                    print(f"(інший варіант: {alt})")
                    if self._try_local(normalize(alt), utterance):
                        return
            _, raw = split_wake_word(utterance.accurate(), self.settings.wake_words)

        if not self.brain.available():
            self.say(NOT_UNDERSTOOD)
            return
        self._utterance = utterance
        self.brain.ask(raw, on_text=self.say)

    def _try_local(self, text: str, utterance=None) -> bool:
        found = registry.match(text)
        if found is None:
            return False
        cmd, args = found
        self._utterance, self._command_raw = utterance, text
        try:
            reply = cmd.handler(**args)
        except registry.NotHandled:
            return False
        except Exception:
            traceback.print_exc()
            self.say("Не вийшло виконати команду.")
            return True
        if reply:
            self.say(reply)
        return True

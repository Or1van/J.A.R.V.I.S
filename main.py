"""Джарвіс — голосовий асистент для керування комп'ютером.

Запуск:
    python main.py              вікно + голос (слухає після гарячої клавіші, за замовчуванням «-» і «=» разом)
    python main.py --console    без вікна, лише консоль
    python main.py --text       без мікрофона: команди з клавіатури в консолі
    python main.py --mute       не озвучувати відповіді
    python main.py --list-mics  показати мікрофони
"""
import argparse
import json
import os
import sys
import threading
import urllib.request

from jarvis.paths import DATA_DIR, SETTINGS_FILE, VOSK_MODEL

LOG_FILE = DATA_DIR / "jarvis.log"


def main() -> None:
    windowless = sys.stdout is None  # запуск без консолі (pythonw, ярлик Ctrl+Alt+J)
    if windowless:
        sys.stdout = sys.stderr = open(os.devnull, "w", encoding="utf-8")
    else:
        sys.stdout.reconfigure(encoding="utf-8")
        if sys.stdin is not None:
            sys.stdin.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Джарвіс — голосовий асистент")
    parser.add_argument("--console", action="store_true", help="без вікна, лише консоль")
    parser.add_argument("--text", action="store_true", help="команди з клавіатури в консолі замість голосу")
    parser.add_argument("--mute", action="store_true", help="не озвучувати відповіді")
    parser.add_argument("--list-mics", action="store_true", help="показати доступні мікрофони")
    args = parser.parse_args()

    if args.list_mics:
        import speech_recognition as sr
        for i, name in enumerate(sr.Microphone.list_microphone_names()):
            print(f"{i}: {name}")
        return

    if not args.text and not VOSK_MODEL.exists():
        print("Немає офлайн-моделі розпізнавання мовлення. Запустіть: python setup_models.py")
        return

    from jarvis.settings import Settings

    settings = Settings.load()
    if not args.text and _already_running(settings.event_port):
        print("Джарвіс уже запущений — показую його вікно.")
        return
    if windowless:
        # Тепер точно лише одна копія — усе, що друкується, пишемо в журнал
        sys.stdout = sys.stderr = open(LOG_FILE, "w", encoding="utf-8", buffering=1)

    from jarvis.brains.local import LocalBrain
    from jarvis.core import registry
    from jarvis.core.assistant import Assistant
    from jarvis.core.events import EventServer
    from jarvis.ui.console import ConsoleUI
    from jarvis.voice.stt import TextEars, VoiceEars
    from jarvis.voice.tts import Mouth

    print(f"Налаштування: {SETTINGS_FILE}")
    registry.load_skills()

    ears = TextEars() if args.text else VoiceEars(settings.mic_index, pause_seconds=settings.pause_seconds)
    mouth = Mouth(settings, ears, muted=args.mute)
    use_window = not (args.console or args.text)
    if use_window:
        from jarvis.ui.hud import Hud

        # Вікно створюється до асистента, але йому потрібен асистент — підставимо після створення.
        ui_proxy = _LateUI()
        assistant = Assistant(settings, ears, mouth, LocalBrain(settings), ui_proxy)
        ui_proxy.target = Hud(assistant, settings.hotkey)
    else:
        assistant = Assistant(settings, ears, mouth, LocalBrain(settings), ConsoleUI())

    server = None
    try:
        server = EventServer(settings.event_port, assistant.events)
        server.start()
    except OSError as e:
        print(f"[сервер подій не запустився на порту {settings.event_port}: {e}]")

    from jarvis.core.desktop import start_tracking
    start_tracking()

    if not args.text:
        import keyboard
        keyboard.add_hotkey(settings.hotkey, lambda: assistant.events.put(("jarvis.activate", {})))
        print(f"Гаряча клавіша: {settings.hotkey}")

    try:
        if use_window:
            threading.Thread(target=_run_safely, args=(assistant,), daemon=True).start()
            ui_proxy.target.run()
        else:
            assistant.run()
    except KeyboardInterrupt:
        pass
    finally:
        assistant.stop()
        if server:
            server.stop()
        ears.close()
    print("Джарвіс завершив роботу.")


def _already_running(port: int) -> bool:
    """Якщо Джарвіс уже працює, просимо його показати вікно й почати слухати."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=0.5) as resp:
            if resp.read() != b"jarvis ok":
                return False
        body = json.dumps({"type": "jarvis.show"}).encode()
        request = urllib.request.Request(f"http://127.0.0.1:{port}/event", data=body,
                                         headers={"Content-Type": "application/json"})
        urllib.request.urlopen(request, timeout=1).close()
        return True
    except OSError:
        return False


class _LateUI:
    """Передає виклики інтерфейсу вікну, яке створюється трохи пізніше за асистента."""
    target = None

    def log(self, who: str, text: str) -> None:
        print(f"{who}: {text}")
        if self.target:
            self.target.log(who, text)

    def status(self, state: str) -> None:
        if self.target:
            self.target.status(state)

    def show(self) -> None:
        if self.target:
            self.target.show()


def _run_safely(assistant) -> None:
    try:
        assistant.run()
    except Exception:
        import traceback
        traceback.print_exc()
    finally:
        assistant.stop()


if __name__ == "__main__":
    main()

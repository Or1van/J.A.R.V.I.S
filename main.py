"""Джарвіс — голосовий асистент для керування комп'ютером.

Запуск:
    python main.py              вікно + голос (слухає після гарячої клавіші, за замовчуванням «-» і «=» разом)
    python main.py --console    без вікна, лише консоль
    python main.py --text       без мікрофона: команди з клавіатури в консолі
    python main.py --mute       не озвучувати відповіді
    python main.py --list-mics  показати мікрофони
"""
import argparse
import importlib
import json
import os
import queue
import sys
import threading
import traceback
import urllib.request
from concurrent.futures import ThreadPoolExecutor

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

    from jarvis.core.events import EventServer

    events: queue.Queue = queue.Queue()
    server = None
    try:
        server = EventServer(settings.event_port, events)
        server.start()
    except OSError as e:
        print(f"[сервер подій не запустився на порту {settings.event_port}: {e}]")

    if not args.text:
        import keyboard
        keyboard.add_hotkey(settings.hotkey, lambda: events.put(("jarvis.activate", {})))
        print(f"Гаряча клавіша: {settings.hotkey}")

    print(f"Налаштування: {SETTINGS_FILE}")
    use_window = not (args.console or args.text)
    if use_window:
        # Вікно — одразу, ще до завантаження моделей; асистент під'єднається, коли буде готовий
        from jarvis.ui.hud import Hud
        ui = Hud(settings, events)
    else:
        from jarvis.ui.console import ConsoleUI
        ui = ConsoleUI()

    started: dict = {}

    def boot_and_run() -> None:
        try:
            assistant = started["assistant"] = _build(settings, args, ui, events)
            if use_window:
                ui.attach(assistant)
            assistant.run()
        except Exception:
            traceback.print_exc()
            ui.log("Джарвіс", "Не вдалося запуститися. Подробиці — у журналі.")
        finally:
            if "assistant" in started:
                started["assistant"].stop()

    try:
        if use_window:
            threading.Thread(target=boot_and_run, daemon=True).start()
            ui.run()
        else:
            boot_and_run()
    except KeyboardInterrupt:
        pass
    finally:
        if "assistant" in started:
            started["assistant"].stop()
            started["assistant"].ears.close()
        if server:
            server.stop()
    print("Джарвіс завершив роботу.")


def _build(settings, args, ui, events):
    """Створює асистента. Найдовші частини запуску — офлайн-модель розпізнавання мовлення, бібліотеки
    голосу й навички — вантажаться паралельно, а не одна за одною."""
    from jarvis.core import registry

    with ThreadPoolExecutor(max_workers=2) as pool:
        skills = pool.submit(registry.load_skills)
        tts = pool.submit(importlib.import_module, "jarvis.voice.tts")
        from jarvis.voice.stt import TextEars, VoiceEars
        ears = TextEars() if args.text else VoiceEars(settings.mic_index, pause_seconds=settings.pause_seconds)
        skills.result()
        mouth = tts.result().Mouth(settings, ears, muted=args.mute)

    from jarvis.brains.local import LocalBrain
    from jarvis.core.assistant import Assistant
    from jarvis.core.desktop import start_tracking

    start_tracking()
    return Assistant(settings, ears, mouth, LocalBrain(settings), ui, events)


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


if __name__ == "__main__":
    main()

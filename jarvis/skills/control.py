"""Керування самим Джарвісом: нова розмова, довідка, повтор, вихід."""
from jarvis.core import runtime
from jarvis.core.registry import command, tool

HELP = ("Я вмію відкривати й закривати програми та вікна, керувати звуком і музикою, шукати в інтернеті, "
        "відкривати папки й проєкти, показувати стан комп'ютера і відкривати Claude Code. "
        "Наприклад: Джарвіс, відкрий Claude Code.")


@tool
def stop_assistant() -> str:
    """Вимкнути самого Джарвіса (завершити роботу асистента), коли користувач прощається або просить вимкнутися."""
    runtime.assistant().stop()
    return "Асистент завершить роботу після цієї відповіді."


@command(r"яка (?:зараз )?модель|на якій моделі (?:ти )?(?:працюєш|думаєш)", priority=8)
def _which_brain():
    a = runtime.assistant()
    if a.brain.available():
        return f"Я думаю на локальній моделі {a.settings.local_model}."
    return "Локальна модель не встановлена, тож я виконую лише вбудовані команди."


@command(r"нова розмова|забудь (?:усе|все)|почнемо спочатку|почни нову розмову", priority=8)
def _new_conversation():
    runtime.assistant().brain.reset()
    return "Гаразд, почнемо з чистого аркуша."


@command(r"що ти вмієш|допомога|довідка|що ти можеш", priority=8)
def _help():
    return HELP


@command(r"повтори|що ти сказав", priority=8)
def _repeat():
    return runtime.assistant().last_said or "Я ще нічого не казав."


@command(r"вимкнись|вимкни себе|до побачення|бувай|на сьогодні все|відпочинь", priority=8)
def _goodbye():
    runtime.assistant().stop()
    return "До зустрічі, сер."

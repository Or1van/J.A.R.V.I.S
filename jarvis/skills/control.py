"""Керування самим Джарвісом: швидкість мовлення, "ще", нова розмова, довідка, повтор, вихід."""
from jarvis.core import runtime
from jarvis.core.registry import NotHandled, command, tool

HELP = ("Я вмію відкривати й закривати програми та вікна, керувати звуком, музикою й відео, шукати в інтернеті, "
        "розповідати новини, пропонувати ідеї для проєктів, записувати цілі й нотатки, працювати з Telegram, "
        "відкривати проєкти, Claude Code і чат Claude. Наприклад: Джарвіс, новини.")


@command(r"(?:говори|розмовляй) (?P<how>швидше|повільніше)(?: будь ласка)?|(?P<how2>швидше|повільніше) говори", priority=8)
def _speech_speed(how=None, how2=None):
    settings = runtime.settings()
    step = 15 if (how or how2) == "швидше" else -15
    settings.speech_speed = max(-40, min(80, settings.speech_speed + step))
    settings.save()
    return "Так краще?"


@command(r"ще|більше|ще трохи|наступні|інші|ще варіанти|ще ідеї|ще новини|далі новини", priority=6)
def _more():
    if runtime.more is None:  # "ще" має сенс лише після новин, ідей тощо
        raise NotHandled
    return runtime.more()


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


# «Розгорни/згорни вікно» — це про вікна користувача, а «розгорнись/згорнись» — про самого Джарвіса.
@command(r"розгорнись(?: на весь екран)?|розгорни себе|покажи себе на весь екран|режим (?:повного екрана|hud)", priority=8)
def _view_full():
    return _view("full")


@command(r"згорнись|сховайся|зменшись|міні режим|режим міні|маленький режим", priority=8)
def _view_mini():
    return _view("mini")


@command(r"(?:звичайний|компактний|нормальний) режим|зроби звичайне вікно", priority=8)
def _view_normal():
    return _view("normal")


def _view(mode: str) -> str | None:
    ui = runtime.assistant().ui
    if not ui.has_window:
        return "Зараз я працюю без вікна."
    ui.view(mode)
    return None


@command(r"повтори|що ти сказав", priority=8)
def _repeat():
    return runtime.assistant().last_said or "Я ще нічого не казав."


@command(
    r"вимкнись|виключись|закрийся|вимкни себе|закрий себе|до побачення|бувай|на сьогодні все|відпочинь"
    r"|(?:вимкни|виключи|закрий|заверши)(?: роботу)? (?:джарвіс\w*|jarvis|джервіс\w*|асистент\w*)"
    r"|заверши роботу|вийди з програми",
    priority=8,
)
def _goodbye():
    runtime.assistant().stop()
    return "До зустрічі, сер."

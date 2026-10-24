"""Звук і медіа: гучність, пауза, треки."""
from jarvis.core.desktop import press_vk
from jarvis.core.registry import NotHandled, command, tool
from jarvis.core.text import parse_number

VK = {"mute": 0xAD, "down": 0xAE, "up": 0xAF, "next": 0xB0, "previous": 0xB1, "play_pause": 0xB3}
PERCENT = r"(?: відсотків| відсотки| відсоток| процентів)?"


@tool
def volume(action: str, amount: int = 10) -> str:
    """Керування гучністю системи.

    Args:
        action: "up" (гучніше), "down" (тихіше), "set" (встановити рівень), "mute" (вимкнути/увімкнути звук).
        amount: Для up/down — на скільки відсотків змінити; для set — цільовий рівень 0-100.
    """
    amount = max(0, min(100, amount))
    if action == "mute":
        press_vk(VK["mute"])
        return "Готово."
    if action == "set":
        press_vk(VK["down"], 50)  # одне натискання = 2%
        press_vk(VK["up"], amount // 2)
        return f"Гучність {amount}."
    if action in ("up", "down"):
        press_vk(VK[action], max(1, amount // 2))
        return ""
    return f"Невідома дія {action}."


@tool
def media_control(action: str) -> str:
    """Керування відтворенням музики/відео (Spotify, YouTube у браузері тощо).

    Args:
        action: "play_pause" (пауза/продовжити), "next" (наступний трек), "previous" (попередній).
    """
    if action not in ("play_pause", "next", "previous"):
        return f"Невідома дія {action}."
    press_vk(VK[action])
    return ""


def _amount(n: str | None, default: int = 10) -> int:
    if n is None:
        return default
    value = parse_number(n)
    if value is None:
        raise NotHandled
    return value


@command(
    rf"(?:зроби )?(?:гучніше|голосніше)(?: на (?P<n>.+?){PERCENT})?",
    rf"(?:збільш|додай|прибав) (?:гучність|звук)(?: на (?P<n>.+?){PERCENT})?",
    priority=5,
)
def _louder(n=None):
    return volume("up", _amount(n))


@command(
    rf"(?:зроби )?тихіше(?: на (?P<n>.+?){PERCENT})?",
    rf"(?:зменш|убав|притиш\w*) (?:гучність|звук)(?: на (?P<n>.+?){PERCENT})?",
    priority=5,
)
def _quieter(n=None):
    return volume("down", _amount(n))


@command(rf"(?:зроби |постав |встанови )?гучність (?:на )?(?P<n>.+?){PERCENT}", priority=2)
def _set_volume(n):
    return volume("set", _amount(n))


@command(r"(?:вимкни|прибери|увімкни|поверни) звук|без звуку", priority=2)
def _mute():
    return volume("mute")


@command(
    r"пауза|(?:постав )?на паузу|зупини(?: музику| відео)?|продовж\w*(?: музику| відео)?|грай|відтвори",
    priority=2,
)
def _play_pause():
    return media_control("play_pause")


@command(r"(?:наступн\w*|перемкни|далі)(?: трек| пісн\w*| відео)?", priority=2)
def _next():
    return media_control("next")


@command(r"попередн\w*(?: трек| пісн\w*| відео)?", priority=2)
def _previous():
    return media_control("previous")

"""Екран: зберегти знімок."""
from datetime import datetime
from pathlib import Path

import pyautogui

from jarvis.core.registry import command, tool


@tool
def save_screenshot() -> str:
    """Зберегти знімок екрана у файл (папка Зображення/Jarvis)."""
    folder = Path.home() / "Pictures" / "Jarvis"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"screenshot_{datetime.now():%Y-%m-%d_%H-%M-%S}.png"
    pyautogui.screenshot().save(path)
    return "Знімок збережено в папку Зображення, Jarvis."


@command(r"(?:зроби |збережи )?(?:скріншот|скрін|знімок екрана)", priority=4)
def _screenshot():
    return save_screenshot()

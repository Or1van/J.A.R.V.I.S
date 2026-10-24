"""Проєкти: останні папки з VS Code і власні назви з settings.json -> projects."""
import json
import os
import shutil
import subprocess
from pathlib import Path
from urllib.parse import unquote

from jarvis.core import runtime
from jarvis.core.registry import OPEN, command, tool
from jarvis.core.text import best_match

VSCODE_WORKSPACES = Path(os.environ.get("APPDATA", "")) / "Code" / "User" / "workspaceStorage"
PROJECT = r"(?:проєкт|проект)\w*"


def recent_projects() -> list[Path]:
    """Папки, які нещодавно відкривались у VS Code (найсвіжіші першими).
    VS Code тримає для кожної папки каталог у workspaceStorage; час його зміни = коли проєкт відкривали."""
    found: dict[Path, float] = {}
    for meta in VSCODE_WORKSPACES.glob("*/workspace.json"):
        try:
            uri = json.loads(meta.read_text(encoding="utf-8")).get("folder", "")
        except (OSError, ValueError):
            continue
        if not uri.startswith("file:///"):
            continue
        path = Path(unquote(uri[len("file:///"):]))
        if path.is_dir():
            used = max(f.stat().st_mtime for f in meta.parent.iterdir())
            found[path] = max(used, found.get(path, 0.0))
    return sorted(found, key=found.get, reverse=True)


def all_projects() -> dict[str, Path]:
    """Назва -> шлях. Власні назви з налаштувань мають перевагу."""
    projects = {p.name.lower(): p for p in reversed(recent_projects())}
    try:
        custom = runtime.settings().projects
    except RuntimeError:
        custom = {}
    projects.update({name.lower(): Path(path) for name, path in custom.items()})
    return projects


def find_project(name: str = "") -> Path | None:
    """Порожня назва — останній проєкт."""
    if not name:
        recent = recent_projects()
        return recent[0] if recent else None
    projects = all_projects()
    found = best_match(name, list(projects))
    return projects[found] if found else None


@tool
def open_project(name: str = "") -> str:
    """Відкрити проєкт (папку з кодом) у VS Code.

    Args:
        name: Назва проєкту (папки). Порожньо — останній відкритий проєкт.
    """
    path = find_project(name)
    if path is None:
        return f"Не знайшов проєкт {name}." if name else "Не знайшов останніх проєктів."
    code = shutil.which("code") or "code"
    subprocess.Popen([code, str(path)])
    return f"Відкриваю проєкт {path.name}."


@tool
def list_projects() -> str:
    """Список останніх проєктів (папок, відкритих у VS Code)."""
    names = [p.name for p in recent_projects()[:7]]
    return ("Останні проєкти: " + ", ".join(names) + ".") if names else "Проєктів не знайдено."


@command(rf"{OPEN} (?:наш |мій )?(?:останній|минулий|попередній) {PROJECT}", priority=6)
def _open_last():
    return open_project()


@command(rf"{OPEN} {PROJECT} (?P<name>.+)", priority=6)
def _open_named(name):
    return open_project(name)


@command(rf"(?:які|покажи|список|перелічи)(?: у мене| в мене| мої| наші)? {PROJECT}", priority=6)
def _list():
    return list_projects()

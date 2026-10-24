"""Цілі на день і нотатки.

"Запиши цілі" -> режим запису: кожна фраза — окрема ціль, "все" — кінець.
"Розкажи цілі на сьогодні" -> Джарвіс зачитує список. "Виконав другу ціль" -> позначає виконаною.
Файли лежать у %LOCALAPPDATA%\\Jarvis\\notes (не в репозиторії): goals-РРРР-ММ-ДД.md і notes.md.
"""
import os
import re
from datetime import date, datetime

from jarvis.core import runtime
from jarvis.core.registry import OPEN, command, tool
from jarvis.core.text import ORDINAL, normalize, parse_ordinal, split_wake_word
from jarvis.paths import DATA_DIR

NOTES_DIR = DATA_DIR / "notes"
NOTES_FILE = NOTES_DIR / "notes.md"
GOAL = r"(?:ціл\w*|задач\w*|план\w*)"
TODAY = r"(?: на сьогодні| на день| на зараз)?"
DONE_WORDS = r"(?:все|це все|достатньо|кінець|закінчив|закінчила|готово|стоп|вистачить|більше нічого)"
ORDINAL_SPOKEN = ("Перша", "Друга", "Третя", "Четверта", "П'ята", "Шоста", "Сьома", "Восьма", "Дев'ята", "Десята")


def _goals_file(day: date | None = None):
    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    return NOTES_DIR / f"goals-{(day or date.today()):%Y-%m-%d}.md"


def load_goals() -> list[list]:
    """[[виконано, текст], ...] на сьогодні."""
    path = _goals_file()
    if not path.exists():
        return []
    goals = []
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"- \[( |x)\] (.+)", line)
        if m:
            goals.append([m.group(1) == "x", m.group(2)])
    return goals


def save_goals(goals: list[list]) -> None:
    lines = [f"# Цілі на {date.today():%d.%m.%Y}", ""]
    lines += [f"- [{'x' if done else ' '}] {text}" for done, text in goals]
    _goals_file().write_text("\n".join(lines) + "\n", encoding="utf-8")


@tool
def add_goal(text: str) -> str:
    """Додати ціль (задачу) до списку на сьогодні.

    Args:
        text: Текст цілі.
    """
    goals = load_goals()
    goals.append([False, text.strip().rstrip(".")])
    save_goals(goals)
    return "Записав."


@tool
def read_goals() -> str:
    """Список цілей на сьогодні з позначкою, що вже виконано."""
    goals = load_goals()
    if not goals:
        return "На сьогодні цілей ще немає. Скажіть «запиши цілі»."
    left = sum(not done for done, _ in goals)
    parts = []
    for i, (done, text) in enumerate(goals):
        number = ORDINAL_SPOKEN[i] if i < len(ORDINAL_SPOKEN) else f"{i + 1}-а"
        parts.append(f"{number}: {text}{' — виконано' if done else ''}")
    return f"Цілей на сьогодні: {len(goals)}, лишилось {left}. " + ". ".join(parts) + "."


@tool
def complete_goal(number: int) -> str:
    """Позначити ціль на сьогодні виконаною.

    Args:
        number: Номер цілі у списку, починаючи з 1.
    """
    goals = load_goals()
    if not 1 <= number <= len(goals):
        return f"Немає цілі номер {number}."
    goals[number - 1][0] = True
    save_goals(goals)
    left = sum(not done for done, _ in goals)
    return "Чудово, всі цілі на сьогодні виконано!" if left == 0 else f"Відмітив. Лишилось {left}."


@tool
def add_note(text: str) -> str:
    """Записати нотатку (з датою й часом) у файл нотаток.

    Args:
        text: Текст нотатки.
    """
    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    with open(NOTES_FILE, "a", encoding="utf-8") as f:
        f.write(f"- {datetime.now():%d.%m.%Y %H:%M} — {text.strip()}\n")
    return "Записав нотатку."


@tool
def read_notes(count: int = 5) -> str:
    """Прочитати останні нотатки.

    Args:
        count: Скільки останніх нотаток прочитати.
    """
    if not NOTES_FILE.exists():
        return "Нотаток ще немає."
    lines = [l[2:] for l in NOTES_FILE.read_text(encoding="utf-8").splitlines() if l.startswith("- ")]
    return "Останні нотатки: " + ". ".join(lines[-count:]) + "."


class GoalsMode:
    """Режим запису цілей: кожна фраза — нова ціль, доки не скажете "все"."""

    def __init__(self):
        self.added = 0

    def handle(self, text: str, utterance) -> None:
        if re.fullmatch(DONE_WORDS, text) or re.fullmatch(rf"{DONE_WORDS} {GOAL}?", text):
            runtime.set_mode(None)
            runtime.say(f"Записав цілей: {self.added}. Скажіть «розкажи цілі», щоб послухати.")
            return
        _, goal = split_wake_word(utterance.accurate(), runtime.settings().wake_words)
        if normalize(goal):
            add_goal(goal)
            self.added += 1
            runtime.say("Записав. Далі?")


def _raw_after(pattern: str) -> str:
    return re.sub(rf"^.*?{pattern}[\s,:]*", "", runtime.command_text(), count=1, flags=re.I).strip()


@command(rf"(?:запиши|записуй|постав|додай|склади)(?: мені)?(?: кілька| декілька| мої)? {GOAL}{TODAY}", priority=6)
def _start_goals():
    runtime.set_mode(GoalsMode())
    return "Диктуйте цілі по одній. Коли закінчите, скажіть «все»."


@command(r"(?:запиши|додай|постав) (?:ціль|задачу)(?: на сьогодні)? (?P<text>.+)", priority=7)
def _add_goal(text):
    return add_goal(_raw_after(r"(?:ціль|задачу)(?: на сьогодні)?") or text)


@command(
    rf"(?:розкажи|прочитай|назви|перелічи|нагадай|які)(?: мені)?(?: мої| в мене| у мене)? {GOAL}{TODAY}",
    r"що (?:в мене|у мене) (?:на сьогодні|в планах|запланован\w*)",
    priority=6,
)
def _read_goals():
    return read_goals()


@command(
    rf"(?:виконав|виконала|зробив|зробила|відміть|познач) (?P<n>{ORDINAL})(?: {GOAL})?(?: виконаною)?",
    rf"(?P<n>{ORDINAL}) {GOAL} (?:виконано|виконана|зроблено|готово)",
    priority=7,
)
def _complete(n):
    number = parse_ordinal(n)
    return complete_goal(number) if number else None


@command(rf"(?:очисти|видали|зітри) (?:всі |усі )?{GOAL}{TODAY}", priority=7)
def _clear_goals():
    if runtime.confirm("Видалити всі цілі на сьогодні?"):
        save_goals([])
        return "Видалив."
    return "Добре, лишаю."


@command(r"(?:запиши|запам'ятай|занотуй) (?:нотатку|замітку|що) (?P<text>.+)", r"нотатка (?P<text>.+)", priority=6)
def _note(text):
    return add_note(_raw_after(r"(?:нотатку|замітку|що|нотатка)") or text)


@command(r"(?:прочитай|розкажи|покажи) (?:мої |останні )?(?:нотатки|замітки)", priority=6)
def _read_notes():
    return read_notes()


@command(rf"{OPEN} (?:мої )?(?P<what>нотатки|замітки|{GOAL})", priority=6)
def _open_file(what):
    path = NOTES_FILE if what in ("нотатки", "замітки") else _goals_file()
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
    os.startfile(path)
    return "Відкриваю."

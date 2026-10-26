"""Реєстр навичок: локальні голосові команди та інструменти для локальної ШІ.

Кожна навичка — файл у jarvis/skills/. Він реєструє:
  @tool    — дію, яку може викликати локальна модель (Ollama);
  @command — фразу, яку Джарвіс виконує сам, без ШІ й без інтернету.
Нова навичка = новий файл у jarvis/skills/, підключається автоматично.
"""
import importlib
import inspect
import pkgutil
import re
from dataclasses import dataclass
from typing import Callable

from jarvis.core.text import correct_words, fix_layout, normalize

# Шаблони дієслів, які часто повторюються в командах.
OPEN = r"(?:відкри\w*|запуст\w*)"
CLOSE = r"(?:закри\w*)"

_JSON_TYPES = {str: "string", int: "integer", float: "number", bool: "boolean"}


class NotHandled(Exception):
    """Команда схожа на локальну, але виконати її локально не вийшло — передати її ШІ."""


@dataclass
class Command:
    patterns: list[re.Pattern]
    handler: Callable[..., str | None]
    priority: int


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict  # JSON Schema аргументів
    fn: Callable[..., str]


COMMANDS: list[Command] = []
TOOLS: dict[str, Tool] = {}


def command(*patterns: str, priority: int = 0):
    """Реєструє локальну команду. Іменовані групи з шаблону передаються в обробник як аргументи.
    Шаблон має збігатися з усією нормалізованою фразою. Вищий priority перевіряється першим."""
    def decorator(fn):
        COMMANDS.append(Command([re.compile(p) for p in patterns], fn, priority))
        COMMANDS.sort(key=lambda c: -c.priority)
        return fn
    return decorator


def tool(fn):
    """Реєструє функцію як інструмент для ШІ. Опис і аргументи беруться з docstring (розділ Args:)."""
    doc = inspect.getdoc(fn) or ""
    description, _, args_doc = doc.partition("Args:")
    arg_help = dict(re.findall(r"^\s*(\w+):\s*(.+)$", args_doc, flags=re.M))
    properties, required = {}, []
    for param in inspect.signature(fn).parameters.values():
        properties[param.name] = {
            "type": _JSON_TYPES.get(param.annotation, "string"),
            "description": arg_help.get(param.name, ""),
        }
        if param.default is inspect.Parameter.empty:
            required.append(param.name)
    schema = {"type": "object", "properties": properties, "required": required}
    TOOLS[fn.__name__] = Tool(fn.__name__, " ".join(description.split()), schema, fn)
    return fn


def match(text: str, raw: str | None = None) -> tuple[Command, dict, str] | None:
    """Шукає команду для нормалізованої фрази. Якщо точного збігу немає (або спрацювала лише загальна
    команда на кшталт "відкрий X"), пробує виправити одруківки, суржик і неправильну розкладку клавіатури
    (для розкладки потрібен raw — фраза до нормалізації, бо "," і "." там — це літери "б" і "ю").
    Повертає (команда, аргументи, фраза, яку зрештою зрозуміли)."""
    found = _match_exact(text)
    if found and found[0].priority >= _SPECIFIC:
        return *found, text
    words, stems = _vocabulary()
    candidates = [correct_words(text, words, stems)]
    raw = raw or text
    if re.search(r"[a-z]", raw.lower()) and not re.search(r"[а-яіїєґ]", raw.lower()):
        candidates.append(correct_words(normalize(fix_layout(raw)), words, stems))
    for i, fixed in enumerate(candidates):
        if fixed == text:
            continue
        better = _match_exact(fixed)
        if better and (found is None or better[0].priority > found[0].priority):
            # Назви й тексти всередині команди ("запиши нотатку купити хліб") не виправляємо —
            # лише слова самої команди.
            original = text if i == 0 else normalize(fix_layout(raw))
            kept = _keep_slots(fixed, original, better[0])
            if kept is not None:
                fixed, better = kept
            print(f"(зрозумів як: {fixed})")
            return *better, fixed
    return (*found, text) if found else None


def _keep_slots(fixed: str, original: str, cmd: Command) -> tuple[str, tuple[Command, dict]] | None:
    """Повертає в іменовані частини команди слова з оригінальної фрази, якщо команда від цього не зміниться."""
    fixed_words, original_words = fixed.split(), original.split()
    if len(fixed_words) != len(original_words):
        return None
    for pattern in cmd.patterns:
        m = pattern.fullmatch(fixed)
        if not m:
            continue
        slots = [m.span(g) for g in m.groupdict() if m.group(g) is not None]
        result, pos = [], 0
        for fw, ow in zip(fixed_words, original_words):
            start = fixed.index(fw, pos)
            pos = start + len(fw)
            result.append(ow if any(a <= start < b for a, b in slots) else fw)
        restored = " ".join(result)
        again = _match_exact(restored)
        if again and again[0] is cmd:
            return restored, again
        return None
    return None


# Команди з таким пріоритетом і вище — конкретні; нижче — загальні ("відкрий X", "закрий X", "напиши X").
_SPECIFIC = 2
_vocab_cache: tuple[int, set[str], set[str]] = (-1, set(), set())


def _match_exact(text: str) -> tuple[Command, dict] | None:
    for cmd in COMMANDS:
        for pattern in cmd.patterns:
            m = pattern.fullmatch(text)
            if m:
                return cmd, {k: v for k, v in m.groupdict().items() if v is not None}
    return None


def _vocabulary() -> tuple[set[str], set[str]]:
    """Слова з шаблонів усіх команд: цілі слова й основи (те, що стоїть перед \\w* чи [ая])."""
    global _vocab_cache
    if _vocab_cache[0] == len(COMMANDS):
        return _vocab_cache[1], _vocab_cache[2]
    words, stems = set(), set()
    for cmd in COMMANDS:
        for pattern in cmd.patterns:
            src = re.sub(r"\(\?P<\w+>", "(", pattern.pattern)
            src = re.sub(r"\\w[*+]", "\0", src)
            src = re.sub(r"\\.", " ", src)
            for word, after in re.findall(r"([^\W\d_]+(?:'[^\W\d_]+)*)([\0\[(?]?)", src):
                word = word.lower()
                if after == "?":  # "вікна?" — і "вікна", і "вікн"
                    words.add(word)
                    stems.add(word[:-1])
                else:
                    (stems if after else words).add(word)
    _vocab_cache = (len(COMMANDS), words, stems)
    return words, stems


def call_tool(name: str, args: dict) -> str:
    """Виконує інструмент за назвою і повертає текстовий результат для ШІ."""
    if name not in TOOLS:
        return f"Помилка: інструмента {name} не існує."
    t = TOOLS[name]
    known = {k: v for k, v in args.items() if k in t.parameters["properties"]}
    try:
        return t.fn(**known) or "Готово."
    except Exception as e:
        return f"Помилка: {e}"


def load_skills() -> None:
    from jarvis import skills
    for info in pkgutil.iter_modules(skills.__path__):
        if not info.name.startswith("_"):
            importlib.import_module(f"{skills.__name__}.{info.name}")

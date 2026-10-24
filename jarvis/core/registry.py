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


def match(text: str) -> tuple[Command, dict] | None:
    for cmd in COMMANDS:
        for pattern in cmd.patterns:
            m = pattern.fullmatch(text)
            if m:
                return cmd, {k: v for k, v in m.groupdict().items() if v is not None}
    return None


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

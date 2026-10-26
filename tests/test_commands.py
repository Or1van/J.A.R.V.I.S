"""Яка команда спрацює на фразу. Команди тут не виконуються — лише перевіряється вибір."""
import pytest

from jarvis.core import registry
from jarvis.core.text import normalize

registry.load_skills()


def understood(phrase: str):
    found = registry.match(normalize(phrase), phrase)
    if found is None:
        return None
    cmd, args, text = found
    return cmd.handler.__name__, args, text


@pytest.mark.parametrize("phrase, handler", [
    ("котра година", "_time"),
    ("яке сьогодні число", "_date"),
    ("що ти вмієш", "_help"),
    ("стан системи", "_status"),
    ("закрий вкладку ютуб", "_close_named_tab"),
    ("наступна вкладка", "_next_tab"),
    ("гучність на 30 відсотків", "_set_volume"),
    ("прочитай нотатки", "_read_notes"),
    ("розгорнись", "_view_full"),
    ("згорнись", "_view_mini"),
    ("звичайний режим", "_view_normal"),
])
def test_exact_commands(phrase, handler):
    assert understood(phrase)[0] == handler


@pytest.mark.parametrize("phrase, handler, fixed", [
    ("відкрй браузер", "_open_web", "відкрий браузер"),
    ("котра годна", "_time", "котра година"),
    ("яка сьгодні дата", "_date", "яка сьогодні дата"),
    ("розкажи новнии", "_news", "розкажи новини"),
    ("зроби скрінщот", "_screenshot", "зроби скріншот"),
    ("постав віддео на паузу", "_video_play_pause", "постав відео на паузу"),
    ("сделай громче", "_louder", "зроби гучніше"),
    ("сверни все", "_minimize_all", "згорни все"),
    ("открой блокнот", "_open", "відкрий блокнот"),
    ("dslrhbq ,kjryjn", "_open", "відкрий блокнот"),  # набрано в англійській розкладці
])
def test_typos_are_understood(phrase, handler, fixed):
    name, _, text = understood(phrase)
    assert (name, text) == (handler, fixed)


def test_text_inside_command_is_not_corrected():
    name, args, _ = understood("зпиши нотатку купити хліб")
    assert name == "_note"
    assert args["text"] == "купити хліб"


@pytest.mark.parametrize("phrase, name", [
    ("запусти стім", "стім"),
    ("відкрий програму телеграмм", "телеграмм"),
])
def test_app_names_are_not_corrected(phrase, name):
    handler, args, _ = understood(phrase)
    assert (handler, args["name"]) == ("_open_app", name)

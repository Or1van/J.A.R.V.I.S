"""Робота з текстом: одруківки, розкладка клавіатури, суржик."""
from jarvis.core.text import correct_words, edit_distance, fix_layout


def test_edit_distance():
    assert edit_distance("відкрий", "відкрий") == 0
    assert edit_distance("відкрй", "відкрий") == 1        # пропущена літера
    assert edit_distance("новнии", "новини") == 1         # переставлені літери
    assert edit_distance("блокнот", "калькулятор", limit=2) == 3  # далеко — далі не рахує


def test_fix_layout():
    assert fix_layout("dslrhbq ,kjryjn") == "відкрий блокнот"


def test_correct_words():
    words, stems = {"браузер", "година", "котра"}, {"відкри"}
    assert correct_words("відкрй браузер", words, stems) == "відкрий браузер"
    assert correct_words("котра годна", words, stems) == "котра година"
    assert correct_words("открой браузер", words, stems) == "відкрий браузер"  # суржик


def test_correct_words_keeps_unknown_and_short_words():
    words, stems = {"година"}, set()
    assert correct_words("ютуб", words, stems) == "ютуб"
    assert correct_words("рік", words, stems) == "рік"

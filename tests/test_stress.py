import json
from pathlib import Path

import pytest

from poetryforge.phonetics.stress import StressAnalyzer, _USER_DICT_PATH


@pytest.fixture
def sa():
    return StressAnalyzer()


@pytest.fixture
def clean_user_dict():
    """Сохранить и восстановить user_dict после теста."""
    backup = _USER_DICT_PATH.read_text(encoding="utf-8") if _USER_DICT_PATH.exists() else "{}"
    yield
    _USER_DICT_PATH.write_text(backup, encoding="utf-8")


def test_single_syllable_content_word(sa):
    """Односложное знаменательное слово — ударение на 0."""
    assert sa.get_stress("мой") == 0
    assert sa.get_stress("день") == 0


def test_single_syllable_function_word(sa):
    """Односложные служебные слова — безударные."""
    assert sa.get_stress("не") is None
    assert sa.get_stress("и") is None
    assert sa.get_stress("в") is None


def test_no_vowels(sa):
    assert sa.get_stress("в") is None


def test_yo_always_stressed(sa):
    """Буква ё — всегда ударная."""
    assert sa.get_stress("ёж") == 0
    assert sa.get_stress("ёлка") == 0


def test_dyadya(sa):
    """Слово «дядя» — ударение на первый слог."""
    assert sa.get_stress("дядя") == 0


def test_moloko(sa):
    """Слово «молоко» — ударение на последний слог."""
    assert sa.get_stress("молоко") == 2


def test_analyze_line(sa):
    """Анализ строки Пушкина."""
    result = sa.analyze("Мой дядя самых честных правил")
    words = [r["word"] for r in result]
    assert words == ["Мой", "дядя", "самых", "честных", "правил"]
    # Все слова имеют ударения (нет служебных безударных)
    for r in result:
        assert r["stress_pos"] is not None


def test_stress_pattern(sa):
    """Бинарная схема ударений."""
    pattern = sa.stress_pattern("Мой дядя самых честных правил")
    # Каждая 1 — ударный слог, 0 — безударный
    assert len(pattern) == 9  # 1+2+2+2+2 = 9 слогов
    assert all(ch in "01" for ch in pattern)


def test_user_dict_priority(sa, clean_user_dict):
    """Пользовательский словарь имеет приоритет."""
    # «замок» — ruaccent даст какое-то ударение
    original = sa.get_stress("замок")
    # Переопределим на 1 (замо́к)
    sa.add_to_user_dict("замок", 1)
    assert sa.get_stress("замок") == 1
    # Удалим — вернётся к ruaccent
    sa.remove_from_user_dict("замок")
    assert sa.get_stress("замок") == original


def test_analyze_with_punctuation(sa):
    """Строка с пунктуацией — знаки препинания не мешают."""
    result = sa.analyze("Скажи-ка, дядя, ведь недаром")
    words = [r["word"] for r in result]
    assert "Скажи" in words or "ка" in words  # дефис разделяет
    assert "дядя" in words


# --- Словарный lookup (dict layer) ---


def test_dict_layer_unambiguous(sa):
    """Однозначные слова разрешаются через dict без нейросети."""
    # молоко — в словаре, не омограф
    assert sa.get_stress("молоко") == 2


def test_dict_layer_omograph_falls_through(sa):
    """Омографы обходят dict layer."""
    # замок — в omographs, должен вернуть валидный результат
    pos = sa.get_stress("замок")
    assert pos in (0, 1)


def test_dict_layer_coverage(sa):
    """Dict layer покрывает большинство обычных слов."""
    # Все эти слова должны быть в словаре
    words_expected = {
        "любовь": 1,   # любо́вь
        "правил": 0,   # пра́вил
        "дядя": 0,     # дя́дя
    }
    for word, expected in words_expected.items():
        assert sa.get_stress(word) == expected, f"{word}: expected {expected}"


def test_dict_single_variant_for_non_omograph(sa):
    """Неомограф через get_stress_variants → единственный вариант."""
    variants = sa.get_stress_variants("молоко")
    assert variants == [2]

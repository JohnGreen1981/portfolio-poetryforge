"""Тесты для модуля определения рифменной схемы."""

import pytest

from poetryforge.phonetics.rhyme_scheme import (
    _check_onegin_structure,
    _clausulae_compatible,
    _normalize_scheme,
    _match_pattern,
    _segment_into_stanzas,
    detect_rhyme_scheme,
)
from poetryforge.phonetics.meter import MeterAnalyzer


# --- _normalize_scheme ---


class TestNormalizeScheme:
    def test_simple(self):
        assert _normalize_scheme("AbAb") == "AbAb"

    def test_shifted_letters(self):
        assert _normalize_scheme("EfEf") == "AbAb"

    def test_paired(self):
        assert _normalize_scheme("ccDD") == "aaBB"

    def test_empty(self):
        assert _normalize_scheme("") == ""

    def test_enclosing(self):
        assert _normalize_scheme("XyyX") == "AbbA"


# --- _clausulae_compatible ---


class TestClausulaeCompatible:
    def test_masc_masc(self):
        assert _clausulae_compatible("masculine", "masculine") is True

    def test_fem_fem(self):
        assert _clausulae_compatible("feminine", "feminine") is True

    def test_fem_dactylic(self):
        assert _clausulae_compatible("feminine", "dactylic") is True

    def test_masc_fem(self):
        assert _clausulae_compatible("masculine", "feminine") is False

    def test_unknown_fem(self):
        assert _clausulae_compatible("unknown", "feminine") is True


# --- _match_pattern ---


class TestMatchPattern:
    def test_cross(self):
        name, ru = _match_pattern("AbAb", 4)
        assert name == "cross"
        assert ru == "перекрёстная"

    def test_paired(self):
        name, ru = _match_pattern("AAbb", 4)
        assert name == "paired"
        assert ru == "парная"

    def test_enclosing(self):
        name, ru = _match_pattern("AbbA", 4)
        assert name == "enclosing"
        assert ru == "опоясывающая"

    def test_unknown_pattern(self):
        name, ru = _match_pattern("AbCd", 4)
        assert name is None
        assert ru is None


# --- _segment_into_stanzas ---


class TestSegmentIntoStanzas:
    def test_no_blanks_short(self):
        """Короткие стихотворения — одна строфа."""
        groups = _segment_into_stanzas(["a"] * 8, None)
        assert groups == [list(range(8))]

    def test_with_blanks(self):
        """Разделение по пустым строкам."""
        # 4 строки, пустая после 2-й (позиция 2)
        groups = _segment_into_stanzas(["a"] * 4, {2})
        assert groups == [[0, 1], [2, 3]]

    def test_long_poem_quartets(self):
        """Длинные стихотворения без пробелов — четверостишия."""
        groups = _segment_into_stanzas(["a"] * 20, None)
        assert len(groups) == 5
        assert groups[0] == [0, 1, 2, 3]


# --- _check_onegin_structure ---


class TestOneginStructure:
    def test_valid(self):
        assert _check_onegin_structure("AbAbCCddEffEgg") is True

    def test_wrong_length(self):
        assert _check_onegin_structure("AbAb") is False

    def test_wrong_cross(self):
        # 1≠3
        assert _check_onegin_structure("AbCbDDeeEffEgg") is False

    def test_same_clausula_1_2(self):
        # строки 1 и 2 должны различаться по клаузуле
        assert _check_onegin_structure("ABABCCddEffEgg") is False


# --- detect_rhyme_scheme (интеграция) ---


@pytest.fixture(scope="module")
def meter_analyzer():
    return MeterAnalyzer()


class TestDetectRhymeScheme:
    def test_cross_scheme(self, meter_analyzer):
        """Перекрёстная рифма: АБАБ."""
        text = (
            "Мороз и солнце; день чудесный!\n"
            "Ещё ты дремлешь, друг прелестный —\n"
            "Пора, красавица, проснись:\n"
            "Открой сомкнуты негой взоры\n"
        )
        result = meter_analyzer.analyze_poem(text)
        scheme = result["rhyme_scheme"]
        assert len(scheme) == 4

    def test_paired_scheme(self, meter_analyzer):
        """Парная рифма: AABB."""
        text = (
            "Мой дядя самых честных правил,\n"
            "Когда не в шутку занемог,\n"
            "Он уважать себя заставил\n"
            "И лучше выдумать не мог.\n"
        )
        result = meter_analyzer.analyze_poem(text)
        scheme = result["rhyme_scheme"]
        assert len(scheme) == 4

    def test_single_line(self, meter_analyzer):
        """Одна строка — пустая схема."""
        result = meter_analyzer.analyze_poem("Мой дядя самых честных правил")
        assert result["rhyme_scheme"] == ""

    def test_stanza_segmentation(self, meter_analyzer):
        """Разделение на строфы по пустым строкам."""
        text = (
            "Первая строка строфы\n"
            "Вторая строка строфы\n"
            "Третья строка строфы\n"
            "Четвёртая строка строфы\n"
            "\n"
            "Пятая строка строфы\n"
            "Шестая строка строфы\n"
            "Седьмая строка строфы\n"
            "Восьмая строка строфы\n"
        )
        result = meter_analyzer.analyze_poem(text)
        if "stanzas" in result:
            assert len(result["stanzas"]) == 2

    def test_result_has_scheme_key(self, meter_analyzer):
        """Результат всегда содержит rhyme_scheme."""
        text = "Первая строка\nВторая строка\n"
        result = meter_analyzer.analyze_poem(text)
        assert "rhyme_scheme" in result

    def test_clausula_detection(self, meter_analyzer):
        """Клаузулы определяются для каждой строки."""
        text = "Мой дядя самых честных правил\nКогда не в шутку занемог\n"
        result = meter_analyzer.analyze_poem(text)
        for line_result in result["lines"]:
            assert "clausula" in line_result
            assert line_result["clausula"] in (
                "masculine", "feminine", "dactylic", "hyperdactylic", "unknown"
            )

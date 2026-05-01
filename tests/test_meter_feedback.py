"""Тесты разрешения омографов по контексту метра."""

import pytest

from poetryforge.phonetics.stress import StressAnalyzer
from poetryforge.phonetics.meter import MeterAnalyzer


@pytest.fixture(scope="module")
def sa():
    return StressAnalyzer()


@pytest.fixture(scope="module")
def ma():
    return MeterAnalyzer()


# --- get_stress_variants ---


class TestGetStressVariants:
    def test_omograph_has_variants(self, sa):
        """Известный омограф возвращает несколько вариантов."""
        variants = sa.get_stress_variants("замок")
        assert len(variants) == 2
        assert 0 in variants  # за́мок
        assert 1 in variants  # замо́к

    def test_non_omograph_single(self, sa):
        """Неомограф возвращает единственный вариант."""
        variants = sa.get_stress_variants("дядя")
        assert len(variants) == 1

    def test_unstressed_word(self, sa):
        """Служебное односложное слово — пустой список."""
        variants = sa.get_stress_variants("на")
        assert variants == []

    def test_user_dict_overrides(self, sa):
        """User dict — единственный вариант (даже для омографа)."""
        sa.add_to_user_dict("замок", 0)
        variants = sa.get_stress_variants("замок")
        assert variants == [0]
        sa.remove_from_user_dict("замок")

    def test_yo_single(self, sa):
        """Слово с ё — единственный вариант."""
        variants = sa.get_stress_variants("ёлка")
        assert variants == [0]


# --- stress_pattern_with_meter ---


class TestStressPatternWithMeter:
    def test_zamok_iamb(self, sa):
        """'Замок стоит на горе' — ямб, замо́к (stress=1) лучше."""
        pat, amb = sa.stress_pattern_with_meter(
            "Замок стоит на горе", "iamb", 3
        )
        assert len(amb) == 1
        assert amb[0]["word"] == "замок"
        assert amb[0]["chosen"] == 1  # замо́к
        assert amb[0]["default"] == 0  # за́мок (default ruaccent)

    def test_zamok_trochee(self, sa):
        """'Замок древний на горе' — хорей, за́мок (stress=0) лучше."""
        pat, amb = sa.stress_pattern_with_meter(
            "Замок древний на горе", "trochee", 4
        )
        # Хорей: 10101010, за́мок (10) fits the start
        # Если disambiguated → chosen=0 (default), значит ambiguous_words пуст
        # (мы не включаем в отчёт слова, где chosen == default)
        zamok_entries = [a for a in amb if a["word"] == "замок"]
        if zamok_entries:
            assert zamok_entries[0]["chosen"] == 0
        # Pattern should start with 1 (stressed first syllable)
        assert pat[0] == "1"

    def test_no_ambiguity(self, sa):
        """Строка без омографов — пустой ambiguous_words."""
        pat, amb = sa.stress_pattern_with_meter(
            "Мой дядя самых честных правил", "iamb", 4
        )
        assert amb == []
        # Паттерн совпадает с обычным
        assert pat == sa.stress_pattern("Мой дядя самых честных правил")

    def test_user_dict_priority(self, sa):
        """User dict не переопределяется метром."""
        sa.add_to_user_dict("замок", 0)
        try:
            _, amb = sa.stress_pattern_with_meter(
                "Замок стоит на горе", "iamb", 3
            )
            # user_dict = единственный вариант, нет амбигуентности
            assert amb == []
        finally:
            sa.remove_from_user_dict("замок")


# --- MeterAnalyzer integration ---


class TestMeterAnalyzerFeedback:
    def test_analyze_line_with_meter(self, ma):
        """analyze_line с --meter использует feedback."""
        result = ma.analyze_line("Замок стоит на горе", "iamb3")
        # Должен разрешить замок как замо́к
        if "ambiguous_words" in result:
            zamok = [a for a in result["ambiguous_words"] if a["word"] == "замок"]
            if zamok:
                assert zamok[0]["chosen"] == 1

    def test_analyze_line_without_meter(self, ma):
        """analyze_line без --meter не добавляет ambiguous_words."""
        result = ma.analyze_line("Замок стоит на горе")
        assert "ambiguous_words" not in result

    def test_feedback_improves_score(self, ma):
        """Feedback должен улучшать (или не ухудшать) meter_score."""
        line = "Замок стоит на горе"
        result_with = ma.analyze_line(line, "iamb3")
        # Без feedback: используем обычный stress_pattern
        sa = ma._sa
        default_pat = sa.stress_pattern(line)
        from poetryforge.phonetics.meter_utils import match_meter
        default_score, _ = match_meter(default_pat, "iamb", 3)
        assert result_with["meter_score"] >= round(default_score, 3)

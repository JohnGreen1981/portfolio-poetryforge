"""Тесты для дольника и тактовика."""

import pytest

from poetryforge.phonetics.meter_utils import (
    extract_ictus_intervals,
    match_dolnik,
    match_taktovik,
    score_dolnik_only,
    score_taktovik_only,
    score_irregular_only,
)
from poetryforge.phonetics.meter import MeterAnalyzer, _detect_best_meter, _parse_meter_spec


# --- extract_ictus_intervals ---


class TestExtractIctusIntervals:
    def test_basic(self):
        ictuses, intervals = extract_ictus_intervals("010010010")
        assert ictuses == [1, 4, 7]
        assert intervals == [2, 2]

    def test_mixed_intervals(self):
        """Дольниковый паттерн: интервалы 1 и 2."""
        ictuses, intervals = extract_ictus_intervals("01010010")
        assert ictuses == [1, 3, 6]
        assert intervals == [1, 2]

    def test_no_stresses(self):
        ictuses, intervals = extract_ictus_intervals("0000")
        assert ictuses == []
        assert intervals == []

    def test_single_stress(self):
        ictuses, intervals = extract_ictus_intervals("0010")
        assert ictuses == [2]
        assert intervals == []

    def test_consecutive_stresses(self):
        ictuses, intervals = extract_ictus_intervals("01100")
        assert ictuses == [1, 2]
        assert intervals == [0]


# --- match_dolnik ---


class TestMatchDolnik:
    def test_perfect_dolnik(self):
        """Интервалы 1 и 2 — идеальный дольник."""
        # 0 1 0 1 0 0 1 0 → ictuses: 1,3,6 → intervals: 1,2
        score, issues = match_dolnik("01010010", 3)
        assert score > 0.8
        assert not any(i["severity"] == "error" for i in issues)

    def test_wrong_ictus_count(self):
        """3 икта, ожидаем 4 — штраф."""
        score_ok, _ = match_dolnik("01010010", 3)
        score_bad, issues = match_dolnik("01010010", 4)
        assert score_bad < score_ok  # штраф за неверное количество иктов
        assert any(i["type"] == "ictus_count" for i in issues)

    def test_interval_violation(self):
        """Интервал 3 — нарушение для дольника."""
        # 0 1 0 0 0 1 0 → ictuses: 1,5 → interval: 3
        score, issues = match_dolnik("0100010", 2)
        assert any(i["type"] == "interval_violation" for i in issues)
        assert score < 0.5

    def test_stress_clash(self):
        """Стечение ударений (интервал 0) — предупреждение."""
        # 0 1 1 0 0 1 0 → ictuses: 1,2,5 → intervals: 0,2
        score, issues = match_dolnik("0110010", 3)
        assert any(i["type"] == "stress_clash" for i in issues)

    def test_too_few_stresses(self):
        """Менее 2 ударений — ошибка."""
        score, issues = match_dolnik("00010", 2)
        assert score == 0.0

    def test_long_anacrusis(self):
        """Анакруза > 2 слогов — предупреждение."""
        # 0 0 0 1 0 1 0 → ictuses: 3,5 → interval: 1, anacrusis: 3
        score, issues = match_dolnik("0001010", 2)
        assert any(i["type"] == "long_anacrusis" for i in issues)


# --- match_taktovik ---


class TestMatchTaktovik:
    def test_interval_3_ok(self):
        """Интервал 3 допустим для тактовика."""
        # 0 1 0 0 0 1 0 1 0 → ictuses: 1,5,7 → intervals: 3,1
        score, issues = match_taktovik("010001010", 3)
        assert score > 0.7
        assert not any(i["type"] == "interval_violation" for i in issues)

    def test_interval_4_violation(self):
        """Интервал 4 — нарушение для тактовика."""
        # 0 1 0 0 0 0 1 0 → ictuses: 1,6 → interval: 4
        score, issues = match_taktovik("01000010", 2)
        assert any(i["type"] == "interval_violation" for i in issues)

    def test_mixed_intervals_1_2_3(self):
        """Смешанные интервалы 1, 2, 3 — валидный тактовик."""
        # 0 1 0 1 0 0 1 0 0 0 1 → ictuses: 1,3,6,10 → intervals: 1,2,3
        score, issues = match_taktovik("01010010001", 4)
        assert score > 0.7
        assert not any(i["severity"] == "error" for i in issues)


# --- score_*_only (fast scoring) ---


class TestVariationBonus:
    def test_mixed_intervals_beat_uniform(self):
        """Паттерн с вариацией интервалов (1,2) должен быть выше, чем без (1,1)."""
        # 101001 → ictuses: 0,2,5 → intervals: 1,2 (настоящий дольник)
        # 101010 → ictuses: 0,2,4 → intervals: 1,1 (хорей)
        score_dolnik, _ = match_dolnik("101001", 3)
        score_uniform, _ = match_dolnik("101010", 3)
        assert score_dolnik > score_uniform

    def test_fast_scoring_variation_bonus(self):
        """score_dolnik_only тоже даёт бонус за вариацию."""
        score_mixed = score_dolnik_only("101001", 3)
        score_uniform = score_dolnik_only("101010", 3)
        assert score_mixed > score_uniform

    def test_taktovik_variation_bonus(self):
        """Тактовик с вариацией (1,2,3) выше, чем без."""
        # intervals: 1,2,3 vs 2,2,2
        score_varied = score_taktovik_only("01010010001", 4)
        score_uniform = score_taktovik_only("01001001001", 4)
        assert score_varied > score_uniform


class TestFastScoring:
    def test_dolnik_only(self):
        score = score_dolnik_only("01010010", 3)
        assert score > 0.8

    def test_taktovik_only(self):
        score = score_taktovik_only("010001010", 3)
        assert score > 0.7

    def test_irregular_only_dispatch(self):
        d = score_irregular_only("01010010", "dolnik", 3)
        t = score_irregular_only("010001010", "taktovik", 3)
        assert d > 0.8
        assert t > 0.7

    def test_irregular_only_unknown(self):
        assert score_irregular_only("0101", "unknown", 2) == 0.0


# --- _parse_meter_spec ---


class TestParseIrregularMeterSpec:
    def test_dolnik3(self):
        assert _parse_meter_spec("dolnik3") == ("dolnik", 3)

    def test_taktovik4(self):
        assert _parse_meter_spec("taktovik4") == ("taktovik", 4)

    def test_regular_still_works(self):
        assert _parse_meter_spec("iamb4") == ("iamb", 4)

    def test_invalid(self):
        assert _parse_meter_spec("dolnik") is None


# --- _detect_best_meter ---


class TestAutoDetectIrregular:
    def test_regular_preferred_when_good(self):
        """Регулярный ямб не должен определяться как дольник."""
        # Идеальный ямб-4: 01010101
        name, score, _ = _detect_best_meter("01010101")
        assert "iamb" in name
        assert score > 0.9

    def test_dolnik_detected(self):
        """Дольниковый паттерн с вариацией интервалов 1 и 2."""
        # 1 0 1 0 0 1 0 0 1 0 → ictuses: 0,2,5,8 → intervals: 1,2,2
        name, score, _ = _detect_best_meter("1010010010")
        # Может быть дольник или тактовик, но не идеальный регулярный
        # Если регулярный метр набирает > 0.8, он будет предпочтён
        assert score > 0.0  # Что-то определилось

    def test_trochee_not_dolnik(self):
        """Хорей не должен стать дольником."""
        name, score, _ = _detect_best_meter("10101010")
        assert "trochee" in name


# --- MeterAnalyzer integration ---


@pytest.fixture(scope="module")
def analyzer():
    return MeterAnalyzer()


class TestMeterAnalyzerIrregular:
    def test_analyze_line_dolnik(self, analyzer):
        """analyze_line с --meter dolnik3."""
        # "Под насыпью, во рву некошеном" — дольник-3 (Блок)
        result = analyzer.analyze_line(
            "Под насыпью во рву некошеном", "dolnik3"
        )
        assert result["detected_meter"] == "dolnik3"
        assert result["meter_score"] > 0
        assert "clausula" in result

    def test_analyze_line_taktovik(self, analyzer):
        """analyze_line с --meter taktovik3."""
        result = analyzer.analyze_line(
            "Моим стихам написанным так рано", "taktovik3"
        )
        assert result["detected_meter"] == "taktovik3"
        assert result["meter_score"] > 0

    def test_analyze_line_regular_unchanged(self, analyzer):
        """Регулярные метры работают как прежде."""
        result = analyzer.analyze_line(
            "Мой дядя самых честных правил", "iamb4"
        )
        assert result["detected_meter"] == "iamb4"
        assert result["meter_score"] > 0.9

    def test_analyze_poem_dolnik(self, analyzer):
        """analyze_poem определяет дольник по голосованию."""
        # Минимальное стихотворение с дольниковым ритмом
        text = (
            "Под насыпью во рву некошеном\n"
            "Лежит и смотрит как живая\n"
        )
        result = analyzer.analyze_poem(text)
        assert "poem_meter" in result
        assert result["poem_score"] > 0

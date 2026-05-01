"""Модуль анализа стихотворного метра.

Определяет метр строки/стихотворения, находит сбои, оценивает качество.
Поддерживает: ямб, хорей, дактиль, амфибрахий, анапест, дольник, тактовик.
"""

from __future__ import annotations

from poetryforge.phonetics.meter_utils import (
    METER_PATTERNS,
    IRREGULAR_METERS,
    generate_ideal_pattern as _generate_ideal_pattern,
    match_meter as _match_meter,
    match_dolnik as _match_dolnik,
    match_taktovik as _match_taktovik,
    extract_ictus_intervals as _extract_ictus_intervals,
)
from poetryforge.phonetics.stress import StressAnalyzer
from poetryforge.phonetics.rhyme_scheme import detect_rhyme_scheme
from poetryforge.rhyme.phonetic_rhyme import RhymeAnalyzer


def _detect_clausula(stress_pattern: str) -> str:
    """Определить тип клаузулы по последним слогам."""
    if not stress_pattern:
        return "unknown"
    # Находим последний ударный слог
    last_stress = stress_pattern.rfind("1")
    if last_stress == -1:
        return "unknown"
    trailing = len(stress_pattern) - last_stress - 1
    if trailing == 0:
        return "masculine"
    elif trailing == 1:
        return "feminine"
    elif trailing == 2:
        return "dactylic"
    else:
        return "hyperdactylic"


def _detect_best_meter(
    stress_pattern: str,
) -> tuple[str, float, list[dict]]:
    """Перебрать все метры и размеры, найти лучшее совпадение."""
    n = len(stress_pattern)
    if n == 0:
        return "unknown", 0.0, []

    best_meter_name = "unknown"
    best_score = 0.0
    best_issues: list[dict] = []

    # 1. Регулярные метры
    for meter, foot in METER_PATTERNS.items():
        foot_len = len(foot)
        # Возможные размеры: от 2 до max стоп
        min_feet = max(2, (n - 2) // foot_len)
        max_feet = (n + foot_len - 1) // foot_len + 1

        for feet in range(min_feet, max_feet + 1):
            expected_min = feet * foot_len - 2  # с учётом клаузулы
            expected_max = feet * foot_len + 2
            if not (expected_min <= n <= expected_max):
                continue

            score, issues = _match_meter(stress_pattern, meter, feet)
            if score > best_score:
                best_score = score
                best_meter_name = f"{meter}{feet}"
                best_issues = issues

    # 2. Нерегулярные метры — только если регулярные плохо подходят
    if best_score < 0.8:
        ictuses, intervals = _extract_ictus_intervals(stress_pattern)
        n_ict = len(ictuses)

        if n_ict >= 2:
            # Требуем вариацию интервалов (иначе это регулярный метр)
            has_variation = len(set(intervals)) > 1

            if has_variation:
                # Дольник
                dk_score, dk_issues = _match_dolnik(stress_pattern, n_ict)
                if dk_score > best_score:
                    best_score = dk_score
                    best_meter_name = f"dolnik{n_ict}"
                    best_issues = dk_issues

                # Тактовик — ещё более свободный
                if best_score < 0.7:
                    tk_score, tk_issues = _match_taktovik(stress_pattern, n_ict)
                    if tk_score > best_score:
                        best_score = tk_score
                        best_meter_name = f"taktovik{n_ict}"
                        best_issues = tk_issues

    return best_meter_name, best_score, best_issues


def _parse_meter_spec(meter_spec: str) -> tuple[str, int] | None:
    """Разобрать спецификацию метра типа 'iamb4' -> ('iamb', 4).

    Для нерегулярных метров: 'dolnik3' -> ('dolnik', 3), где число — иктов.
    """
    all_names = list(METER_PATTERNS.keys()) + sorted(IRREGULAR_METERS, key=len, reverse=True)
    for name in sorted(all_names, key=len, reverse=True):
        if meter_spec.startswith(name):
            rest = meter_spec[len(name):]
            if rest.isdigit():
                return name, int(rest)
    return None


class MeterAnalyzer:
    """Анализатор стихотворного метра."""

    def __init__(self, stress_analyzer: StressAnalyzer | None = None):
        self._sa = stress_analyzer or StressAnalyzer()
        self._ra = RhymeAnalyzer(self._sa)

    def analyze_line(self, line: str, expected_meter: str | None = None) -> dict:
        """Проанализировать одну стихотворную строку.

        Args:
            line: стихотворная строка
            expected_meter: ожидаемый метр (например, 'iamb4')

        Returns:
            dict с анализом строки
        """
        ambiguous_words = []

        if expected_meter:
            parsed = _parse_meter_spec(expected_meter)
            if parsed:
                meter_name, count = parsed

                # Meter-aware stress: разрешение омографов по метру
                stress_pat, ambiguous_words = self._sa.stress_pattern_with_meter(
                    line, meter_name, count
                )
                syllable_count = len(stress_pat)
                clausula = _detect_clausula(stress_pat)

                if meter_name in IRREGULAR_METERS:
                    # Нерегулярный метр: дольник или тактовик
                    if meter_name == "dolnik":
                        score, issues = _match_dolnik(stress_pat, count)
                    else:
                        score, issues = _match_taktovik(stress_pat, count)
                    detected = expected_meter
                else:
                    # Регулярный метр
                    score, issues = _match_meter(stress_pat, meter_name, count)
                    detected = expected_meter

                    # Проверка количества слогов (только для регулярных)
                    foot_len = len(METER_PATTERNS[meter_name])
                    expected_min = count * foot_len - 2
                    expected_max = count * foot_len + 2
                    if not (expected_min <= syllable_count <= expected_max):
                        issues.insert(0, {
                            "position": -1,
                            "type": "syllable_count",
                            "severity": "error",
                            "description": (
                                f"Неверное количество слогов: {syllable_count}, "
                                f"ожидается {count * foot_len}±2 для {expected_meter}"
                            ),
                        })
            else:
                stress_pat = self._sa.stress_pattern(line)
                syllable_count = len(stress_pat)
                clausula = _detect_clausula(stress_pat)
                detected, score, issues = _detect_best_meter(stress_pat)
        else:
            stress_pat = self._sa.stress_pattern(line)
            syllable_count = len(stress_pat)
            clausula = _detect_clausula(stress_pat)
            detected, score, issues = _detect_best_meter(stress_pat)

        result = {
            "line": line,
            "syllable_count": syllable_count,
            "stress_pattern": stress_pat,
            "detected_meter": detected,
            "meter_score": round(score, 3),
            "clausula": clausula,
            "issues": issues,
        }

        if ambiguous_words:
            result["ambiguous_words"] = ambiguous_words

        return result

    def analyze_poem(self, text: str, expected_meter: str | None = None) -> dict:
        """Проанализировать стихотворение целиком.

        Args:
            text: текст стихотворения (строки через \\n)
            expected_meter: ожидаемый метр

        Returns:
            dict с анализом каждой строки и общей оценкой
        """
        # Сохраняем позиции пустых строк для сегментации строф
        raw_lines = text.strip().split("\n")
        lines = []
        blank_positions: set[int] = set()
        pos = 0
        for raw_line in raw_lines:
            stripped = raw_line.strip()
            if stripped:
                lines.append(stripped)
                pos += 1
            else:
                blank_positions.add(pos)

        line_results = []
        total_score = 0.0

        for line in lines:
            result = self.analyze_line(line, expected_meter)
            line_results.append(result)
            total_score += result["meter_score"]

        avg_score = total_score / len(line_results) if line_results else 0.0

        # Определить общий метр стихотворения (голосование)
        meter_votes: dict[str, int] = {}
        for r in line_results:
            m = r["detected_meter"]
            meter_votes[m] = meter_votes.get(m, 0) + 1
        poem_meter = max(meter_votes, key=meter_votes.get) if meter_votes else "unknown"

        # Определить рифменную схему
        scheme_result = detect_rhyme_scheme(
            lines=lines,
            line_results=line_results,
            rhyme_analyzer=self._ra,
            blank_positions=blank_positions if blank_positions else None,
        )

        result = {
            "lines": line_results,
            "poem_meter": poem_meter,
            "poem_score": round(avg_score, 3),
            "rhyme_scheme": scheme_result["scheme"],
        }

        if scheme_result["stanza_pattern"]:
            result["stanza_pattern"] = scheme_result["stanza_pattern"]
            result["stanza_type"] = scheme_result["stanza_type"]
        if scheme_result["stanzas"]:
            result["stanzas"] = scheme_result["stanzas"]

        return result

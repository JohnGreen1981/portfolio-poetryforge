"""Утилиты для работы с метром (без зависимостей от stress/meter).

Вынесены отдельно для использования из stress.py без циклического импорта.
"""

from __future__ import annotations

# Эталонные паттерны стоп (регулярные метры)
METER_PATTERNS = {
    "iamb": "01",
    "trochee": "10",
    "dactyl": "100",
    "amphibrach": "010",
    "anapest": "001",
}

# Нерегулярные метры (дольник, тактовик)
IRREGULAR_METERS = {"dolnik", "taktovik"}

# Допустимые межиктовые интервалы (кол-во безударных слогов между иктами)
_DOLNIK_INTERVALS = {1, 2}
_TAKTOVIK_INTERVALS = {1, 2, 3}


def generate_ideal_pattern(meter: str, foot_count: int, total_syllables: int) -> str:
    """Сгенерировать идеальный паттерн для заданного метра и размера."""
    foot = METER_PATTERNS[meter]
    pattern = (foot * foot_count)[:total_syllables]
    while len(pattern) < total_syllables:
        pattern += "0"
    return pattern


def match_meter(
    stress_pattern: str, meter: str, foot_count: int
) -> tuple[float, list[dict]]:
    """Оценить соответствие stress_pattern заданному метру.

    Returns:
        (score, issues): score 0..1, список проблем
    """
    n = len(stress_pattern)
    ideal = generate_ideal_pattern(meter, foot_count, n)
    issues = []
    matches = 0

    for i in range(n):
        actual = stress_pattern[i]
        expected = ideal[i]

        if actual == expected:
            matches += 1
        elif expected == "1" and actual == "0":
            matches += 0.5
            issues.append({
                "position": i,
                "type": "pyrrhic",
                "severity": "warning",
                "description": f"Пиррихий: безударный слог на сильной позиции {i + 1}",
            })
        elif expected == "0" and actual == "1":
            if meter == "iamb" and i == 0:
                matches += 0.8
                issues.append({
                    "position": i,
                    "type": "spondee",
                    "severity": "info",
                    "description": "Сверхсхемное ударение на 1-м слоге (допустимо в ямбе)",
                })
            else:
                matches += 0.3
                issues.append({
                    "position": i,
                    "type": "extra_stress",
                    "severity": "warning",
                    "description": f"Сверхсхемное ударение на позиции {i + 1}",
                })

    score = matches / n if n > 0 else 0.0
    return score, issues


def score_meter_only(stress_pattern: str, meter: str, foot_count: int) -> float:
    """Быстрый скоринг без генерации issues (для перебора вариантов)."""
    n = len(stress_pattern)
    ideal = generate_ideal_pattern(meter, foot_count, n)
    matches = 0.0

    for i in range(n):
        actual = stress_pattern[i]
        expected = ideal[i]

        if actual == expected:
            matches += 1
        elif expected == "1" and actual == "0":
            matches += 0.5
        elif expected == "0" and actual == "1":
            if meter == "iamb" and i == 0:
                matches += 0.8
            else:
                matches += 0.3

    return matches / n if n > 0 else 0.0


# ---------------------------------------------------------------------------
# Нерегулярные метры: дольник и тактовик
# ---------------------------------------------------------------------------


def extract_ictus_intervals(
    stress_pattern: str,
) -> tuple[list[int], list[int]]:
    """Извлечь позиции иктов и межиктовые интервалы.

    Returns:
        (ictus_positions, intervals):
            ictus_positions — позиции '1' в паттерне
            intervals — кол-во безударных слогов между соседними иктами
    """
    ictuses = [i for i, ch in enumerate(stress_pattern) if ch == "1"]
    intervals = [ictuses[i + 1] - ictuses[i] - 1 for i in range(len(ictuses) - 1)]
    return ictuses, intervals


def match_dolnik(
    stress_pattern: str, n_ictuses: int,
) -> tuple[float, list[dict]]:
    """Оценить соответствие stress_pattern дольнику с n_ictuses иктами.

    Дольник: межиктовые интервалы 1 или 2 слога, с вариацией.

    Returns:
        (score, issues)
    """
    return _match_irregular(stress_pattern, n_ictuses, _DOLNIK_INTERVALS, "дольник")


def match_taktovik(
    stress_pattern: str, n_ictuses: int,
) -> tuple[float, list[dict]]:
    """Оценить соответствие stress_pattern тактовику с n_ictuses иктами.

    Тактовик: межиктовые интервалы 1, 2 или 3 слога.

    Returns:
        (score, issues)
    """
    return _match_irregular(stress_pattern, n_ictuses, _TAKTOVIK_INTERVALS, "тактовик")


def score_dolnik_only(stress_pattern: str, n_ictuses: int) -> float:
    """Быстрый скоринг дольника (для перебора вариантов омографов)."""
    return _score_irregular_only(stress_pattern, n_ictuses, _DOLNIK_INTERVALS)


def score_taktovik_only(stress_pattern: str, n_ictuses: int) -> float:
    """Быстрый скоринг тактовика (для перебора вариантов омографов)."""
    return _score_irregular_only(stress_pattern, n_ictuses, _TAKTOVIK_INTERVALS)


def score_irregular_only(
    stress_pattern: str, meter: str, ictus_count: int,
) -> float:
    """Диспетчер быстрого скоринга для нерегулярных метров."""
    if meter == "dolnik":
        return score_dolnik_only(stress_pattern, ictus_count)
    if meter == "taktovik":
        return score_taktovik_only(stress_pattern, ictus_count)
    return 0.0


# ---------------------------------------------------------------------------
# Внутренние функции
# ---------------------------------------------------------------------------


def _match_irregular(
    stress_pattern: str,
    n_ictuses: int,
    valid_intervals: set[int],
    meter_name_ru: str,
) -> tuple[float, list[dict]]:
    """Общая логика оценки нерегулярного метра.

    Returns:
        (score, issues)
    """
    ictuses, intervals = extract_ictus_intervals(stress_pattern)
    actual_n = len(ictuses)
    issues: list[dict] = []

    if actual_n < 2:
        return 0.0, [{
            "position": -1,
            "type": "too_few_stresses",
            "severity": "error",
            "description": f"Менее 2 ударений для {meter_name_ru}",
        }]

    # Проверка количества иктов
    if actual_n != n_ictuses:
        diff = abs(actual_n - n_ictuses)
        severity = "warning" if diff == 1 else "error"
        issues.append({
            "position": -1,
            "type": "ictus_count",
            "severity": severity,
            "description": (
                f"Ожидается {n_ictuses} иктов, найдено {actual_n}"
            ),
        })

    # Проверка анакрузы (слоги перед первым иктом)
    anacrusis = ictuses[0]
    if anacrusis > 2:
        issues.append({
            "position": 0,
            "type": "long_anacrusis",
            "severity": "warning",
            "description": f"Длинная анакруза: {anacrusis} слогов",
        })

    # Проверка межиктовых интервалов
    valid_count = 0
    for idx, iv in enumerate(intervals):
        if iv in valid_intervals:
            valid_count += 1
        elif iv == 0:
            issues.append({
                "position": ictuses[idx],
                "type": "stress_clash",
                "severity": "warning",
                "description": (
                    f"Стечение ударений "
                    f"(позиции {ictuses[idx] + 1}–{ictuses[idx + 1] + 1})"
                ),
            })
        else:
            max_iv = max(valid_intervals)
            issues.append({
                "position": ictuses[idx],
                "type": "interval_violation",
                "severity": "error",
                "description": (
                    f"Интервал {iv} между иктами "
                    f"(позиции {ictuses[idx] + 1} и {ictuses[idx + 1] + 1}), "
                    f"допустимо 1–{max_iv} для {meter_name_ru}"
                ),
            })

    # Скоринг
    if not intervals:
        return 0.0, issues

    interval_ratio = valid_count / len(intervals)

    # Штраф за неверное количество иктов
    ictus_penalty = max(0.0, 1.0 - 0.2 * abs(actual_n - n_ictuses))

    # Штраф за длинную анакрузу
    anacrusis_penalty = 1.0 if anacrusis <= 2 else 0.9

    # Базовый score: доля валидных интервалов × штрафы
    score = interval_ratio * ictus_penalty * anacrusis_penalty

    # Потолок: регулярные метры с хорошим score имеют приоритет
    # Но паттерны с вариацией интервалов (настоящий дольник/тактовик)
    # получают чуть более высокий потолок, чем однородные (замаскированный
    # регулярный метр). Это критично для корректного разрешения омографов.
    unique_valid = {iv for iv in intervals if iv in valid_intervals}
    has_variation = len(unique_valid) > 1
    cap = 0.92 if has_variation else 0.85
    score = min(score, cap)

    return round(score, 3), issues


def _score_irregular_only(
    stress_pattern: str,
    n_ictuses: int,
    valid_intervals: set[int],
) -> float:
    """Быстрый скоринг нерегулярного метра без генерации issues."""
    ictuses, intervals = extract_ictus_intervals(stress_pattern)
    actual_n = len(ictuses)

    if actual_n < 2 or not intervals:
        return 0.0

    valid_count = sum(1 for iv in intervals if iv in valid_intervals)
    interval_ratio = valid_count / len(intervals)

    ictus_penalty = max(0.0, 1.0 - 0.2 * abs(actual_n - n_ictuses))
    anacrusis_penalty = 1.0 if ictuses[0] <= 2 else 0.9

    score = interval_ratio * ictus_penalty * anacrusis_penalty

    # Потолок с бонусом за вариацию (как в _match_irregular)
    unique_valid = {iv for iv in intervals if iv in valid_intervals}
    has_variation = len(unique_valid) > 1
    cap = 0.92 if has_variation else 0.85

    return min(score, cap)

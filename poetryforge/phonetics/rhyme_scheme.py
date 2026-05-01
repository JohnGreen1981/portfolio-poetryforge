"""Определение рифменной схемы с различением клаузул и распознаванием строфических форм.

Конвенция: A,B,C... = женские окончания, a,b,c... = мужские окончания.
Дактилические клаузулы приравниваются к женским.
"""

from __future__ import annotations

import re

from poetryforge.phonetics.syllable import count_syllables
from poetryforge.rhyme.phonetic_rhyme import RhymeAnalyzer

# Каталог стандартных строфических паттернов
# Ключ → (список нормализованных схем, русское название)
STANZA_PATTERNS: dict[str, tuple[list[str], str]] = {
    "cross": (
        ["AbAb", "aBaB", "abab", "ABAB"],
        "перекрёстная",
    ),
    "paired": (
        ["AAbb", "aaBB", "AaBb", "aAbB", "aabb", "AABB"],
        "парная",
    ),
    "enclosing": (
        ["AbbA", "aBBa", "AbBa", "aBbA", "abba", "ABBA"],
        "опоясывающая",
    ),
    "onegin": (
        ["AbAbCCddEffEgg"],
        "онегинская строфа",
    ),
}


def detect_rhyme_scheme(
    lines: list[str],
    line_results: list[dict],
    rhyme_analyzer: RhymeAnalyzer,
    blank_positions: set[int] | None = None,
    quality_threshold: float = 0.5,
) -> dict:
    """Определить рифменную схему стихотворения.

    Args:
        lines: непустые строки стихотворения
        line_results: результаты analyze_line для каждой строки (содержат clausula)
        rhyme_analyzer: анализатор рифм (full_check)
        blank_positions: позиции пустых строк (для сегментации строф)
        quality_threshold: минимальное качество рифмы

    Returns:
        dict с ключами: scheme, stanza_pattern, stanza_type, stanzas
    """
    if len(lines) < 2:
        return {"scheme": "", "stanza_pattern": None, "stanza_type": None, "stanzas": []}

    # Сегментация строф
    stanza_groups = _segment_into_stanzas(lines, blank_positions)

    # Анализ каждой строфы
    stanza_results = []
    global_scheme = []
    next_label_idx = 0

    for group in stanza_groups:
        stanza_lines = [lines[i] for i in group]
        stanza_clausulae = [
            line_results[i].get("clausula", "unknown") for i in group
        ]
        stanza_line_results = [line_results[i] for i in group]

        scheme, next_label_idx = _assign_labels(
            stanza_lines, stanza_clausulae, rhyme_analyzer,
            quality_threshold, next_label_idx,
            stanza_line_results,
        )

        normalized = _normalize_scheme(scheme)
        pattern_name, pattern_ru = _match_pattern(normalized, len(group))

        stanza_results.append({
            "lines": group,
            "scheme": scheme,
            "pattern": pattern_name,
            "pattern_ru": pattern_ru,
        })
        global_scheme.append(scheme)

    full_scheme = "".join(global_scheme)

    # Определить общий паттерн стихотворения
    if len(stanza_results) == 1:
        poem_pattern = stanza_results[0]["pattern"]
        poem_type = stanza_results[0]["pattern_ru"]
    else:
        # Все строфы одного типа?
        patterns = [s["pattern"] for s in stanza_results if s["pattern"]]
        if patterns and all(p == patterns[0] for p in patterns):
            poem_pattern = patterns[0]
            poem_type = stanza_results[0]["pattern_ru"]
        else:
            poem_pattern = None
            poem_type = None

    return {
        "scheme": full_scheme,
        "stanza_pattern": poem_pattern,
        "stanza_type": poem_type,
        "stanzas": stanza_results,
    }


def _segment_into_stanzas(
    lines: list[str],
    blank_positions: set[int] | None,
) -> list[list[int]]:
    """Разбить строки на строфы по пустым строкам или эвристике."""
    n = len(lines)

    # 1. По пустым строкам
    if blank_positions:
        groups: list[list[int]] = []
        current: list[int] = []
        for i in range(n):
            current.append(i)
            if (i + 1) in blank_positions:
                if current:
                    groups.append(current)
                    current = []
        if current:
            groups.append(current)
        if len(groups) > 1:
            return groups

    # 2. Одна строфа для коротких стихотворений (≤ 16 строк)
    if n <= 16:
        return [list(range(n))]

    # 3. Четверостишия для длинных стихотворений
    groups = []
    for i in range(0, n, 4):
        groups.append(list(range(i, min(i + 4, n))))
    return groups


def _assign_labels(
    lines: list[str],
    clausulae: list[str],
    rhyme_analyzer: RhymeAnalyzer,
    threshold: float,
    start_label_idx: int,
    line_results: list[dict] | None = None,
) -> tuple[str, int]:
    """Назначить буквы рифменной схемы с учётом клаузул.

    Args:
        line_results: если переданы, из stress_pattern извлекается ударение
            последнего слова (meter-aware) для точной проверки рифмы.

    Returns:
        (scheme_string, next_label_idx)
    """
    n = len(lines)
    last_words = []
    last_word_stresses: list[int | None | object] = []

    for i, line in enumerate(lines):
        words = re.findall(r"[а-яёА-ЯЁ]+", line)
        last_word = words[-1] if words else ""
        last_words.append(last_word)

        # Извлечь ударение последнего слова из stress_pattern
        stress = _STRESS_UNSET
        if line_results and last_word:
            pattern = line_results[i].get("stress_pattern", "")
            n_syl = count_syllables(last_word)
            if n_syl > 0 and len(pattern) >= n_syl:
                tail = pattern[-n_syl:]
                if "1" in tail:
                    stress = tail.index("1")
                else:
                    stress = None  # безударное слово
        last_word_stresses.append(stress)

    label_map: dict[int, str] = {}
    next_idx = start_label_idx

    for i in range(n):
        matched = False
        for j in range(i):
            if not last_words[i] or not last_words[j]:
                continue
            # Сравниваем только строки с совместимыми клаузулами
            if not _clausulae_compatible(clausulae[i], clausulae[j]):
                continue
            if j not in label_map:
                continue

            # Передаём ударения из метра, если известны
            si = last_word_stresses[i]
            sj = last_word_stresses[j]
            kwargs: dict = {}
            if si is not _STRESS_UNSET:
                kwargs["stress1"] = si
            if sj is not _STRESS_UNSET:
                kwargs["stress2"] = sj

            result = rhyme_analyzer.full_check(
                last_words[i], last_words[j], **kwargs,
            )
            if result["rhymes"] and result["quality"] >= threshold:
                label_map[i] = label_map[j]
                matched = True
                break

        if not matched:
            raw_letter = chr(ord("a") + next_idx % 26)
            if clausulae[i] in ("feminine", "dactylic", "hyperdactylic"):
                label_map[i] = raw_letter.upper()
            else:
                label_map[i] = raw_letter
            next_idx += 1

    scheme = "".join(label_map.get(i, "?") for i in range(n))
    return scheme, next_idx


# Sentinel для "ударение не определено"
_STRESS_UNSET = object()


def _clausulae_compatible(c1: str, c2: str) -> bool:
    """Проверить совместимость клаузул для рифмовки."""
    # Мужские рифмуются с мужскими, женские с женскими/дактилическими
    masc = {"masculine"}
    fem = {"feminine", "dactylic", "hyperdactylic", "unknown"}
    if c1 in masc and c2 in masc:
        return True
    if c1 in fem and c2 in fem:
        return True
    return False


def _normalize_scheme(scheme: str) -> str:
    """Нормализовать схему: заменить конкретные буквы на последовательные.

    'EfEf' → 'AbAb', 'ccDD' → 'aaBB'
    """
    if not scheme:
        return ""

    mapping: dict[str, str] = {}
    next_idx = 0

    result = []
    for ch in scheme:
        key = ch.lower()
        if key not in mapping:
            mapping[key] = chr(ord("a") + next_idx)
            next_idx += 1
        normalized = mapping[key]
        if ch.isupper():
            result.append(normalized.upper())
        else:
            result.append(normalized)

    return "".join(result)


def _match_pattern(normalized: str, n_lines: int) -> tuple[str | None, str | None]:
    """Сопоставить нормализованную схему с каталогом паттернов."""
    for name, (variants, ru_name) in STANZA_PATTERNS.items():
        for variant in variants:
            if normalized == variant:
                return name, ru_name

    # Специальная проверка онегинской строфы по субструктуре
    if n_lines == 14:
        match = _check_onegin_structure(normalized)
        if match:
            return "onegin", "онегинская строфа"

    return None, None


def _check_onegin_structure(scheme: str) -> bool:
    """Проверить структуру онегинской строфы (14 строк).

    AbAb + CC + dd + EffE + gg
    Строки 1-4: перекрёстная, 5-6: парная, 7-8: парная,
    9-12: опоясывающая, 13-14: парная.
    """
    if len(scheme) != 14:
        return False

    # Проверяем структурные связи
    # 1-4: перекрёстная (1=3, 2=4, 1≠2)
    if scheme[0].lower() != scheme[2].lower():
        return False
    if scheme[1].lower() != scheme[3].lower():
        return False
    if scheme[0].lower() == scheme[1].lower():
        return False

    # 5-6: парная
    if scheme[4].lower() != scheme[5].lower():
        return False

    # 7-8: парная
    if scheme[6].lower() != scheme[7].lower():
        return False

    # 9-12: опоясывающая (9=12, 10=11, 9≠10)
    if scheme[8].lower() != scheme[11].lower():
        return False
    if scheme[9].lower() != scheme[10].lower():
        return False
    if scheme[8].lower() == scheme[9].lower():
        return False

    # 13-14: парная
    if scheme[12].lower() != scheme[13].lower():
        return False

    # Проверяем чередование клаузул (хотя бы частично)
    # В онегинской строфе: AbAb = жен-муж чередование
    if scheme[0].isupper() == scheme[1].isupper():
        return False  # должны различаться по клаузуле

    return True

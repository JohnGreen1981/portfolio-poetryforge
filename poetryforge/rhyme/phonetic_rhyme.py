"""Модуль анализа рифм на основе фонетического сравнения.

Сравнивает «хвосты» слов (от ударной гласной до конца) и определяет
тип и качество рифмы. Поддерживает глубокие и составные рифмы.
"""

from __future__ import annotations

import re

from poetryforge.phonetics.g2p import (
    rhyme_tail,
    transcribe_phrase,
    consonant_skeleton,
    normalize_skeleton,
    _VOWELS_LOWER,
)
from poetryforge.phonetics.stress import StressAnalyzer

# Sentinel для "вычислить ударение автоматически"
_UNSET = object()


def _stressed_vowel(
    text: str, sa: StressAnalyzer, stress_override=_UNSET,
) -> str | None:
    """Получить ударный гласный последнего слова текста."""
    words = re.findall(r"[а-яёА-ЯЁ]+", text.lower())
    if not words:
        return None
    last_word = words[-1]
    stress = sa.get_stress(last_word) if stress_override is _UNSET else stress_override
    tail = rhyme_tail(last_word, stress)
    if not tail:
        return None
    # Первый символ хвоста — ударный гласный
    for ch in tail:
        if ch in _VOWELS_LOWER:
            return ch
    return None


def _extract_vowels(tail: str) -> str:
    """Извлечь только гласные из фонетического хвоста."""
    return "".join(ch for ch in tail if ch in _VOWELS_LOWER)


def _extract_consonants(tail: str) -> str:
    """Извлечь согласные (с мягкостью) из фонетического хвоста."""
    result = []
    for i, ch in enumerate(tail):
        if ch in _VOWELS_LOWER:
            continue
        if ch == "'":
            continue  # мягкость уже в предыдущем символе
        # Берём согласную с возможной мягкостью
        if i + 1 < len(tail) and tail[i + 1] == "'":
            result.append(ch + "'")
        else:
            result.append(ch)
    return "".join(result)


def _edit_distance(s1: str, s2: str) -> int:
    """Расстояние Левенштейна между двумя строками."""
    if len(s1) < len(s2):
        return _edit_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)
    prev = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        curr = [i + 1]
        for j, c2 in enumerate(s2):
            cost = 0 if c1 == c2 else 1
            curr.append(min(curr[j] + 1, prev[j + 1] + 1, prev[j] + cost))
        prev = curr
    return prev[len(s2)]


class RhymeAnalyzer:
    """Анализатор рифм на основе фонетических хвостов."""

    def __init__(self, stress_analyzer: StressAnalyzer | None = None):
        self._sa = stress_analyzer or StressAnalyzer()

    def check(
        self, word1: str, word2: str,
        stress1=_UNSET, stress2=_UNSET,
    ) -> dict:
        """Проверить, рифмуются ли два слова.

        Args:
            word1, word2: слова для сравнения
            stress1, stress2: позиции ударных слогов (если известны);
                по умолчанию — определяются автоматически

        Returns:
            dict с ключами:
                rhymes: bool
                type: "exact" | "approximate" | "assonance" | null
                quality: float 0..1
                tails: [tail1, tail2]
        """
        stress1 = self._sa.get_stress(word1) if stress1 is _UNSET else stress1
        stress2 = self._sa.get_stress(word2) if stress2 is _UNSET else stress2

        tail1 = rhyme_tail(word1, stress1)
        tail2 = rhyme_tail(word2, stress2)

        if not tail1 or not tail2:
            return {"rhymes": False, "type": None, "quality": 0.0, "tails": [tail1, tail2]}

        # 1. Точная рифма: хвосты совпадают
        if tail1 == tail2:
            return {"rhymes": True, "type": "exact", "quality": 1.0, "tails": [tail1, tail2]}

        # 2. Приблизительная: edit distance <= 1 или совпадение гласных + близкие согласные
        dist = _edit_distance(tail1, tail2)
        max_len = max(len(tail1), len(tail2))

        if dist == 1:
            return {
                "rhymes": True,
                "type": "approximate",
                "quality": 0.8,
                "tails": [tail1, tail2],
            }

        # 3. Ассонансная: совпадение гласных
        vowels1 = _extract_vowels(tail1)
        vowels2 = _extract_vowels(tail2)

        if vowels1 and vowels1 == vowels2 and dist <= 3:
            quality = max(0.3, 1.0 - dist / max_len)
            return {
                "rhymes": True,
                "type": "assonance",
                "quality": round(quality, 2),
                "tails": [tail1, tail2],
            }

        # 4. Слабая приблизительная (dist 2, но короткие хвосты)
        if dist == 2 and max_len <= 4:
            return {
                "rhymes": True,
                "type": "approximate",
                "quality": 0.5,
                "tails": [tail1, tail2],
            }

        # Не рифмуется
        return {"rhymes": False, "type": None, "quality": 0.0, "tails": [tail1, tail2]}

    def full_check(
        self, text1: str, text2: str,
        stress1=_UNSET, stress2=_UNSET,
    ) -> dict:
        """Проверить рифму полным анализом: классика + глубокие.

        Запускает check() первым (быстрый). Если найдена рифма с quality ≥ 0.7,
        возвращает результат. Иначе пробует deep_check().

        Args:
            stress1, stress2: позиции ударных слогов (если известны из контекста метра)

        Returns:
            dict с ключами:
                rhymes: bool
                type: str | None
                quality: float
                depth: float | None
        """
        # 1. Быстрый классический check
        classic = self.check(text1, text2, stress1=stress1, stress2=stress2)
        if classic["rhymes"] and classic["quality"] >= 0.7:
            return {
                "rhymes": True,
                "type": classic["type"],
                "quality": classic["quality"],
                "depth": None,
            }

        # 2. Глубокий check
        deep = self.deep_check(text1, text2, stress1=stress1, stress2=stress2)
        if deep["rhymes"]:
            return {
                "rhymes": True,
                "type": deep["type"],
                "quality": deep["quality"],
                "depth": deep["depth"],
            }

        # 3. Классика с quality < 0.7 всё же лучше, чем ничего
        if classic["rhymes"]:
            return {
                "rhymes": True,
                "type": classic["type"],
                "quality": classic["quality"],
                "depth": None,
            }

        return {"rhymes": False, "type": None, "quality": 0.0, "depth": None}

    def deep_check(
        self, text1: str, text2: str,
        stress1=_UNSET, stress2=_UNSET,
    ) -> dict:
        """Проверить глубокую/составную рифму между двумя словами или фразами.

        Анализирует полные транскрипции, согласные каркасы и обратное
        выравнивание — покрывает панторифму, составную рифму, паронимическую.

        Args:
            text1: слово или фраза (например, «триста лет»)
            text2: слово или фраза (например, «пистолет»)
            stress1, stress2: позиции ударных слогов (если известны)

        Returns:
            dict:
                rhymes: bool
                type: "exact" | "deep" | "skeleton" | "containment" | null
                quality: float 0..1
                depth: float 0..1 — доля совпадающего хвоста
                transcriptions: [t1, t2]
                skeletons: [sk1, sk2]
        """
        t1 = transcribe_phrase(text1)
        t2 = transcribe_phrase(text2)

        if not t1 or not t2:
            return _deep_result(False, None, 0.0, 0.0, t1, t2)

        # Проверка ударного гласного — должен совпадать
        sv1 = _stressed_vowel(text1, self._sa, stress_override=stress1)
        sv2 = _stressed_vowel(text2, self._sa, stress_override=stress2)
        if sv1 and sv2 and sv1 != sv2:
            return _deep_result(False, None, 0.0, 0.0, t1, t2)

        sk1 = consonant_skeleton(t1)
        sk2 = consonant_skeleton(t2)
        # Нормализованные скелеты (звонкие/глухие приведены к одному)
        nsk1 = normalize_skeleton(sk1)
        nsk2 = normalize_skeleton(sk2)

        # 1. Полное совпадение транскрипций
        if t1 == t2:
            return _deep_result(True, "exact", 1.0, 1.0, t1, t2, sk1, sk2)

        # 2. Обратное выравнивание — считаем совпадение с конца
        match_len = _suffix_match_length(t1, t2)
        shorter = min(len(t1), len(t2))
        depth = match_len / shorter if shorter > 0 else 0.0

        # 3. Совпадение нормализованного согласного каркаса с конца
        nsk_match = _suffix_match_length(nsk1, nsk2)
        nsk_shorter = min(len(nsk1), len(nsk2))
        nsk_depth = nsk_match / nsk_shorter if nsk_shorter > 0 else 0.0

        # 4. Containment — одна транскрипция является суффиксом другой
        if t1.endswith(t2) or t2.endswith(t1):
            contained_len = min(len(t1), len(t2))
            c_depth = contained_len / max(len(t1), len(t2))
            quality = 0.6 + 0.4 * c_depth
            return _deep_result(True, "containment", round(quality, 2), round(c_depth, 2),
                                t1, t2, sk1, sk2)

        # 5. Полное совпадение нормализованных согласных каркасов
        if nsk1 == nsk2:
            quality = 0.7 + 0.3 * depth
            return _deep_result(True, "skeleton", round(quality, 2), round(max(depth, nsk_depth), 2),
                                t1, t2, sk1, sk2)

        # 6. Глубокая рифма по обратному выравниванию
        if depth >= 0.5:
            quality = 0.5 + 0.5 * depth
            return _deep_result(True, "deep", round(quality, 2), round(depth, 2),
                                t1, t2, sk1, sk2)

        # 7. Глубокое совпадение нормализованного согласного каркаса (>= 60%)
        if nsk_depth >= 0.6:
            quality = 0.4 + 0.4 * nsk_depth
            return _deep_result(True, "skeleton", round(quality, 2), round(nsk_depth, 2),
                                t1, t2, sk1, sk2)

        # 8. Комбинированная метрика: скелет близок + транскрипция частично совпадает
        nsk_edit = _edit_distance(nsk1, nsk2)
        if nsk_edit <= 2 and depth >= 0.4:
            combined = (depth + nsk_depth) / 2
            quality = 0.4 + 0.4 * combined
            return _deep_result(True, "deep", round(quality, 2), round(combined, 2),
                                t1, t2, sk1, sk2)

        # Не рифмуется глубоко
        best_depth = max(depth, nsk_depth)
        return _deep_result(False, None, 0.0, round(best_depth, 2), t1, t2, sk1, sk2)


def _suffix_match_length(s1: str, s2: str) -> int:
    """Длина совпадающего суффикса двух строк."""
    count = 0
    i, j = len(s1) - 1, len(s2) - 1
    while i >= 0 and j >= 0 and s1[i] == s2[j]:
        count += 1
        i -= 1
        j -= 1
    return count


def _deep_result(
    rhymes: bool,
    rtype: str | None,
    quality: float,
    depth: float,
    t1: str,
    t2: str,
    sk1: str = "",
    sk2: str = "",
) -> dict:
    return {
        "rhymes": rhymes,
        "type": rtype,
        "quality": quality,
        "depth": depth,
        "transcriptions": [t1, t2],
        "skeletons": [sk1, sk2],
    }

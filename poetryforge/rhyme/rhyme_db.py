"""Подбор рифм к слову на основе обратного индекса фонетических хвостов.

Индекс строится один раз из словаря и сохраняется в JSON.
При поиске рифмы — lookup по хвосту, сортировка по точности.
"""

from __future__ import annotations

import json
from pathlib import Path

import pymorphy3

from poetryforge.phonetics.g2p import (
    rhyme_tail,
    transcribe,
    consonant_skeleton,
    _VOWELS_LOWER,
)
from poetryforge.phonetics.stress import StressAnalyzer
from poetryforge.phonetics.syllable import count_syllables
from poetryforge.rhyme.phonetic_rhyme import _edit_distance, _suffix_match_length

_DATA_DIR = Path(__file__).parent.parent / "data"
_INDEX_PATH = _DATA_DIR / "rhyme_index.json"
_DEEP_INDEX_PATH = _DATA_DIR / "deep_rhyme_index.json"

# pymorphy3 POS tag → русское название
_POS_RU = {
    "NOUN": "сущ.",
    "ADJF": "прил.",
    "ADJS": "кр.прил.",
    "COMP": "сравн.",
    "VERB": "глагол",
    "INFN": "инфинитив",
    "PRTF": "причастие",
    "PRTS": "кр.прич.",
    "GRND": "деепричастие",
    "NUMR": "числит.",
    "ADVB": "наречие",
    "NPRO": "местоим.",
    "PRED": "предикатив",
    "PREP": "предлог",
    "CONJ": "союз",
    "PRCL": "частица",
    "INTJ": "междом.",
}


def _morph_info(morph: pymorphy3.MorphAnalyzer, word: str) -> dict:
    """Получить морфологическую информацию о слове."""
    parses = morph.parse(word)
    if not parses:
        return {"pos": None, "pos_ru": None, "gram": None}
    p = parses[0]
    pos = p.tag.POS
    pos_ru = _POS_RU.get(pos, pos) if pos else None
    # Краткая грамматическая характеристика
    gram_parts = []
    if p.tag.case:
        gram_parts.append(str(p.tag.case))
    if p.tag.number:
        gram_parts.append(str(p.tag.number))
    if p.tag.gender:
        gram_parts.append(str(p.tag.gender))
    gram = ",".join(gram_parts) if gram_parts else None
    return {"pos": pos, "pos_ru": pos_ru, "gram": gram}


def _gram_matches(info1: dict, info2: dict) -> bool:
    """Проверить, совпадают ли часть речи и основные грамм. признаки."""
    if not info1["pos"] or not info2["pos"]:
        return False
    if info1["pos"] != info2["pos"]:
        return False
    # Для существительных — совпадение падежа
    if info1["pos"] == "NOUN" and info1["gram"] and info2["gram"]:
        return info1["gram"] == info2["gram"]
    # Для глаголов/инфинитивов — всегда gram_match если та же часть речи
    return True


class RhymeDB:
    """База рифм с обратным индексом по фонетическим хвостам."""

    def __init__(self):
        self._index: dict[str, list[str]] = {}
        self._deep_index: dict[str, list[str]] = {}  # reversed consonant skeleton → words
        self._transcriptions: dict[str, str] = {}  # word → full transcription
        self._sa = StressAnalyzer()
        self._morph = pymorphy3.MorphAnalyzer()
        self._load_index()

    def _load_index(self):
        if _INDEX_PATH.exists():
            text = _INDEX_PATH.read_text(encoding="utf-8")
            if text.strip():
                self._index = json.loads(text)
        if _DEEP_INDEX_PATH.exists():
            text = _DEEP_INDEX_PATH.read_text(encoding="utf-8")
            if text.strip():
                data = json.loads(text)
                self._deep_index = data.get("skeleton", {})
                self._transcriptions = data.get("transcriptions", {})

    def _save_index(self):
        _INDEX_PATH.write_text(
            json.dumps(self._index, ensure_ascii=False),
            encoding="utf-8",
        )

    def _save_deep_index(self):
        data = {
            "skeleton": self._deep_index,
            "transcriptions": self._transcriptions,
        }
        _DEEP_INDEX_PATH.write_text(
            json.dumps(data, ensure_ascii=False),
            encoding="utf-8",
        )

    @property
    def size(self) -> int:
        """Общее количество слов в индексе."""
        return sum(len(words) for words in self._index.values())

    def build_index(self, words: list[str], progress: bool = False):
        """Построить индекс из списка слов (классический + глубокий).

        Args:
            words: список русских слов
            progress: выводить прогресс в stdout
        """
        self._index = {}
        self._deep_index = {}
        self._transcriptions = {}
        total = len(words)

        for i, word in enumerate(words):
            if progress and (i + 1) % 1000 == 0:
                print(f"  {i + 1}/{total}...")

            word = word.strip().lower()
            if not word or count_syllables(word) < 1:
                continue

            stress_pos = self._sa.get_stress(word)
            if stress_pos is None:
                continue

            tail = rhyme_tail(word, stress_pos)
            if not tail:
                continue

            # Классический индекс по хвосту
            if tail not in self._index:
                self._index[tail] = []
            if word not in self._index[tail]:
                self._index[tail].append(word)

            # Глубокий индекс: обратный согласный скелет
            try:
                full_t = transcribe(word)
                sk = consonant_skeleton(full_t)
                rev_sk = sk[::-1]

                # Ключ — первые 4 символа обратного скелета (для группировки)
                key = rev_sk[:4] if len(rev_sk) >= 4 else rev_sk
                if key:
                    if key not in self._deep_index:
                        self._deep_index[key] = []
                    if word not in self._deep_index[key]:
                        self._deep_index[key].append(word)

                    self._transcriptions[word] = full_t
            except Exception:
                continue

        self._save_index()
        self._save_deep_index()

    def find_rhymes(
        self,
        word: str,
        rhyme_type: str = "exact",
        limit: int = 10,
    ) -> list[dict]:
        """Найти рифмы к слову.

        Args:
            word: слово, для которого ищем рифмы
            rhyme_type: "exact" — точные, "approximate" — приблизительные
            limit: максимальное количество результатов

        Returns:
            Список dict: {"word": str, "type": str, "tail": str}
        """
        word_lower = word.strip().lower()
        stress_pos = self._sa.get_stress(word_lower)
        if stress_pos is None:
            return []

        target_tail = rhyme_tail(word_lower, stress_pos)
        if not target_tail:
            return []

        results = []

        # 1. Точные рифмы — тот же хвост
        exact_words = self._index.get(target_tail, [])
        for w in exact_words:
            if w != word_lower:
                results.append({"word": w, "type": "exact", "tail": target_tail})

        # 2. Приблизительные — хвосты с edit distance 1-2
        if rhyme_type == "approximate" or len(results) < limit:
            for tail, words in self._index.items():
                if tail == target_tail:
                    continue
                dist = _edit_distance(tail, target_tail)
                if dist <= 2:
                    for w in words:
                        if w != word_lower:
                            results.append({
                                "word": w,
                                "type": "approximate",
                                "tail": tail,
                            })

        # Сортировка: exact первыми, потом approximate
        type_order = {"exact": 0, "approximate": 1}
        results.sort(key=lambda r: type_order.get(r["type"], 2))

        # Убрать дубли, сохранив порядок
        seen = set()
        unique = []
        for r in results:
            if r["word"] not in seen:
                seen.add(r["word"])
                unique.append(r)

        if rhyme_type == "exact":
            unique = [r for r in unique if r["type"] == "exact"]

        limited = unique[:limit]

        # Морфологическая разметка и антиграмматический фильтр
        source_info = _morph_info(self._morph, word_lower)
        for r in limited:
            info = _morph_info(self._morph, r["word"])
            r["pos"] = info["pos"]
            r["pos_ru"] = info["pos_ru"]
            r["gram_match"] = _gram_matches(source_info, info)

        # Грамматически разнородные — выше (при равном типе рифмы)
        type_order = {"exact": 0, "approximate": 1}
        limited.sort(key=lambda r: (type_order.get(r["type"], 2), r["gram_match"]))

        return limited

    def find_deep_rhymes(
        self,
        word: str,
        limit: int = 10,
        min_depth: float = 0.5,
    ) -> list[dict]:
        """Найти глубокие рифмы к слову.

        Ищет по обратному согласному скелету, затем ранжирует по глубине
        совпадения полной транскрипции.

        Args:
            word: слово для поиска глубоких рифм
            limit: максимальное количество результатов
            min_depth: минимальная глубина совпадения (0..1)

        Returns:
            Список dict: {"word", "type", "depth", "quality"}
        """
        word_lower = word.strip().lower()

        if not self._deep_index:
            return []

        # Транскрипция и скелет искомого слова
        try:
            target_t = transcribe(word_lower)
        except Exception:
            return []

        target_sk = consonant_skeleton(target_t)
        target_rev = target_sk[::-1]

        if not target_rev:
            return []

        # Ударный гласный целевого слова — для фильтрации кандидатов
        target_stress = self._sa.get_stress(word_lower)
        target_tail = rhyme_tail(word_lower, target_stress)
        target_stressed_v = None
        if target_tail:
            for ch in target_tail:
                if ch in _VOWELS_LOWER:
                    target_stressed_v = ch
                    break

        if not target_stressed_v:
            return []

        # Собираем кандидатов из deep_index
        candidates: set[str] = set()

        # Ищем по ключам с совпадающим началом обратного скелета
        target_key = target_rev[:4] if len(target_rev) >= 4 else target_rev
        for key_len in range(len(target_key), 0, -1):
            prefix = target_key[:key_len]
            for key, words in self._deep_index.items():
                if key.startswith(prefix) or prefix.startswith(key):
                    candidates.update(words)

        candidates.discard(word_lower)

        target_len = len(target_t)

        # Ранжируем кандидатов по глубине совпадения
        results = []
        for cand in candidates:
            cand_t = self._transcriptions.get(cand)
            if not cand_t:
                continue

            cand_len = len(cand_t)

            # Фильтр: ударный гласный должен совпадать
            if target_stressed_v:
                cand_stress = self._sa.get_stress(cand)
                cand_tail = rhyme_tail(cand, cand_stress) if cand_stress is not None else ""
                cand_stressed_v = None
                if cand_tail:
                    for ch in cand_tail:
                        if ch in _VOWELS_LOWER:
                            cand_stressed_v = ch
                            break
                if cand_stressed_v and cand_stressed_v != target_stressed_v:
                    continue

            # Фильтр: слишком разная длина — не глубокая рифма
            len_ratio = min(target_len, cand_len) / max(target_len, cand_len)
            if len_ratio < 0.4:
                continue

            # Обратное выравнивание полных транскрипций
            match_len = _suffix_match_length(target_t, cand_t)
            shorter = min(target_len, cand_len)
            depth = match_len / shorter if shorter > 0 else 0.0

            # Минимальное абсолютное совпадение — не менее 3 символов
            if match_len < 3:
                continue

            # Совпадение согласного каркаса
            cand_sk = consonant_skeleton(cand_t)
            sk_match = _suffix_match_length(target_sk, cand_sk)
            sk_shorter = min(len(target_sk), len(cand_sk))
            sk_depth = sk_match / sk_shorter if sk_shorter > 0 else 0.0

            # Итоговый score — взвешенная комбинация с штрафом за разницу длин
            combined = max(depth, sk_depth * 0.9) * (0.5 + 0.5 * len_ratio)

            if combined < min_depth:
                continue

            # Определяем тип
            if depth >= 0.8:
                rtype = "pantorhyme"
            elif target_sk == cand_sk:
                rtype = "skeleton"
            elif depth >= 0.5:
                rtype = "deep"
            else:
                rtype = "deep"

            quality = 0.4 + 0.6 * combined

            results.append({
                "word": cand,
                "type": rtype,
                "depth": round(combined, 2),
                "quality": round(quality, 2),
            })

        # Сортировка по глубине (лучшие первыми)
        results.sort(key=lambda r: -r["depth"])
        limited = results[:limit]

        # Морфологическая разметка и антиграмматический фильтр
        source_info = _morph_info(self._morph, word_lower)
        for r in limited:
            info = _morph_info(self._morph, r["word"])
            r["pos"] = info["pos"]
            r["pos_ru"] = info["pos_ru"]
            r["gram_match"] = _gram_matches(source_info, info)

        # Грамматически разнородные — выше (при равной глубине)
        limited.sort(key=lambda r: (r["gram_match"], -r["depth"]))

        return limited

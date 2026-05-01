"""Модуль определения ударений в русских словах.

Стратегия (каскад с приоритетами):
1. user_dict.json — пользовательский словарь (высший приоритет)
2. Буква «ё» — всегда ударная
3. Словарный lookup — прямой O(1) поиск в словаре ruaccent (3.19M слов)
4. ruaccent neural — нейросеть (fallback для неизвестных/омографов)

Служебные односложные слова считаются безударными.
"""

import json
import re
from pathlib import Path

from ruaccent import RUAccent

from poetryforge.phonetics.syllable import syllabify, count_syllables, VOWELS
from poetryforge.phonetics.meter_utils import (
    score_meter_only,
    score_irregular_only,
    IRREGULAR_METERS,
)

# Путь к пользовательскому словарю
_DATA_DIR = Path(__file__).parent.parent / "data"
_USER_DICT_PATH = _DATA_DIR / "user_dict.json"

# Односложные служебные слова — безударные в стихе
_UNSTRESSED_WORDS = {
    "а", "б", "бы", "в", "во", "да", "до", "же", "за", "и",
    "из", "к", "ко", "ль", "на", "не", "ни", "но", "о", "об",
    "от", "по", "с", "со", "у", "уж",
}


def _find_yo_stress(word: str) -> int | None:
    """Найти позицию ударного слога по букве «ё»."""
    lower = word.lower()
    if "ё" not in lower:
        return None
    # Находим позицию «ё» и считаем, в каком она слоге
    syllable_idx = 0
    for ch in word:
        if ch.lower() == "ё":
            return syllable_idx
        if ch in VOWELS:
            syllable_idx += 1
    return None


class StressAnalyzer:
    """Анализатор ударений с каскадом: user_dict → ё → dict → ruaccent."""

    def __init__(self):
        self._user_dict: dict[str, int] = {}
        self._load_user_dict()
        self._accent = RUAccent()
        self._accent.load(omograph_model_size="turbo", use_dictionary=True)

    def _load_user_dict(self):
        if _USER_DICT_PATH.exists():
            text = _USER_DICT_PATH.read_text(encoding="utf-8").strip()
            if text:
                self._user_dict = json.loads(text)

    def _save_user_dict(self):
        _USER_DICT_PATH.write_text(
            json.dumps(self._user_dict, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def add_to_user_dict(self, word: str, stress_pos: int):
        """Добавить слово в пользовательский словарь.

        Args:
            word: слово в нижнем регистре
            stress_pos: позиция ударного слога (0-indexed)
        """
        self._user_dict[word.lower()] = stress_pos
        self._save_user_dict()

    def remove_from_user_dict(self, word: str):
        """Удалить слово из пользовательского словаря."""
        self._user_dict.pop(word.lower(), None)
        self._save_user_dict()

    def list_user_dict(self) -> dict[str, int]:
        return dict(self._user_dict)

    def get_stress(self, word: str) -> int | None:
        """Определить позицию ударного слога для одного слова.

        Returns:
            Позиция ударного слога (0-indexed) или None если слово безударное.
        """
        clean = re.sub(r"[^\w]", "", word)
        if not clean:
            return None

        lower = clean.lower()
        n_syllables = count_syllables(clean)

        # Слова без гласных — не имеют ударения
        if n_syllables == 0:
            return None

        # Односложные служебные слова — безударные
        if n_syllables == 1 and lower in _UNSTRESSED_WORDS:
            return None

        # Односложные знаменательные слова — ударение на единственный слог
        if n_syllables == 1:
            return 0

        # 1. Пользовательский словарь
        if lower in self._user_dict:
            return self._user_dict[lower]

        # 2. Буква «ё»
        yo_pos = _find_yo_stress(clean)
        if yo_pos is not None:
            return yo_pos

        # 3. Словарный lookup (быстрый, детерминированный)
        dict_pos = self._stress_from_dict(lower)
        if dict_pos is not None:
            return dict_pos

        # 4. ruaccent neural (fallback)
        return self._stress_from_ruaccent(clean)

    def _stress_from_dict(self, word: str) -> int | None:
        """Прямой lookup в словаре ruaccent (3.19M слов, O(1)).

        Для однозначных слов (не в omographs) возвращает позицию ударения
        без вызова нейросети. Для омографов возвращает None → fallthrough.
        """
        if word in self._accent.omographs:
            return None

        accented = self._accent.accents.get(word)
        if accented is None:
            return None

        return self._parse_stress_from_accented(accented)

    def _stress_from_ruaccent(self, word: str) -> int | None:
        """Получить ударение через ruaccent.

        ruaccent возвращает слово с '+' перед ударной гласной.
        """
        try:
            result = self._accent.process_all(word)
        except Exception:
            return None
        if "+" not in result:
            return None

        # Находим позицию '+' и считаем, какой это слог
        syllable_idx = 0
        for i, ch in enumerate(result):
            if ch == "+":
                # Следующий символ — ударная гласная, текущий слог
                return syllable_idx
            if ch in VOWELS:
                syllable_idx += 1

        return None

    @staticmethod
    def _parse_stress_from_accented(accented: str) -> int | None:
        """Извлечь позицию ударного слога из строки формата 'сло+во'."""
        syllable_idx = 0
        for ch in accented:
            if ch == "+":
                return syllable_idx
            if ch.lower() in VOWELS:
                syllable_idx += 1
        return None

    def get_stress_variants(self, word: str) -> list[int]:
        """Получить все возможные позиции ударения для слова.

        Для однозначных слов возвращает список из одного элемента.
        Для омографов — список вариантов из ruaccent.omographs.
        """
        clean = re.sub(r"[^\w]", "", word)
        if not clean:
            return []

        lower = clean.lower()
        n_syllables = count_syllables(clean)

        if n_syllables == 0:
            return []
        if n_syllables == 1 and lower in _UNSTRESSED_WORDS:
            return []
        if n_syllables == 1:
            return [0]

        # user_dict — единственный вариант (пользователь решил)
        if lower in self._user_dict:
            return [self._user_dict[lower]]

        # ё — однозначно
        yo_pos = _find_yo_stress(clean)
        if yo_pos is not None:
            return [yo_pos]

        # Омографы — несколько вариантов
        if lower in self._accent.omographs:
            variants = []
            for accented in self._accent.omographs[lower]:
                pos = self._parse_stress_from_accented(accented)
                if pos is not None and pos not in variants:
                    variants.append(pos)
            if variants:
                return variants

        # Словарный lookup (быстрый)
        dict_pos = self._stress_from_dict(lower)
        if dict_pos is not None:
            return [dict_pos]

        # Fallback: ruaccent neural
        pos = self._stress_from_ruaccent(clean)
        return [pos] if pos is not None else []

    def stress_pattern_with_meter(
        self, line: str, meter: str, foot_count: int
    ) -> tuple[str, list[dict]]:
        """Построить stress pattern с учётом метра для разрешения омографов.

        Args:
            line: стихотворная строка
            meter: название метра ('iamb', 'trochee', etc.)
            foot_count: количество стоп

        Returns:
            (pattern, ambiguous_words): паттерн и список разрешённых омографов
        """
        words = re.findall(r"[а-яёА-ЯЁ]+", line)
        word_data = []  # (word, n_syllables, variants, default_stress)

        for word in words:
            n = count_syllables(word)
            variants = self.get_stress_variants(word)
            default = self.get_stress(word)
            word_data.append((word, n, variants, default))

        # Найти слова с неоднозначным ударением (>1 вариант)
        ambiguous_indices = [
            i for i, (_, _, variants, _) in enumerate(word_data)
            if len(variants) > 1
        ]

        if not ambiguous_indices:
            # Нет омографов — обычный паттерн
            pattern = self._build_pattern(word_data, {})
            return pattern, []

        # Перебор вариантов
        total_combos = 1
        for idx in ambiguous_indices:
            total_combos *= len(word_data[idx][2])

        if total_combos <= 8:
            # Полный перебор
            best_pattern, best_choices = self._brute_force_resolve(
                word_data, ambiguous_indices, meter, foot_count
            )
        else:
            # Жадный подход
            best_pattern, best_choices = self._greedy_resolve(
                word_data, ambiguous_indices, meter, foot_count
            )

        # Формируем отчёт о разрешённых омографах
        ambiguous_words = []
        for idx in ambiguous_indices:
            word, _, variants, default = word_data[idx]
            chosen = best_choices.get(idx, default)
            if chosen != default:
                ambiguous_words.append({
                    "word": word.lower(),
                    "position": idx,
                    "variants": variants,
                    "chosen": chosen,
                    "default": default,
                })

        return best_pattern, ambiguous_words

    def _build_pattern(
        self, word_data: list[tuple], overrides: dict[int, int]
    ) -> str:
        """Построить stress pattern с опциональными переопределениями."""
        pattern = []
        for i, (_, n, _, default) in enumerate(word_data):
            stress = overrides.get(i, default)
            for s in range(n):
                pattern.append("1" if s == stress else "0")
        return "".join(pattern)

    @staticmethod
    def _score_for_meter(pattern: str, meter: str, count: int) -> float:
        """Диспетчер скоринга: регулярный или нерегулярный метр."""
        if meter in IRREGULAR_METERS:
            return score_irregular_only(pattern, meter, count)
        return score_meter_only(pattern, meter, count)

    def _brute_force_resolve(
        self,
        word_data: list[tuple],
        ambiguous_indices: list[int],
        meter: str,
        foot_count: int,
    ) -> tuple[str, dict[int, int]]:
        """Перебрать все комбинации ударений и выбрать лучшую."""
        import itertools

        variant_lists = [word_data[idx][2] for idx in ambiguous_indices]
        best_score = -1.0
        best_pattern = ""
        best_choices: dict[int, int] = {}

        for combo in itertools.product(*variant_lists):
            overrides = {
                ambiguous_indices[j]: combo[j]
                for j in range(len(ambiguous_indices))
            }
            pattern = self._build_pattern(word_data, overrides)
            score = self._score_for_meter(pattern, meter, foot_count)
            if score > best_score:
                best_score = score
                best_pattern = pattern
                best_choices = overrides

        return best_pattern, best_choices

    def _greedy_resolve(
        self,
        word_data: list[tuple],
        ambiguous_indices: list[int],
        meter: str,
        foot_count: int,
    ) -> tuple[str, dict[int, int]]:
        """Жадное разрешение: по одному слову, слева направо."""
        overrides: dict[int, int] = {}

        for idx in ambiguous_indices:
            _, _, variants, _ = word_data[idx]
            best_score = -1.0
            best_variant = variants[0]

            for v in variants:
                overrides[idx] = v
                pattern = self._build_pattern(word_data, overrides)
                score = self._score_for_meter(pattern, meter, foot_count)
                if score > best_score:
                    best_score = score
                    best_variant = v

            overrides[idx] = best_variant

        pattern = self._build_pattern(word_data, overrides)
        return pattern, overrides

    def analyze(self, line: str) -> list[dict]:
        """Проанализировать ударения в строке.

        Args:
            line: строка текста (стихотворная строка)

        Returns:
            Список словарей для каждого слова:
                word: исходное слово
                syllables: количество слогов
                stress_pos: позиция ударного слога (0-indexed) или None
        """
        words = re.findall(r"[а-яёА-ЯЁ]+", line)
        result = []
        for word in words:
            syl_info = syllabify(word)
            stress_pos = self.get_stress(word)
            result.append({
                "word": word,
                "syllables": syl_info["count"],
                "stress_pos": stress_pos,
            })
        return result

    def stress_pattern(self, line: str) -> str:
        """Построить бинарную схему ударений для строки.

        Returns:
            Строка из 0 и 1, где 1 = ударный слог, 0 = безударный.
        """
        analysis = self.analyze(line)
        pattern = []
        for word_info in analysis:
            n = word_info["syllables"]
            stress = word_info["stress_pos"]
            for i in range(n):
                pattern.append("1" if i == stress else "0")
        return "".join(pattern)

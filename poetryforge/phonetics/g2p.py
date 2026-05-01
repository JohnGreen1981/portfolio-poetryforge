"""Grapheme-to-Phoneme: фонетическая транскрипция русских слов.

Реализация по правилам русской фонетики. Для анализа рифм достаточно
транскрипции окончания от ударного гласного до конца слова.

Обозначения в транскрипции:
- ' после согласной = мягкость (к'  = кь)
- й = [j]
- Гласные: а, о, у, э, и, ы
"""

import re

from poetryforge.phonetics.syllable import VOWELS

# Парные звонкие → глухие
DEVOICE = {
    "б": "п", "в": "ф", "г": "к", "д": "т", "ж": "ш", "з": "с",
}

# Парные глухие → звонкие
VOICE = {v: k for k, v in DEVOICE.items()}

VOICED = set(DEVOICE.keys())
VOICELESS = set(DEVOICE.values()) | {"х", "ц", "ч", "щ"}
SONOROUS_CONS = {"л", "м", "н", "р"}

# Согласные, которые всегда мягкие
ALWAYS_SOFT = {"ч", "щ", "й"}
# Согласные, которые всегда твёрдые
ALWAYS_HARD = {"ж", "ш", "ц"}

# Йотированные гласные
YOTATED = {
    "я": ("й", "а"),
    "е": ("й", "э"),
    "ё": ("й", "о"),
    "ю": ("й", "у"),
}

# Гласные, смягчающие предыдущую согласную
SOFTENING_VOWELS = {"я", "е", "ё", "ю", "и", "ь"}

_VOWELS_LOWER = {ch.lower() for ch in VOWELS}


def _is_vowel(ch: str) -> bool:
    return ch.lower() in _VOWELS_LOWER


def _is_consonant(ch: str) -> bool:
    return ch.lower() in (VOICED | VOICELESS | SONOROUS_CONS | {"й"})


def transcribe(word: str) -> str:
    """Фонетическая транскрипция русского слова.

    Args:
        word: русское слово

    Returns:
        Строка транскрипции (упрощённая фонетическая запись)
    """
    w = word.lower().strip()
    if not w:
        return ""

    # Шаг 0: обработка «ого/его» в окончаниях прилагательных
    w = _apply_ogo_rule(w)

    # Шаг 1: развернуть йотированные гласные и мягкость
    phonemes = _expand_to_phonemes(w)

    # Шаг 2: ассимиляция по звонкости/глухости
    phonemes = _apply_assimilation(phonemes)

    # Шаг 3: оглушение на конце слова
    phonemes = _devoice_final(phonemes)

    return "".join(phonemes)


def _apply_ogo_rule(word: str) -> str:
    """Замена «ого/его» → «ово/ево» в окончаниях."""
    if len(word) >= 4:
        if word.endswith("ого"):
            return word[:-3] + "ово"
        if word.endswith("его"):
            return word[:-3] + "ево"
    return word


def _expand_to_phonemes(word: str) -> list[str]:
    """Развернуть буквы в фонемы с учётом мягкости и йотации."""
    result = []
    i = 0
    while i < len(word):
        ch = word[i]

        if ch == "ъ":
            # Твёрдый знак — просто разделитель, пропускаем
            i += 1
            continue

        if ch == "ь":
            # Мягкий знак — смягчает предыдущую согласную
            if result and not result[-1].endswith("'") and _is_base_consonant(result[-1]):
                result[-1] = result[-1] + "'"
            i += 1
            continue

        if ch in YOTATED:
            y, vowel = YOTATED[ch]
            if i == 0 or _is_vowel(word[i - 1]) or word[i - 1] in "ъь":
                # После гласной, в начале слова, после ъ/ь — йотация
                result.append(y)
                result.append(vowel)
            else:
                # После согласной — смягчение + гласная
                if result and _is_base_consonant(result[-1]):
                    if result[-1].rstrip("'") not in ALWAYS_HARD:
                        result[-1] = result[-1].rstrip("'") + "'"
                result.append(vowel)
            i += 1
            continue

        if ch == "и":
            # «и» смягчает предыдущую согласную
            if result and _is_base_consonant(result[-1]):
                if result[-1].rstrip("'") not in ALWAYS_HARD:
                    result[-1] = result[-1].rstrip("'") + "'"
            result.append("и")
            i += 1
            continue

        if _is_consonant(ch):
            phoneme = ch
            # Всегда мягкие
            if ch in ALWAYS_SOFT:
                phoneme = ch + "'"
            # Проверяем, смягчает ли следующая буква
            elif ch not in ALWAYS_HARD and i + 1 < len(word) and word[i + 1] in SOFTENING_VOWELS:
                phoneme = ch + "'"
            result.append(phoneme)
            i += 1
            continue

        # Обычная гласная (а, о, у, э, ы)
        result.append(ch)
        i += 1

    return result


def _is_base_consonant(phoneme: str) -> bool:
    """Проверить, является ли фонема согласной (возможно с мягкостью)."""
    base = phoneme.rstrip("'")
    return base in (VOICED | VOICELESS | SONOROUS_CONS | {"й"})


def _apply_assimilation(phonemes: list[str]) -> list[str]:
    """Ассимиляция по звонкости/глухости в кластерах согласных."""
    result = list(phonemes)
    for i in range(len(result) - 1):
        base_cur = result[i].rstrip("'")
        base_next = result[i + 1].rstrip("'")
        soft = "'" if result[i].endswith("'") else ""

        # Звонкий перед глухим → оглушается
        if base_cur in VOICED and base_next in VOICELESS:
            result[i] = DEVOICE[base_cur] + soft

        # Глухой перед звонким (не сонорным) → озвончается
        elif base_cur in VOICELESS and base_next in VOICED:
            if base_cur in VOICE:
                result[i] = VOICE[base_cur] + soft

    return result


def _devoice_final(phonemes: list[str]) -> list[str]:
    """Оглушение звонких согласных на конце слова."""
    if not phonemes:
        return phonemes
    result = list(phonemes)
    # Идём с конца, оглушаем последние согласные
    for i in range(len(result) - 1, -1, -1):
        base = result[i].rstrip("'")
        soft = "'" if result[i].endswith("'") else ""
        if base in VOICED:
            result[i] = DEVOICE[base] + soft
        elif base in (VOICELESS | SONOROUS_CONS | {"й"}):
            break  # Дальше не оглушаем
        else:
            break  # Гласная — стоп
    return result


def rhyme_tail(word: str, stress_pos: int | None = None) -> str:
    """Получить фонетический «хвост» слова от ударной гласной.

    Args:
        word: русское слово
        stress_pos: позиция ударного слога (0-indexed).
                    Если None, используется StressAnalyzer.

    Returns:
        Фонетическая транскрипция от ударной гласной до конца слова.
    """
    if stress_pos is None:
        from poetryforge.phonetics.stress import StressAnalyzer
        sa = StressAnalyzer()
        stress_pos = sa.get_stress(word)
        if stress_pos is None:
            return ""

    # Транскрибируем всё слово
    full = transcribe(word)

    # Находим ударную гласную (stress_pos-й гласный звук в транскрипции)
    vowel_count = 0
    for i, ch in enumerate(full):
        if ch in _VOWELS_LOWER:
            if vowel_count == stress_pos:
                return full[i:]
            vowel_count += 1

    return full


def transcribe_phrase(text: str) -> str:
    """Транскрибировать фразу (одно или несколько слов) в единый фонетический поток.

    Применяет ого-правило пословно, затем объединяет и выполняет
    ассимиляцию и оглушение как для единого слова (корректная
    обработка стыков слов).

    Args:
        text: одно слово или фраза (например, «триста лет»)

    Returns:
        Склеенная транскрипция всех слов.
    """
    words = re.findall(r"[а-яёА-ЯЁ]+", text.lower())
    if not words:
        return ""
    if len(words) == 1:
        return transcribe(words[0])

    # Применяем ого-правило к каждому слову, затем склеиваем
    processed = "".join(_apply_ogo_rule(w) for w in words)

    # Общая обработка как единого слова
    phonemes = _expand_to_phonemes(processed)
    phonemes = _apply_assimilation(phonemes)
    phonemes = _devoice_final(phonemes)
    return "".join(phonemes)


def consonant_skeleton(transcription: str) -> str:
    """Извлечь согласный каркас из транскрипции.

    Убирает гласные, оставляет согласные с мягкостью.
    Например: «с'иб'а» → «с'б'», «бр_н'» для «брон'а».

    Args:
        transcription: фонетическая транскрипция (результат transcribe/transcribe_phrase)

    Returns:
        Строка только из согласных (с маркерами мягкости).
    """
    result = []
    i = 0
    while i < len(transcription):
        ch = transcription[i]
        if ch == "'":
            # Мягкость — добавить к последнему
            if result:
                result[-1] = result[-1] + "'"
            i += 1
            continue
        if ch not in _VOWELS_LOWER:
            result.append(ch)
        i += 1
    return "".join(result)


def normalize_skeleton(skeleton: str) -> str:
    """Нормализовать согласный скелет: привести звонкие/глухие пары к одному виду.

    Это позволяет считать б/п, в/ф, г/к, д/т, ж/ш, з/с эквивалентными.
    """
    result = []
    i = 0
    while i < len(skeleton):
        ch = skeleton[i]
        soft = ""
        if i + 1 < len(skeleton) and skeleton[i + 1] == "'":
            soft = "'"
            i += 1
        # Нормализуем звонкие к глухим
        base = DEVOICE.get(ch, ch)
        result.append(base + soft)
        i += 1
    return "".join(result)


def reverse_consonant_key(word: str) -> str:
    """Получить обратный согласный ключ слова для индексации глубоких рифм.

    Транскрибирует слово, извлекает согласный скелет, переворачивает.
    Слова с одинаковым обратным ключом — кандидаты на глубокую рифму.
    """
    t = transcribe(word)
    sk = consonant_skeleton(t)
    return sk[::-1]

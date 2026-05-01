"""Модуль слогоделения русских слов.

Реализует правила русского слогоделения:
- Слогообразующий элемент — гласная
- Правило восходящей звучности (стечение согласных отходит к следующему слогу)
- Исключения: сонорный перед шумным, «й» перед согласной
"""

VOWELS = set("аеёиоуыэюяАЕЁИОУЫЭЮЯ")

# Сонорные согласные
SONOROUS = set("лмнрйЛМНРЙ")

# Шумные согласные (звонкие и глухие)
NOISY = set("бвгджзкпстфхцчшщБВГДЖЗКПСТФХЦЧШЩ")

# Й — всегда отходит к предыдущему слогу перед согласной
Y_LETTER = set("йЙ")


def _is_vowel(ch: str) -> bool:
    return ch in VOWELS


def _is_consonant(ch: str) -> bool:
    return ch in SONOROUS or ch in NOISY


def _is_sonorous(ch: str) -> bool:
    return ch in SONOROUS and ch not in Y_LETTER


def _is_y(ch: str) -> bool:
    return ch in Y_LETTER


def syllabify(word: str) -> dict:
    """Разбить слово на слоги.

    Args:
        word: Русское слово (без пробелов и знаков препинания).

    Returns:
        dict с ключами:
            word: исходное слово
            syllables: список слогов
            count: количество слогов
    """
    if not word:
        return {"word": word, "syllables": [], "count": 0}

    # Убираем мягкий и твёрдый знаки из анализа, но сохраняем в выводе
    # Находим позиции гласных — они определяют границы слогов
    vowel_positions = [i for i, ch in enumerate(word) if _is_vowel(ch)]

    if not vowel_positions:
        # Нет гласных — нет слогов (предлоги «в», «к» и т.п.)
        return {"word": word, "syllables": [word], "count": 0}

    if len(vowel_positions) == 1:
        return {"word": word, "syllables": [word], "count": 1}

    # Определяем границы слогов между каждой парой гласных
    boundaries = []
    for idx in range(len(vowel_positions) - 1):
        v1 = vowel_positions[idx]
        v2 = vowel_positions[idx + 1]

        # Символы между двумя гласными
        between = word[v1 + 1 : v2]

        if len(between) == 0:
            # Две гласные подряд — граница между ними
            boundaries.append(v2)
        elif len(between) == 1:
            # Одна согласная — отходит к следующему слогу
            boundaries.append(v1 + 1)
        else:
            # Несколько согласных между гласными — определяем границу
            split_pos = _find_split_in_cluster(between, v1 + 1)
            boundaries.append(split_pos)

    # Разбиваем слово по найденным границам
    syllables = []
    start = 0
    for b in boundaries:
        syllables.append(word[start:b])
        start = b
    syllables.append(word[start:])

    return {"word": word, "syllables": syllables, "count": len(syllables)}


def _find_split_in_cluster(cluster: str, offset: int) -> int:
    """Найти позицию разбиения в группе согласных между двумя гласными.

    Правила:
    1. «й» перед согласной — отходит к предыдущему слогу (бой-ня)
    2. Сонорный перед шумным — сонорный отходит к предыдущему слогу (кон-тра)
    3. Иначе — вся группа отходит к следующему слогу (мо-сква)

    Args:
        cluster: группа согласных/знаков между гласными
        offset: позиция начала группы в исходном слове

    Returns:
        Абсолютная позиция разбиения в слове
    """
    # Приоритет правил: ъ/ь → й → сонорный+шумный → всё к следующему слогу
    # Ищем первое подходящее правило слева направо
    best_split = None

    for i in range(len(cluster)):
        ch = cluster[i]

        # Мягкий/твёрдый знак — граница после знака (всегда приоритет)
        if ch in "ьъЬЪ":
            return offset + i + 1

        # «й» перед согласной — граница после «й»
        if _is_y(ch) and i < len(cluster) - 1:
            return offset + i + 1

        # Сонорный перед шумным — граница после сонорного
        if best_split is None and _is_sonorous(ch) and i < len(cluster) - 1:
            next_ch = cluster[i + 1]
            if next_ch in NOISY:
                best_split = offset + i + 1

    if best_split is not None:
        return best_split

    # По умолчанию вся группа отходит к следующему слогу
    return offset


def count_syllables(word: str) -> int:
    """Быстрый подсчёт количества слогов (= количество гласных)."""
    return sum(1 for ch in word if _is_vowel(ch))

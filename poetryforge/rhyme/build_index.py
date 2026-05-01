"""Скрипт для построения индекса рифм из словаря.

Использование:
    uv run python -m poetryforge.rhyme.build_index [путь_к_файлу_слов]

По умолчанию ищет data/words.txt (один-слово-на-строку).
"""

import sys
from pathlib import Path

from poetryforge.rhyme.rhyme_db import RhymeDB

_DATA_DIR = Path(__file__).parent.parent / "data"
_DEFAULT_WORDS = _DATA_DIR / "words.txt"


def main():
    words_path = Path(sys.argv[1]) if len(sys.argv) > 1 else _DEFAULT_WORDS

    if not words_path.exists():
        print(f"Файл не найден: {words_path}")
        print("Скачайте словарь, например:")
        print("  curl -sL https://raw.githubusercontent.com/hingston/russian/master/10000-russian-words.txt -o poetryforge/data/words.txt")
        sys.exit(1)

    words = words_path.read_text(encoding="utf-8").strip().split("\n")
    print(f"Загружено {len(words)} слов из {words_path}")

    db = RhymeDB()
    print("Строю индекс...")
    db.build_index(words, progress=True)
    print(f"Готово! Классический индекс: {db.size} слов в {len(db._index)} группах")
    print(f"Глубокий индекс: {len(db._transcriptions)} слов в {len(db._deep_index)} группах")


if __name__ == "__main__":
    main()

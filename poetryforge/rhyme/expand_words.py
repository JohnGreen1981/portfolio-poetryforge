"""Расширение словаря лемм до всех словоформ через pymorphy3.

Использование:
    uv run python -m poetryforge.rhyme.expand_words [входной_файл] [выходной_файл]

По умолчанию:
    вход:  data/words.txt (100K лемм)
    выход: data/words_expanded.txt
"""

import sys
from pathlib import Path

import pymorphy3

_DATA_DIR = Path(__file__).parent.parent / "data"
_DEFAULT_INPUT = _DATA_DIR / "words.txt"
_DEFAULT_OUTPUT = _DATA_DIR / "words_expanded.txt"


def expand(input_path: Path, output_path: Path):
    morph = pymorphy3.MorphAnalyzer()

    words = input_path.read_text(encoding="utf-8").strip().split("\n")
    print(f"Загружено {len(words)} лемм из {input_path}")

    all_forms: set[str] = set()
    total = len(words)

    for i, word in enumerate(words):
        if (i + 1) % 5000 == 0:
            print(f"  {i + 1}/{total}... ({len(all_forms)} форм)")

        word = word.strip().lower()
        if not word:
            continue

        all_forms.add(word)

        # Получаем все словоформы через pymorphy3
        try:
            parses = morph.parse(word)
            if parses:
                for form_obj in parses[0].lexeme:
                    form = form_obj.word
                    if form:
                        all_forms.add(form)
        except Exception:
            continue

    # Сортируем и сохраняем
    sorted_forms = sorted(all_forms)
    output_path.write_text("\n".join(sorted_forms), encoding="utf-8")
    print(f"Готово! {len(sorted_forms)} уникальных словоформ → {output_path}")


def main():
    input_path = Path(sys.argv[1]) if len(sys.argv) > 1 else _DEFAULT_INPUT
    output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else _DEFAULT_OUTPUT

    if not input_path.exists():
        print(f"Файл не найден: {input_path}")
        sys.exit(1)

    expand(input_path, output_path)


if __name__ == "__main__":
    main()

# PoetryForge

CLI-тулкит для анализа русской силлаботонической поэзии. Внешний фонетический валидатор для LLM: Claude генерирует стихи, poetryforge проверяет метр и рифму, Claude исправляет — до сходимости.

## Зачем

LLM не контролируют метр и рифму в русской силлаботонике. Причина — BPE-токенизатор не совпадает со слоговыми границами, у модели нет информации об ударениях. PoetryForge компенсирует эту слепую зону.

## Возможности

- **Анализ метра** — ямб, хорей, дактиль, амфибрахий, анапест, дольник, тактовик
- **Определение ударений** — каскад из 4 стратегий, 3.19M слов в словаре, 19K омографов
- **Разрешение омографов по метру** — за́мок/замо́к выбирается по контексту метрической схемы
- **Проверка рифм** — точные, приблизительные, ассонансные, глубокие (скелетные, containment)
- **Подбор рифм** — 1.13M словоформ в индексе, морфологическая разметка
- **Рифменная схема** — автоопределение (ABAB, ABBA, AABB и др.), строфы, клаузулы
- **Слогоделение** — по правилу восходящей звучности

## Установка

```bash
git clone <repo-url>
cd poetryforge
uv sync
```

Требования: Python >= 3.12, [uv](https://docs.astral.sh/uv/).

## Быстрый старт

```bash
# Анализ строки с проверкой метра
poetryforge analyze-line "Мой дядя самых честных правил" --meter iamb4

# Анализ стихотворения из файла
poetryforge analyze poem.txt --meter iamb4

# Проверка рифмы (классика + глубокие автоматически)
poetryforge rhyme-check "кровь" "любовь"

# Подбор рифм (все типы)
poetryforge rhyme "любовь" --type all --limit 10

# Расстановка ударений
poetryforge stress "Мой дядя самых честных правил"

# Слоговая разбивка
poetryforge syllables "перевоплощение"

# Пользовательский словарь ударений
poetryforge dict add "окоём" --stress 2
poetryforge dict list
poetryforge dict remove "окоём"
```

## Архитектура

```text
poetryforge/
├── phonetics/
│   ├── syllable.py        # слогоделение
│   ├── stress.py          # ударения (каскад: user_dict → ё → словарь → нейросеть)
│   ├── meter.py           # анализ метра, MeterAnalyzer
│   ├── meter_utils.py     # скоринг метров (регулярные + дольник/тактовик)
│   ├── g2p.py             # фонетическая транскрипция (правила, без внешних библиотек)
│   └── rhyme_scheme.py    # рифменная схема, клаузулы, строфы
├── rhyme/
│   ├── phonetic_rhyme.py  # проверка рифм (check, deep_check, full_check)
│   ├── rhyme_db.py        # подбор рифм по индексу (1.13M словоформ)
│   ├── build_index.py     # построение индексов
│   └── expand_words.py    # расширение лемм через pymorphy3
├── data/
│   ├── user_dict.json     # пользовательский словарь ударений
│   ├── words.txt          # generated data, не входит в git
│   ├── words_expanded.txt # generated data, не входит в git
│   ├── rhyme_index.json   # generated data, не входит в git
│   └── deep_rhyme_index.json  # generated data, не входит в git
└── cli.py                 # CLI (click)
```

## Данные и индексы

В публичный репозиторий не включены большие сгенерированные словари и индексы:

- `poetryforge/data/words.txt`
- `poetryforge/data/words_expanded.txt`
- `poetryforge/data/rhyme_index.json`
- `poetryforge/data/deep_rhyme_index.json`

Они нужны для полного подбора рифм, но не обязательны для чтения архитектуры, запуска большей части тестов и проверки метра/ударений. В production-сценарии такие файлы лучше хранить как release artifacts или пересобирать отдельным шагом.

Базовая сборка индекса:

```bash
uv run python -m poetryforge.rhyme.build_index
```

### Каскад определения ударений

```text
Слово → user_dict.json → буква «ё» → словарь ruaccent (3.19M, O(1)) → нейросеть ruaccent
                                              ↓ (омографы)
                                       meter feedback
                                  (перебор вариантов по метру)
```

1. **user_dict** — пользовательские переопределения (высший приоритет)
2. **Буква «ё»** — всегда ударная
3. **Словарный lookup** — O(1) по 3.19M слов, ~0.2 мкс/слово
4. **Нейросеть ruaccent** — fallback для неизвестных слов, ~5.5 мс/слово
5. **Meter feedback** — при `--meter`: перебор вариантов ударения омографов (19K слов) для максимального соответствия метру

### Типы рифм

| Тип         | Описание                         | Пример            |
| ----------- | -------------------------------- | ----------------- |
| exact       | Точное совпадение хвостов        | кровь/любовь      |
| approximate | Отличие в 1 звуке                | порог/далёк       |
| assonance   | Совпадение гласных               | радость/старость  |
| deep        | Глубокое фонетическое совпадение | себя/сипя         |
| skeleton    | Совпадение согласного скелета    | броня/браня       |
| containment | Одно слово содержит другое       | падаван/под диван |

### Метры

| Метр       | Код        | Тип             | Пример                 |
| ---------- | ---------- | --------------- | ---------------------- |
| Ямб        | iamb       | паттерн `01`    | iamb4 = четырёхстопный |
| Хорей      | trochee    | паттерн `10`    | trochee4               |
| Дактиль    | dactyl     | паттерн `100`   | dactyl3                |
| Амфибрахий | amphibrach | паттерн `010`   | amphibrach4            |
| Анапест    | anapest    | паттерн `001`   | anapest3               |
| Дольник    | dolnik     | интервалы 1–2   | dolnik3 = 3-иктовый    |
| Тактовик   | taktovik   | интервалы 1–3   | taktovik3 = 3-иктовый  |

Регулярные метры — сравнение с идеальным паттерном. Нерегулярные (дольник, тактовик) — интервальный анализ между иктами.

## Python API

```python
from poetryforge.phonetics.meter import MeterAnalyzer

ma = MeterAnalyzer()

# Одна строка
result = ma.analyze_line("Мой дядя самых честных правил", "iamb4")
# {
#   "line": "Мой дядя самых честных правил",
#   "syllable_count": 9,
#   "stress_pattern": "101010010",
#   "detected_meter": "iamb4",
#   "meter_score": 0.95,
#   "clausula": "feminine",
#   "issues": [...]
# }

# Стихотворение
result = ma.analyze_poem("""Мой дядя самых честных правил,
Когда не в шутку занемог,
Он уважать себя заставил
И лучше выдумать не мог.""", "iamb4")
# {
#   "lines": [...],
#   "poem_meter": "iamb4",
#   "poem_score": 0.95,
#   "rhyme_scheme": "ABAB",
#   "stanza_type": "quatrain",
#   "stanza_pattern": "cross"
# }
```

```python
from poetryforge.rhyme.phonetic_rhyme import RhymeAnalyzer
from poetryforge.phonetics.stress import StressAnalyzer

sa = StressAnalyzer()
ra = RhymeAnalyzer(sa)

# Проверка рифмы (классика + глубокие)
ra.full_check("кровь", "любовь")
# {"rhymes": True, "type": "exact", "quality": 1.0}
```

```python
from poetryforge.rhyme.rhyme_db import RhymeDB

rdb = RhymeDB()

# Подбор рифм
rdb.find_rhymes("любовь", limit=5)
# [{"word": "кровь", "type": "exact", "quality": 1.0, "pos_ru": "сущ.", ...}, ...]

# Глубокие рифмы
rdb.find_deep_rhymes("броня", limit=5)
# [{"word": "браня", "type": "deep", "depth": 0.85, "pos_ru": "деепричастие", ...}, ...]
```

## Тесты

```bash
uv run pytest           # все 167 тестов
uv run pytest -v        # подробный вывод
uv run pytest -k dolnik # только тесты дольника
```

9 тестовых файлов: слогоделение, ударения, метр, g2p, классические рифмы, глубокие рифмы, рифменные схемы, нерегулярные метры, разрешение омографов.

В clean repo без больших рифменных индексов ожидаемый результат: `161 passed, 6 skipped`. Пропускаются тесты `test_rhyme_db.py`, которым нужен построенный `rhyme_index.json`.

## Зависимости

| Пакет                                                    | Назначение                                        |
| -------------------------------------------------------- | ------------------------------------------------- |
| [ruaccent](https://github.com/Den4ikAI/ruaccent)         | Ударения: словарь 3.19M слов + BERT для омографов |
| [click](https://click.palletsprojects.com)               | CLI-фреймворк                                     |
| [pymorphy3](https://github.com/no-plagiarism/pymorphy3)  | Морфология: расширение словаря, POS-теги рифм     |
| [pytest](https://pytest.org)                             | Тесты (dev)                                       |

## Интеграция с Claude Code

`CLAUDE.md` в корне проекта является ссылкой на `AGENTS.md`, чтобы Codex и Claude Code читали один публичный контекст. Цикл генерации:

1. Claude генерирует черновик стихотворения
2. `poetryforge analyze --meter <метр>` проверяет метр и рифму
3. Claude читает issues и исправляет строки с severity "error"
4. Повтор до сходимости (макс. 5 итераций)

Принципы рифмовки при генерации:

- Минимум 15–20% рифменных пар — глубокие (deep, skeleton, containment)
- Предпочитать грамматически разнородные пары (разные части речи)
- Смысл первичен — глубокая рифма обогащает, но не в ущерб содержанию

## Статистика

- ~2,800 строк кода (core)
- ~1,240 строк тестов (167 тестов)
- 3.19M слов в словаре ударений
- 1.13M словоформ в рифменном индексе
- 19K омографов с meter feedback

## Лицензия

MIT

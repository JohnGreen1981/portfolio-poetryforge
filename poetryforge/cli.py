"""CLI-интерфейс PoetryForge."""

import json
import sys

import click

from poetryforge.phonetics.meter import MeterAnalyzer
from poetryforge.phonetics.stress import StressAnalyzer
from poetryforge.phonetics.syllable import syllabify
from poetryforge.rhyme.phonetic_rhyme import RhymeAnalyzer
from poetryforge.rhyme.rhyme_db import RhymeDB


def _output(data: dict | list, human: bool = False):
    """Вывести результат в JSON или человекочитаемом формате."""
    if human:
        click.echo(_format_human(data))
    else:
        click.echo(json.dumps(data, ensure_ascii=False, indent=2))


def _format_human(data) -> str:
    """Форматировать результат для человека."""
    if isinstance(data, list):
        return "\n".join(_format_human(item) for item in data)
    if isinstance(data, dict):
        lines = []
        for k, v in data.items():
            if k == "ambiguous_words" and isinstance(v, list):
                if v:
                    lines.append("  Омографы (разрешены по метру):")
                    for aw in v:
                        lines.append(
                            f"    {aw['word']}: ударение {aw['default']}→{aw['chosen']} "
                            f"(варианты: {aw['variants']})"
                        )
            elif k == "issues" and isinstance(v, list):
                if v:
                    lines.append("  Issues:")
                    for issue in v:
                        severity = issue.get("severity", "?").upper()
                        desc = issue.get("description", "")
                        lines.append(f"    [{severity}] {desc}")
            elif k == "lines" and isinstance(v, list):
                for line_data in v:
                    lines.append(_format_human(line_data))
                    lines.append("")
            elif k == "stanzas" and isinstance(v, list):
                if v:
                    lines.append("  Строфы:")
                    for i, stanza in enumerate(v, 1):
                        scheme = stanza.get("scheme", "?")
                        pattern_ru = stanza.get("pattern_ru") or "—"
                        lines.append(f"    {i}. {scheme} ({pattern_ru})")
            elif k == "stanza_type" and v:
                lines.append(f"  stanza_type: {v}")
            elif k == "stanza_pattern" and v:
                lines.append(f"  stanza_pattern: {v}")
            else:
                lines.append(f"  {k}: {v}")
        return "\n".join(lines)
    return str(data)


@click.group()
def cli():
    """PoetryForge — CLI-тулкит для анализа русской силлаботонической поэзии."""
    pass


@cli.command("analyze-line")
@click.argument("line")
@click.option("--meter", default=None, help="Ожидаемый метр (например, iamb4, trochee5)")
@click.option("--human", is_flag=True, help="Человекочитаемый вывод")
def analyze_line(line: str, meter: str | None, human: bool):
    """Анализ одной стихотворной строки."""
    ma = MeterAnalyzer()
    result = ma.analyze_line(line, meter)
    _output(result, human)


@cli.command("analyze")
@click.argument("file", required=False, type=click.Path(exists=True))
@click.option("--meter", default=None, help="Ожидаемый метр (например, iamb4)")
@click.option("--human", is_flag=True, help="Человекочитаемый вывод")
def analyze(file: str | None, meter: str | None, human: bool):
    """Анализ стихотворения из файла или stdin."""
    if file:
        with open(file, encoding="utf-8") as f:
            text = f.read()
    else:
        text = sys.stdin.read()

    ma = MeterAnalyzer()
    result = ma.analyze_poem(text, meter)
    _output(result, human)


@cli.command("stress")
@click.argument("line")
@click.option("--human", is_flag=True, help="Человекочитаемый вывод")
def stress_cmd(line: str, human: bool):
    """Расстановка ударений в строке."""
    sa = StressAnalyzer()
    result = sa.analyze(line)
    _output(result, human)


@cli.command("syllables")
@click.argument("word")
@click.option("--human", is_flag=True, help="Человекочитаемый вывод")
def syllables_cmd(word: str, human: bool):
    """Слоговая разбивка слова."""
    result = syllabify(word)
    _output(result, human)


@cli.command("rhyme-check")
@click.argument("word1")
@click.argument("word2")
@click.option("--classic-only", is_flag=True, help="Только классическая проверка (без глубоких рифм)")
@click.option("--human", is_flag=True, help="Человекочитаемый вывод")
def rhyme_check(word1: str, word2: str, classic_only: bool, human: bool):
    """Проверить, рифмуются ли два слова (или фразы).

    По умолчанию проверяет и классические, и глубокие рифмы.
    """
    ra = RhymeAnalyzer()
    if classic_only:
        result = ra.check(word1, word2)
    else:
        result = ra.full_check(word1, word2)
    _output(result, human)


@cli.command("rhyme")
@click.argument("word")
@click.option("--type", "rhyme_type", default="approximate",
              type=click.Choice(["exact", "approximate", "deep", "all"]),
              help="Тип рифмы: exact, approximate, deep, all (классика + глубокие)")
@click.option("--limit", default=10, help="Максимальное количество результатов")
@click.option("--human", is_flag=True, help="Человекочитаемый вывод")
def rhyme_cmd(word: str, rhyme_type: str, limit: int, human: bool):
    """Подобрать рифмы к слову."""
    db = RhymeDB()
    if db.size == 0:
        click.echo("Индекс рифм пуст. Постройте его:")
        click.echo("  uv run python -m poetryforge.rhyme.build_index")
        return

    if rhyme_type == "all":
        # Комбинированный поиск: классика + глубокие
        classic = db.find_rhymes(word, rhyme_type="approximate", limit=limit)
        deep = db.find_deep_rhymes(word, limit=limit)
        # Объединить, дедуплицировать
        seen = set()
        results = []
        for r in classic:
            if r["word"] not in seen:
                seen.add(r["word"])
                results.append(r)
        for r in deep:
            if r["word"] not in seen:
                seen.add(r["word"])
                results.append(r)
        results = results[:limit]
    elif rhyme_type == "deep":
        results = db.find_deep_rhymes(word, limit=limit)
    else:
        results = db.find_rhymes(word, rhyme_type=rhyme_type, limit=limit)

    if human:
        if not results:
            click.echo(f"Рифмы к «{word}» не найдены")
        else:
            click.echo(f"Рифмы к «{word}»:")
            for r in results:
                parts = [r["type"]]
                if r.get("depth") is not None:
                    parts.append(f"depth={r['depth']}")
                if r.get("pos_ru"):
                    parts.append(r["pos_ru"])
                if r.get("gram_match"):
                    parts.append("⚠ gram_match")
                click.echo(f"  {r['word']} ({', '.join(parts)})")
    else:
        _output(results)


@cli.group("dict")
def dict_group():
    """Управление пользовательским словарём ударений."""
    pass


@dict_group.command("add")
@click.argument("word")
@click.option("--stress", required=True, type=int, help="Позиция ударного слога (0-indexed)")
def dict_add(word: str, stress: int):
    """Добавить слово в пользовательский словарь."""
    sa = StressAnalyzer()
    sa.add_to_user_dict(word, stress)
    click.echo(f"Добавлено: {word} (ударение на слог {stress})")


@dict_group.command("remove")
@click.argument("word")
def dict_remove(word: str):
    """Удалить слово из пользовательского словаря."""
    sa = StressAnalyzer()
    sa.remove_from_user_dict(word)
    click.echo(f"Удалено: {word}")


@dict_group.command("list")
def dict_list():
    """Показать содержимое пользовательского словаря."""
    sa = StressAnalyzer()
    d = sa.list_user_dict()
    if not d:
        click.echo("Словарь пуст")
    else:
        for word, pos in d.items():
            click.echo(f"  {word}: ударение на слог {pos}")

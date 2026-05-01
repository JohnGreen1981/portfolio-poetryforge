import pytest

from poetryforge.phonetics.meter import MeterAnalyzer


@pytest.fixture(scope="module")
def ma():
    return MeterAnalyzer()


class TestAnalyzeLine:
    def test_pushkin_iamb4(self, ma):
        """Пушкин: «Мой дядя самых честных правил» — ямб-4."""
        result = ma.analyze_line("Мой дядя самых честных правил", "iamb4")
        assert result["detected_meter"] == "iamb4"
        assert result["meter_score"] >= 0.8

    def test_tyutchev_iamb4(self, ma):
        """Тютчев: «Люблю грозу в начале мая» — ямб-4."""
        result = ma.analyze_line("Люблю грозу в начале мая", "iamb4")
        assert result["detected_meter"] == "iamb4"
        assert result["meter_score"] >= 0.8

    def test_pushkin_onegin_2(self, ma):
        """Пушкин: «Когда не в шутку занемог» — ямб-4."""
        result = ma.analyze_line("Когда не в шутку занемог", "iamb4")
        assert result["detected_meter"] == "iamb4"
        assert result["meter_score"] >= 0.8

    def test_nekrasov_ternary(self, ma):
        """Некрасов: «Однажды в студёную зимнюю пору» — трёхсложный размер (12 слогов = 4 стопы)."""
        result = ma.analyze_line("Однажды в студёную зимнюю пору")
        # 12 слогов, трёхсложный размер (амфибрахий или анапест 4-стопный)
        assert result["syllable_count"] == 12
        assert any(m in result["detected_meter"] for m in ("amphibrach", "anapest"))
        assert result["meter_score"] >= 0.6

    def test_clausula_feminine(self, ma):
        """Женская клаузула: ударение на предпоследний слог."""
        result = ma.analyze_line("Мой дядя самых честных правил")
        assert result["clausula"] == "feminine"

    def test_clausula_masculine(self, ma):
        """Мужская клаузула: ударение на последний слог."""
        result = ma.analyze_line("Когда не в шутку занемог")
        assert result["clausula"] == "masculine"


class TestAutoDetect:
    def test_auto_detect_iamb(self, ma):
        """Автоопределение ямба без указания метра."""
        result = ma.analyze_line("Мой дядя самых честных правил")
        assert "iamb" in result["detected_meter"]

    def test_auto_detect_ternary(self, ma):
        """Автоопределение трёхсложного размера."""
        result = ma.analyze_line("Однажды в студёную зимнюю пору")
        assert any(m in result["detected_meter"] for m in ("amphibrach", "anapest"))


class TestAnalyzePoem:
    def test_onegin_stanza(self, ma):
        """Четверостишие Онегина — ямб-4."""
        poem = """Мой дядя самых честных правил,
Когда не в шутку занемог,
Он уважать себя заставил
И лучше выдумать не мог."""
        result = ma.analyze_poem(poem, "iamb4")
        assert result["poem_meter"] == "iamb4"
        assert result["poem_score"] >= 0.7
        assert len(result["lines"]) == 4

    def test_issues_severity(self, ma):
        """Проверка что severity корректно расставляются."""
        result = ma.analyze_line("Мой дядя самых честных правил", "iamb4")
        for issue in result["issues"]:
            assert issue["severity"] in ("error", "warning", "info")

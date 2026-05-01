import pytest

from poetryforge.rhyme.phonetic_rhyme import RhymeAnalyzer


@pytest.fixture(scope="module")
def ra():
    return RhymeAnalyzer()


class TestExactRhymes:
    def test_krov_lyubov(self, ra):
        """кровь/любовь — точная рифма."""
        result = ra.check("кровь", "любовь")
        assert result["rhymes"] is True
        assert result["type"] == "exact"
        assert result["quality"] == 1.0

    def test_den_ten(self, ra):
        """день/тень — точная рифма."""
        result = ra.check("день", "тень")
        assert result["rhymes"] is True
        assert result["type"] == "exact"
        assert result["quality"] == 1.0

    def test_pravil_zastavil(self, ra):
        """правил/заставил — точная рифма."""
        result = ra.check("правил", "заставил")
        assert result["rhymes"] is True
        assert result["type"] == "exact"

    def test_zanemog_mog(self, ra):
        """занемог/мог — точная рифма."""
        result = ra.check("занемог", "мог")
        assert result["rhymes"] is True
        assert result["type"] == "exact"


class TestApproximateRhymes:
    def test_approximate(self, ra):
        """Приблизительная рифма — отличие в 1 звуке."""
        result = ra.check("радость", "старость")
        assert result["rhymes"] is True
        assert result["quality"] >= 0.5


class TestNoRhyme:
    def test_no_rhyme(self, ra):
        """Слова без рифмы."""
        result = ra.check("стол", "дверь")
        assert result["rhymes"] is False
        assert result["quality"] == 0.0

    def test_symmetric(self, ra):
        """Проверка рифмы симметрична."""
        r1 = ra.check("кровь", "любовь")
        r2 = ra.check("любовь", "кровь")
        assert r1["rhymes"] == r2["rhymes"]
        assert r1["type"] == r2["type"]


class TestFullCheck:
    """Тесты full_check() — объединённая проверка классика + глубокие."""

    def test_classic_exact(self, ra):
        """Точная классическая рифма — быстрый путь."""
        r = ra.full_check("кровь", "любовь")
        assert r["rhymes"] is True
        assert r["type"] == "exact"
        assert r["quality"] == 1.0
        assert r["depth"] is None  # классика, без глубины

    def test_deep_fallback(self, ra):
        """Глубокая рифма — fallback для составной пары."""
        r = ra.full_check("триста лет", "пистолет")
        assert r["rhymes"] is True
        assert r["type"] in ("skeleton", "deep")
        assert r["depth"] is not None
        assert r["depth"] is not None

    def test_no_rhyme(self, ra):
        """Нерифмующаяся пара."""
        r = ra.full_check("стол", "кошка")
        assert r["rhymes"] is False
        assert r["quality"] == 0.0

    def test_result_format(self, ra):
        """Все обязательные ключи в результате."""
        r = ra.full_check("день", "тень")
        assert "rhymes" in r
        assert "type" in r
        assert "quality" in r
        assert "depth" in r

    def test_symmetric(self, ra):
        """full_check симметричен."""
        r1 = ra.full_check("броня", "браня")
        r2 = ra.full_check("браня", "броня")
        assert r1["rhymes"] == r2["rhymes"]
        assert r1["type"] == r2["type"]

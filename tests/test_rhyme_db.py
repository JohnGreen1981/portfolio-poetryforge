import pytest

from poetryforge.rhyme.rhyme_db import RhymeDB


@pytest.fixture(scope="module")
def db():
    rdb = RhymeDB()
    if rdb.size == 0:
        pytest.skip("Rhyme index not built")
    return rdb


def test_index_loaded(db):
    assert db.size > 0


def test_exact_rhyme_lyubov(db):
    """любовь → кровь (exact)."""
    results = db.find_rhymes("любовь", rhyme_type="exact", limit=50)
    words = [r["word"] for r in results]
    assert "кровь" in words
    assert all(r["type"] == "exact" for r in results)


def test_exact_rhyme_odinochestvo(db):
    """одиночество → пророчество (exact)."""
    results = db.find_rhymes("одиночество", rhyme_type="exact", limit=10)
    words = [r["word"] for r in results]
    assert "пророчество" in words


def test_approximate_returns_more(db):
    """Approximate возвращает больше результатов, чем exact."""
    exact = db.find_rhymes("день", rhyme_type="exact", limit=20)
    approx = db.find_rhymes("день", rhyme_type="approximate", limit=20)
    assert len(approx) >= len(exact)


def test_no_self_in_results(db):
    """Слово не рифмуется само с собой."""
    results = db.find_rhymes("любовь", rhyme_type="approximate", limit=50)
    words = [r["word"] for r in results]
    assert "любовь" not in words


def test_unknown_word(db):
    """Несуществующее слово — пустой результат."""
    results = db.find_rhymes("ываыва", rhyme_type="exact", limit=10)
    assert results == []

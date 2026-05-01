from poetryforge.phonetics.syllable import syllabify, count_syllables


def test_two_syllables():
    result = syllabify("Москва")
    assert result["count"] == 2
    assert result["syllables"] == ["Мо", "сква"]


def test_single_syllable():
    result = syllabify("страсть")
    assert result["count"] == 1
    assert result["syllables"] == ["страсть"]


def test_many_syllables():
    result = syllabify("перевоплощение")
    assert result["count"] == 7


def test_sonorous_before_noisy():
    """Сонорный перед шумным — отходит к предыдущему слогу."""
    result = syllabify("контракт")
    assert result["count"] == 2
    assert result["syllables"][0] == "кон"


def test_y_before_consonant():
    """Й перед согласной — отходит к предыдущему слогу."""
    result = syllabify("бойня")
    assert result["count"] == 2
    assert result["syllables"] == ["бой", "ня"]


def test_two_vowels_adjacent():
    """Две гласные подряд — разные слоги."""
    result = syllabify("поэт")
    assert result["count"] == 2
    assert result["syllables"] == ["по", "эт"]


def test_soft_sign():
    """Мягкий знак — граница после него."""
    result = syllabify("письмо")
    assert result["count"] == 2
    assert result["syllables"] == ["пись", "мо"]


def test_hard_sign():
    """Твёрдый знак — граница после него."""
    result = syllabify("объект")
    assert result["count"] == 2
    assert result["syllables"] == ["объ", "ект"]


def test_empty_string():
    result = syllabify("")
    assert result["count"] == 0
    assert result["syllables"] == []


def test_no_vowels():
    """Слово без гласных (предлог «в»)."""
    result = syllabify("в")
    assert result["count"] == 0


def test_yo_letter():
    result = syllabify("ёж")
    assert result["count"] == 1


def test_count_syllables():
    assert count_syllables("перевоплощение") == 7
    assert count_syllables("Москва") == 2
    assert count_syllables("в") == 0


def test_dyadya():
    result = syllabify("дядя")
    assert result["count"] == 2
    assert result["syllables"] == ["дя", "дя"]


def test_pravil():
    result = syllabify("правил")
    assert result["count"] == 2
    assert result["syllables"] == ["пра", "вил"]

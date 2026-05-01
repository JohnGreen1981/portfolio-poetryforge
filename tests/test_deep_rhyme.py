"""Тесты глубоких рифм: панторифма, составная, паронимическая, containment."""

import pytest

from poetryforge.phonetics.g2p import (
    transcribe_phrase,
    consonant_skeleton,
    normalize_skeleton,
)
from poetryforge.rhyme.phonetic_rhyme import RhymeAnalyzer


@pytest.fixture(scope="module")
def ra():
    return RhymeAnalyzer()


# --- g2p: transcribe_phrase ---

class TestTranscribePhrase:
    def test_single_word(self):
        assert transcribe_phrase("кровь") == transcribe_phrase("кровь")

    def test_multi_word_joins(self):
        """Составная фраза транскрибируется как поток."""
        t = transcribe_phrase("триста лет")
        assert "л" in t  # буква «л» из «лет» присутствует
        assert "т" in t

    def test_cross_word_no_double_devoicing(self):
        """«под диван» — д перед д' не оглушается на стыке."""
        t = transcribe_phrase("под диван")
        # Не должно быть «пот» + «д'иван» (т.е. «потд'иван»)
        # Правильно: слитная транскрипция без ложного оглушения
        assert "т" not in t[:3]  # начало не «пот»


# --- g2p: consonant_skeleton ---

class TestConsonantSkeleton:
    def test_basic(self):
        sk = consonant_skeleton("брон'а")
        assert "а" not in sk
        assert "о" not in sk
        assert "н'" in sk

    def test_empty(self):
        assert consonant_skeleton("") == ""
        assert consonant_skeleton("аоу") == ""


# --- g2p: normalize_skeleton ---

class TestNormalizeSkeleton:
    def test_devoice_pairs(self):
        """Звонкие нормализуются к глухим."""
        assert normalize_skeleton("б") == "п"
        assert normalize_skeleton("д'") == "т'"
        assert normalize_skeleton("з") == "с"

    def test_already_voiceless(self):
        assert normalize_skeleton("п") == "п"
        assert normalize_skeleton("т'") == "т'"

    def test_sebya_sipya_match(self):
        """себя и сипя дают одинаковый нормализованный скелет."""
        sk1 = consonant_skeleton(transcribe_phrase("себя"))
        sk2 = consonant_skeleton(transcribe_phrase("сипя"))
        assert normalize_skeleton(sk1) == normalize_skeleton(sk2)


# --- deep_check: все примеры из ТЗ ---

class TestDeepRhymePairs:
    """Все пары из задания пользователя должны распознаваться."""

    def test_sebya_sipya(self, ra):
        """себя — сипя (совпадение согласного каркаса с_п/б_я)."""
        r = ra.deep_check("себя", "сипя")
        assert r["rhymes"] is True
        assert r["type"] == "skeleton"

    def test_trista_let_pistolet(self, ra):
        """триста лет — пистолет (составная рифма)."""
        r = ra.deep_check("триста лет", "пистолет")
        assert r["rhymes"] is True
        assert r["depth"] >= 0.7

    def test_padavan_pod_divan(self, ra):
        """падаван — под диван (составная, «аван/диван»)."""
        r = ra.deep_check("падаван", "под диван")
        assert r["rhymes"] is True

    def test_ozhidaya_dzhedaya(self, ra):
        """ожидая — джедая (глубокое созвучие _д_ая)."""
        r = ra.deep_check("ожидая", "джедая")
        assert r["rhymes"] is True
        assert r["type"] == "deep"

    def test_past_upast(self, ra):
        """пасть — упасть (containment)."""
        r = ra.deep_check("пасть", "упасть")
        assert r["rhymes"] is True
        assert r["type"] == "containment"
        assert r["quality"] >= 0.9

    def test_zashity_zashchity(self, ra):
        """зашиты — защиты (паронимическая пара ш/щ)."""
        r = ra.deep_check("зашиты", "защиты")
        assert r["rhymes"] is True

    def test_pozhalet_ozheledj(self, ra):
        """пожалеть — ожеледь (глубокая предударная зона)."""
        r = ra.deep_check("пожалеть", "ожеледь")
        assert r["rhymes"] is True
        assert r["depth"] >= 0.5

    def test_bronya_branya(self, ra):
        """броня — браня (корневой каркас бр_ня)."""
        r = ra.deep_check("броня", "браня")
        assert r["rhymes"] is True
        assert r["type"] == "skeleton"
        assert r["depth"] >= 0.8


# --- Негативные примеры ---

class TestDeepRhymeNegative:
    def test_no_rhyme_unrelated(self, ra):
        """Совсем разные слова не рифмуются."""
        r = ra.deep_check("стол", "кошка")
        assert r["rhymes"] is False

    def test_no_rhyme_distant(self, ra):
        """Далёкие слова не рифмуются."""
        r = ra.deep_check("дерево", "молоко")
        assert r["rhymes"] is False

    def test_stressed_vowel_mismatch(self, ra):
        """Слова с разным ударным гласным не рифмуются глубоко."""
        # крокодИл (и) vs кодИла (и → но заударная часть отличается)
        # На самом деле оба на «и», но структура разная — проверяем
        # более явный случай: разные ударные гласные
        r = ra.deep_check("стола", "села")  # о vs е
        assert r["rhymes"] is False

    def test_symmetric(self, ra):
        """Глубокая рифма симметрична."""
        r1 = ra.deep_check("броня", "браня")
        r2 = ra.deep_check("браня", "броня")
        assert r1["rhymes"] == r2["rhymes"]
        assert r1["type"] == r2["type"]


# --- Морфологическая разметка и антиграмматический фильтр ---

class TestMorphAnnotation:
    """Тесты морфоразметки и антиграмматического фильтра в rhyme_db."""

    @pytest.fixture(scope="class")
    def morph(self):
        import pymorphy3
        return pymorphy3.MorphAnalyzer()

    def test_morph_info_noun(self, morph):
        from poetryforge.rhyme.rhyme_db import _morph_info
        info = _morph_info(morph, "стол")
        assert info["pos"] == "NOUN"
        assert info["pos_ru"] == "сущ."

    def test_morph_info_verb(self, morph):
        from poetryforge.rhyme.rhyme_db import _morph_info
        info = _morph_info(morph, "бежать")
        assert info["pos"] in ("INFN", "VERB")
        assert info["pos_ru"] is not None

    def test_morph_info_empty(self, morph):
        from poetryforge.rhyme.rhyme_db import _morph_info
        info = _morph_info(morph, "")
        assert info["pos"] is None

    def test_gram_matches_same_pos(self, morph):
        from poetryforge.rhyme.rhyme_db import _morph_info, _gram_matches
        info1 = _morph_info(morph, "бежали")
        info2 = _morph_info(morph, "лежали")
        assert _gram_matches(info1, info2) is True

    def test_gram_no_match_diff_pos(self, morph):
        from poetryforge.rhyme.rhyme_db import _morph_info, _gram_matches
        info1 = _morph_info(morph, "бежали")
        info2 = _morph_info(morph, "печали")
        assert _gram_matches(info1, info2) is False

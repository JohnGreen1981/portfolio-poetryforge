from poetryforge.phonetics.g2p import transcribe, rhyme_tail


class TestTranscribe:
    def test_devoice_final_voiced(self):
        """Оглушение на конце: город → горат."""
        t = transcribe("город")
        assert t.endswith("т")
        # д → т на конце
        assert "д" not in t[-1]

    def test_devoice_v_to_f(self):
        """Оглушение в → ф: кровь → кроф'."""
        t = transcribe("кровь")
        assert "ф'" in t

    def test_devoice_lyubov(self):
        """любовь → оканчивается на ф'."""
        t = transcribe("любовь")
        assert t.endswith("ф'")

    def test_ogo_ending(self):
        """«ого» → «ово» в окончаниях."""
        t = transcribe("большого")
        assert "ово" in t

    def test_ego_ending(self):
        """«его» → «ево» в окончаниях; «е» после гласной йотируется → «йэво»."""
        t = transcribe("моего")
        assert "эво" in t

    def test_yotated_start(self):
        """Йотированная в начале слова: яма → йама."""
        t = transcribe("яма")
        assert t.startswith("й")

    def test_soft_sign(self):
        """Мягкий знак: день → д'эн'."""
        t = transcribe("день")
        assert "д'" in t
        assert "н'" in t

    def test_always_soft(self):
        """Ч и Щ всегда мягкие."""
        t = transcribe("чаща")
        assert "ч'" in t
        assert "щ'" in t

    def test_empty(self):
        assert transcribe("") == ""


class TestRhymeTail:
    def test_gorod(self):
        """город — хвост от ударной «о» (слог 0)."""
        tail = rhyme_tail("город", stress_pos=0)
        # город: [горат], ударение на первый слог
        # хвост от «о»: «орат»
        assert tail.startswith("о")
        assert tail.endswith("т")

    def test_krov(self):
        """кровь — хвост [оф']."""
        tail = rhyme_tail("кровь", stress_pos=0)
        assert "о" in tail
        assert tail.endswith("ф'")

    def test_lyubov(self):
        """любовь — хвост [оф']."""
        tail = rhyme_tail("любовь", stress_pos=1)
        assert "о" in tail
        assert tail.endswith("ф'")

    def test_krov_lyubov_match(self):
        """кровь и любовь — одинаковые хвосты."""
        t1 = rhyme_tail("кровь", stress_pos=0)
        t2 = rhyme_tail("любовь", stress_pos=1)
        assert t1 == t2

    def test_den_ten_match(self):
        """день и тень — одинаковые хвосты."""
        t1 = rhyme_tail("день", stress_pos=0)
        t2 = rhyme_tail("тень", stress_pos=0)
        assert t1 == t2

    def test_pravil_zastavil_match(self):
        """правил и заставил — рифмуются."""
        t1 = rhyme_tail("правил", stress_pos=0)
        t2 = rhyme_tail("заставил", stress_pos=1)
        assert t1 == t2

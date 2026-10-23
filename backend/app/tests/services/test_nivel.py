from app.services.nivel import rotulo_nivel


def test_nivel_0_e_o_absoluto():
    assert rotulo_nivel(0) == "ABSOLUTO"


def test_nivel_1_e_nivel_1_de_verdade():
    assert rotulo_nivel(1) == "Nível 1"


def test_niveis_2_a_4_mostram_nivel_n():
    assert [rotulo_nivel(n) for n in (2, 3, 4)] == ["Nível 2", "Nível 3", "Nível 4"]

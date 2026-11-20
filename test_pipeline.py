"""Testes: decoder vs scheptk, consistência do baseline, CP-SAT e Busca Tabu."""
import random
from pathlib import Path

import pytest

from src.baseline import RULES, dispatch
from src.cpsat_model import solve_cpsat
from src.decoder import base_sequence, decode, evaluate, random_sequence
from src.generator import generate
from src.instance import load_jsplib
from src.tabu_search import tabu_search

BENCH = Path(__file__).resolve().parent.parent / "data" / "benchmarks"


def test_generator_reprodutivel():
    a, b = generate(15, 7), generate(15, 7)
    assert (a.route, a.p, a.due) == (b.route, b.p, b.due)
    assert generate(15, 8).p != a.p


def test_decoder_vs_scheptk(tmp_path):
    scheptk = pytest.importorskip("scheptk.scheptk")
    inst = generate(12, 3, only_family=0)  # rota completa (única condição aceita pelo scheptk)
    f = tmp_path / "i.txt"
    inst.to_scheptk(f)
    js = scheptk.JobShop(str(f))
    rng = random.Random(0)
    for _ in range(25):
        s = random_sequence(inst, rng)
        assert evaluate(inst, s) == (js.Cmax(s), js.SumTj(s))


def test_rotas_variaveis_sem_scheptk():
    inst = generate(10, 1)
    assert not inst.is_complete()
    with pytest.raises(ValueError):
        inst.to_scheptk("x.txt")


@pytest.mark.parametrize("rule", RULES)
def test_baseline_valido_e_sem_sobreposicao(rule):
    inst = generate(20, 5)
    seq = dispatch(inst, rule)
    assert sorted(seq) == sorted(base_sequence(inst))
    sch = decode(inst, seq)
    for ops in sch.ops_by_machine:  # sem sobreposição na estação
        for (s1, e1, *_), (s2, e2, *_) in zip(ops, ops[1:]):
            assert e1 <= s2
    for j in range(inst.n):  # precedências do roteiro
        for k in range(1, len(inst.route[j])):
            assert sch.start[j][k] >= sch.end[j][k - 1]


def test_cpsat_ft06_otimo_e_validado_pelo_decoder():
    ft = load_jsplib(BENCH / "ft06")
    cp = solve_cpsat(ft, time_limit=20)
    assert cp.status == "OPTIMAL" and cp.cmax == 55
    assert decode(ft, cp.seq).metrics["cmax"] == 55


def test_tabu_nao_supera_otimo_e_melhora_inicial():
    inst = generate(12, 11)
    cp = solve_cpsat(inst, time_limit=20)
    assert cp.status == "OPTIMAL"
    r = tabu_search(inst, seed=0, max_evals=3000)
    assert r.cmax >= cp.cmax
    assert evaluate(inst, r.seq)[0] == r.cmax
    assert r.cmax <= r.history[0][1]


def test_vizinhos_criticos_validos():
    from src.tabu_search import critical_neighbors
    inst = generate(15, 4)
    s = random_sequence(inst, random.Random(2))
    nbs = critical_neighbors(inst, s)
    assert nbs
    for nb, _ in nbs:
        assert sorted(nb) == sorted(s) and nb != s
        decode(inst, nb)  # decodifica sem erro

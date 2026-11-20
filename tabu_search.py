"""Busca Tabu para JSSP (permutação com repetição).

Vizinhança principal (`critical`): inversão de pares de operações consecutivas na mesma estação
sobre o caminho crítico (movimento tipo N1 de Nowicki–Smutnicki / van Laarhoven), mais alguns
vizinhos aleatórios para diversificar. Vizinhança `random` (swap/insert aleatórios) fica como
versão básica para ablação.
"""
from __future__ import annotations

import random
import time
from dataclasses import dataclass, field

from .decoder import K, evaluate, random_sequence
from .instance import Instance


@dataclass
class Result:
    seq: list[int]
    cmax: int
    sum_tj: int
    evals: int
    seconds: float
    history: list[tuple[int, int]] = field(default_factory=list)  # (avaliações, melhor Cmax)

    @property
    def obj(self) -> int:
        return self.cmax * K + self.sum_tj


def random_move(seq: list[int], rng: random.Random) -> tuple[list[int], tuple]:
    """Vizinho por swap ou insert entre posições de jobs distintos. Devolve (seq, movimento)."""
    L = len(seq)
    while True:
        i, j = rng.sample(range(L), 2)
        if seq[i] != seq[j]:
            break
    new = seq[:]
    if rng.random() < 0.5:
        new[i], new[j] = new[j], new[i]
        return new, ("swap", i, j)
    v = new.pop(i)
    new.insert(j, v)
    return new, ("ins", i, j)


def critical_neighbors(inst: Instance, seq: list[int]) -> list[tuple[list[int], tuple]]:
    """Vizinhos obtidos invertendo, no caminho crítico, duas operações consecutivas da mesma estação.

    Trabalha na sequência de operações (job, k) para que o movimento só troque a ordem do par na
    estação e preserve as precedências do job. Devolve [(nova_sequência, (u, v))], onde v passa
    a preceder u.
    """
    jr = list(inst.release)
    mr = [0] * inst.m
    nxt = [0] * inst.n
    last = [None] * inst.m
    ops, st, en, mp = [], {}, {}, {}
    for j in seq:
        k = nxt[j]
        mc = inst.route[j][k]
        s = max(jr[j], mr[mc])
        e = s + inst.p[j][k]
        op = (j, k)
        ops.append(op)
        st[op], en[op], mp[op] = s, e, last[mc]
        last[mc] = op
        jr[j] = mr[mc] = e
        nxt[j] = k + 1
    pos = {op: i for i, op in enumerate(ops)}
    cur = max(ops, key=lambda o: en[o])
    moves = []
    while True:
        j, k = cur
        if mp[cur] is not None and en[mp[cur]] == st[cur]:
            u, v = mp[cur], cur            # elo de estação: candidato a inversão
            pu, pv = pos[u], pos[v]
            new = None
            if k == 0 or pos[(j, k - 1)] < pu:      # v pode subir para antes de u
                new = ops[:pv] + ops[pv + 1:]
                new.insert(pu, v)
            elif u[1] + 1 >= len(inst.route[u[0]]) or pos[(u[0], u[1] + 1)] > pv:  # u desce para depois de v
                new = ops[:pu] + ops[pu + 1:]
                new.insert(pv, u)
            if new is not None:
                moves.append(([o[0] for o in new], (u, v)))
            cur = u
        elif k > 0 and en[(j, k - 1)] == st[cur]:
            cur = (j, k - 1)
        else:
            break
    return moves


def tabu_search(inst: Instance, seed: int = 0, max_evals: int = 8000, tenure: int = 10,
                n_neighbors: int = 5, init: list[int] | None = None, restart_after: int = 100,
                time_limit: float | None = None, neighborhood: str = "critical") -> Result:
    """Busca Tabu com:
    - solução corrente que sempre anda para o melhor vizinho admissível (mesmo pior);
    - lista tabu por atributo: proíbe recriar a ordem antiga de um par de operações na estação
      (modo `random`: proíbe devolver a operação à posição antiga);
    - aspiração por melhor global; reinício perturbando a melhor solução após `restart_after`
      iterações sem melhora. Orçamento medido em avaliações (comparável ao SA).
    `n_neighbors` = nº de vizinhos aleatórios (no modo `critical`, somados aos críticos).
    """
    rng = random.Random(seed)
    t0 = time.perf_counter()
    cur = list(init) if init else random_sequence(inst, rng)
    c, t = evaluate(inst, cur)
    best, best_obj, best_c, best_t = cur[:], c * K + t, c, t
    evals, it, stall = 1, 0, 0
    hist = [(evals, best_c)]
    tabu: dict[tuple, int] = {}

    while evals < max_evals and (time_limit is None or time.perf_counter() - t0 < time_limit):
        it += 1
        cand = []  # (obj, seq, chaves_a_marcar, é_tabu, cmax, sum_tj)
        if neighborhood == "critical":
            for nb, (u, v) in critical_neighbors(inst, cur):
                c, t = evaluate(inst, nb)
                evals += 1
                cand.append((c * K + t, nb, [(u, v)], tabu.get((v, u), 0) > it, c, t))
        occ, cnt = [], {}
        for v in cur:
            occ.append(cnt.get(v, 0))
            cnt[v] = occ[-1] + 1
        for _ in range(n_neighbors if neighborhood == "critical" else n_neighbors):
            nb, (kind, i, j) = random_move(cur, rng)
            c, t = evaluate(inst, nb)
            evals += 1
            if kind == "swap":
                dest = [(cur[i], occ[i], j), (cur[j], occ[j], i)]
                back = [(cur[i], occ[i], i), (cur[j], occ[j], j)]
            else:
                dest, back = [(cur[i], occ[i], j)], [(cur[i], occ[i], i)]
            cand.append((c * K + t, nb, back, any(tabu.get(k, 0) > it for k in dest), c, t))
        if not cand:
            break
        ok = [x for x in cand if not x[3] or x[0] < best_obj]
        o, nb, back, _, c, t = min(ok, key=lambda x: x[0]) if ok else rng.choice(cand)
        cur = nb
        for k in back:
            tabu[k] = it + tenure
        if o < best_obj:
            best, best_obj, best_c, best_t = nb[:], o, c, t
            stall = 0
        else:
            stall += 1
        hist.append((evals, best_c))
        if restart_after and stall >= restart_after:  # reinício perturbado a partir do melhor
            cur = best[:]
            for _ in range(rng.randint(3, 6)):
                cur, _m = random_move(cur, rng)
            evals += 1
            tabu.clear()
            stall = 0
    return Result(best, best_c, best_t, evals, time.perf_counter() - t0, hist)

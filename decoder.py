"""Decodificador semi-ativo para JSSP com roteiros variáveis.

Solução = permutação com repetição: o job j aparece len(route[j]) vezes; a k-ésima
ocorrência de j é a k-ésima operação do job. Cada operação começa assim que o job e a
estação estão livres, na ordem em que aparece na sequência.
"""
from __future__ import annotations

import random
from dataclasses import dataclass

from .instance import Instance

K = 10_000_000  # peso lexicográfico: obj = Cmax*K + ΣTj (Cmax primeiro, ΣTj desempata)


def base_sequence(inst: Instance) -> list[int]:
    return [j for j in range(inst.n) for _ in inst.route[j]]


def random_sequence(inst: Instance, rng: random.Random) -> list[int]:
    seq = base_sequence(inst)
    rng.shuffle(seq)
    return seq


def evaluate(inst: Instance, seq: list[int]) -> tuple[int, int]:
    """(Cmax, ΣTj) — versão rápida usada dentro das metaheurísticas."""
    jr = list(inst.release)
    mr = [0] * inst.m
    nxt = [0] * inst.n
    route, p = inst.route, inst.p
    for j in seq:
        k = nxt[j]
        mc = route[j][k]
        s = jr[j] if jr[j] > mr[mc] else mr[mc]
        e = s + p[j][k]
        jr[j] = mr[mc] = e
        nxt[j] = k + 1
    due = inst.due
    return max(jr), sum(c - d for c, d in zip(jr, due) if c > d)


def objective(inst: Instance, seq: list[int]) -> int:
    c, t = evaluate(inst, seq)
    return c * K + t


@dataclass
class Schedule:
    start: list[list[int]]
    end: list[list[int]]
    completion: list[int]
    metrics: dict
    ops_by_machine: list[list[tuple[int, int, int, int]]]  # (início, fim, job, k)


def decode(inst: Instance, seq: list[int]) -> Schedule:
    """Cronograma completo + métricas (Cmax, ΣTj, Tmax, ΣUj, ociosidade, utilização)."""
    assert len(seq) == inst.nops, "sequência com tamanho incompatível com a instância"
    jr = list(inst.release)
    mr = [0] * inst.m
    nxt = [0] * inst.n
    start = [[0] * len(r) for r in inst.route]
    end = [[0] * len(r) for r in inst.route]
    byM: list[list[tuple[int, int, int, int]]] = [[] for _ in range(inst.m)]
    for j in seq:
        k = nxt[j]
        mc = inst.route[j][k]
        s = max(jr[j], mr[mc])
        e = s + inst.p[j][k]
        start[j][k], end[j][k] = s, e
        jr[j] = mr[mc] = e
        nxt[j] = k + 1
        byM[mc].append((s, e, j, k))
    assert all(nxt[j] == len(inst.route[j]) for j in range(inst.n)), "sequência incompleta"
    cmax = max(jr)
    tard = [max(0, c - d) for c, d in zip(jr, inst.due)]
    busy = [sum(e - s for s, e, _, _ in ops) for ops in byM]
    metrics = {
        "cmax": cmax, "sum_tj": sum(tard), "tmax": max(tard), "n_late": sum(t > 0 for t in tard),
        "busy": busy, "idle": [cmax - b for b in busy], "util": [b / cmax for b in busy],
        "util_mean": sum(busy) / (inst.m * cmax),
    }
    return Schedule(start, end, jr, metrics, byM)

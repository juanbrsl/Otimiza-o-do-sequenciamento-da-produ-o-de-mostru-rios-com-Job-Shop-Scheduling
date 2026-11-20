"""ANTES: simulação da prática empírica (FIFO por estação, urgentes na frente) e regras de despacho."""
from __future__ import annotations

from .instance import Instance

RULES = ("FIFO", "SPT", "EDD", "MWKR")


def best_rule_sequence(inst: Instance) -> list[int]:
    """Melhor sequência (Cmax, depois ΣTj) entre as regras de despacho: ponto de partida das metaheurísticas."""
    from .decoder import objective
    return min((dispatch(inst, r) for r in RULES), key=lambda s: objective(inst, s))


def dispatch(inst: Instance, rule: str = "FIFO") -> list[int]:
    """Despacho sem espera (non-delay). Devolve a sequência na ordem em que as operações
    foram iniciadas; decodificada, reproduz exatamente o cronograma simulado.

    FIFO: fila por estação em ordem de chegada, urgentes primeiro (prática atual simulada).
    SPT: menor tempo de operação; EDD: menor prazo; MWKR: maior trabalho restante.
    """
    assert rule in RULES
    n, m = inst.n, inst.m
    ready = list(inst.release)       # quando o job fica disponível p/ a próxima operação
    free = [0] * m                   # quando a estação fica livre
    nxt = [0] * n
    remaining = [sum(t) for t in inst.p]
    seq: list[int] = []

    def key(j: int) -> tuple:
        k = nxt[j]
        if rule == "FIFO":
            return (not inst.urgent[j], ready[j], j)
        if rule == "SPT":
            return (inst.p[j][k], ready[j], j)
        if rule == "EDD":
            return (inst.due[j], ready[j], j)
        return (-remaining[j], ready[j], j)  # MWKR

    for _ in range(inst.nops):
        cand: dict[int, list[int]] = {}
        for j in range(n):
            if nxt[j] < len(inst.route[j]):
                cand.setdefault(inst.route[j][nxt[j]], []).append(j)
        # estação cuja próxima decisão ocorre mais cedo
        t_m = {mc: max(free[mc], min(ready[j] for j in js)) for mc, js in cand.items()}
        mc = min(t_m, key=lambda x: (t_m[x], x))
        t = t_m[mc]
        j = min((j for j in cand[mc] if ready[j] <= t), key=key)
        k = nxt[j]
        end = t + inst.p[j][k]
        ready[j] = free[mc] = end
        remaining[j] -= inst.p[j][k]
        nxt[j] = k + 1
        seq.append(j)
    return seq

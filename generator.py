"""Gerador parametrizado e reprodutível de instâncias (fábrica de mostruários de pequeno porte)."""
from __future__ import annotations

import numpy as np

from .instance import Instance

DAY = 480  # min úteis por dia (turno único)

MACHINES = ["Corte", "Personalização", "Colagem/prensagem", "Costura/acabamento",
            "Montagem/encardenamento", "Conferência/embalagem"]

# família -> (nome, roteiro, peso)
FAMILIES = {
    0: ("F1 Mostruário personalizado", [0, 1, 2, 3, 4, 5], 0.45),
    1: ("F2 Case/caixa de madeira", [0, 2, 3, 1, 4, 5], 0.25),
    2: ("F3 Kit pronto", [0, 3, 4, 5], 0.15),
    3: ("F4 Sob medida", [0, 4, 1, 5], 0.15),
}
FIXED = [20, 30, 15, 10, 10, 10]        # min fixos por estação
UNIT = [1.5, 2.0, 1.8, 3.5, 4.0, 1.0]   # min por unidade do lote
LOTS = [15, 25, 50, 100, 150]
LOT_W = [0.25, 0.25, 0.25, 0.15, 0.10]


def generate(n: int, seed: int, urgent_frac: float = 0.2, due_days: int = 10,
             urgent_days: int = 5, noise: float = 0.10, time_scale: float = 1.0,
             only_family: int | None = None, name: str | None = None) -> Instance:
    """Gera n ordens. `only_family` restringe a uma família (útil p/ rotas completas)."""
    rng = np.random.default_rng(seed)
    fams = list(FAMILIES)
    w = np.array([FAMILIES[f][2] for f in fams])
    fam = rng.choice(fams, size=n, p=w / w.sum()) if only_family is None else np.full(n, only_family)
    lots = rng.choice(LOTS, size=n, p=LOT_W)
    urgent = np.zeros(n, dtype=bool)
    urgent[rng.choice(n, size=round(urgent_frac * n), replace=False)] = True

    route, p = [], []
    for j in range(n):
        r = list(FAMILIES[int(fam[j])][1])
        t = [max(1, round((FIXED[mc] + UNIT[mc] * lots[j]) * rng.lognormal(0, noise) * time_scale))
             for mc in r]
        route.append(r)
        p.append(t)
    due = [(urgent_days if u else due_days) * DAY for u in urgent]
    inst = Instance(name or f"mostruarios_n{n}_s{seed}", len(MACHINES), route, p, due, [0] * n,
                    [int(f) for f in fam], [bool(u) for u in urgent], list(MACHINES))
    inst.validate()
    return inst


def load_report(inst: Instance) -> dict:
    """Carga por estação, backlog (dias úteis) e limite inferior simples do makespan."""
    load = [0] * inst.m
    for j in range(inst.n):
        for mc, t in zip(inst.route[j], inst.p[j]):
            load[mc] += t
    return {"load_min": load, "backlog_days": max(load) / DAY,
            "mean_load_days": sum(load) / inst.m / DAY,
            "lb_cmax": max(max(load), max(sum(t) for t in inst.p))}

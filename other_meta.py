"""Simulated Annealing para JSSP (mesma representação, vizinhanças e orçamento da Busca Tabu)."""
from __future__ import annotations

import math
import random
import time

from .decoder import K, evaluate, random_sequence
from .instance import Instance
from .tabu_search import Result, random_move


def simulated_annealing(inst: Instance, seed: int = 0, max_evals: int = 8000,
                        t0_frac: float = 0.01, t_end: float = 0.5,
                        init: list[int] | None = None) -> Result:
    """Resfriamento geométrico por avaliação, de t0_frac*Cmax inicial até t_end (em minutos)."""
    rng = random.Random(seed)
    start = time.perf_counter()
    cur = list(init) if init else random_sequence(inst, rng)
    c, t = evaluate(inst, cur)
    cur_f = c * K + t
    best, best_f, best_c, best_t = cur[:], cur_f, c, t
    T0 = max(t0_frac * c, 2 * t_end)
    evals = 1
    hist = [(evals, best_c)]
    while evals < max_evals:
        T = T0 * (t_end / T0) ** (evals / max_evals)
        nb, _ = random_move(cur, rng)
        c, t = evaluate(inst, nb)
        evals += 1
        f = c * K + t
        delta = (f - cur_f) / K  # em minutos de Cmax (ΣTj só desempata)
        if delta <= 0 or rng.random() < math.exp(-delta / T):
            cur, cur_f = nb, f
            if f < best_f:
                best, best_f, best_c, best_t = nb[:], f, c, t
        if evals % 20 == 0:
            hist.append((evals, best_c))
    return Result(best, best_c, best_t, evals, time.perf_counter() - start, hist)

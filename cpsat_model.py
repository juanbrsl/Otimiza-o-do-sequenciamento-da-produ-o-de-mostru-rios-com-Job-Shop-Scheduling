"""Modelo exato OR-Tools CP-SAT: intervalos + NoOverlap por estação, minimiza Cmax."""
from __future__ import annotations

import os
from dataclasses import dataclass

from ortools.sat.python import cp_model

from .decoder import decode
from .instance import Instance


@dataclass
class CPResult:
    status: str          # OPTIMAL / FEASIBLE / UNKNOWN / INFEASIBLE
    cmax: int | None
    bound: float | None  # melhor limite inferior provado
    gap: float | None    # (cmax - bound)/cmax em %
    seconds: float
    seq: list[int] | None


def solve_cpsat(inst: Instance, time_limit: float = 30.0, workers: int | None = None,
                seed: int = 0, hint: list[int] | None = None) -> CPResult:
    """`hint` (sequência) vira solução inicial sugerida ao solver."""
    mdl = cp_model.CpModel()
    horizon = sum(sum(t) for t in inst.p) + max(inst.release)
    S, E, per_m = {}, {}, [[] for _ in range(inst.m)]
    for j in range(inst.n):
        for k, mc in enumerate(inst.route[j]):
            S[j, k] = mdl.NewIntVar(inst.release[j], horizon, f"s{j}_{k}")
            E[j, k] = mdl.NewIntVar(0, horizon, f"e{j}_{k}")
            per_m[mc].append(mdl.NewIntervalVar(S[j, k], inst.p[j][k], E[j, k], f"i{j}_{k}"))
            if k:
                mdl.Add(S[j, k] >= E[j, k - 1])
    for ivs in per_m:
        mdl.AddNoOverlap(ivs)
    cmax = mdl.NewIntVar(0, horizon, "cmax")
    mdl.AddMaxEquality(cmax, [E[j, len(inst.route[j]) - 1] for j in range(inst.n)])
    mdl.Minimize(cmax)
    if hint:
        sc = decode(inst, hint)
        for (j, k), v in S.items():
            mdl.AddHint(v, sc.start[j][k])

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_workers = workers or min(8, os.cpu_count() or 1)
    solver.parameters.random_seed = seed
    st = solver.Solve(mdl)
    name = solver.StatusName(st)
    if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return CPResult(name, None, None, None, solver.WallTime(), None)
    obj, bound = solver.ObjectiveValue(), solver.BestObjectiveBound()
    ops = sorted((solver.Value(S[j, k]), j, k) for (j, k) in S)
    return CPResult(name, int(obj), bound, 100 * (obj - bound) / obj if obj else 0.0,
                    solver.WallTime(), [j for _, j, _ in ops])

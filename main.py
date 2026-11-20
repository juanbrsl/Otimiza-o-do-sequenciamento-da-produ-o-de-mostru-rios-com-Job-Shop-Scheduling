"""Pipeline: gera instância → ANTES (simulado) → otimiza → compara → salva em results/, tabelas/, figuras/.

Uso (na raiz do projeto):
    python main.py --stage base                 # caso-base (n=25): ANTES × DEPOIS
    python main.py --stage experiments          # benchmarks, calibração, comparação, sensibilidade
    python main.py --stage all --quick          # versão reduzida para conferir a pipeline
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

from src import plots
from src.baseline import RULES, dispatch
from src.cpsat_model import solve_cpsat
from src.decoder import K, decode
from src.experiments import (ROOT, calibrate, environment, run_experiments, run_tasks,
                             sensitivity, validate_benchmarks)
from src.generator import generate, load_report

RES, TAB, FIG, DATA = (ROOT / d for d in ("results", "tabelas", "figuras", "data/instances"))


def stage_base(a, params: dict) -> None:
    for d in (RES, TAB, FIG, DATA):
        d.mkdir(parents=True, exist_ok=True)
    inst = generate(a.n, a.seed, name=f"caso_base_n{a.n}")
    inst.save_json(DATA / f"{inst.name}.json")
    rep = load_report(inst)
    print(f"Instância {inst.name}: {inst.n} ordens, {inst.nops} operações; backlog {rep['backlog_days']:.1f} dias "
          f"(estação gargalo), limite inferior {rep['lb_cmax']} min")

    # ANTES (FIFO + urgentes) e regras de referência
    sched = {r: decode(inst, dispatch(inst, r)) for r in RULES}
    # DEPOIS: metaheurísticas com várias sementes
    tasks = [({}, inst, m, s, a.budget, params, True) for m in ("Tabu", "SA") for s in range(a.runs)]
    res = run_tasks(tasks, a.jobs)
    best = {m: min((r for r in res if r["method"] == m), key=lambda r: r["cmax"] * K + r["sum_tj"])
            for m in ("Tabu", "SA")}
    cp = solve_cpsat(inst, time_limit=a.cp_time, hint=best["Tabu"]["seq"])
    print(f"CP-SAT: {cp.status}, Cmax={cp.cmax}, limite={cp.bound}, gap={cp.gap:.2f}%, {cp.seconds:.1f}s")
    sched["SA"] = decode(inst, best["SA"]["seq"])
    sched["Tabu"] = decode(inst, best["Tabu"]["seq"])
    if cp.seq:
        sched["CP-SAT"] = decode(inst, cp.seq)
        assert sched["CP-SAT"].metrics["cmax"] <= cp.cmax

    fifo = sched["FIFO"].metrics
    rows = []
    for name, s in sched.items():
        m = s.metrics
        rows.append({"metodo": name + (" (ANTES)" if name == "FIFO" else ""), "cmax": m["cmax"],
                     "sum_tj": m["sum_tj"], "tmax": m["tmax"], "n_atrasadas": m["n_late"],
                     "util_media_%": round(100 * m["util_mean"], 1),
                     "ganho_cmax_%": round(100 * (fifo["cmax"] - m["cmax"]) / fifo["cmax"], 2),
                     "ganho_sum_tj_%": round(100 * (fifo["sum_tj"] - m["sum_tj"]) / fifo["sum_tj"], 2)
                     if fifo["sum_tj"] else None})
    comp = pd.DataFrame(rows)
    comp.to_csv(TAB / "comparacao_caso_base.csv", index=False)
    runs = pd.DataFrame(res).drop(columns=["seq", "history"])
    runs.to_csv(RES / "runs_caso_base.csv", index=False)
    stats = runs.groupby("method")["cmax"].agg(["mean", "std", "min", "max"]).round(2)
    stats.to_csv(TAB / "execucoes_caso_base.csv")
    print(comp.to_string(index=False), "\n", stats, sep="")

    after = "CP-SAT" if cp.status == "OPTIMAL" and "CP-SAT" in sched else "Tabu"
    plots.gantt(inst, [("ANTES — FIFO com prioridade a urgentes (simulado)", sched["FIFO"]),
                       (f"DEPOIS — {after}" + (" (ótimo comprovado)" if after == "CP-SAT" else ""), sched[after])],
                FIG / "gantt_antes_depois.png")
    plots.convergence({m: [r["history"] for r in res if r["method"] == m] for m in ("Tabu", "SA")},
                      FIG / "convergencia.png", a.budget)
    plots.utilization(inst, [("ANTES (FIFO)", fifo), (f"DEPOIS ({after})", sched[after].metrics)],
                      FIG / "utilizacao_estacoes.png")
    out = {"instancia": inst.name, "carga": rep, "params_tabu": params, "orcamento_avaliacoes": a.budget,
           "execucoes": a.runs, "cpsat": {"status": cp.status, "cmax": cp.cmax, "bound": cp.bound,
                                          "gap_pct": cp.gap, "seconds": cp.seconds},
           "antes": {k: v for k, v in fifo.items()}, "ambiente": environment()}
    (RES / "caso_base.json").write_text(json.dumps(out, indent=1, ensure_ascii=False, default=str))


def stage_experiments(a, params: dict) -> None:
    for d in (RES, TAB, FIG):
        d.mkdir(parents=True, exist_ok=True)
    print("\n== Benchmarks (ft06, ft10, ta01) ==")
    names = ("ft06", "ft10") if a.quick else ("ft06", "ft10", "ta01")
    print(validate_benchmarks(names, runs=min(a.runs, 10), cp_time=a.cp_time, jobs=a.jobs).to_string(index=False))
    print("\n== Calibração da Busca Tabu ==")
    if a.calibrate:
        params, tab = calibrate(runs=5, budget=a.budget, jobs=a.jobs)
        print(tab.to_string(index=False), "\nmelhor:", params)
    sizes, n_inst = ((10, 15, 20), 3) if a.quick else ((10, 15, 20, 25, 30), 10)
    print("\n== Comparação de métodos ==")
    ex = run_experiments(sizes, n_inst, a.runs, a.budget, a.cp_time, params, a.jobs)
    print(ex["summary"].to_string(index=False), "\n", ex["cp_summary"].to_string(index=False), sep="")
    plots.boxplot_arpd(ex["runs_all"], FIG / "boxplot_arpd.png")
    print("\n== Sensibilidade ==")
    print(sensitivity(n=25 if not a.quick else 15, n_inst=5 if not a.quick else 2, runs=5,
                      budget=a.budget, cp_time=min(a.cp_time, 30), params=params, jobs=a.jobs).to_string(index=False))
    (RES / "ambiente.json").write_text(json.dumps(environment(), indent=1, ensure_ascii=False))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["base", "experiments", "all"], default="base")
    ap.add_argument("--n", type=int, default=25)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--runs", type=int, default=30)
    ap.add_argument("--budget", type=int, default=8000, help="avaliações por execução")
    ap.add_argument("--cp-time", type=float, default=60, dest="cp_time")
    ap.add_argument("--jobs", type=int, default=min(8, os.cpu_count() or 1))
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--no-calibrate", action="store_false", dest="calibrate")
    a = ap.parse_args()
    if a.quick:
        a.runs, a.cp_time = min(a.runs, 5), min(a.cp_time, 10)
    params = {"tenure": 10, "n_neighbors": 30}
    if a.stage in ("experiments", "all"):
        stage_experiments(a, params)
        cal = RES / "calibracao.csv"
        if cal.exists():
            top = pd.read_csv(cal).sort_values("arpd").iloc[0]
            params = {"tenure": int(top["tenure"]), "n_neighbors": int(top["vizinhos"])}
    if a.stage in ("base", "all"):
        stage_base(a, params)


if __name__ == "__main__":
    main()

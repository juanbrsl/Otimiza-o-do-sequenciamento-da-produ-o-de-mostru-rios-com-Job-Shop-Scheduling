"""Experimentos: benchmarks, calibração, comparação de métodos (ARPD) e sensibilidade."""
from __future__ import annotations

import json
import os
import platform
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import pandas as pd

from .baseline import RULES, best_rule_sequence, dispatch
from .cpsat_model import solve_cpsat
from .decoder import decode
from .generator import generate
from .instance import Instance, load_jsplib
from .other_meta import simulated_annealing
from .tabu_search import tabu_search

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PARAMS = {"tenure": 10, "n_neighbors": 5}
TABU_ALE = {"tenure": 3, "n_neighbors": 10, "neighborhood": "random"}


def _run_meta(task: tuple) -> dict:
    tag, inst, method, seed, budget, params, keep = task
    init = best_rule_sequence(inst)  # mesmo ponto de partida (melhor regra) para todas as metaheurísticas
    if method == "Tabu":
        r = tabu_search(inst, seed=seed, max_evals=budget, init=init, **(params or DEFAULT_PARAMS))
    elif method == "Tabu-ale":  # versão básica (vizinhança aleatória), usada na ablação
        r = tabu_search(inst, seed=seed, max_evals=budget, init=init, **TABU_ALE)
    else:
        r = simulated_annealing(inst, seed=seed, max_evals=budget, init=init)
    out = {**tag, "method": method, "seed": seed, "cmax": r.cmax, "sum_tj": r.sum_tj,
           "seconds": r.seconds}
    if keep:
        out.update(seq=r.seq, history=r.history)
    return out


def run_tasks(tasks: list[tuple], jobs: int = 1) -> list[dict]:
    """Executa tarefas de metaheurística (em paralelo se jobs > 1)."""
    if jobs <= 1:
        return [_run_meta(t) for t in tasks]
    with ProcessPoolExecutor(jobs) as ex:
        return list(ex.map(_run_meta, tasks, chunksize=4))


def environment() -> dict:
    import ortools
    cpu = platform.processor()
    try:  # nome comercial da CPU no Windows
        import subprocess
        cpu = subprocess.run(["wmic", "cpu", "get", "name"], capture_output=True, text=True,
                             timeout=10).stdout.split("\n")[1].strip() or cpu
    except Exception:
        pass
    ram = None
    try:
        import ctypes

        class MS(ctypes.Structure):
            _fields_ = [("l", ctypes.c_ulong), ("m", ctypes.c_ulong), ("tot", ctypes.c_ulonglong),
                        ("a", ctypes.c_ulonglong), ("b", ctypes.c_ulonglong), ("c", ctypes.c_ulonglong),
                        ("d", ctypes.c_ulonglong), ("e", ctypes.c_ulonglong), ("f", ctypes.c_ulonglong)]
        ms = MS(); ms.l = ctypes.sizeof(MS)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(ms))
        ram = round(ms.tot / 2**30, 1)
    except Exception:
        pass
    return {"so": platform.platform(), "cpu": cpu, "nucleos_logicos": os.cpu_count(),
            "ram_gb": ram, "python": sys.version.split()[0], "ortools": ortools.__version__}


# ----------------------------------------------------------------- benchmarks
def validate_benchmarks(names=("ft06", "ft10", "ta01"), runs: int = 10, budget: int = 30000,
                        cp_time: float = 60, jobs: int = 8) -> pd.DataFrame:
    """CP-SAT e Busca Tabu vs. ótimo/melhor conhecido (JSPLIB, conferido em instances.json)."""
    bdir = ROOT / "data" / "benchmarks"
    known = {e["name"]: e for e in json.loads((bdir / "instances.json").read_text())}
    rows = []
    for nm in names:
        inst = load_jsplib(bdir / nm)
        e = known[nm]
        ref = e.get("optimum") or e.get("bounds", {}).get("upper")
        cp = solve_cpsat(inst, time_limit=cp_time)
        assert cp.seq is None or decode(inst, cp.seq).metrics["cmax"] <= cp.cmax
        res = run_tasks([({}, inst, "Tabu", s, budget, None, False) for s in range(runs)], jobs)
        c = [r["cmax"] for r in res]
        rows.append({"instancia": nm, "n_x_m": f"{inst.n}x{inst.m}", "otimo_conhecido": ref,
                     "cpsat_status": cp.status, "cpsat_cmax": cp.cmax,
                     "cpsat_s": round(cp.seconds, 1), "tabu_melhor": min(c),
                     "tabu_media": round(sum(c) / len(c), 1),
                     "tabu_gap_%": round(100 * (min(c) - ref) / ref, 2)})
    df = pd.DataFrame(rows)
    (ROOT / "tabelas").mkdir(exist_ok=True)
    df.to_csv(ROOT / "tabelas" / "benchmarks.csv", index=False)
    return df


# ----------------------------------------------------------------- calibração
def calibrate(n: int = 20, seeds=(1001, 1002, 1003), runs: int = 5, budget: int = 8000,
              jobs: int = 8) -> tuple[dict, pd.DataFrame]:
    """Grade (tenure × vizinhos) em instâncias separadas das de teste (sementes 1xxx)."""
    insts = [generate(n, s, name=f"cal_{s}") for s in seeds]
    grid = [(t, k) for t in (3, 5, 10, 20) for k in (0, 2, 5)]  # tenure × vizinhos aleatórios extras
    tasks = [({"inst": i.name, "tenure": t, "vizinhos": k}, i, "Tabu", sd, budget,
              {"tenure": t, "n_neighbors": k}, False)
             for i in insts for (t, k) in grid for sd in range(runs)]
    df = pd.DataFrame(run_tasks(tasks, jobs))
    best = df.groupby("inst")["cmax"].transform("min")
    df["arpd"] = 100 * (df["cmax"] - best) / best
    tab = df.groupby(["tenure", "vizinhos"])["arpd"].mean().round(3).reset_index()
    (ROOT / "results").mkdir(exist_ok=True)
    tab.to_csv(ROOT / "results" / "calibracao.csv", index=False)
    top = tab.loc[tab["arpd"].idxmin()]
    return {"tenure": int(top["tenure"]), "n_neighbors": int(top["vizinhos"])}, tab


# ----------------------------------------------------------------- comparação
def run_experiments(sizes=(10, 15, 20, 25, 30), n_inst: int = 10, runs: int = 30,
                    budget: int = 8000, cp_time: float = 60, params: dict | None = None,
                    jobs: int = 8) -> dict[str, pd.DataFrame]:
    """Regras × CP-SAT × SA × Tabu em n_inst instâncias por tamanho; ARPD vs melhor conhecido."""
    res, tab = ROOT / "results", ROOT / "tabelas"
    res.mkdir(exist_ok=True); tab.mkdir(exist_ok=True)
    inst_dir = ROOT / "data" / "instances"
    inst_dir.mkdir(parents=True, exist_ok=True)
    insts = [generate(n, 2000 + 100 * n + k, name=f"n{n}_i{k}") for n in sizes for k in range(n_inst)]
    cp_rows, rule_rows = [], []
    for inst in insts:
        inst.save_json(inst_dir / f"{inst.name}.json")
        cp = solve_cpsat(inst, time_limit=cp_time, hint=dispatch(inst, "SPT"))
        assert cp.seq is None or decode(inst, cp.seq).metrics["cmax"] <= cp.cmax
        cp_rows.append({"inst": inst.name, "n": inst.n, "status": cp.status, "cmax": cp.cmax,
                        "bound": cp.bound, "gap_pct": cp.gap, "seconds": cp.seconds})
        for rule in RULES:
            m = decode(inst, dispatch(inst, rule)).metrics
            rule_rows.append({"inst": inst.name, "n": inst.n, "method": rule, "cmax": m["cmax"],
                              "sum_tj": m["sum_tj"], "n_late": m["n_late"]})
        print(f"  CP-SAT {inst.name}: {cp.status} {cp.cmax} ({cp.seconds:.1f}s)", flush=True)
    cp_df, rule_df = pd.DataFrame(cp_rows), pd.DataFrame(rule_rows)
    tasks = [({"inst": i.name, "n": i.n}, i, m, s, budget, params, False)
             for i in insts for m in ("Tabu", "Tabu-ale", "SA") for s in range(runs)]
    meta_df = pd.DataFrame(run_tasks(tasks, jobs))
    # melhor conhecido por instância = menor Cmax entre todos os métodos
    allc = pd.concat([cp_df[["inst", "cmax"]], rule_df[["inst", "cmax"]], meta_df[["inst", "cmax"]]])
    best = allc.groupby("inst")["cmax"].min()
    for d in (rule_df, meta_df, cp_df):
        d["arpd"] = 100 * (d["cmax"] - d["inst"].map(best)) / d["inst"].map(best)
    cp_df.to_csv(res / "cpsat.csv", index=False)
    meta_df.to_csv(res / "runs_metaheuristicas.csv", index=False)
    rule_df.to_csv(res / "regras.csv", index=False)
    runs_all = pd.concat([meta_df.assign(kind="meta"), rule_df.assign(kind="regra")])
    summ = (runs_all.groupby(["n", "method"])
            .agg(cmax_medio=("cmax", "mean"), cmax_dp=("cmax", "std"), cmax_melhor=("cmax", "min"),
                 cmax_pior=("cmax", "max"), arpd_medio=("arpd", "mean"), sum_tj_medio=("sum_tj", "mean"))
            .round(2).reset_index())
    summ.to_csv(tab / "resumo_metodos.csv", index=False)
    cp_sum = (cp_df.groupby("n").agg(otimas=("status", lambda s: int((s == "OPTIMAL").sum())),
                                     total=("status", "size"), gap_medio_pct=("gap_pct", "mean"),
                                     tempo_medio_s=("seconds", "mean")).round(2).reset_index())
    cp_sum.to_csv(tab / "resumo_cpsat.csv", index=False)
    return {"cp": cp_df, "rules": rule_df, "meta": meta_df, "runs_all": runs_all,
            "summary": summ, "cp_summary": cp_sum}


# ----------------------------------------------------------------- sensibilidade
def sensitivity(n: int = 25, n_inst: int = 5, runs: int = 5, budget: int = 8000,
                cp_time: float = 30, params: dict | None = None, jobs: int = 8) -> pd.DataFrame:
    """Variações de ±20% nos tempos e da proporção de urgentes: ganho da Busca Tabu vs FIFO."""
    variants = [("base", {}), ("tempos -20%", {"time_scale": 0.8}), ("tempos +20%", {"time_scale": 1.2}),
                ("urgentes 10%", {"urgent_frac": 0.1}), ("urgentes 30%", {"urgent_frac": 0.3})]
    rows = []
    for label, kw in variants:
        for k in range(n_inst):
            inst = generate(n, 3000 + k, name=f"sens_{k}", **kw)
            f = decode(inst, dispatch(inst, "FIFO")).metrics
            cp = solve_cpsat(inst, time_limit=cp_time)
            ts = run_tasks([({}, inst, "Tabu", s, budget, params, False) for s in range(runs)], jobs)
            tc = sum(r["cmax"] for r in ts) / runs
            tt = sum(r["sum_tj"] for r in ts) / runs
            rows.append({"variante": label, "fifo_cmax": f["cmax"], "tabu_cmax": tc,
                         "cpsat_cmax": cp.cmax, "cpsat_status": cp.status,
                         "fifo_sum_tj": f["sum_tj"], "tabu_sum_tj": tt,
                         "ganho_cmax_pct": 100 * (f["cmax"] - tc) / f["cmax"]})
    df = pd.DataFrame(rows)
    out = (df.groupby("variante", sort=False)
           .agg(fifo_cmax=("fifo_cmax", "mean"), tabu_cmax=("tabu_cmax", "mean"),
                cpsat_cmax=("cpsat_cmax", "mean"), cpsat_otimas=("cpsat_status", lambda s: int((s == "OPTIMAL").sum())),
                fifo_sum_tj=("fifo_sum_tj", "mean"), tabu_sum_tj=("tabu_sum_tj", "mean"),
                ganho_cmax_pct=("ganho_cmax_pct", "mean")).round(2).reset_index())
    (ROOT / "tabelas").mkdir(exist_ok=True)
    out.to_csv(ROOT / "tabelas" / "sensibilidade.csv", index=False)
    return out

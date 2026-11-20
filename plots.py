"""Figuras: Gantt antes×depois, convergência, boxplot de ARPD e utilização por estação."""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Patch

from .decoder import Schedule
from .instance import Instance

COLORS = ["#4C78A8", "#F58518", "#54A24B", "#B279A2", "#9D9D9D"]  # famílias F1..F4, n/d
FAM_NAMES = ["F1 Mostruário personalizado", "F2 Case de madeira", "F3 Kit pronto", "F4 Sob medida"]


def gantt(inst: Instance, panels: list[tuple[str, Schedule]], path: str | Path) -> None:
    """Gantt empilhado no mesmo eixo de tempo; cor = família; contorno vermelho = job atrasado."""
    xmax = max(s.metrics["cmax"] for _, s in panels)
    fig, axes = plt.subplots(len(panels), 1, figsize=(13, 3.4 * len(panels)), sharex=True)
    axes = np.atleast_1d(axes)
    for ax, (title, sch) in zip(axes, panels):
        for mc, ops in enumerate(sch.ops_by_machine):
            for s, e, j, k in ops:
                late = sch.completion[j] > inst.due[j]
                fam = inst.family[j] if inst.family and inst.family[j] >= 0 else 4
                ax.barh(mc, e - s, left=s, height=0.7, color=COLORS[fam],
                        edgecolor="red" if late else "white", linewidth=1.6 if late else 0.5)
                if e - s > xmax * 0.012:
                    ax.text((s + e) / 2, mc, str(j), ha="center", va="center", fontsize=6.5, color="white")
        ax.set_yticks(range(inst.m))
        ax.set_yticklabels(inst.machine_names or [f"M{i}" for i in range(inst.m)], fontsize=8)
        ax.invert_yaxis()
        ax.axvline(sch.metrics["cmax"], color="black", ls="--", lw=1)
        m = sch.metrics
        ax.set_title(f"{title} — Cmax={m['cmax']} min | ΣTj={m['sum_tj']} | atrasadas={m['n_late']}",
                     fontsize=10, loc="left")
        ax.set_xlim(0, xmax * 1.02)
    axes[-1].set_xlabel("Tempo (min úteis)")
    handles = [Patch(color=COLORS[i], label=FAM_NAMES[i]) for i in range(4)]
    handles.append(Patch(facecolor="white", edgecolor="red", label="Ordem atrasada"))
    fig.legend(handles=handles, loc="lower center", ncol=5, fontsize=8, frameon=False)
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    fig.savefig(path, dpi=150)
    plt.close(fig)


def convergence(histories: dict[str, list[list[tuple[int, int]]]], path: str | Path, budget: int) -> None:
    """Melhor Cmax médio (± desvio) por número de avaliações, para cada método."""
    grid = np.linspace(1, budget, 200)
    fig, ax = plt.subplots(figsize=(7, 4.2))
    for name, runs in histories.items():
        ys = []
        for h in runs:
            x, y = zip(*h)
            ys.append(np.interp(grid, x, y))
        mu, sd = np.mean(ys, axis=0), np.std(ys, axis=0)
        ax.plot(grid, mu, label=name)
        ax.fill_between(grid, mu - sd, mu + sd, alpha=0.2)
    ax.set_xlabel("Avaliações da função objetivo")
    ax.set_ylabel("Melhor Cmax (min)")
    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def boxplot_arpd(df: pd.DataFrame, path: str | Path, order=("FIFO", "SPT", "EDD", "MWKR", "SA", "Tabu-ale", "Tabu")) -> None:
    """ARPD (%) por método (execuções das metaheurísticas e instâncias para as regras)."""
    order = [m for m in order if m in set(df["method"])]
    fig, ax = plt.subplots(figsize=(7, 4.2))
    ax.boxplot([df.loc[df["method"] == m, "arpd"] for m in order], tick_labels=order, showmeans=True)
    ax.set_ylabel("ARPD (%)")
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def utilization(inst: Instance, panels: list[tuple[str, dict]], path: str | Path) -> None:
    """Utilização (%) por estação, uma barra por cenário (ex.: ANTES × DEPOIS)."""
    names = inst.machine_names or [f"M{i}" for i in range(inst.m)]
    w = 0.8 / len(panels)
    fig, ax = plt.subplots(figsize=(8, 4))
    for i, (label, met) in enumerate(panels):
        ax.bar(np.arange(inst.m) + i * w, [100 * u for u in met["util"]], w, label=label)
    ax.set_xticks(np.arange(inst.m) + w * (len(panels) - 1) / 2)
    ax.set_xticklabels(names, rotation=20, ha="right", fontsize=8)
    ax.set_ylabel("Utilização (%)")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)

"""Instância de JSSP com roteiros variáveis: leitura, validação e conversão."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class Instance:
    name: str
    m: int                      # nº de estações (1 máquina por estação)
    route: list[list[int]]      # route[j] = estações visitadas pelo job j, em ordem
    p: list[list[int]]          # p[j][k] = tempo (min) da k-ésima operação do job j
    due: list[int]              # prazo de cada job (min úteis)
    release: list[int]          # data de liberação de cada job
    family: list[int] = field(default_factory=list)   # família do produto (-1 = n/d)
    urgent: list[bool] = field(default_factory=list)
    machine_names: list[str] = field(default_factory=list)

    @property
    def n(self) -> int:
        return len(self.route)

    @property
    def nops(self) -> int:
        return sum(len(r) for r in self.route)

    def validate(self) -> None:
        assert len(self.p) == self.n == len(self.due) == len(self.release)
        for j in range(self.n):
            assert len(self.route[j]) == len(self.p[j]) > 0, f"job {j} sem operações"
            assert len(set(self.route[j])) == len(self.route[j]), f"job {j} repete estação"
            assert all(0 <= mc < self.m for mc in self.route[j])
            assert all(t > 0 for t in self.p[j])

    def is_complete(self) -> bool:
        """True se todo job visita todas as estações (condição do scheptk)."""
        return all(len(r) == self.m for r in self.route)

    def to_scheptk(self, path: str | Path) -> None:
        """Escreve o formato do scheptk (PT: estações nas linhas, jobs nas colunas)."""
        if not self.is_complete():
            raise ValueError("scheptk exige que todo job visite todas as estações")
        pt = [[0] * self.n for _ in range(self.m)]
        for j in range(self.n):
            for k, mc in enumerate(self.route[j]):
                pt[mc][j] = self.p[j][k]
        txt = (f"[JOBS={self.n}]\n[MACHINES={self.m}]\n"
               f"[PT={';'.join(','.join(map(str, r)) for r in pt)}]\n"
               f"[RT={';'.join(','.join(map(str, r)) for r in self.route)}]\n"
               f"[DD={','.join(map(str, self.due))}]\n"
               f"[R={','.join(map(str, self.release))}]\n")
        Path(path).write_text(txt)

    def save_json(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(asdict(self), ensure_ascii=False))

    @staticmethod
    def load_json(path: str | Path) -> "Instance":
        inst = Instance(**json.loads(Path(path).read_text()))
        inst.validate()
        return inst


def load_jsplib(path: str | Path, name: str | None = None) -> Instance:
    """Lê benchmark no formato JSPLIB (linhas de pares 'máquina tempo'). Sem prazos."""
    lines = [l for l in Path(path).read_text().splitlines() if l.strip() and not l.startswith("#")]
    n, m = map(int, lines[0].split())
    route, p = [], []
    for ln in lines[1:1 + n]:
        v = list(map(int, ln.split()))
        route.append(v[0::2])
        p.append(v[1::2])
    inst = Instance(name or Path(path).stem, m, route, p, [10**9] * n, [0] * n,
                    [-1] * n, [False] * n, [f"M{i}" for i in range(m)])
    inst.validate()
    return inst

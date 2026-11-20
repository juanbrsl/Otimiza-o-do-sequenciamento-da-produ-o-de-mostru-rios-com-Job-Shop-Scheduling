# Escopo do projeto

## 1. Contexto

Disciplina: Pesquisa Operacional II (UFC) — Prof. Bruno de Athayde Prata.

## 2. Problema

JSSP com roteiros variáveis (etapas puladas, ordens distintas), 1 máquina por estação, turno de 480 min/dia, tempo contínuo em minutos úteis, sem setups. Objetivo: minimizar Cmax; secundárias ΣTj, Tmax, ΣUj, ociosidade/utilização.

**Estações:** M0 Corte · M1 Personalização · M2 Colagem/prensagem · M3 Costura/acabamento · M4 Montagem/encardenamento · M5 Conferência/embalagem.

| Família | Peso | Roteiro |
|---|---|---|
| F1 Mostruário em couro sintético personalizado | 45% | M0→M1→M2→M3→M4→M5 |
| F2 Case/caixa de madeira | 25% | M0→M2→M3→M1→M4→M5 |
| F3 Kit pronto | 15% | M0→M3→M4→M5 |
| F4 Sob medida | 15% | M0→M4→M1→M5 |

Lote ∈ {15, 25, 50, 100, 150} com pesos 0,25/0,25/0,25/0,15/0,10.
Tempo = fixo + unitário × lote, ruído log-normal ~10%. Fixo/unitário (min): M0 20/1,5 · M1 30/2,0 · M2 15/1,8 · M3 10/3,5 · M4 10/4,0 · M5 10/1,0.
Calibrar para ~10–15 dias úteis de backlog e utilização média 75–90%; reportar a carga resultante.
Prazo padrão 10 dias úteis; 20% urgentes com 5 dias úteis; liberação 0 (opcional: chegadas escalonadas).
Instâncias: n ∈ {10, 15, 20, 25, 30}, 10 por tamanho; caso-base n = 25.

Todas as premissas são estimativas (porte e produto calibrados com informações públicas de empresa de referência) e entram numa tabela de premissas no relatório.

## 3. ANTES × DEPOIS

- **ANTES:** simulação da prática empírica — FIFO por estação com prioridade manual a urgentes. Referências: SPT, EDD, MWKR.
- **DEPOIS:** melhor solução da Busca Tabu / CP-SAT.
- "Ótimo" só onde o CP-SAT retornar OPTIMAL; nos demais casos, "melhor solução encontrada" com gap.

## 4. Métodos e módulos

| Módulo | Função |
|---|---|
| `generator.py` | instância sintética parametrizada, seed fixa |
| `instance.py` | leitura, validação, conversão (CSV / scheptk) |
| `decoder.py` | decoder semi-ativo, rotas variáveis; Cmax, Tj, Uj, ociosidade; cronograma |
| `baseline.py` | FIFO+urgentes, SPT, EDD, MWKR |
| `tabu_search.py` | Tabu com swap e insert, tabu por atributo, aspiração, restart opcional |
| `cpsat_model.py` | OR-Tools CP-SAT (intervalos + NoOverlap), limite de tempo |
| `other_meta.py` | VNS ou SA |
| `experiments.py` | múltiplas sementes, calibração, ARPD, tabelas CSV |
| `plots.py` | Gantt antes×depois, convergência, boxplot ARPD, utilização |

O `scheptk` exige rota completa, por isso o decoder próprio, validado contra ele.

## 5. Protocolo experimental

1. Validar em benchmarks (ft06, ft10, Taillard), conferindo ótimos/melhores conhecidos na fonte.
2. ≥30 execuções independentes por configuração (média, desvio, melhor, pior; boxplot de ARPD %).
3. Calibração (tenure, vizinhança, iterações) em instâncias separadas das de teste.
4. Comparações: Tabu × outra metaheurística × regras × CP-SAT; gap vs. ótimo/limite.
5. Ambiente computacional e tempos de execução.
6. Sensibilidade (±20% nos tempos; proporção de urgentes) e limitações (sem setups, sem quebras).

## 6. Referências a verificar antes de entrar no .bib

Taillard (1993) · Garey, Johnson e Sethi (1976) · Nowicki e Smutnicki (1996) · Glover (1989/1990) · Fisher e Thompson (1963) · Pinedo, *Scheduling* · documentação OR-Tools CP-SAT · fontes web da empresa de referência (@misc, acesso nov/2026).

## 7. Entregáveis e etapas

| Etapa | Conteúdo |
|---|---|
| 1 | gerador + decoder + baseline, validados |
| 2 | Busca Tabu + CP-SAT |
| 3 | experimentos e gráficos |
| 4 | relatório LaTeX (compilado e conferido) |
| 5 | slides (~6, pitch de 5 min), roteiro com tempos, 10 perguntas de arguição com respostas |

## 8. Fora do escopo

Setups sequenciais, quebras de máquina, dados reais de chão de fábrica, múltiplas máquinas por estação.

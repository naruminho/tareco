"""Metrô: qual o caminho mais rápido, quais as alternativas, que estação é vital?

Quatro linhas de metrô (fictícias). Cada linha da tabela liga duas estações
vizinhas e diz quantos minutos leva.

Rode na pasta do tareco:  python examples/receitas/08-metro/metro.py
"""

from pathlib import Path

import tareco

AQUI = Path(__file__).parent
SAIDA = AQUI / "saida"
SAIDA.mkdir(exist_ok=True)
tareco.set_language("pt")

# %% 1. Carregar
# ligacoes.csv: estacao_a, estacao_b, minutos, linha. weight="minutos" diz que o
# custo de cada trecho é o tempo.
metro = tareco.Graph(AQUI / "ligacoes.csv", source="estacao_a", target="estacao_b", weight="minutos")
print(metro)
print()

# %% 2. O caminho mais rápido
rota = metro.shortest_path("Aeroporto", "Lagoa", weight="weight")
minutos = metro.distance("Aeroporto", "Lagoa", weight="weight")
print(f"Aeroporto até Lagoa: {' -> '.join(rota)} ({minutos} minutos)")

# %% 3. Alternativas
for alternativa in metro.k_shortest_paths("Aeroporto", "Lagoa", k=3, weight="weight")[1:]:
    tempo = sum(metro.edges[a, b]["minutos"] for a, b in zip(alternativa, alternativa[1:]))
    print(f"  alternativa ({tempo} min): {' -> '.join(alternativa)}")
print()

# %% 4. Que estação é vital?
# betweenness: em quantos dos caminhos mais curtos a estação está no meio.
vitais = sorted(metro.betweenness().items(), key=lambda kv: -kv[1])[:4]
print("Estações por onde mais caminhos passam:", ", ".join(e for e, _ in vitais))

# %% 5. E se a estação Centro fechar?
sem_centro = metro.copy()
sem_centro.remove_node("Centro")
try:
    novo = sem_centro.distance("Aeroporto", "Lagoa", weight="weight")
    print(f"Sem a Centro, Aeroporto até Lagoa passa a levar {novo} minutos (antes: {minutos}).")
except tareco.NoPath:
    # nenhum caminho: a Centro era a única ligação do Aeroporto com o resto
    isolados = sorted(sem_centro.components()[1:], key=len)
    print("Sem a Centro não há como ir do Aeroporto à Lagoa. Ficam isoladas:",
          "; ".join(", ".join(sorted(c)) for c in isolados))
print()

# %% 6. Ver
metro.save(SAIDA / "metro.html", size="betweenness", title="Metrô")
print("Abra:", SAIDA / "metro.html")

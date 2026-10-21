"""Cadeia de suprimentos: quanto dá para entregar por semana, e onde está o gargalo?

Fornecedores abastecem fábricas, fábricas mandam para centros de distribuição
(CDs) e os CDs abastecem as lojas. Cada rota tem capacidade (unidades por
semana), custo por unidade e prazo em dias.

Rode na pasta do tareco:  python examples/receitas/03-suprimentos/suprimentos.py
"""

from pathlib import Path

import tareco

AQUI = Path(__file__).parent
SAIDA = AQUI / "saida"
SAIDA.mkdir(exist_ok=True)
tareco.set_language("pt")

# %% 1. Carregar
# rotas.csv: de, para, capacidade, custo, dias. "de" e "para" são reconhecidos
# sozinhos. As rotas têm sentido (do fornecedor para a loja), então directed=True.
rotas = tareco.Graph(AQUI / "rotas.csv", directed=True)
print(rotas)
print()

# %% 2. Quanto chega da origem ao destino?
# O fluxo máximo usa a capacidade de cada rota. Para medir a rede inteira, um
# truque comum: uma "origem" ligada a todos os fornecedores e um "destino"
# ligado a todas as lojas, com capacidade sobrando.
fornecedores = [n for n in rotas if str(n).startswith("Fornecedor")]
lojas = [n for n in rotas if str(n).startswith("Loja")]
rede = rotas.copy()
for f in fornecedores:
    rede.add_edge("ORIGEM", f, capacidade=10**9)
for loja in lojas:
    rede.add_edge(loja, "DESTINO", capacidade=10**9)
fluxo = rede.max_flow("ORIGEM", "DESTINO", capacity="capacidade")
print(f"A rede entrega até {fluxo.value} unidades por semana.")
# O corte mínimo: as rotas que, somadas, limitam a entrega. Aumentar outra rota
# qualquer não adianta nada; é aqui que se investe.
lojas_no_corte = [c for c in fluxo.cut if c[1].startswith("Loja")]
print(f"O gargalo tem {len(fluxo.cut)} rotas; {len(lojas_no_corte)} são entregas dos CDs para as lojas.")
for de, para, capacidade in fluxo.cut:
    if not para.startswith("Loja"):
        print(f"  e também {de} -> {para} ({capacidade} por semana)")
print()

# %% 3. E se uma fábrica parar?
for fabrica in ("Fabrica SP", "Fabrica MG", "Fabrica PR"):
    sem = rede.copy()
    sem.remove_node(fabrica)
    perda = fluxo.value - sem.max_flow("ORIGEM", "DESTINO", capacity="capacidade").value
    print(f"Sem a {fabrica}, a rede perde {perda} unidades por semana.")
print()

# %% 4. O caminho mais barato até uma loja, e as alternativas
caminho = rotas.shortest_path("Fornecedor A", "Loja 07", weight="custo")
custo = rotas.distance("Fornecedor A", "Loja 07", weight="custo")
print(f"Mais barato de Fornecedor A até Loja 07 (custo {custo}):", " -> ".join(caminho))
for alternativa in rotas.k_shortest_paths("Fornecedor A", "Loja 07", k=3, weight="custo")[1:]:
    custo = sum(rotas.edges[a, b]["custo"] for a, b in zip(alternativa, alternativa[1:]))
    print(f"  alternativa (custo {custo}):", " -> ".join(alternativa))
print()

# %% 5. Ver
# A espessura de cada rota mostra a capacidade.
rotas.save(SAIDA / "rotas.html", edge_width="capacidade", color="#6366f1", title="Rotas de abastecimento")
print("Abra:", SAIDA / "rotas.html")

"""Uma turma de amigos: quem anda com quem, e quem faz a ponte entre as turmas?

A primeira receita, a mais simples. Uma tabela com quem conversa com quem e
quantas mensagens trocaram, outra com a cidade e a idade de cada pessoa.

Rode na pasta do tareco:  python examples/receitas/01-amigos/amigos.py
"""

from pathlib import Path

import tareco

AQUI = Path(__file__).parent
DADOS = AQUI.parent.parent  # friends.csv e people.csv ficam em examples/
SAIDA = AQUI / "saida"
SAIDA.mkdir(exist_ok=True)
tareco.set_language("pt")

# %% 1. Carregar
# friends.csv tem as colunas from, to, messages. people.csv tem name, city, age.
# weight="messages" diz que a força de cada amizade é o número de mensagens.
g = tareco.Graph(DADOS / "friends.csv", nodes=DADOS / "people.csv", weight="messages")
print(g)
print()

# %% 2. O resumo em palavras
print(g.explain())
print()

# %% 3. Perguntas diretas
# communities() devolve uma lista de grupos; cada grupo é um conjunto de nomes.
for i, grupo in enumerate(g.communities(), 1):
    print(f"Grupo {i}:", ", ".join(sorted(grupo)))
print("Caminho de Ana até Otto:", g.shortest_path("Ana", "Otto"))
print("Com quem Iris mais conversa:", g.top_neighbors("Iris", n=3))
print("Quem deveria se conhecer:", [(a, b) for a, b, _ in g.suggest_links(top=3)])
print()

# %% 4. O retrato de cada grupo
print(g.profile())
print()

# %% 5. Ver
# Colorido por cidade, tamanho pela importância de ponte (betweenness).
g.save(SAIDA / "amigos.html", color="city", size="betweenness", title="Amigos por cidade")
print("Abra:", SAIDA / "amigos.html")

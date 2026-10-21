"""Dependências de software: em que ordem instalar, tem dependência circular, o que quebra se X cair?

Cada linha diz que um pacote depende de outro (pacote -> depende_de).

Rode na pasta do tareco:  python examples/receitas/06-software/software.py
"""

from pathlib import Path

import tareco

AQUI = Path(__file__).parent
SAIDA = AQUI / "saida"
SAIDA.mkdir(exist_ok=True)
tareco.set_language("pt")

# %% 1. Carregar
# As colunas "pacote" e "depende_de" não são nomes conhecidos, então dizemos
# quais são. directed=True: "loja-web depende de api" não é o mesmo que o contrário.
deps = tareco.Graph(AQUI / "dependencias.csv", source="pacote", target="depende_de", directed=True)
print(deps)
print()

# %% 2. Tem dependência circular?
ciclo = deps.find_cycle()
if ciclo:
    print("Dependência circular:", " -> ".join(ciclo + ciclo[:1]))
else:
    print("Nenhuma dependência circular.")
print()

# %% 3. Ordem de instalação
# topological_sort põe cada pacote antes dos que ele aponta. Aqui as setas vão do
# pacote para a dependência, então invertemos (reverse) para instalar a base primeiro.
# Com ciclo não existe ordem; removemos a aresta do ciclo para seguir.
sem_ciclo = deps.copy()
sem_ciclo.remove_edge("config", "cache")
ordem = sem_ciclo.reverse().topological_sort()
print("Instalar nesta ordem:", ", ".join(ordem))
print()

# %% 4. O que quebra se um pacote cair?
# Quem depende de utils, direta ou indiretamente: seguir as setas ao contrário.
afetados = deps.reverse().bfs("utils")[1:]
print(f"Se 'utils' quebrar, {len(afetados)} pacotes quebram junto: {', '.join(afetados[:8])}...")
print()

# %% 5. Os pacotes mais críticos
# pagerank no grafo de dependências: quanto mais coisas importantes dependem de
# um pacote, mais alto ele fica.
criticos = sorted(deps.pagerank().items(), key=lambda kv: -kv[1])[:5]
print("Mais críticos:", ", ".join(nome for nome, _ in criticos))
print()

# %% 6. Ver
deps.save(SAIDA / "dependencias.html", size="pagerank", title="Dependências")
print("Abra:", SAIDA / "dependencias.html")

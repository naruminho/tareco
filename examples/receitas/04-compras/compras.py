"""Cesta de compras: que tipos de cliente existem, e quem compra X também compra o quê?

Uma planilha de Excel com duas abas: "compras" (cliente, produto, valor, data)
e "clientes" (cliente, segmento, cidade). Os dados não dizem quem se parece com
quem; a projeção liga clientes que compram as mesmas coisas.

Rode na pasta do tareco:  python examples/receitas/04-compras/compras.py
"""

from pathlib import Path

import tareco

AQUI = Path(__file__).parent
SAIDA = AQUI / "saida"
SAIDA.mkdir(exist_ok=True)
tareco.set_language("pt")

# %% 1. Ler a planilha
# Não precisa de pandas: o tareco lê .xlsx sozinho. sheet escolhe a aba.
compras = tareco.read_excel(AQUI / "compras.xlsx", sheet="compras")
clientes = tareco.read_excel(AQUI / "compras.xlsx", sheet="clientes")
print(len(compras), "compras de", len(clientes), "clientes")
print()

# %% 2. Clientes ligados por produtos em comum
# method="newman": produto que todo mundo compra (água, pão) quase não conta;
# produto de nicho conta muito. attrs traz o segmento e a cidade de cada cliente.
parecidos = tareco.project(compras, nodes="cliente", via="produto", method="newman", attrs=clientes)
print(parecidos)
print(parecidos.explain())
print()

# %% 3. Produtos ligados por clientes em comum: "quem compra X também compra"
produtos = tareco.project(compras, nodes="produto", via="cliente")
for produto in ("fraldas", "whey", "picanha"):
    juntos = [outro for outro, _ in produtos.top_neighbors(produto, n=3)]
    print(f"Quem compra {produto} também compra: {', '.join(juntos)}")
print()

# %% 4. Ver
parecidos.save(SAIDA / "clientes.html", title="Clientes com compras parecidas")
produtos.save(SAIDA / "produtos.html", title="Produtos comprados juntos")
print("Abra:", SAIDA / "clientes.html")

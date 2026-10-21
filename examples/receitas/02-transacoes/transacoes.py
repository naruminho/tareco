"""Transferências entre contas: onde o dinheiro circula de um jeito estranho?

Seis meses de transferências (sintéticas) de um banco: salários, compras em
lojas, Pix entre amigos. No meio disso há três comportamentos plantados que
valem uma investigação. A receita mostra como o tareco aponta cada um.

Rode na pasta do tareco:  python examples/receitas/02-transacoes/transacoes.py
Os gráficos interativos vão para a pasta saida/ ao lado deste arquivo.
"""

from pathlib import Path

import tareco

AQUI = Path(__file__).parent
SAIDA = AQUI / "saida"
SAIDA.mkdir(exist_ok=True)
tareco.set_language("pt")  # textos em português

# %% 1. Carregar
# Cada linha de transacoes.csv é uma transferência: origem, destino, valor, data.
# O tareco reconhece "origem" e "destino" sozinho e usa "valor" como peso.
# Transferências repetidas entre as mesmas contas viram uma conexão só:
# os valores são somados e a coluna "count" diz quantas foram.
# directed=True porque dinheiro tem sentido: sai de uma conta e entra em outra.
g = tareco.Graph(AQUI / "transacoes.csv", nodes=AQUI / "contas.csv", directed=True)
print(g)
print()

# %% 2. O que a rede mostra
# Um resumo em linguagem simples: grupos, contas centrais e padrões estranhos.
print(g.explain())
print()

# %% 3. Os padrões, um por um
# - ciclo: dinheiro que dá a volta e volta para onde saiu;
# - fan_in: conta que recebe de muitas e quase não envia;
# - chain: cadeia de intermediárias, cada uma recebe de uma e repassa para uma.
# Os mais fortes vêm primeiro (limit=3 por tipo). Compare o valor que dá a volta
# no primeiro ciclo com o dos outros: amigos que fazem Pix entre si também fecham
# ciclos, mas com trocados.
print(g.patterns(kinds=["cycle", "fan_in", "chain"], limit=3))
print()

# %% 4. Ao longo do tempo
# A mesma tabela, agora mês a mês: quando cada coisa começou?
linha_do_tempo = tareco.timeline(AQUI / "transacoes.csv", time="data", directed=True,
                                 weight="valor", nodes=AQUI / "contas.csv")
for mudanca in linha_do_tempo.changes():
    print("-", mudanca.text)
print()

# %% 5. Investigar uma conta
# Só a vizinhança da conta x01: quem mandou para ela e para onde o dinheiro foi.
# Numa tabela gigante (Spark), isto busca só o necessário, sem carregar tudo.
perto = tareco.neighborhood(AQUI / "transacoes.csv", start="x01", hops=5, directed=True,
                            direction="out")
print(perto, "a partir de x01, seguindo o dinheiro")
for origem, destino in perto.edges:
    print(f"  {origem} -> {destino}: {perto.edges[origem, destino]['valor']:,.0f}")
print()

# %% 6. Ver e compartilhar
# Os arquivos abrem em qualquer navegador; o relatório tem os achados, as
# tabelas e o grafo com a linha do tempo. Troque save por show para abrir na hora.
g.save(SAIDA / "transacoes.html", title="Transferências")
perto.save(SAIDA / "x01.html", color="hop", title="Para onde foi o dinheiro de x01")
linha_do_tempo.report(SAIDA / "relatorio.html", title="Transferências, jan a jun")
print("Abra:", SAIDA / "relatorio.html")

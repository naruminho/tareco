"""Um surto: a partir do primeiro caso, quem pode ter sido exposto, e quando?

Três semanas de contatos entre 160 pessoas (quem esteve com quem, em que dia e
por quantos minutos). O primeiro caso é P017, no dia 3.

Rode na pasta do tareco:  python examples/receitas/07-surto/surto.py
"""

from pathlib import Path

import tareco

AQUI = Path(__file__).parent
SAIDA = AQUI / "saida"
SAIDA.mkdir(exist_ok=True)
tareco.set_language("pt")

# %% 1. Carregar como linha do tempo
# contatos.csv: pessoa_a, pessoa_b, dia, minutos. Os nomes de coluna não dizem
# quem é origem e destino, e tanto faz: contato vale para os dois lados.
contatos = tareco.timeline(AQUI / "contatos.csv", time="dia", freq="day", weight="minutos",
                           source="pessoa_a", target="pessoa_b")
print(contatos)
print()

# %% 2. Quem pode ter sido exposto, seguindo a ordem dos encontros
# Só conta uma cadeia de contatos que aconteceu nessa ordem: P017 encontra A,
# depois A encontra B.
expostos = contatos.spread("P017", since="2026-05-03")
# spread devolve {pessoa: quando foi alcançada}, incluindo a própria P017.
print(f"{len(expostos) - 1} pessoas podem ter sido expostas a partir de P017.")
por_dia = {}
for pessoa, quando in expostos.items():
    if pessoa != "P017":
        por_dia[quando.date()] = por_dia.get(quando.date(), 0) + 1
print("Expostos acumulados, dia a dia:")
acumulado = 0
for dia, n in sorted(por_dia.items()):
    acumulado += n
    print(f"  {dia}: {acumulado}")
print()

# %% 3. O que mudou dia a dia: o evento que espalhou tudo
for mudanca in contatos.changes():
    print("-", mudanca.text)
print()

# %% 4. Quem testar primeiro
# Pessoas expostas mais cedo e com mais contatos no período.
grafo = contatos.union
prioridade = sorted((p for p in expostos if p != "P017"),
                    key=lambda p: (expostos[p], -grafo.degree(p)))[:10]
print("Testar primeiro:", ", ".join(prioridade))
print()

# %% 5. Ver, com a linha do tempo
contatos.save(SAIDA / "contatos.html", title="Contatos dia a dia")
print("Abra:", SAIDA / "contatos.html")

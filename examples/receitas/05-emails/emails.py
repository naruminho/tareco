"""E-mails numa empresa: as áreas conversam entre si? Quem faz a ponte? O que mudou?

Seis meses de e-mails (quem escreveu para quem, e quando) e uma tabela com a
área e o cargo de cada pessoa.

Rode na pasta do tareco:  python examples/receitas/05-emails/emails.py
"""

from pathlib import Path

import tareco

AQUI = Path(__file__).parent
SAIDA = AQUI / "saida"
SAIDA.mkdir(exist_ok=True)
tareco.set_language("pt")

# %% 1. Carregar
# emails.csv: de, para, data. pessoas.csv: nome, area, cargo.
# Cada e-mail repetido entre as mesmas pessoas soma: a coluna count vira o peso.
g = tareco.Graph(AQUI / "emails.csv", nodes=AQUI / "pessoas.csv")
print(g)
print()

# %% 2. As áreas conversam entre si? (silos)
# profile(groups="area") olha cada área como um grupo: quanto das conversas fica
# dentro da área e com qual outra ela mais fala.
for area in g.profile(groups="area"):
    print(f"{area.name:<11} {area.size:>3} pessoas, {area.inward:.0%} das conversas dentro da área,"
          f" fala mais com {area.linked}")
print()

# %% 3. O resumo em palavras, incluindo quem faz ponte entre grupos
print(g.explain())
print()

# %% 4. O que mudou ao longo do tempo
linha = tareco.timeline(AQUI / "emails.csv", time="data", nodes=AQUI / "pessoas.csv", freq="month")
for mudanca in linha.changes():
    print("-", mudanca.text)
print()

# %% 5. Um comunicado da diretoria chega até onde, e quando?
# spread segue a ordem dos e-mails: só conta se A escreveu para B antes de B
# escrever para C.
diretor = next(n for n in g if g.nodes[n]["area"] == "Diretoria" and g.nodes[n]["cargo"] == "gerente")
alcance = linha.spread(diretor, since="2026-03-02")
print(f"Partindo de {diretor} em 2026-03-02, a notícia pode ter chegado a {len(alcance) - 1} pessoas.")
print()

# %% 6. Ver
linha.save(SAIDA / "emails.html", color="area", title="E-mails por área")
print("Abra:", SAIDA / "emails.html")

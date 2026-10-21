# 07. Um surto: quem pode ter sido exposto, e quando?

**A pergunta:** a partir do primeiro caso, quem pode ter sido exposto, seguindo
a ordem real dos encontros? Teve algum evento que espalhou tudo? Quem testar
primeiro?

O mesmo raciocínio serve para boato numa rede social, falha em cascata, ou
contaminação de um lote ao longo de uma cadeia de produção.

## Os dados

`contatos.csv`: uma linha por encontro, durante três semanas, entre 160 pessoas.

| pessoa_a | pessoa_b | dia | minutos |
| --- | --- | --- | --- |
| P008 | P019 | 2026-05-01 | 74 |
| P005 | P012 | 2026-05-01 | 82 |

O primeiro caso é P017, no dia 3.

## Rodar

```bash
python examples/receitas/07-surto/surto.py
```

## Passo a passo

**1. Carregar como linha do tempo.** Uma linha do tempo é uma rede por período
(aqui, por dia):

```python
contatos = tareco.timeline("contatos.csv", time="dia", freq="day", weight="minutos",
                           source="pessoa_a", target="pessoa_b")
```

```
<Timeline by day, 21 periods, 160 nodes, 871 connections>
```

**2. Quem pode ter sido exposto.** `spread` só segue uma cadeia de contatos que
aconteceu nessa ordem: P017 encontra A, **depois** A encontra B. Num grafo comum
(sem tempo) todo mundo que está ligado contaria, mesmo quem encontrou A antes
de A ser exposto.

```python
expostos = contatos.spread("P017", since="2026-05-03")
```

```
158 pessoas podem ter sido expostas a partir de P017.
Expostos acumulados, dia a dia:
  2026-05-03: 1
  2026-05-06: 6
  2026-05-09: 24
  2026-05-10: 62
  2026-05-11: 81
  ...
  2026-05-19: 158
```

O resultado é um dicionário `{pessoa: quando foi alcançada}`. Repare no salto do
dia 9 (24) para o dia 10 (62).

**3. O que aconteceu no dia 10?**

```python
for mudanca in contatos.changes():
    print(mudanca.text)
```

```
- A atividade cresceu 80% em 2026-05-10 (de 51 para 92 conexões).
- P077 saltou para 42 conexões em 2026-05-10 (cerca de 0,4 por período antes).
- Um grupo novo de 28 nós se formou em 2026-05-10, em torno de P077, ...
- A atividade caiu 43% em 2026-05-11 (de 92 para 52 conexões).
```

Uma festa: P077, que costumava encontrar menos de uma pessoa por dia, encontrou
42 pessoas de todas as turmas no mesmo dia. `changes()` encontrou isso sem
ninguém dizer o que procurar.

**4. Quem testar primeiro.** Quem foi exposto mais cedo e teve mais contatos:

```python
grafo = contatos.union          # todos os dias juntos, num grafo só
prioridade = sorted((p for p in expostos if p != "P017"),
                    key=lambda p: (expostos[p], -grafo.degree(p)))[:10]
```

```
Testar primeiro: P016, P011, P102, P115, P155, P008, P007, P003, P150, P118
```

**5. Ver.** `saida/contatos.html`, com a barra de tempo.

## O que olhar no gráfico

- Arraste a barra de tempo até 2026-05-10 e veja P077 no meio de todo mundo.
- Em **Destaques**, clique em "P077 saltou para 42 conexões": a página pula para
  o dia certo e acende os contatos dele.
- `contatos["2026-05-10"]` dá a rede só daquele dia, para analisar à parte.

## Com os seus dados

Qualquer tabela de encontros ou eventos com data. Se a ordem não importa, use
`contatos.union`, que junta todos os períodos num grafo só.

# 05. E-mails numa empresa: as áreas conversam entre si?

**A pergunta:** as áreas de uma empresa trabalham em silos? Quem faz a ponte
entre elas? O que mudou nos últimos seis meses? Um comunicado da diretoria
chega até onde?

Análise de redes organizacionais (ONA) é feita assim, com e-mails, reuniões ou
mensagens de chat. Os dados aqui são sintéticos.

## Os dados

`emails.csv`: uma linha por e-mail (1.139 linhas).

| de | para | data |
| --- | --- | --- |
| Tiago TI6 | Ursula TI7 | 2026-01-01 |
| Sara Mar5 | Tiago Mar6 | 2026-01-01 |

`pessoas.csv`: uma linha por pessoa.

| nome | area | cargo |
| --- | --- | --- |
| Ana Ven1 | Vendas | gerente |
| Bruno Ven2 | Vendas | analista |

## Rodar

```bash
python examples/receitas/05-emails/emails.py
```

## Passo a passo

**1. Carregar.** Não tem coluna de peso, e nem precisa: e-mails repetidos entre
as mesmas duas pessoas são somados numa ligação só, e a coluna `count` (quantos
e-mails) vira o peso sozinha.

```python
g = tareco.Graph("emails.csv", nodes="pessoas.csv")
```

```
<Graph undirected, 59 nodes, 291 edges>
```

Sem `directed=True`: aqui interessa quem conversa com quem, não quem escreveu
primeiro.

**2. As áreas conversam entre si?** `profile(groups="area")` trata cada área como
um grupo:

```python
for area in g.profile(groups="area"):
    print(area.name, area.size, area.inward, area.linked)
```

```
Vendas       14 pessoas, 89% das conversas dentro da área, fala mais com Marketing
TI           12 pessoas, 79% das conversas dentro da área, fala mais com Dados
Financeiro    8 pessoas, 91% das conversas dentro da área, fala mais com Vendas
Marketing     8 pessoas, 64% das conversas dentro da área, fala mais com Vendas
Dados         7 pessoas, 72% das conversas dentro da área, fala mais com TI
RH            6 pessoas, 86% das conversas dentro da área, fala mais com Vendas
Diretoria     4 pessoas, 71% das conversas dentro da área, fala mais com Vendas
```

`inward` é quanto das conversas fica dentro da área. O Financeiro (91%) é o mais
fechado; o Marketing (64%) é o que mais conversa para fora.

**3. O resumo em palavras.**

```
- Formam-se 7 grupos que se conectam principalmente entre si: 83% das conexões ficam dentro de um grupo.
- Grupo 1 (15 nós, 25%): area: Vendas em 93% (contra 24% no geral). Principais membros: Paulo Mar2, Ana Ven1 e Elisa Ven5.
- Grupo 2 (12 nós, 20%): area: TI em 100% (contra 20% no geral). ...
- Paulo Mar2 é uma ponte entre grupos: liga Grupo 1, Grupo 2 e Grupo 4.
- Os 10% de conexões mais fortes concentram 34% do total de ocorrências.
```

Os grupos que o tareco encontrou sozinho batem com as áreas: são silos de
verdade. Repare no Paulo Mar2: é do Marketing, mas caiu no grupo de Vendas e
liga Vendas, TI e Marketing. Se ele sair da empresa, essas áreas perdem o canal.

**4. O que mudou ao longo do tempo.**

```python
linha = tareco.timeline("emails.csv", time="data", nodes="pessoas.csv", freq="month")
```

```
- 7 nós novos apareceram em 2026-04.
- Um grupo novo de 7 nós se formou em 2026-04, em torno de Gabi Dad7, Elisa Dad5 e Ana Dad1.
```

Em abril nasceu a área de Dados: 7 pessoas novas que formam um grupo próprio.
`freq` pode ser `"day"`, `"week"`, `"month"`, `"quarter"` ou `"year"`; sem ele, o
tareco escolhe sozinho (no máximo 24 períodos).

**5. Um comunicado chega até onde?** `spread` segue a ordem dos e-mails: só conta
se A escreveu para B **antes** de B escrever para C.

```python
alcance = linha.spread("Wanda Dir1", since="2026-03-02")
```

```
Partindo de Wanda Dir1 em 2026-03-02, a notícia pode ter chegado a 58 pessoas.
```

O resultado é um dicionário `{pessoa: quando foi alcançada}`.

**6. Ver.** `saida/emails.html`, colorido por área, com a barra de tempo.

## O que olhar no gráfico

- Aperte **Reproduzir** na barra de tempo: os meses passam e a área de Dados
  aparece em abril.
- Clique em "Paulo Mar2 é uma ponte" em **Destaques** para ver as pontes dele.
- Legenda: dois cliques em "Financeiro" para ver só essa área.

## Com os seus dados

Qualquer registro de quem falou com quem: e-mails, reuniões (participante com
participante), mensagens, chamados. Para reuniões, que ligam várias pessoas de
uma vez, use a projeção da receita 04: `tareco.project(reunioes, nodes="pessoa", via="reuniao")`.

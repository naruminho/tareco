# Guia do tareco para quem nunca mexeu com grafos

Este guia parte do zero. Se você sabe abrir um CSV no Python, sabe usar o tareco.

- [O que é um grafo](#o-que-é-um-grafo)
- [Instalar](#instalar)
- [Seu primeiro grafo](#seu-primeiro-grafo)
- [Como a tabela precisa estar](#como-a-tabela-precisa-estar)
- [De onde vêm os dados](#de-onde-vêm-os-dados)
- [Entender a tela](#entender-a-tela)
- [Pergunta, função](#pergunta-função)
- [O resumo em palavras](#o-resumo-em-palavras)
- [Ao longo do tempo](#ao-longo-do-tempo)
- [Dados de dois lados](#dados-de-dois-lados)
- [Tabelas enormes, Spark e Databricks](#tabelas-enormes-spark-e-databricks)
- [Deu problema](#deu-problema)
- [Glossário](#glossário)

## O que é um grafo

Um grafo é uma rede: **coisas** e **ligações entre elas**.

| Coisas (nós) | Ligações | Pergunta típica |
| --- | --- | --- |
| pessoas | amizades, e-mails, reuniões | quem faz a ponte entre as áreas? |
| contas | transferências | o dinheiro está dando voltas? |
| clientes | produtos comprados em comum | que perfis de cliente existem? |
| estações | trechos de metrô | qual o caminho mais rápido? |
| pacotes, tarefas | "depende de" | em que ordem fazer? |
| fábricas, lojas | rotas de entrega | onde está o gargalo? |

Quando a pergunta é sobre **relações** (quem está ligado a quem, por onde passa,
quem está no meio, que grupos se formam), uma tabela comum não responde bem e um
grafo responde.

## Instalar

```bash
pip install tareco
```

Não precisa de mais nada. pandas, polars e Spark funcionam se você já tiver,
mas nenhum é obrigatório.

## Seu primeiro grafo

Uma tabela, `amizades.csv`:

```
de,para
Ana,Bia
Ana,Caio
Bia,Caio
Caio,Davi
```

Uma linha de código:

```python
import tareco

tareco.show("amizades.csv")
```

Abre uma página no navegador (ou dentro do notebook) com a rede: dá para
arrastar, buscar e clicar. As cores são os grupos que o tareco encontrou e o
tamanho é a importância de cada nó.

Para fazer perguntas, carregue num `Graph`:

```python
g = tareco.Graph("amizades.csv")
print(g.explain())                      # o que a rede mostra, em palavras
g.shortest_path("Ana", "Davi")          # ['Ana', 'Caio', 'Davi']
g.save("amizades.html")                 # a página, para mandar para alguém
```

Os textos saem no idioma do seu computador. Para fixar em português:
`tareco.set_language("pt")`.

## Como a tabela precisa estar

**Uma linha por ligação.** Uma coluna com a origem, outra com o destino. O resto
das colunas vira informação da ligação.

O tareco reconhece estes nomes sozinho:

| Papel | Nomes reconhecidos |
| --- | --- |
| origem | `source`, `from`, `src`, `origin`, `origem`, `de`, `sender`, `start`, `parent` |
| destino | `target`, `to`, `dst`, `destination`, `dest`, `destino`, `para`, `receiver`, `end`, `child` |
| peso | `weight`, `peso`, `valor`, `value`, `amount`, `quantidade`, `qtd`, `count`, `total`, `montante`, `quantity` |

Com outros nomes, diga quais são:

```python
g = tareco.Graph("pix.csv", source="pagador", target="recebedor", weight="quantia")
```

Se você não disser e nenhum nome bater, o tareco usa as duas primeiras colunas e
**avisa** qual escolheu (um `GuessWarning`). Leia o aviso: se a coluna estiver
errada, passe `source=` e `target=`.

**Direção.** Por padrão a ligação vale para os dois lados (amizade, contato).
Quando tem sentido (pagamento, e-mail enviado, "depende de"), use
`directed=True`.

**Linhas repetidas** entre as mesmas duas pontas viram uma ligação só: as colunas
de número são somadas e uma coluna `count` diz quantas linhas eram. Dez
transferências de Ana para Bia viram uma ligação com o valor total e `count=10`.

**O peso** é o que diz quanto uma ligação é forte (valor, número de mensagens,
minutos). Ele é usado no resumo, na espessura das linhas e quando você pede
`weight="weight"` nos algoritmos. O tareco escolhe a coluna sozinho pelos nomes
acima; para escolher outra, `weight="nome_da_coluna"`.

**Tabela de nós (opcional).** Uma segunda tabela, uma linha por nó, com o que
você sabe de cada um (cidade, área, segmento). É o que deixa o resumo
interessante: "Grupo 1: cidade Recife em 75%".

```python
g = tareco.Graph("amizades.csv", nodes="pessoas.csv")
```

A coluna que identifica o nó é reconhecida por nomes como `id`, `name`, `nome`,
`conta`, `cliente`, `usuario`, `pessoa`, `codigo`; senão vale a primeira coluna.
Para escolher: `node_id="matricula"`.

## De onde vêm os dados

Tudo isto funciona em `tareco.Graph(...)`, `tareco.show(...)` e nas outras funções:

```python
tareco.Graph("dados.csv")                 # CSV com , ; tab ou |, e decimais com vírgula
tareco.Graph("dados.xlsx")                # Excel (primeira aba), sem precisar de pandas
tareco.read_excel("dados.xlsx", sheet="vendas")   # outra aba
tareco.Graph("grafo.json")
tareco.Graph(df)                          # pandas ou polars
tareco.Graph(spark.table("tabela"))       # Spark
tareco.Graph([("Ana", "Bia"), ("Bia", "Caio", 3)])   # lista de pares (com peso opcional)
tareco.Graph({"Ana": ["Bia", "Caio"]})              # dicionário de vizinhos
```

E pelo terminal, sem escrever código:

```bash
tareco amizades.csv --nodes pessoas.csv --explain --lang pt
```

## Entender a tela

- **Passar o mouse** num nó: ele e os vizinhos acendem.
- **Clicar** num nó: abre a ficha com métricas, atributos e vizinhos (clicáveis).
- **Arrastar** um nó: ele fica preso onde você soltou. Botão direito solta.
- **Buscar** (tecla `/`): digite um nome e aperte Enter.
- **Destaques**: as frases do resumo. Clicar numa acende os nós de que ela fala.
- **Caminho mínimo**: clique em dois nós e o caminho entre eles acende.
- **Legenda**: um clique esconde o grupo, dois cliques mostram só ele.
- **Visão por grupos**: cada grupo vira uma bolha; clique numa para abrir.
- **Barra de tempo** (quando há datas): arraste ou aperte Reproduzir.
- Botões de enquadrar, rótulos, congelar o layout, tema claro/escuro e salvar imagem.

Escolhendo o que a tela mostra:

```python
g.show(color="cidade",           # cor por um atributo, ou "community", "pagerank"...
       size="betweenness",       # tamanho por uma métrica
       label="nome",             # o que aparece escrito
       edge_width="valor",       # espessura das linhas
       title="Minha rede")
```

Grafos grandes (milhares de nós) mudam sozinhos para WebGL, que aguenta dezenas
de milhares sem travar.

## Pergunta, função

| Você quer saber | Use |
| --- | --- |
| O que a rede mostra, em palavras | `g.explain()` |
| Que grupos existem e o que caracteriza cada um | `g.profile()`, `g.communities()` |
| Como cada área (ou outro atributo) se relaciona | `g.profile(groups="area")` |
| Quem é mais importante | `g.pagerank()` |
| Quem faz a ponte, por onde mais passa | `g.betweenness()` |
| Quem tem mais ligações | `g.degree(no)`, `g.degree_centrality()` |
| Com quem alguém mais se relaciona | `g.top_neighbors(no, n=5)` |
| O caminho entre dois | `g.shortest_path(a, b)`; o mais barato: `weight="weight"` |
| Caminhos alternativos | `g.k_shortest_paths(a, b, k=3)` |
| Quanto pode passar e qual o gargalo | `g.max_flow(a, b, capacity="capacidade")` |
| Quem deveria se conhecer | `g.suggest_links(top=10)` |
| Formas suspeitas (ciclos, concentradores, cadeias) | `g.patterns()` |
| Tem ciclo? Qual? | `g.has_cycle()`, `g.find_cycle()` |
| Em que ordem fazer | `g.topological_sort()` |
| Tudo que se alcança a partir de um nó | `g.bfs(no)` |
| A rede está partida? | `g.components()` |
| Só os vizinhos de alguém | `g.ego(no, radius=2)` |
| Um relatório para mandar | `g.report("relatorio.html")` |
| Levar os resultados para uma tabela | `g.to_pandas(metrics=["pagerank", "community"])` |

Os resultados são dicionários e listas comuns do Python:

```python
rank = g.pagerank()                                    # {'Ana': 0.31, 'Bia': 0.22, ...}
top3 = sorted(rank.items(), key=lambda kv: -kv[1])[:3] # os 3 maiores
```

Depois de mexer no grafo: `g.add_edge(a, b, valor=10)`, `g.remove_node(x)`,
`g.copy()`, `g.reverse()` (inverte as setas), `g.subgraph([...])`.

## O resumo em palavras

`explain()` é o melhor jeito de começar uma rede que você não conhece:

```python
print(g.explain())
```

Ele diz se a rede está partida, que grupos existem **e o que diferencia cada um**
(atributos muito mais comuns no grupo do que no geral), quem é importante, quem
faz ponte, quem concentra ligações, padrões que valem um olhar e o quanto o peso
está concentrado. Cada frase também guarda os nós de que fala:

```python
for achado in g.explain():
    print(achado.text, achado.nodes)
```

- `g.profile()`: a ficha completa de cada grupo.
- `g.patterns()`: as formas, uma por uma (ciclo, muitos para um, um para muitos,
  repassador, cadeia, ida e volta, estrela, panelinha).
- `g.report("arquivo.html")`: tudo isso numa página só, com tabelas e o grafo.
- `tareco.explain("dados.csv")` e `tareco.report("dados.csv", "saida.html")`
  fazem o mesmo direto do arquivo.

Um padrão é um ponto de partida para olhar, não um veredito. A
[receita 02](../examples/receitas/02-transacoes/) mostra a diferença.

## Ao longo do tempo

Se cada linha tem uma data, a rede vira uma linha do tempo:

```python
linha = tareco.timeline("emails.csv", time="data")
print(linha.explain())       # o que mudou: quem surgiu, quem disparou, grupos novos
linha.show()                 # a tela com a barra de tempo
linha["2026-04"]             # a rede de um período só
linha.union                  # todos os períodos juntos
linha.spread("Ana")          # quem pode ter recebido algo de Ana, na ordem do tempo
```

Datas podem vir como data, texto `2026-04-15`, `15/04/2026` ou número. O tareco
escolhe dia, semana, mês, trimestre ou ano sozinho; para escolher, `freq="month"`.

## Dados de dois lados

Às vezes a tabela não diz quem está ligado a quem, e sim "cliente comprou
produto", "aluno cursou disciplina", "conta usou dispositivo". A projeção liga
os clientes que compraram as mesmas coisas:

```python
clientes = tareco.project(compras, nodes="cliente", via="produto", method="newman")
```

`method="newman"` faz produto que todo mundo compra valer pouco. Veja a
[receita 04](../examples/receitas/04-compras/).

## Tabelas enormes, Spark e Databricks

- O tareco lê um DataFrame Spark direto: `tareco.Graph(spark.table("t"))`. As
  linhas vêm para a máquina aos poucos, sem pandas.
- Acima de 1 milhão de linhas ele recusa e sugere **agregar no Spark antes**:
  uma linha por par, com a soma. Quase sempre é o certo. (`max_rows=None`
  tira o limite.)
- Para investigar uma conta numa tabela gigante, `tareco.neighborhood(tabela,
  start="conta", hops=2)` busca só a vizinhança, dentro do cluster.
- No Databricks, `g.show()` desenha dentro da célula. Se o grafo não couber no
  limite de saída da célula, o tareco mostra a parte mais importante e avisa.
- `tareco.doctor(spark)` confere se tudo funciona no ambiente. Há um notebook
  pronto em [examples/databricks_check.py](../examples/databricks_check.py).

## Deu problema

**"no column looks like the source, so 'x' was used"**
O tareco não achou a coluna de origem pelo nome e chutou. Passe
`source="coluna"` e `target="coluna"`. Se o chute estiver certo e o aviso
incomodar: `warnings.filterwarnings("ignore", category=tareco.GuessWarning)`.

**As setas estão ao contrário**
Troque `source` e `target`, ou use `g.reverse()`.

**`tareco.NoPath: no path from 'A' to 'B'`**
Não existe caminho. Em grafos com direção, pode existir de B para A e não de A
para B. Veja as partes da rede com `g.components()`. Para tratar no código:

```python
try:
    g.shortest_path("A", "B")
except tareco.NoPath:
    print("sem caminho")
```

**`tareco.NodeNotFound: node 'X' is not in the graph`**
O nó não existe com esse nome exato. Confira maiúsculas, espaços e se o código
veio como número (`123`) ou texto (`"123"`): `"123" in g`.

**Na projeção, todo mundo ficou ligado a todo mundo**
Algum item é comprado por quase todos. Use `method="newman"`, ou diminua
`max_item_size`.

**O peso não é a coluna que eu queria**
Diga qual é: `tareco.Graph(..., weight="minutos")`. Para ignorar o peso num
algoritmo, não passe `weight`.

**Arquivo `.xls` (Excel antigo)**
Salve como `.xlsx` no Excel, ou leia com pandas.

**Os textos estão em inglês**
`tareco.set_language("pt")`, ou a variável de ambiente `TARECO_LANG=pt`.

**A página ficou pesada**
`g.show(max_nodes=5000)` mostra só os nós mais importantes. Em grafos enormes a
tela abre na visão por grupos.

## Glossário

- **Nó** (ou vértice): uma das coisas da rede. Uma pessoa, uma conta, uma estação.
- **Ligação** (ou aresta, conexão): a relação entre dois nós.
- **Peso**: quanto a ligação é forte ou custa (valor, mensagens, minutos).
- **Com direção** (dirigido): a ligação vai de um para o outro, como uma seta.
- **Grau**: quantas ligações um nó tem.
- **Vizinhos**: os nós ligados diretamente a um nó.
- **Grupo** (comunidade): nós que se ligam muito mais entre si do que com o resto.
- **Ponte**: nó que liga grupos diferentes.
- **PageRank**: importância de um nó, contando que ligações vindas de nós
  importantes valem mais.
- **Betweenness** (intermediação): em quantos caminhos mais curtos o nó está no
  meio. Alto = ponte, gargalo, ponto de falha.
- **Closeness** (proximidade): quão perto o nó está de todos os outros.
- **Componente**: uma parte da rede separada das outras.
- **Caminho mínimo**: o caminho com menos passos, ou o mais barato quando há peso.
- **Ciclo**: um caminho que volta ao ponto de partida.
- **Panelinha** (clique): um grupo em que todos estão ligados a todos.
- **Fluxo máximo**: o máximo que passa de um ponto a outro, respeitando a
  capacidade de cada ligação.
- **Corte mínimo**: as ligações que limitam o fluxo máximo; o gargalo.
- **Projeção**: transformar "cliente comprou produto" em "cliente parecido com cliente".
- **Ordem topológica**: uma ordem em que cada item vem antes dos que dependem dele.

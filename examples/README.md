# Exemplos

Oito receitas completas, cada uma com uma pergunta de verdade, os dados prontos
na pasta e um script comentado passo a passo. Rode de dentro da pasta do tareco:

```bash
python examples/receitas/01-amigos/amigos.py
```

Cada receita grava páginas HTML interativas na sua pasta `saida/`. Os scripts
são divididos em células (`# %%`), então também abrem como notebook no VS Code,
no Jupyter (com jupytext) e no Databricks.

Nunca usou grafos? Comece pela 01 e leia o [guia do iniciante](../docs/guia.md).

| Receita | A pergunta | O que você aprende |
| --- | --- | --- |
| [01. Amigos](receitas/01-amigos/) | Quem anda com quem e quem faz a ponte? | `Graph`, `explain`, `communities`, `shortest_path`, `top_neighbors`, `suggest_links`, `profile`, `save` |
| [02. Transferências](receitas/02-transacoes/) | Onde o dinheiro circula de um jeito estranho? | `directed=True`, `patterns` (ciclo, muitos para um, cadeia), `timeline`, `neighborhood`, `report` |
| [03. Suprimentos](receitas/03-suprimentos/) | Quanto dá para entregar e onde está o gargalo? | `max_flow` e corte mínimo, `remove_node`, `k_shortest_paths` |
| [04. Cesta de compras](receitas/04-compras/) | Que tipos de cliente existem? Quem compra X compra o quê? | `read_excel`, `project` (dados de dois lados), `method="newman"`, `attrs` |
| [05. E-mails](receitas/05-emails/) | As áreas trabalham em silos? O que mudou? | `profile(groups=...)`, pontes, `timeline(freq="month")`, `spread` |
| [06. Dependências](receitas/06-software/) | Em que ordem instalar? O que quebra junto? | `find_cycle`, `topological_sort`, `reverse`, `bfs`, `pagerank` |
| [07. Surto](receitas/07-surto/) | Quem pode ter sido exposto, e quando? | `timeline(freq="day")`, `spread` na ordem do tempo, `changes` |
| [08. Metrô](receitas/08-metro/) | Qual o caminho mais rápido? Que estação é vital? | `weight=`, `distance`, `betweenness`, `components`, o erro `NoPath` |

Os dados são sintéticos, gerados para cada história. Os comportamentos que as
receitas encontram (o anel de transferências, a festa no surto, a área nova nos
e-mails) foram plantados de propósito, para você ver o tareco achando sozinho.

## Outros arquivos

- [quickstart.py](quickstart.py): um tour rápido, em inglês, com `friends.csv` e `people.csv`.
- [databricks_check.py](databricks_check.py): notebook para importar no
  Databricks e conferir se tudo funciona lá (`tareco.doctor(spark)` e um gráfico
  por célula).

# 06. Dependências de software: em que ordem instalar?

**A pergunta:** num sistema com 22 pacotes que dependem uns dos outros, tem
dependência circular? Em que ordem instalar? Se um pacote quebrar, o que quebra
junto? Quais são os mais críticos?

Vale para qualquer coisa com "depende de": tarefas de um projeto, disciplinas
com pré-requisito, etapas de um processo, jobs de um pipeline de dados.

## Os dados

`dependencias.csv`: uma linha por dependência.

| pacote | depende_de |
| --- | --- |
| loja-web | api |
| loja-web | ui-kit |

## Rodar

```bash
python examples/receitas/06-software/software.py
```

## Passo a passo

**1. Carregar.** `pacote` e `depende_de` não são nomes que o tareco reconhece,
então dizemos quais são. A direção importa: "loja-web depende de api" não é o
mesmo que o contrário.

```python
deps = tareco.Graph("dependencias.csv", source="pacote", target="depende_de", directed=True)
```

Se você esquecer `source=` e `target=`, o tareco usa as duas primeiras colunas e
avisa qual escolheu.

**2. Tem dependência circular?**

```python
deps.find_cycle()
```

```
Dependência circular: config -> cache -> config
```

`find_cycle()` devolve um ciclo qualquer (de qualquer tamanho) ou `None`.
`has_cycle()` só responde sim ou não. Para ver todos os pacotes envolvidos em
ciclos: `[c for c in deps.strong_components() if len(c) > 1]`.

**3. Ordem de instalação.** `topological_sort()` põe cada pacote antes dos que
ele aponta. Aqui as setas vão do pacote para a dependência, então invertemos
(`reverse()`) para instalar a base primeiro. Com ciclo não existe ordem
possível, então tiramos a ligação do ciclo antes:

```python
sem_ciclo = deps.copy()
sem_ciclo.remove_edge("config", "cache")
sem_ciclo.reverse().topological_sort()
```

```
Instalar nesta ordem: utils, config, crypto, texto, datas, driver-sql, json, pdf, ui-kit, ...
```

**4. O que quebra se um pacote cair?** Quem depende de `utils`, direta ou
indiretamente: seguir as setas ao contrário.

```python
deps.reverse().bfs("utils")[1:]
```

```
Se 'utils' quebrar, 21 pacotes quebram junto: ui-kit, logging, banco, cache, config, ...
```

`bfs` (busca em largura) devolve todo mundo que dá para alcançar a partir de um
nó, dos mais próximos para os mais distantes.

**5. Os mais críticos.** PageRank num grafo de dependências: quanto mais coisas
importantes dependem de um pacote, mais alto ele fica.

```
Mais críticos: utils, logging, json, cache, config
```

**6. Ver.** `saida/dependencias.html`, com o tamanho de cada pacote pelo PageRank.

## O que olhar no gráfico

- Setas apontam para a dependência.
- Clique em `utils`: a ficha mostra quem depende dele.
- Os maiores círculos são os pacotes que não podem quebrar.

## Com os seus dados

Uma tabela de "item" e "depende de" basta. Para um projeto, `tarefa` e
`depende_de` dão a ordem de execução com `topological_sort()`.

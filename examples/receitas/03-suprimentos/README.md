# 03. Cadeia de suprimentos: quanto dá para entregar, e onde está o gargalo?

**A pergunta:** fornecedores abastecem fábricas, fábricas mandam para centros de
distribuição (CDs) e os CDs abastecem as lojas. Quanto a rede inteira consegue
entregar por semana? Qual rota limita tudo? E se uma fábrica parar?

O mesmo raciocínio vale para qualquer rede com capacidade: tubulação, rede
elétrica, rede de computadores, fluxo de pacientes entre hospitais.

## Os dados

`rotas.csv`: uma linha por rota (40 rotas).

| de | para | capacidade | custo | dias |
| --- | --- | --- | --- | --- |
| Fornecedor A | Fabrica MG | 600 | 8 | 2 |
| Fabrica SP | CD Sudeste | 400 | 4 | 1 |

`capacidade` é quanto passa por semana, `custo` é o custo por unidade e `dias`
é o prazo.

## Rodar

```bash
python examples/receitas/03-suprimentos/suprimentos.py
```

## Passo a passo

**1. Carregar.** `de` e `para` são reconhecidos sozinhos. As rotas têm sentido
(do fornecedor para a loja), então `directed=True`.

```python
rotas = tareco.Graph("rotas.csv", directed=True)
```

**2. Quanto chega na ponta?** O **fluxo máximo** usa a capacidade de cada rota e
calcula o máximo que sai de um ponto e chega em outro. Para medir a rede inteira
(vários fornecedores, várias lojas), um truque comum: criar uma `ORIGEM` ligada
a todos os fornecedores e um `DESTINO` ligado a todas as lojas, com capacidade
sobrando.

```python
rede = rotas.copy()
for f in fornecedores:
    rede.add_edge("ORIGEM", f, capacidade=10**9)
for loja in lojas:
    rede.add_edge(loja, "DESTINO", capacidade=10**9)
fluxo = rede.max_flow("ORIGEM", "DESTINO", capacity="capacidade")
```

```
A rede entrega até 2040 unidades por semana.
O gargalo tem 19 rotas; 18 são entregas dos CDs para as lojas.
  e também Fabrica MG -> CD Sul (300 por semana)
```

`fluxo.value` é o total. `fluxo.cut` é o **corte mínimo**: as rotas que, somadas,
limitam a entrega. Aumentar qualquer outra rota não adianta nada; é nelas que
se investe. Aqui o gargalo é a última milha (CDs para lojas), mais a rota da
fábrica de MG para o CD Sul.

`fluxo.flows` diz quanto passa em cada rota no melhor cenário.

**3. E se uma fábrica parar?** Tire a fábrica e calcule de novo:

```
Sem a Fabrica SP, a rede perde 740 unidades por semana.
Sem a Fabrica MG, a rede perde 620 unidades por semana.
Sem a Fabrica PR, a rede perde 100 unidades por semana.
```

A Fabrica PR quase não faz falta: outras rotas compensam. A SP é a mais crítica.

**4. O caminho mais barato, e as alternativas.**

```python
rotas.shortest_path("Fornecedor A", "Loja 07", weight="custo")
rotas.k_shortest_paths("Fornecedor A", "Loja 07", k=3, weight="custo")
```

```
Mais barato de Fornecedor A até Loja 07 (custo 17): Fornecedor A -> Fabrica MG -> CD Sul -> Loja 07
  alternativa (custo 20): Fornecedor A -> Fabrica MG -> CD Sudeste -> Loja 07
  alternativa (custo 22): Fornecedor A -> Fabrica SP -> CD Sudeste -> Loja 07
```

Troque `weight="custo"` por `weight="dias"` e a pergunta vira "qual o caminho
mais rápido".

**5. Ver.** `saida/rotas.html`, com a espessura de cada rota mostrando a
capacidade (`edge_width="capacidade"`).

## O que olhar no gráfico

- Setas mostram o sentido de cada rota.
- Botão **Caminho mínimo**: clique num fornecedor e depois numa loja.
- Clique num CD para ver de onde ele recebe e para quem entrega.

## Com os seus dados

Qualquer tabela de origem, destino e capacidade. Os nomes das colunas podem ser
outros: `max_flow(..., capacity="nome_da_coluna")`.

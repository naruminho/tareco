# 02. Transferências: onde o dinheiro circula de um jeito estranho?

**A pergunta:** em seis meses de transferências entre contas, há algo que
merece uma investigação? Dinheiro que dá a volta e volta para a origem, uma
conta que junta dinheiro de muitas outras, uma fila de contas que só repassam?

Esse é um dos usos mais comuns de grafos em bancos e fintechs (prevenção a
fraude e lavagem de dinheiro). Os dados aqui são **sintéticos**: salários,
compras em lojas, Pix entre amigos, e três comportamentos plantados no meio.

## Os dados

`transacoes.csv`: uma linha por transferência (10.501 linhas).

| origem | destino | valor | data |
| --- | --- | --- | --- |
| c004 | loja06 | 169.16 | 2026-01-01 |
| empresa | c001 | 7933.73 | 2026-01-05 |

`contas.csv`: uma linha por conta.

| conta | tipo | cidade | abertura |
| --- | --- | --- | --- |
| c001 | PF | Porto Alegre | 2024-02-10 |
| loja06 | PJ | Fortaleza | 2023-05-10 |

## Rodar

```bash
python examples/receitas/02-transacoes/transacoes.py
```

## Passo a passo

**1. Carregar.** `origem` e `destino` são reconhecidos sozinhos, e `valor` vira o
peso de cada ligação. `directed=True` porque dinheiro tem sentido: sai de uma
conta e entra em outra.

```python
g = tareco.Graph("transacoes.csv", nodes="contas.csv", directed=True)
```

```
<Graph directed, 371 nodes, 6257 edges>
```

10.501 transferências viraram 6.257 ligações: transferências repetidas entre as
mesmas duas contas são **somadas** numa ligação só, e uma coluna `count` guarda
quantas foram.

**2. O que a rede mostra.**

```python
print(g.explain())
```

```
O que esta rede mostra
- 371 nós e 6.257 ligações com direção; em média cada nó participa de 33,7 ligações.
- Os nós mais importantes são x01, x02 e y1.
- empresa tem 13,6x mais conexões que um nó típico (300 contra 22).
- r1, r2, r3 e r4 formam um ciclo: r1 para r2 para r3 para r4 para r1. Até 92.732 pode dar a volta completa.
- x01 recebe de 30 nós, 30 deles não enviam para mais ninguém, e envia para 2.
- empresa envia para 300 nós mas recebe de nenhum.
- Uma cadeia de 4 intermediários: x01 para x02 para y1 para y2 para y3 para exterior.
- 5 nós estão todos conectados entre si: c043, c048, c046, c044 e empresa.
- Os 10% de conexões mais fortes concentram 87% do total de valor.
- A conexão mais forte é entre x01 e x02 (145.000).
```

Os três comportamentos plantados aparecem sozinhos:

| Achado | O que é | Por que chama atenção |
| --- | --- | --- |
| r1, r2, r3, r4 formam um ciclo | o dinheiro sai de r1 e volta para r1 | girar dinheiro em círculo infla movimentação sem motivo econômico |
| x01 recebe de 30 nós que não enviam para mais ninguém | 30 contas novas mandam um valor cada para x01 | muitas contas "de passagem" juntando dinheiro numa só |
| cadeia x01, x02, y1, y2, y3, exterior | cada conta recebe de uma e repassa quase tudo para a próxima | camadas para afastar o dinheiro da origem |

E o que **não** é problema também aparece: "empresa envia para 300 nós" é a
folha de pagamento; a panelinha de 5 é um grupo de amigos que faz Pix entre
si, mais a empresa que paga o salário de todos. **Um padrão é um ponto de
partida para olhar, não um veredito.**

**3. Os padrões, um por um.** `patterns()` lista cada tipo de forma, os mais
fortes primeiro:

```python
g.patterns(kinds=["cycle", "fan_in", "chain"], limit=3)
```

```
- r1, r2, r3 e r4 formam um ciclo: ... Até 92.732 pode dar a volta completa.
- c235, c239 e c236 formam um ciclo: ... Até 201 pode dar a volta completa.
- c289, c293 e c290 formam um ciclo: ... Até 175 pode dar a volta completa.
- x01 recebe de 30 nós, 30 deles não enviam para mais ninguém, e envia para 2.
- loja03 recebe de 195 nós mas envia para nenhum.
- ...
```

Compare o primeiro ciclo (92.732) com os seguintes (201, 175): amigos que fazem
Pix entre si também fecham ciclos, mas com trocados. O valor que dá a volta é o
que separa um do outro.

Os tipos que existem: `cycle` (ciclo), `fan_in` (muitos para um), `fan_out` (um
para muitos), `relay` (recebe e repassa), `chain` (cadeia), `back_and_forth`
(ida e volta), `star` (estrela) e `clique` (todos ligados entre si).

**4. Ao longo do tempo.** A mesma tabela, mês a mês:

```python
linha = tareco.timeline("transacoes.csv", time="data", directed=True, weight="valor",
                        nodes="contas.csv")
for mudanca in linha.changes():
    print("-", mudanca.text)
```

```
- 31 nós novos apareceram em 2026-04.
- x01 apareceu em 2026-04 já com 30 conexões.
- Um grupo novo de 6 nós se formou em 2026-05, em torno de x01, x02 e y1.
```

Agora dá para contar a história: em abril surgem 30 contas novas e x01, que já
aparece recebendo de todas; em maio a cadeia que leva o dinheiro embora.

**5. Investigar uma conta.** Só a vizinhança de x01, seguindo o dinheiro:

```python
perto = tareco.neighborhood("transacoes.csv", start="x01", hops=5, directed=True, direction="out")
```

```
<Graph directed, 7 nodes, 6 edges> a partir de x01, seguindo o dinheiro
  x01 -> x02: 145,000
  x02 -> y1: 142,454
  y1 -> y2: 139,993
  y2 -> y3: 138,782
  y3 -> exterior: 136,433
```

Numa tabela gigante no Spark, `neighborhood` busca só essas linhas no cluster,
sem trazer a tabela inteira.

**6. Ver e compartilhar.** Três arquivos em `saida/`:

- `transacoes.html`: a rede inteira.
- `x01.html`: só o caminho do dinheiro de x01, colorido por distância (`color="hop"`).
- `relatorio.html`: o relatório para mandar para quem não usa Python, com os
  achados, tabelas e o grafo com a barra de tempo.

## O que olhar no gráfico

- Com mais de 2.000 ligações a página usa WebGL: continua leve com dezenas de milhares.
- Botão **Destaques**: clique em "r1, r2, r3 e r4 formam um ciclo" e o anel acende.
- No relatório, a barra de tempo embaixo: arraste até 2026-04 e veja x01 surgir.

## Com os seus dados

Uma tabela com quem pagou, quem recebeu e quanto já basta. Se tiver data, a
linha do tempo vem de graça. Para tabelas grandes, agregue no Spark antes
(uma linha por par de contas, com a soma e a contagem) e use `neighborhood`
para investigar contas específicas.

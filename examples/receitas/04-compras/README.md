# 04. Cesta de compras: que tipos de cliente existem?

**A pergunta:** olhando só o que cada cliente comprou, dá para descobrir os
perfis de cliente? E quem compra fraldas também compra o quê?

Aqui os dados **não dizem quem está ligado a quem**. Dizem "cliente comprou
produto". Esse tipo de dado (de dois lados) é muito comum: cliente e produto,
aluno e disciplina, conta e dispositivo, paciente e médico, ator e filme. A
**projeção** resolve: liga dois clientes quando compram as mesmas coisas.

## Os dados

Uma planilha de Excel, `compras.xlsx`, com duas abas. Não precisa de pandas nem
de Excel instalado: o tareco lê `.xlsx` sozinho.

Aba `compras` (854 linhas):

| cliente | produto | valor | data |
| --- | --- | --- | --- |
| cliente 001 | salgadinho | 77.39 | 2026-02-06 |
| cliente 001 | arroz | 71.99 | 2026-01-15 |

Aba `clientes` (120 linhas):

| cliente | segmento | cidade |
| --- | --- | --- |
| cliente 001 | fitness | Joao Pessoa |
| cliente 002 | churrasco | Maceio |

## Rodar

```bash
python examples/receitas/04-compras/compras.py
```

## Passo a passo

**1. Ler a planilha.** `sheet` escolhe a aba, pelo nome ou pela posição.

```python
compras = tareco.read_excel("compras.xlsx", sheet="compras")
clientes = tareco.read_excel("compras.xlsx", sheet="clientes")
```

O resultado é uma lista de linhas (dicionários). Datas viram datas e números
viram números. Também dá para passar o arquivo direto: `tareco.Graph("planilha.xlsx")`
usa a primeira aba.

**2. Ligar clientes que compram as mesmas coisas.**

```python
parecidos = tareco.project(compras, nodes="cliente", via="produto",
                           method="newman", attrs=clientes)
print(parecidos.explain())
```

- `nodes="cliente"`: quem vira nó.
- `via="produto"`: o que liga um ao outro.
- `method="newman"`: produto que todo mundo compra (arroz, pão) quase não conta;
  produto de nicho (whey, carvão) conta muito. Sem isso, todo mundo fica ligado
  a todo mundo pelo arroz.
- `attrs=clientes`: traz o segmento e a cidade de cada cliente, para o tareco
  dizer o que caracteriza cada grupo.

```
- Formam-se 4 grupos, mas a maioria das conexões (60%) cruza de um grupo para outro.
- Grupo 1 (31 nós, 26%): segmento: estudante em 97% (contra 25% no geral). Principais membros: cliente 075, cliente 103 e cliente 063.
- Grupo 2 (30 nós, 25%): segmento: fitness em 100% (contra 25% no geral). ...
- Grupo 3 (30 nós, 25%): segmento: churrasco em 100% (contra 25% no geral). ...
- Grupo 4 (29 nós, 24%): segmento: familia em 100% (contra 25% no geral). ...
- cliente 009 é uma ponte entre grupos: liga Grupo 2, Grupo 1, Grupo 4 e Grupo 3.
```

O tareco não sabia o segmento de ninguém na hora de formar os grupos: encontrou
4 grupos só pelas compras, e depois conferiu que cada grupo corresponde a um
segmento. Num caso real, é assim que se descobre um segmento que ninguém tinha
cadastrado. O cliente 009, que liga os quatro grupos, compra de tudo um pouco.

**3. Quem compra X também compra.** Agora o contrário: produtos ligados por
clientes em comum.

```python
produtos = tareco.project(compras, nodes="produto", via="cliente")
produtos.top_neighbors("fraldas", n=3)
```

```
Quem compra fraldas também compra: biscoito, leite, lenco umedecido
Quem compra whey também compra: pasta de amendoim, banana, aveia
Quem compra picanha também compra: cerveja, linguica, carvao
```

`top_neighbors` devolve os vizinhos com a ligação mais forte: aqui, os produtos
com mais clientes em comum.

**4. Ver.** `saida/clientes.html` (clientes coloridos por grupo) e
`saida/produtos.html` (produtos comprados juntos).

## O que olhar no gráfico

- Passe o mouse sobre uma ligação entre dois clientes: `shared` diz quantos
  produtos eles têm em comum e `examples` mostra alguns.
- Na legenda, cada grupo aparece com o traço mais forte (por exemplo, "estudante").
- Botão **Visão por grupos**: cada grupo vira uma bolha, ligada às outras pelo
  quanto se parecem.

## Com os seus dados

Qualquer tabela com uma coluna "quem" e uma coluna "o quê". Produtos que quase
todo mundo compra são pulados acima de `max_item_size` (1.000 clientes), com
aviso: eles ligariam todo mundo a todo mundo.

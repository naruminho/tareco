# 01. Amigos: quem anda com quem?

A receita mais simples. Comece por aqui.

**A pergunta:** numa turma de 16 amigos, quais grupinhos existem, quem faz a
ponte entre eles e quem deveria se conhecer?

## Os dados

Duas planilhas CSV que já vêm na pasta `examples/`:

`friends.csv`: uma linha por amizade.

| from | to | messages |
| --- | --- | --- |
| Ana | Bia | 42 |
| Ana | Caio | 18 |

`people.csv`: uma linha por pessoa (opcional, mas é o que dá cor ao resultado).

| name | city | age |
| --- | --- | --- |
| Ana | Recife | 31 |
| Bia | Recife | 28 |

Só isso. A primeira tabela diz quem está ligado a quem; a segunda diz quem é
cada um.

## Rodar

Na pasta do tareco:

```bash
python examples/receitas/01-amigos/amigos.py
```

## Passo a passo

**1. Carregar.** O tareco reconhece sozinho as colunas `from` e `to`. Como a
coluna com o número de mensagens não se chama `weight`, dizemos qual é:

```python
g = tareco.Graph("friends.csv", nodes="people.csv", weight="messages")
print(g)
```

```
<Graph undirected, 16 nodes, 31 edges>
```

16 pessoas (nós) e 31 amizades (conexões). *Undirected* quer dizer "sem
direção": amizade vale para os dois lados.

**2. O resumo em palavras.** `explain()` conta o que a rede mostra, sem você
precisar saber o nome de nenhum algoritmo:

```
O que esta rede mostra
- 16 nós e 31 conexões; em média cada nó se conecta a 3,9 outros.
- Tudo está conectado numa única rede.
- Formam-se 4 grupos que se conectam principalmente entre si: 77% das conexões ficam dentro de um grupo.
- Grupo 1 (4 nós, 25%): city: Recife em 75% (contra 19% no geral). Principais membros: Bia, Caio e Ana.
- Grupo 2 (4 nós, 25%): city: São Paulo em 75% (contra 19% no geral). Principais membros: Gabi, Fabi e Edu.
- ...
- Iris é uma ponte entre grupos: liga Grupo 3, Grupo 2 e Grupo 1.
- A conexão mais forte é entre Ana e Bia (42).
```

Repare em "city: Recife em 75% (contra 19% no geral)": o tareco olhou a tabela
de pessoas e descobriu sozinho o que caracteriza cada grupo.

**3. Perguntas diretas.** Cada pergunta é um método:

```python
g.communities()                 # os grupos
g.shortest_path("Ana", "Otto")  # o caminho mais curto
g.top_neighbors("Iris", n=3)    # com quem Iris mais conversa
g.suggest_links(top=3)          # quem tem amigos em comum mas ainda não se conhece
```

```
Grupo 1: Ana, Bia, Caio, Duda
Grupo 2: Edu, Fabi, Gabi, Heitor
Grupo 3: Iris, João, Kaio, Lia
Grupo 4: Mel, Nina, Otto, Pedro
Caminho de Ana até Otto: ['Ana', 'Pedro', 'Otto']
Com quem Iris mais conversa: [('João', 35), ('Lia', 24), ('Kaio', 19)]
Quem deveria se conhecer: [('Ana', 'Mel'), ('Bia', 'Pedro'), ('Ana', 'Edu')]
```

**4. O retrato de cada grupo.** `profile()` dá a ficha completa: traços, membros
principais, quanto das conexões fica dentro do grupo e com qual outro ele mais
fala.

**5. Ver.** `g.save(...)` grava uma página HTML que abre em qualquer navegador
(`g.show(...)` abre na hora):

```python
g.save("amigos.html", color="city", size="betweenness", title="Amigos por cidade")
```

- `color="city"`: uma cor por cidade.
- `size="betweenness"`: quem faz mais ponte fica maior. Iris e Mel saltam aos olhos.

## O que olhar no gráfico

- Passe o mouse num nó: os vizinhos acendem.
- Clique num nó: abre a ficha com métricas, atributos e vizinhos.
- Botão **Destaques**: as mesmas frases do `explain()`. Clicar numa acende os nós de que ela fala.
- Botão **Caminho mínimo**: clique em Ana e depois em Otto.
- Legenda: clique numa cidade para escondê-la, dois cliques para ver só ela.

## Com os seus dados

Qualquer tabela com duas colunas de "quem" e "com quem" serve. Se as colunas
tiverem outros nomes, diga quais são:

```python
g = tareco.Graph("minha_tabela.csv", source="remetente", target="destinatario")
```

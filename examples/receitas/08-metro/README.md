# 08. Metrô: qual o caminho mais rápido, e que estação é vital?

**A pergunta:** numa rede de metrô (fictícia), qual o caminho mais rápido entre
duas estações? Quais as alternativas? Por que estações passa mais gente? E se a
estação Centro fechar?

Serve para qualquer rede de deslocamento: ruas, voos, rede logística, cabos de
rede, corredores de um prédio.

## Os dados

`ligacoes.csv`: uma linha por trecho entre duas estações vizinhas.

| estacao_a | estacao_b | minutos | linha |
| --- | --- | --- | --- |
| Aeroporto | Vila Nova | 5 | Azul |
| Vila Nova | Centro | 6 | Azul |

## Rodar

```bash
python examples/receitas/08-metro/metro.py
```

## Passo a passo

**1. Carregar.** `weight="minutos"` diz que o custo de cada trecho é o tempo. Sem
`directed`: o trem anda nos dois sentidos.

```python
metro = tareco.Graph("ligacoes.csv", source="estacao_a", target="estacao_b", weight="minutos")
```

**2. O caminho mais rápido.**

```python
metro.shortest_path("Aeroporto", "Lagoa", weight="weight")
metro.distance("Aeroporto", "Lagoa", weight="weight")
```

```
Aeroporto até Lagoa: Aeroporto -> Vila Nova -> Centro -> Catedral -> Estadio -> Lagoa (28 minutos)
```

`weight="weight"` quer dizer "use o peso do grafo", que aqui é `minutos`. Sem
`weight`, o caminho mais curto é o de **menos estações**, não o mais rápido.

**3. Alternativas.**

```python
metro.k_shortest_paths("Aeroporto", "Lagoa", k=3, weight="weight")
```

```
  alternativa (32 min): Aeroporto -> Vila Nova -> Centro -> Praca -> Catedral -> Estadio -> Lagoa
  alternativa (32 min): Aeroporto -> Vila Nova -> Centro -> Catedral -> Shopping -> Estadio -> Lagoa
```

**4. Que estação é vital?** *Betweenness* (intermediação) conta em quantos dos
caminhos mais curtos a estação está no meio do caminho.

```
Estações por onde mais caminhos passam: Centro, Catedral, Praca, Shopping
```

**5. E se a Centro fechar?**

```python
sem_centro = metro.copy()
sem_centro.remove_node("Centro")
sem_centro.distance("Aeroporto", "Lagoa", weight="weight")
```

```
Sem a Centro não há como ir do Aeroporto à Lagoa. Ficam isoladas: Aeroporto, Vila Nova; Fabrica, Porto
```

Quando não existe caminho, `distance` e `shortest_path` levantam o erro
`tareco.NoPath`. A receita captura esse erro (`try` / `except tareco.NoPath`) e
mostra quem ficou isolado com `components()`, que devolve as partes separadas da
rede, a maior primeiro.

**6. Ver.** `saida/metro.html`, com o tamanho de cada estação pela betweenness.

## O que olhar no gráfico

- Botão **Caminho mínimo**: clique em Aeroporto e depois em Lagoa.
- A Centro é a maior bolinha: é por onde tudo passa.
- Arraste uma estação: ela fica presa onde você soltou (botão direito solta de novo).

## Com os seus dados

Uma tabela de trechos com o custo (tempo, distância, preço). Para ruas de mão
única ou voos, use `directed=True`.

# 08. Subway: what is the fastest way, and which station is vital?

**The question:** on a (made-up) subway network, what is the fastest way
between two stations? What are the alternatives? Which stations do most trips
go through? What if Central station closes?

It works for any network you move through: streets, flights, a logistics
network, network cables, the corridors of a building.

## The data

`links.csv`: one row per stretch between two neighboring stations.

| station_a | station_b | minutes | line |
| --- | --- | --- | --- |
| Airport | New Town | 5 | Blue |
| New Town | Central | 6 | Blue |

## Run it

```bash
python examples/recipes/08-subway/subway.py
```

## Step by step

**1. Load.** `minutes` is the only number column, so it becomes the weight: the
cost of each stretch is its time. No `directed`: trains run both ways.

```python
subway = tareco.Graph("links.csv", source="station_a", target="station_b")
```

**2. The fastest way.**

```python
subway.shortest_path("Airport", "Lake", weight="weight")
subway.distance("Airport", "Lake", weight="weight")
```

```
Airport to Lake: Airport -> New Town -> Central -> Cathedral -> Stadium -> Lake (28 minutes)
```

`weight="weight"` means "use the graph's weight", `minutes` here. Without
`weight`, the shortest path is the one with the **fewest stations**, not the
fastest.

**3. Alternatives.**

```python
subway.k_shortest_paths("Airport", "Lake", k=3, weight="weight")
```

```
  alternative (32 min): Airport -> New Town -> Central -> Square -> Cathedral -> Stadium -> Lake
  alternative (32 min): Airport -> New Town -> Central -> Cathedral -> Mall -> Stadium -> Lake
```

**4. Which station is vital?** *Betweenness* counts in how many of the shortest
paths a station sits in the middle.

```
Stations most paths go through: Central, Cathedral, Square, Mall
```

**5. What if Central closes?**

```python
without_central = subway.copy()
without_central.remove_node("Central")
without_central.distance("Airport", "Lake", weight="weight")
```

```
Without Central there is no way from Airport to Lake. Cut off: Airport, New Town; Factory, Port
```

When there is no path, `distance` and `shortest_path` raise `tareco.NoPath`. The
recipe catches it (`try` / `except tareco.NoPath`) and shows who got cut off
with `components()`, which returns the separate parts of the network, largest
first.

**6. See it.** `out/subway.html`, with each station sized by betweenness.

## What to look at in the page

- **Shortest path** button: click Airport, then Lake.
- Central is the biggest dot: everything goes through it.
- Drag a station: it stays where you drop it (right-click lets it go again).

## With your own data

A table of stretches with their cost (time, distance, price). For one-way
streets or flights, use `directed=True`.

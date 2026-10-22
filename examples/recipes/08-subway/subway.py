"""Subway: what is the fastest way, what are the alternatives, which station is vital?

Four (made-up) subway lines. Each row links two neighboring stations and says how
many minutes the ride takes.

Run from the tareco folder:  python examples/recipes/08-subway/subway.py
"""

from pathlib import Path

import tareco

HERE = Path(__file__).parent
OUT = HERE / "out"
OUT.mkdir(exist_ok=True)

# %% 1. Load
# links.csv: station_a, station_b, minutes, line. minutes is the only number
# column, so it becomes the weight: the cost of each stretch is its time.
subway = tareco.Graph(HERE / "links.csv", source="station_a", target="station_b")
print(subway)
print()

# %% 2. The fastest way
# weight="weight" means "use the graph's weight", minutes here. Without it the
# shortest path is the one with the fewest stations, not the fastest.
route = subway.shortest_path("Airport", "Lake", weight="weight")
minutes = subway.distance("Airport", "Lake", weight="weight")
print(f"Airport to Lake: {' -> '.join(route)} ({minutes} minutes)")

# %% 3. Alternatives
for alternative in subway.k_shortest_paths("Airport", "Lake", k=3, weight="weight")[1:]:
    time = sum(subway.edges[a, b]["minutes"] for a, b in zip(alternative, alternative[1:]))
    print(f"  alternative ({time} min): {' -> '.join(alternative)}")
print()

# %% 4. Which station is vital?
# betweenness: in how many of the shortest paths the station sits in the middle.
vital = sorted(subway.betweenness().items(), key=lambda kv: -kv[1])[:4]
print("Stations most paths go through:", ", ".join(s for s, _ in vital))

# %% 5. What if Central closes?
without_central = subway.copy()
without_central.remove_node("Central")
try:
    new = without_central.distance("Airport", "Lake", weight="weight")
    print(f"Without Central, Airport to Lake takes {new} minutes (it was {minutes}).")
except tareco.NoPath:
    # no path at all: Central was the Airport's only link to the rest
    cut_off = sorted(without_central.components()[1:], key=len)
    print("Without Central there is no way from Airport to Lake. Cut off:",
          "; ".join(", ".join(sorted(c)) for c in cut_off))
print()

# %% 6. See it
subway.save(OUT / "subway.html", size="betweenness", title="Subway")
print("Open:", OUT / "subway.html")

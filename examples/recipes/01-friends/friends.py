"""Friends: who hangs out with whom, and who bridges the groups?

The simplest recipe; start here. One table says who talks to whom and how many
messages they exchanged, another gives each person's city and age.

Run from the tareco folder:  python examples/recipes/01-friends/friends.py
"""

from pathlib import Path

import tareco

HERE = Path(__file__).parent
DATA = HERE.parent.parent  # friends.csv and people.csv live in examples/
OUT = HERE / "out"
OUT.mkdir(exist_ok=True)

# %% 1. Load
# friends.csv has the columns from, to, messages; people.csv has name, city, age.
# "from" and "to" are recognized on their own, and messages, the only number
# column, becomes the strength of each friendship (the weight).
g = tareco.Graph(DATA / "friends.csv", nodes=DATA / "people.csv")
print(g)
print()

# %% 2. What it shows, in words
print(g.explain())
print()

# %% 3. Direct questions
# communities() returns a list of groups; each group is a set of names.
for i, group in enumerate(g.communities(), 1):
    print(f"Group {i}:", ", ".join(sorted(group)))
print("Path from Ana to Otto:", g.shortest_path("Ana", "Otto"))
print("Who Iris talks to most:", g.top_neighbors("Iris", n=3))
print("Who should meet:", [(a, b) for a, b, _ in g.suggest_links(top=3)])
print()

# %% 4. A portrait of each group
print(g.profile())
print()

# %% 5. See it
# Colored by city, sized by how much each person bridges the others (betweenness).
g.save(OUT / "friends.html", color="city", size="betweenness", title="Friends by city")
print("Open:", OUT / "friends.html")

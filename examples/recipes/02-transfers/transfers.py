"""Money transfers: where does money move in a strange way?

Six months of (synthetic) transfers between bank accounts: salaries, shopping,
friends paying each other back. Hidden in there are three behaviors worth a
closer look. The recipe shows how tareco points at each one.

Run from the tareco folder:  python examples/recipes/02-transfers/transfers.py
The interactive pages go to the out/ folder next to this file.
"""

from pathlib import Path

import tareco

HERE = Path(__file__).parent
OUT = HERE / "out"
OUT.mkdir(exist_ok=True)

# %% 1. Load
# Each row of transfers.csv is one transfer: sender, receiver, amount, date.
# tareco recognizes "sender" and "receiver" on its own and uses "amount" as the weight.
# Repeated transfers between the same two accounts become one connection: the
# amounts are added up and a "count" column says how many there were.
# directed=True because money has a direction: it leaves one account and enters another.
g = tareco.Graph(HERE / "transfers.csv", nodes=HERE / "accounts.csv", directed=True)
print(g)
print()

# %% 2. What the network shows
# A summary in plain words: groups, central accounts and odd shapes.
print(g.explain())
print()

# %% 3. The patterns, one by one
# - cycle: money that goes around and comes back to where it left;
# - fan_in: an account that receives from many and hardly sends anything on;
# - chain: a line of go-betweens, each receiving from one and passing it to one.
# The strongest come first (limit=3 per kind). Compare the amount that goes all
# the way around in the first loop with the others: friends paying each other
# back close loops too, but with pocket money.
print(g.patterns(kinds=["cycle", "fan_in", "chain"], limit=3))
print()

# %% 4. Over time
# The same table, month by month: when did each thing start?
timeline = tareco.timeline(HERE / "transfers.csv", time="date", directed=True,
                           nodes=HERE / "accounts.csv")
for change in timeline.changes():
    print("-", change.text)
print()

# %% 5. Look into one account
# Only the neighborhood of x01, following the money out of it.
# On a huge table (Spark) this fetches just what it needs, without loading everything.
near = tareco.neighborhood(HERE / "transfers.csv", start="x01", hops=5, directed=True,
                           direction="out")
print(near, "from x01, following the money")
for sender, receiver in near.edges:
    print(f"  {sender} -> {receiver}: {near.edges[sender, receiver]['amount']:,.0f}")
print()

# %% 6. See and share
# The files open in any browser; the report has the findings, the tables and the
# graph with the time slider. Swap save for show to open them right away.
g.save(OUT / "transfers.html", title="Transfers")
near.save(OUT / "x01.html", color="hop", title="Where the money from x01 went")
timeline.report(OUT / "report.html", title="Transfers, January to June")
print("Open:", OUT / "report.html")

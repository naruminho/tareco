"""Bank statements: what deserves a closer look, and how do I get back to the records?

Six months of statements (one row per entry on an account, money out negative)
for 200 customers, plus each customer's occupation and income, and the devices
each one logs in from. All synthetic, with a few behaviors planted on purpose.

Run from the tareco folder:  python examples/recipes/09-statements/statements.py
"""

from pathlib import Path

import tareco

HERE = Path(__file__).parent
OUT = HERE / "out"
OUT.mkdir(exist_ok=True)

# %% 1. Load the statements
# account and counterparty name the two sides of each entry; the sign of amount
# says which way the money went. A transfer between two customers shows on both
# statements, and tareco counts it once. keep=True keeps the rows behind every
# link, so every finding can take us back to the records.
g = tareco.Graph(HERE / "statements.csv", account="account", counterparty="counterparty",
                 kind="transfer", nodes=HERE / "customers.csv", keep=True)

# %% 2. Another kind of link: who logs in from which device
# Logins have no direction and carry no money; they join the same graph as links
# of their own kind, and devices become nodes of their own kind.
g.add_links(HERE / "logins.csv", source="account", target="device", kind="uses")
print(g)
print(g.kinds())
print()

# %% 3. What it shows
print(g.explain())
print()

# %% 4. Many amounts just under a limit
# The limit comes from you: here, transfers of 10,000 or more get reported.
print(g.splits(limit=10_000, within="7 days"))
print()

# %% 5. Amounts far above what the account usually sends
print(g.unusual_amounts(limit=3))
print()

# %% 6. Where the money goes
flows = g.flows(by="counterparty_country")
print(flows)
print("Sent to Palm Isles by:", ", ".join(flows["Palm Isles"].nodes))
print()

# %% 7. Who does not fit with the people they deal with
print(g.misfits("monthly_income"))
print(g.misfits("occupation"))
print()

# %% 8. Close to a known case
# a017 is already under review. Who is close to it? Paths do not go through
# shops or employers: everybody is two steps from a supermarket.
print(g.near(["a017"]))
print()

# %% 9. One account, up close
print(g.why("a023"))
print()

# %% 10. Others that behave like a known case
alike = g.similar_to("a017", n=5)
print(alike)
print()

# %% 11. The work list
# Everything above, gathered per account and ranked: the strongest cases first,
# one line per kind of signal, and the ids of the transactions behind them.
# review.to_pandas() or review.to_spark(spark) turns it into a table to work from.
review = g.review(watch=["a017"], limit=10_000, top=5)
print(review)
print()

# %% 12. Money passed on fast
# A large amount in, and most of it out to others within a few days.
print(g.fast_moves(within="3 days"))
print()

# %% 13. Following the money in time
# Only paths where each transfer happens after the one before it count.
print(g.trace("a181", "PI-ACC-8", within="30 days"))
print()

# %% 14. One person, several accounts?
# Accounts tied by the devices they share. A device shared by many accounts (a
# branch computer) would tie nobody. people.graph() merges each group into one
# node, and the same questions then run per person.
people = g.entities(via="device")
print(people.of("a017"))
print(people.graph().review(limit=10_000, top=1))
print()

# %% 15. Back to the records
# Every finding keeps the rows of your table behind it.
pile = g.splits(limit=10_000)[0]
print("Transactions to review:", ", ".join(pile.rows.column("transaction_id")))
# And any list of accounts can be looked up in the original table. With Spark,
# tareco.records(spark.table("statements"), ...) filters in the cluster.
rows = tareco.records(HERE / "statements.csv", alike.nodes[0], columns=["account"])
print(f"{alike.nodes[0]} has {len(rows)} rows in statements.csv")
print()

# %% 16. See it
# Colored by kind of node; click an account for what stands out about it, click a
# finding for the rows behind it, and use the legend to hide each kind of link.
g.save(OUT / "statements.html", color="kind", title="Statements and devices")
g.save(OUT / "statements.svg", color="kind", title="Statements")  # a still picture for slides
print("Open:", OUT / "statements.html")

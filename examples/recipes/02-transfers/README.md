# 02. Money transfers: where does money move in a strange way?

**The question:** in six months of transfers between accounts, is anything
worth investigating? Money that goes around and comes back, one account
collecting from many others, a line of accounts that only pass money on?

This is one of the most common uses of graphs in banks and fintechs (fraud and
money-laundering prevention). The data here is **synthetic**: salaries,
shopping, friends paying each other back, and three behaviors planted in the
middle.

## The data

`transfers.csv`: one row per transfer (10,501 rows).

| sender | receiver | amount | date |
| --- | --- | --- | --- |
| c004 | shop06 | 169.16 | 2026-01-01 |
| employer | c001 | 7933.73 | 2026-01-05 |

`accounts.csv`: one row per account.

| account | type | city | opened |
| --- | --- | --- | --- |
| c001 | person | Seattle | 2024-02-10 |
| shop06 | business | Chicago | 2023-05-10 |

## Run it

```bash
python examples/recipes/02-transfers/transfers.py
```

## Step by step

**1. Load.** `sender` and `receiver` are recognized on their own, and `amount`
becomes the weight of each link. `directed=True` because money has a direction:
it leaves one account and enters another.

```python
g = tareco.Graph("transfers.csv", nodes="accounts.csv", directed=True)
```

```
<Graph directed, 371 nodes, 6257 edges>
```

10,501 transfers became 6,257 links: repeated transfers between the same two
accounts are **added up** into one link, and a `count` column keeps how many
there were.

**2. What the network shows.**

```python
print(g.explain())
```

```
What this network shows
- 371 nodes and 6,257 directed links; on average each node takes part in 33.7 links.
- The most important nodes are x01, x02 and y1.
- employer has 13.6x more connections than a typical node (300 vs 22).
- r1, r2, r3 and r4 form a loop: r1 to r2 to r3 to r4 to r1. Up to 92,732 can go all the way around.
- x01 receives from 30 nodes, 30 of which send to nobody else, and sends to 2.
- employer sends to 300 nodes but receives from none.
- A chain of 4 intermediaries: x01 to x02 to y1 to y2 to y3 to abroad.
- 5 nodes are all connected to each other: c043, c048, c046, c044 and employer.
- The heaviest 10% of the connections carry 87% of the total amount.
- The strongest connection is x01 and x02 (145,000).
```

The three planted behaviors show up on their own:

| Finding | What it is | Why it stands out |
| --- | --- | --- |
| r1, r2, r3, r4 form a loop | money leaves r1 and comes back to r1 | moving money in a circle inflates activity with no economic reason |
| x01 receives from 30 nodes that send to nobody else | 30 new accounts each send one payment to x01 | many pass-through accounts pooling money into one |
| chain x01, x02, y1, y2, y3, abroad | each account receives from one and passes almost all of it to the next | layers that put distance between the money and where it came from |

What is **not** a problem shows up too: "employer sends to 300 nodes" is the
payroll; the group of 5 all connected is friends paying each other back, plus
the employer who pays all of them. **A pattern is a place to start looking, not
a verdict.**

**3. The patterns, one by one.** `patterns()` lists each kind of shape, the
strongest first:

```python
g.patterns(kinds=["cycle", "fan_in", "chain"], limit=3)
```

```
- r1, r2, r3 and r4 form a loop: ... Up to 92,732 can go all the way around.
- c235, c239 and c236 form a loop: ... Up to 201 can go all the way around.
- c289, c293 and c290 form a loop: ... Up to 175 can go all the way around.
- x01 receives from 30 nodes, 30 of which send to nobody else, and sends to 2.
- shop03 receives from 195 nodes but sends to none.
- ...
```

Compare the first loop (92,732) with the next ones (201, 175): friends paying
each other back close loops too, but with pocket money. The amount that goes
all the way around is what tells them apart.

The kinds are `cycle`, `fan_in` (many to one), `fan_out` (one to many), `relay`
(receives and passes on), `chain`, `back_and_forth`, `star` and `clique` (all
linked to all).

**4. Over time.** The same table, month by month:

```python
timeline = tareco.timeline("transfers.csv", time="date", directed=True, nodes="accounts.csv")
for change in timeline.changes():
    print("-", change.text)
```

```
- 31 new nodes showed up in 2026-04.
- x01 appeared in 2026-04 with 30 connections at once.
- A new group of 6 nodes formed in 2026-05, around x01, x02 and y1.
```

Now the story can be told: in April, 30 new accounts show up along with x01,
which already receives from all of them; in May, the chain that takes the money
away.

**5. Look into one account.** Only the neighborhood of x01, following the money:

```python
near = tareco.neighborhood("transfers.csv", start="x01", hops=5, directed=True, direction="out")
```

```
<Graph directed, 7 nodes, 6 edges> from x01, following the money
  x01 -> x02: 145,000
  x02 -> y1: 142,454
  y1 -> y2: 139,993
  y2 -> y3: 138,782
  y3 -> abroad: 136,433
```

On a huge Spark table, `neighborhood` fetches only these rows in the cluster,
without bringing the whole table over.

**6. See and share.** Three files in `out/`:

- `transfers.html`: the whole network.
- `x01.html`: just the path of the money from x01, colored by distance (`color="hop"`).
- `report.html`: the report for people who do not use Python, with the
  findings, tables and the graph with a time slider.

## What to look at in the page

- With more than 2,000 links the page uses WebGL: it stays smooth with tens of thousands.
- **Insights** button: click "r1, r2, r3 and r4 form a loop" and the ring lights up.
- In the report, the time slider at the bottom: drag it to 2026-04 and watch x01 appear.

## With your own data

A table with who paid, who got paid and how much is enough. With a date column
the timeline comes for free. For big tables, aggregate in Spark first (one row
per pair of accounts, with the sum and the count) and use `neighborhood` to
look into specific accounts.

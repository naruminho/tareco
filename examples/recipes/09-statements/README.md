# 09. Bank statements: what deserves a closer look?

**The question:** in six months of bank statements, which accounts behave in a
way worth investigating? And once something turns up, how do I get back to the
transactions in my own records?

This is the kind of question anti-money-laundering and fraud teams ask every day.
The data here is **synthetic**: 200 customers with salaries, shopping and money
sent to friends, plus a few behaviors planted on purpose. tareco describes what it
finds in neutral network terms; what counts as suspicious, and which limits and
lists apply, is your call.

## The data

`statements.csv`: one row per entry on a customer's statement (15,467 rows).
Money out is negative.

| transaction_id | account | date | counterparty | counterparty_country | amount |
| --- | --- | --- | --- | --- | --- |
| T000001 | a001 | 2026-01-01 | SHOP-22 | Northland | -85.38 |
| T009038 | a017 | 2026-04-13 | PI-ACC-3 | Palm Isles | -9901.16 |

`customers.csv`: who each account belongs to.

| account | occupation | monthly_income | city |
| --- | --- | --- | --- |
| a001 | cleaner | 1660 | Denver |

`logins.csv`: which device each account logs in from.

| account | device |
| --- | --- |
| a001 | dev-a001-phone |

## Run it

```bash
python examples/recipes/09-statements/statements.py
```

## Step by step

**1. Look at the table first.**

```python
tareco.check("statements.csv", account="account", counterparty="counterparty")
```

```
Nothing to fix in 15,467 rows.
```

Real exports carry placeholders ("N/A", "0", "UNKNOWN") that tie thousands of
unrelated rows to one fake account, the same id written two ways ("123" and 123),
copied rows and dates nobody can read. `check` lists each of them with how many
rows it touches, before any of it reaches the graph; `skip=["N/A"]` leaves such
ids out when loading. From the terminal: `tareco statements.csv --account account
--counterparty counterparty --check`.

**2. Load the statements.**

```python
g = tareco.Graph("statements.csv", account="account", counterparty="counterparty",
                 kind="transfer", nodes="customers.csv", keep=True)
```

- `account` and `counterparty` name the two sides of each entry; the **sign** of
  the amount says which way the money went. A link always goes from who paid to
  who got paid, with a positive amount.
- When both accounts are customers, a transfer shows up twice: money out on one
  statement, money in on the other. tareco counts it **once**, from the side it
  left.
- Statement holders become nodes of kind `account`; everyone else (shops,
  employers, accounts at other banks) becomes `counterparty`.
- `keep=True` keeps the rows behind every link, so each finding can take you back
  to the transactions.

**3. Another kind of link: devices.**

```python
g.add_links("logins.csv", source="account", target="device", kind="uses")
```

```
<Graph directed, 573 nodes, 7645 edges>
{'links': {'transfer': 7303, 'uses': 342}, 'nodes': {'account': 200, 'counterparty': 62, 'device': 311}}
```

Logins join the same graph as links of their own kind. A login carries no money
and has no direction, so tareco keeps it apart from the transfers: the flow
analyses below only look at transfers, and the devices can still tie accounts
together.

**4. What it shows.** Among the lines of `g.explain()`:

```
- Links: 7,303 transfer and 342 uses. Nodes: 311 device, 200 account and 62 counterparty.
- a023 receives from 6 nodes and passes almost all of it on to 32 (207,767 in, 173,508 out).
- 4 account nodes share dev-77 (device).
- a017 sent 8 transfers just under 10,000 within 5 days (2026-04-13 to 2026-04-18), to 4 receivers, 9,434 to 9,901 each.
- a142 sent 7 transfers just under 10,000 within 3 days (2026-05-18 to 2026-05-21), to 3 receivers, 9,436 to 9,945 each.
- a055 sent 85,000 to ART-DEALER-W on 2026-03-14, 819x what it usually sends (104).
- a023 has monthly_income 2,060, 67x lower than the median of the 5 nodes it deals with (137,780).
```

Every planted behavior shows up without asking. The rest of the recipe looks at
each one.

**5. Many amounts just under a limit.**

```python
g.splits(limit=10_000, within="7 days")
```

```
- a017 sent 8 transfers just under 10,000 within 5 days (2026-04-13 to 2026-04-18), to 4 receivers, 9,434 to 9,901 each.
- a142 sent 7 transfers just under 10,000 within 3 days (2026-05-18 to 2026-05-21), to 3 receivers, 9,436 to 9,945 each.
```

The limit and the time window come from you. Without `limit`, tareco looks for
amounts piling up just under any round number. A pile only counts when the
amounts gather just under the limit: payroll paying salaries of every size, or
shopping that happens to reach the limit, is not a pile.

**6. Amounts far above the usual.**

```python
g.unusual_amounts(limit=3)
```

```
- a055 sent 85,000 to ART-DEALER-W on 2026-03-14, 819x what it usually sends (104).
- a023 sent 41,746 to PI-ACC-8 on 2026-03-23, 467x what it usually sends (89.4).
- a023 sent 32,440 to PI-ACC-8 on 2026-04-23, 363x what it usually sends (89.4).
```

Each account is compared with itself (10 times its usual amount, by default),
and only amounts among the largest 5% of the whole network count.

**7. Where the money goes.**

```python
flows = g.flows(by="counterparty_country")
```

```
Where it goes, by counterparty_country
- Northland: 28,970,160 (98% of the total), 6,980 links from 210 nodes: EMPLOYER-EXE-1, EMPLOYER-EXE-2, EMPLOYER-ENG-1 and 207 more
- Westland: 378,487 (1.3% of the total), 314 links from 192 nodes: a055, a200, a199 and 189 more
- Palm Isles: 313,738 (1.1% of the total), 9 links from 4 nodes: a023, a017, a142 and 1 more
Sent to Palm Isles by: a023, a017, a142, a120
```

`by` can be a column of the transfers (as here) or an attribute of the receiving
node. `flows["Palm Isles"].nodes` lists who sent money there, biggest first. The
fourth, a120, sent a 300 gift: not everything in a watched place is a problem.

**8. Who does not fit.**

```python
g.misfits("monthly_income")
g.misfits("occupation")
```

```
- a023 has monthly_income 2,060, 67x lower than the median of the 5 nodes it deals with (137,780).
- a023 has occupation cleaner, but 100% of the 5 nodes it deals with have executive.
```

Each account is compared with the accounts it deals with, whatever the link.

**9. Close to a known case.**

```python
g.near(["a017"])
```

```
- a023 is 2 steps from a017, through dev-77 (device).
- a142 is 2 steps from a017, through dev-77 (device).
- a199 is 2 steps from a017, through dev-77 (device).
```

Paths do not go through hubs (a supermarket, a payroll account): everybody is two
steps away from them. `g.near("flagged")` also works with a true/false attribute.

**10. One account, up close.**

```python
g.why("a023")
```

```
About a023
- a023 (account): occupation cleaner, monthly_income 2,060, city Denver.
- It sent 173,508 to 32 nodes and received 207,767 from 6.
- It is in Group 11.
- a023 is a bridge between groups: it links Group 11, Group 6 and Group 9.
- a023 receives from 6 nodes and passes almost all of it on to 32 (207,767 in, 173,508 out).
- a023 sent 41,746 to PI-ACC-8 on 2026-03-23, 467x what it usually sends (89.4).
- a023 sent 32,440 to PI-ACC-8 on 2026-04-23, 363x what it usually sends (89.4).
- a023 sent 32,377 to PI-ACC-8 on 2026-06-23, 362x what it usually sends (89.4).
- a023 sent 31,587 to PI-ACC-8 on 2026-02-23, 353x what it usually sends (89.4).
- a023 sent 29,884 to PI-ACC-8 on 2026-05-23, 334x what it usually sends (89.4).
- a023 has monthly_income 2,060, 67x lower than the median of the 5 nodes it deals with (137,780).
- a023 has occupation cleaner, but 100% of the 5 nodes it deals with have executive.
- It shares dev-77 (device) with a017, a142 and a199.
- Its rows go from 2026-01-02 to 2026-06-24 (85 rows).
```

`g.why("a023", watch=["a017"])` also says how close it is to a list.

**11. Others that behave like a known case.**

```python
g.similar_to("a017", n=5)
```

```
Most like a017
- a142 (0.26): sends to nodes that hear from nobody else; piles amounts just under a round limit; made transfers far above its usual; shares a device with other nodes
- a055 (0.24): sends to nodes that hear from nobody else; made transfers far above its usual; shares a device with other nodes; sends large amounts
...
```

Behavior means how an account sits in the flow (links in and out, amounts,
passing money on, piles under a limit, unusual amounts, things shared), not who
it is. Only accounts are compared with accounts. Several known cases work too:
`g.similar_to(["a017", "a142"])`.

**12. The work list.** Everything above, gathered per account and ranked:

```python
review = g.review(watch=["a017"], limit=10_000, top=5)
review.to_pandas()          # or review.to_spark(spark), to save next to the data
```

```
Worth a look
1. a023 (score 11.2), 6 rows behind it
   - a023 received 40,493 and passed on 41,746 within 3 days (2026-03-20 to 2026-03-23).
   - a023 receives from 6 nodes and passes almost all of it on to 32 (207,767 in, 173,508 out).
   - a023 sent 41,746 to PI-ACC-8 on 2026-03-23, 467x what it usually sends (89.4). (and 4 more like it)
   - a023 has monthly_income 2,060, 67x lower than the median of the 5 nodes it deals with (137,780).
   - a023 has occupation cleaner, but 100% of the 5 nodes it deals with have executive.
   - a023 is 2 steps from a017, through dev-77 (device).
   - 4 account nodes share dev-77 (device).
2. a142 (score 8), 7 rows behind it
   - a142 sent 7 transfers just under 10,000 within 3 days (2026-05-18 to 2026-05-21), to 3 receivers, 9,436 to 9,945 each.
   ...
3. a017 (score 6.5), 8 rows behind it
   ...
```

The score adds up the signals: piles under a limit weigh most, then money passed
on fast, unusual amounts, loops, chains and pass-throughs, then misfits,
closeness to the list and things shared. Twenty loops are one story: a second
signal of the same kind adds only a little. The table has the account, the
score, the signals, one line per reason, the number of rows and their ids, plus
the account's own attributes.

**13. Money passed on fast.**

```python
g.fast_moves(within="3 days")
```

```
- a023 received 40,493 and passed on 41,746 within 3 days (2026-03-20 to 2026-03-23).
```

A large amount in, far above what the account usually receives, and most of it
out to others within days. Money sent back to whoever sent it does not count.

**14. Following the money in time.**

```python
g.trace("a181", "PI-ACC-8", within="30 days")
```

```
- a181 to a023 to PI-ACC-8: 2 transfers from 2026-02-20 to 2026-02-23, up to 31,587 all the way.
```

A path only counts when each transfer happens after the one before it.
`g.trace("a181")`, without a target, lists everyone the money could have
reached.

**15. One person, several accounts?**

```python
people = g.entities(via="device")
people.of("a017")
people.graph().review(limit=10_000, top=1)
```

```
a017, a023, a142, a199 (through dev-77)
Worth a look
1. E1 (score 8), 34 rows behind it
   - E1 sent 8 transfers just under 10,000 within 5 days (2026-04-13 to 2026-04-18), to 4 receivers, 9,434 to 9,901 each.
   ...
```

Accounts tied by the devices they share (phones, addresses and e-mails work the
same way, as links of their own kind). A device shared by more than 10 accounts,
like a branch computer, ties nobody. `people.graph()` merges each group into one
node, `E1`, with its links and rows added up, and every question then runs per
person.

**16. Back to the records.**

```python
pile = g.splits(limit=10_000)[0]
pile.rows.column("transaction_id")      # the transactions behind the finding
g.rows("a017")                          # every row about an account
tareco.records(spark.table("statements"), alike.nodes, columns=["account"])
```

```
Transactions to review: T009037, T009038, T009125, T009193, T009281, T009282, T009346, T009430
a142 has 78 rows in statements.csv
```

Every finding keeps the rows of your table behind it (`.rows`, with
`.to_pandas()`). `tareco.records` looks up any list of ids in the original table
and returns it in the table's own format: on a Spark table the filter runs in the
cluster and nothing is collected.

**17. How sensitive.**

```python
with tareco.settings(split_count=8):
    g.splits(limit=10_000)
```

```
Piles of 8 or more: a017
```

Every threshold has a default (piles of 3, 10 times the usual amount, 3 days to
pass money on, the weights of the work list...). `tareco.settings` changes them
for every tool at once, from then on or only inside a `with` block;
`print(tareco.settings())` lists them all, the changed ones marked.

**18. What changed since the last work list.** Say the list was made at the end
of April:

```python
april = tareco.Graph(rows_until_april, account="account", counterparty="counterparty", ...)
last = april.review(watch=["a017"], limit=10_000, top=5)
g.review(watch=["a017"], limit=10_000, top=5).compare(last)
```

```
Since the last review
New in the list: 2
- a188 (score 4.8)
   - a181, a188 and a190 form a loop: a181 to a188 to a190 to a181. Up to 6,563 can go all the way around. (and 2 more like it)
   ...
Score went up: 2
- a023, score 9 before, 11.2 now
   - a023 receives from 6 nodes and passes almost all of it on to 32 (207,767 in, 173,508 out).
- a142, score 2.5 before, 8 now
   - a142 sent 7 transfers just under 10,000 within 3 days (2026-05-18 to 2026-05-21), to 3 receivers, 9,436 to 9,945 each.
   ...
No longer in the list: 2
- a187 (score 4 before)
- a189 (score 4 before)
```

An account whose score went up shows only the reasons that are new. "No longer
in the list" means out of the top 5 here, not cleared. The earlier list can also
be the table it was saved as: `review.to_pandas()`, a CSV, a Spark table. From
the terminal: `--review -o list.csv` now, `--review --since list.csv` next month.

**19. Pick it up later.**

```python
g.save("out/case.tareco")
g = tareco.load("out/case.tareco")
```

One file keeps the whole graph: nodes, links, the rows behind them, the kinds
and the prefixes, dates still dates. The next session starts where this one
stopped, without reading the statements again.

**20. See it.** `out/statements.html`, colored by kind of node.

- The flag button lists the accounts worth a look, the strongest first; click
  one to open it.
- Click an account: its card starts with what stands out about it.
- Click a finding under **Insights**: the rows of your table behind it show up
  right under it.
- The legend lists the kinds of link: click `uses` to hide the logins and look
  at the money alone.

`out/statements.svg` is a still picture of the same graph, for a slide.

## With your own data

- A statement export with account, counterparty and a signed amount is enough;
  dates make `splits` and the time lines of `why` possible.
- Transfers already in "from, to, amount" form work too:
  `tareco.Graph(transfers, kind="transfer", directed=True, keep=True)`.
- Devices, phones, addresses, emails: each one is another `add_links` of its own
  kind.
- On Spark, aggregate or filter first, or use `tareco.neighborhood` around the
  accounts you care about; then come back to the full table with `tareco.records`.

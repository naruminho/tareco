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

`statements.csv`: one row per entry on a customer's statement (15,461 rows).
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

**1. Load the statements.**

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

**2. Another kind of link: devices.**

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

**3. What it shows.** Among the lines of `g.explain()`:

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

**4. Many amounts just under a limit.**

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

**5. Amounts far above the usual.**

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

**6. Where the money goes.**

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

**7. Who does not fit.**

```python
g.misfits("monthly_income")
g.misfits("occupation")
```

```
- a023 has monthly_income 2,060, 67x lower than the median of the 5 nodes it deals with (137,780).
- a023 has occupation cleaner, but 100% of the 5 nodes it deals with have executive.
```

Each account is compared with the accounts it deals with, whatever the link.

**8. Close to a known case.**

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

**9. One account, up close.**

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

**10. Others that behave like a known case.**

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

**11. Back to the records.**

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

**12. See it.** `out/statements.html`, colored by kind of node. The legend also
lists the kinds of link: click `uses` to hide the logins and look at the money
alone.

## With your own data

- A statement export with account, counterparty and a signed amount is enough;
  dates make `splits` and the time lines of `why` possible.
- Transfers already in "from, to, amount" form work too:
  `tareco.Graph(transfers, kind="transfer", directed=True, keep=True)`.
- Devices, phones, addresses, emails: each one is another `add_links` of its own
  kind.
- On Spark, aggregate or filter first, or use `tareco.neighborhood` around the
  accounts you care about; then come back to the full table with `tareco.records`.

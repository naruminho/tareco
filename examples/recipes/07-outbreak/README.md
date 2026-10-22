# 07. An outbreak: who may have been exposed, and when?

**The question:** starting from the first case, who may have been exposed,
following the real order of the meetings? Was there an event that spread it
all? Who should be tested first?

The same reasoning works for a rumor on a social network, a cascade of
failures, or contamination moving along a production chain.

## The data

`contacts.csv`: one row per meeting, over three weeks, among 160 people.

| person_a | person_b | day | minutes |
| --- | --- | --- | --- |
| P008 | P019 | 2026-05-01 | 74 |
| P005 | P012 | 2026-05-01 | 82 |

The first case is P017, on day 3.

## Run it

```bash
python examples/recipes/07-outbreak/outbreak.py
```

## Step by step

**1. Load as a timeline.** A timeline is one network per period (here, per day).
`minutes`, the only number column, becomes the weight:

```python
contacts = tareco.timeline("contacts.csv", time="day", freq="day",
                           source="person_a", target="person_b")
```

```
<Timeline by day, 21 periods, 160 nodes, 871 connections>
```

**2. Who may have been exposed.** `spread` only follows a chain of contacts that
happened in that order: P017 meets A, **then** A meets B. In a plain graph
(without time) everyone linked would count, even people who met A before A was
exposed.

```python
exposed = contacts.spread("P017", since="2026-05-03")
```

```
158 people may have been exposed, starting from P017.
Exposed so far, day by day:
  2026-05-03: 1
  2026-05-06: 6
  2026-05-09: 24
  2026-05-10: 62
  2026-05-11: 81
  ...
  2026-05-19: 158
```

The result is a dict `{person: when they were reached}`. Note the jump from day
9 (24) to day 10 (62).

**3. What happened on day 10?**

```python
for change in contacts.changes():
    print(change.text)
```

```
- Activity grew 80% in 2026-05-10 (51 to 92 connections).
- P077 jumped to 42 connections in 2026-05-10 (about 0.4 per period before).
- A new group of 28 nodes formed in 2026-05-10, around P077, P028 and P089.
- Activity fell 43% in 2026-05-11 (92 to 52 connections).
```

A party: P077, who used to meet less than one person a day, met 42 people from
every class on the same day. `changes()` found it without anyone saying what to
look for.

**4. Who to test first.** Whoever was exposed earliest and had the most contacts:

```python
everyone = contacts.union          # all days together, in one graph
first = sorted((p for p in exposed if p != "P017"),
               key=lambda p: (exposed[p], -everyone.degree(p)))[:10]
```

```
Test first: P016, P011, P102, P115, P155, P008, P007, P003, P150, P118
```

**5. See it.** `out/contacts.html`, with the time slider.

## What to look at in the page

- Drag the time slider to 2026-05-10 and see P077 in the middle of everyone.
- In **Insights**, click "P077 jumped to 42 connections": the page jumps to the
  right day and lights up their contacts.
- `contacts["2026-05-10"]` gives the network of that day alone, to study apart.

## With your own data

Any table of meetings or events with a date. If the order does not matter, use
`contacts.union`, which puts every period together in one graph.

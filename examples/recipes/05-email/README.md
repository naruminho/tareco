# 05. E-mail in a company: do the departments talk to each other?

**The question:** do the departments of a company work in silos? Who bridges
them? What changed over the last six months? How far does a note from
leadership reach?

Organizational network analysis (ONA) is done this way, with e-mail, meetings or
chat messages. The data here is synthetic.

## The data

`emails.csv`: one row per e-mail (1,139 rows).

| from | to | date |
| --- | --- | --- |
| Tiago IT6 | Ursula IT7 | 2026-01-01 |
| Sara Mar5 | Tiago Mar6 | 2026-01-01 |

`people.csv`: one row per person.

| name | department | role |
| --- | --- | --- |
| Ana Sal1 | Sales | manager |
| Bruno Sal2 | Sales | analyst |

## Run it

```bash
python examples/recipes/05-email/emails.py
```

## Step by step

**1. Load.** There is no weight column, and none is needed: repeated e-mails
between the same two people are added up into one link, and the `count` column
(how many e-mails) becomes the weight on its own.

```python
g = tareco.Graph("emails.csv", nodes="people.csv")
```

```
<Graph undirected, 59 nodes, 291 edges>
```

No `directed=True`: what matters here is who talks to whom, not who wrote
first.

**2. Do the departments talk to each other?** `profile(groups="department")`
treats each department as a group:

```python
for dept in g.profile(groups="department"):
    print(dept.name, dept.size, dept.inward, dept.linked)
```

```
Sales        14 people, 89% of conversations inside, talks most with Marketing
IT           12 people, 79% of conversations inside, talks most with Data
Finance       8 people, 91% of conversations inside, talks most with Sales
Marketing     8 people, 64% of conversations inside, talks most with Sales
Data          7 people, 72% of conversations inside, talks most with IT
HR            6 people, 86% of conversations inside, talks most with Sales
Leadership    4 people, 71% of conversations inside, talks most with Sales
```

`inward` is how much of the conversation stays inside the department. Finance
(91%) is the most closed; Marketing (64%) talks outside the most.

**3. The summary in words.**

```
- It forms 7 groups that mostly connect among themselves: 83% of the connections stay inside a group.
- Group 1 (15 nodes, 25%): department: Sales in 93% (vs 24% overall). Key members: Paulo Mar2, Ana Sal1 and Elisa Sal5.
- Group 2 (12 nodes, 20%): department: IT in 100% (vs 20% overall). ...
- Paulo Mar2 is a bridge between groups: it links Group 1, Group 2 and Group 4.
- The heaviest 10% of the connections carry 34% of the total occurrences.
```

The groups tareco found on its own match the departments: they are real silos.
Look at Paulo Mar2: he is in Marketing, but he landed in the Sales group and
links Sales, IT and Marketing. If he leaves, those departments lose their
channel.

**4. What changed over time.**

```python
timeline = tareco.timeline("emails.csv", time="date", nodes="people.csv", freq="month")
```

```
- 7 new nodes showed up in 2026-04.
- A new group of 7 nodes formed in 2026-04, around Gabi Dat7, Ana Dat1 and Bruno Dat2.
```

In April the Data team was born: 7 new people who form a group of their own.
`freq` can be `"day"`, `"week"`, `"month"`, `"quarter"` or `"year"`; without it,
tareco picks one (at most 24 periods).

**5. How far does a note reach?** `spread` follows the order of the e-mails: it
only counts if A wrote to B **before** B wrote to C.

```python
reach = timeline.spread("Wanda Lea1", since="2026-03-02")
```

```
Starting from Wanda Lea1 on 2026-03-02, the news could have reached 58 people.
```

The result is a dict `{person: when they were reached}`.

**6. See it.** `out/emails.html`, colored by department, with the time slider.

## What to look at in the page

- Press **Play** on the time slider: the months go by and the Data team shows
  up in April.
- Click "Paulo Mar2 is a bridge" in **Insights** to see whom he connects.
- Legend: double-click "Finance" to see only that department.

## With your own data

Any record of who talked to whom: e-mails, meetings (attendee with attendee),
messages, tickets. For meetings, which link several people at once, use the
projection from recipe 04: `tareco.project(meetings, nodes="person", via="meeting")`.

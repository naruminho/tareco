"""E-mail in a company: do the departments talk to each other? Who bridges them? What changed?

Six months of e-mail (who wrote to whom, and when) and a table with each
person's department and role.

Run from the tareco folder:  python examples/recipes/05-email/emails.py
"""

from pathlib import Path

import tareco

HERE = Path(__file__).parent
OUT = HERE / "out"
OUT.mkdir(exist_ok=True)

# %% 1. Load
# emails.csv: from, to, date. people.csv: name, department, role.
# Repeated e-mails between the same two people add up: the count column
# (how many e-mails) becomes the weight on its own.
g = tareco.Graph(HERE / "emails.csv", nodes=HERE / "people.csv")
print(g)
print()

# %% 2. Do the departments talk to each other? (silos)
# profile(groups="department") looks at each department as a group: how much of
# its conversation stays inside, and which other department it talks to most.
for dept in g.profile(groups="department"):
    print(f"{dept.name:<11} {dept.size:>3} people, {dept.inward:.0%} of conversations inside,"
          f" talks most with {dept.linked}")
print()

# %% 3. The summary in words, including who bridges the groups
print(g.explain())
print()

# %% 4. What changed over time
timeline = tareco.timeline(HERE / "emails.csv", time="date", nodes=HERE / "people.csv", freq="month")
for change in timeline.changes():
    print("-", change.text)
print()
# Or two months side by side: what is different in June compared with January?
print(timeline.compare("2026-01", "2026-06"))
print()

# %% 5. How far does a note from leadership reach, and when?
# spread follows the order of the e-mails: it only counts if A wrote to B before
# B wrote to C.
head = next(n for n in g if g.nodes[n]["department"] == "Leadership" and g.nodes[n]["role"] == "manager")
reach = timeline.spread(head, since="2026-03-02")
print(f"Starting from {head} on 2026-03-02, the news could have reached {len(reach) - 1} people.")
print()

# %% 6. See it
timeline.save(OUT / "emails.html", color="department", title="E-mail by department")
print("Open:", OUT / "emails.html")

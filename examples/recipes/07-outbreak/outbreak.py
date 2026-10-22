"""An outbreak: starting from the first case, who may have been exposed, and when?

Three weeks of contacts among 160 people (who met whom, on what day, for how
many minutes). The first case is P017, on day 3.

Run from the tareco folder:  python examples/recipes/07-outbreak/outbreak.py
"""

from pathlib import Path

import tareco

HERE = Path(__file__).parent
OUT = HERE / "out"
OUT.mkdir(exist_ok=True)

# %% 1. Load as a timeline
# contacts.csv: person_a, person_b, day, minutes. The column names do not say who
# is the source and who the target, and it does not matter: a contact goes both ways.
contacts = tareco.timeline(HERE / "contacts.csv", time="day", freq="day",
                           source="person_a", target="person_b")
print(contacts)
print()

# %% 2. Who may have been exposed, following the order of the meetings
# Only a chain of contacts that happened in that order counts: P017 meets A,
# then A meets B.
exposed = contacts.spread("P017", since="2026-05-03")
# spread returns {person: when they were reached}, including P017 itself.
print(f"{len(exposed) - 1} people may have been exposed, starting from P017.")
per_day = {}
for person, when in exposed.items():
    if person != "P017":
        per_day[when.date()] = per_day.get(when.date(), 0) + 1
print("Exposed so far, day by day:")
so_far = 0
for day, n in sorted(per_day.items()):
    so_far += n
    print(f"  {day}: {so_far}")
print()

# %% 3. What changed from day to day: the event that spread it all
for change in contacts.changes():
    print("-", change.text)
print()

# %% 4. Who to test first
# People exposed earliest, and with the most contacts over the period.
everyone = contacts.union
first = sorted((p for p in exposed if p != "P017"),
               key=lambda p: (exposed[p], -everyone.degree(p)))[:10]
print("Test first:", ", ".join(first))
print()

# %% 5. See it, with the timeline
contacts.save(OUT / "contacts.html", title="Contacts day by day")
print("Open:", OUT / "contacts.html")

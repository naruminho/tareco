"""The synthetic data behind the recipes, with the stories they hide planted on purpose.

The files are already in each recipe's folder; this script only shows how they
were made. Running it again gives the same files (needs openpyxl for the Excel one).
"""

import csv
import datetime as dt
import random
from pathlib import Path

HERE = Path(__file__).parent


def write_csv(path, header, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def day(rng, month, year=2026):
    return dt.date(year, month, rng.randint(1, 28))


def transfers():
    """Salaries, shopping and friends paying each other back; plus a loop, a collector and a chain."""
    rng = random.Random(42)
    out = HERE / "02-transfers"
    customers = [f"c{i:03d}" for i in range(1, 301)]
    shops = [f"shop{i:02d}" for i in range(1, 31)]
    cities = ["Austin", "Boston", "Chicago", "Denver", "Miami", "Seattle"]
    accounts = []
    for c in customers:
        accounts.append((c, "person", rng.choice(cities), "2024-0%d-1%d" % (rng.randint(1, 9), rng.randint(0, 9))))
    for s in shops:
        accounts.append((s, "business", rng.choice(cities), "2023-05-10"))
    accounts.append(("employer", "business", "Austin", "2020-01-02"))
    rows = []
    friends = [customers[i:i + 6] for i in range(0, len(customers), 6)]
    for m in range(1, 7):
        for c in customers:
            rows.append(("employer", c, round(rng.uniform(2500, 9000), 2), dt.date(2026, m, 5)))
            for _ in range(rng.randint(3, 6)):
                rows.append((c, rng.choice(shops), round(rng.uniform(20, 500), 2), day(rng, m)))
        for group in friends:
            for _ in range(2):
                a, b = rng.sample(group, 2)
                rows.append((a, b, round(rng.uniform(10, 200), 2), day(rng, m)))
    # money that goes around and comes back
    ring = ["r1", "r2", "r3", "r4"]
    for a in ring:
        accounts.append((a, "business", "Miami", "2026-02-01"))
    for week in (3, 17):
        amount = 48000
        for a, b in zip(ring, ring[1:] + ring[:1]):
            amount -= rng.randint(200, 600)
            rows.append((a, b, amount, dt.date(2026, 3, week)))
    # many new accounts paying one account, which sends it on through a chain
    new = [f"n{i:02d}" for i in range(1, 31)]
    for n in new:
        accounts.append((n, "person", rng.choice(cities), "2026-04-0%d" % rng.randint(1, 9)))
        rows.append((n, "x01", round(rng.uniform(4800, 4990), 2), day(rng, 4)))
    for c in ("x01", "x02", "y1", "y2", "y3", "abroad"):
        accounts.append((c, "business", "Chicago", "2026-03-20"))
    total = 145000
    rows.append(("x01", "x02", total, dt.date(2026, 5, 2)))
    rows.append(("x01", "shop07", 300, dt.date(2026, 5, 3)))
    for a, b in (("x02", "y1"), ("y1", "y2"), ("y2", "y3"), ("y3", "abroad")):
        total -= rng.randint(1000, 3000)
        rows.append((a, b, total, dt.date(2026, 5, rng.randint(3, 20))))
    rows.sort(key=lambda r: r[3])
    write_csv(out / "transfers.csv", ["sender", "receiver", "amount", "date"],
              [(a, b, v, d.isoformat()) for a, b, v, d in rows])
    write_csv(out / "accounts.csv", ["account", "type", "city", "opened"], accounts)


def supply_chain():
    """Suppliers, factories, distribution centers and stores; one thin route on purpose."""
    rng = random.Random(7)
    out = HERE / "03-supply-chain"
    suppliers = ["Supplier A", "Supplier B", "Supplier C", "Supplier D"]
    factories = ["Factory East", "Factory Central", "Factory South"]
    centers = ["DC North", "DC Northeast", "DC Southeast", "DC South"]
    stores = [f"Store {i:02d}" for i in range(1, 13)]
    rows = []
    for s in suppliers:
        for f in rng.sample(factories, 2):
            rows.append((s, f, rng.choice([300, 400, 500, 600]), rng.randint(8, 15), rng.randint(2, 6)))
    for f in factories:
        for dc in centers:
            if f == "Factory Central" or rng.random() < 0.6:
                cap = 120 if (f, dc) == ("Factory Central", "DC Northeast") else rng.choice([200, 300, 400])
                rows.append((f, dc, cap, rng.randint(4, 9), rng.randint(1, 4)))
    for i, store in enumerate(stores):
        for dc in (centers[i % 4], centers[(i + 1) % 4]):
            rows.append((dc, store, rng.choice([60, 80, 100, 120]), rng.randint(2, 5), rng.randint(1, 3)))
    write_csv(out / "routes.csv", ["from", "to", "capacity", "cost", "days"], rows)


def shopping():
    """Four kinds of shopper, an Excel workbook with two sheets."""
    import openpyxl

    rng = random.Random(11)
    out = HERE / "04-shopping"
    out.mkdir(parents=True, exist_ok=True)
    baskets = {
        "family": ["diapers", "milk", "baby food", "wet wipes", "cookies"],
        "fitness": ["whey", "oats", "bananas", "peanut butter", "chicken"],
        "barbecue": ["steak", "charcoal", "beer", "garlic bread", "sausages"],
        "student": ["instant noodles", "coffee", "energy drink", "frozen pizza", "chips"],
    }
    everyone = ["water", "bread", "rice"]
    prices = {}
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "purchases"
    ws.append(["customer", "product", "amount", "date"])
    customers = []
    for i in range(1, 121):
        segment = list(baskets)[i % 4]
        customer = f"customer {i:03d}"
        customers.append((customer, segment, rng.choice(["Austin", "Boston", "Denver", "Miami"])))
        for _ in range(rng.randint(5, 9)):
            if rng.random() < 0.75:
                product = rng.choice(baskets[segment])
            elif rng.random() < 0.5:
                product = rng.choice(everyone)
            else:
                product = rng.choice(baskets[rng.choice(list(baskets))])
            price = prices.setdefault(product, round(rng.uniform(3, 90), 2))
            ws.append([customer, product, price, dt.datetime(2026, rng.randint(1, 6), rng.randint(1, 28))])
    ws2 = wb.create_sheet("customers")
    ws2.append(["customer", "segment", "city"])
    for row in customers:
        ws2.append(list(row))
    wb.save(out / "shopping.xlsx")


def email():
    """Six months of e-mail in a company: departments, one go-between, a team born in April."""
    rng = random.Random(5)
    out = HERE / "05-email"
    departments = {"Sales": 14, "IT": 12, "Finance": 8, "HR": 6, "Marketing": 8, "Leadership": 4}
    names = ["Ana", "Bruno", "Carla", "Diego", "Elisa", "Fabio", "Gabi", "Hugo", "Iara", "Joao", "Kelly", "Lucas",
             "Marta", "Nilo", "Olga", "Paulo", "Quesia", "Rafa", "Sara", "Tiago", "Ursula", "Vitor", "Wanda",
             "Xavier", "Yara", "Zeca"]
    people = []
    k = 0
    for dept, n in departments.items():
        for i in range(n):
            people.append((f"{names[k % len(names)]} {dept[:3]}{i + 1}", dept, "manager" if i == 0 else "analyst"))
            k += 1
    data_team = [(f"{names[i]} Dat{i + 1}", "Data", "manager" if i == 0 else "analyst") for i in range(7)]
    by_dept = {}
    for p in people:
        by_dept.setdefault(p[1], []).append(p[0])
    managers = [p[0] for p in people if p[2] == "manager"]
    go_between = by_dept["Marketing"][1]
    rows = []
    for m in range(1, 7):
        for dept, staff in by_dept.items():
            for _ in range(25 if dept != "Finance" else 18):
                a, b = rng.sample(staff, 2)
                rows.append((a, b, day(rng, m)))
        for _ in range(12):
            a, b = rng.sample(managers, 2)
            rows.append((a, b, day(rng, m)))
        for _ in range(8):  # the person everybody in Sales and IT writes to
            rows.append((go_between, rng.choice(by_dept["Sales"] + by_dept["IT"]), day(rng, m)))
            rows.append((rng.choice(by_dept["Sales"] + by_dept["IT"]), go_between, day(rng, m)))
        if m >= 4:  # a new data team, talking to itself and to IT
            team = [d[0] for d in data_team]
            for _ in range(30):
                a, b = rng.sample(team, 2)
                rows.append((a, b, day(rng, m)))
            for _ in range(6):
                rows.append((rng.choice(team), rng.choice(by_dept["IT"]), day(rng, m)))
    head = by_dept["Leadership"][0]
    for g in managers[1:]:
        rows.append((head, g, dt.date(2026, 3, 2)))
    rows.sort(key=lambda r: r[2])
    write_csv(out / "emails.csv", ["from", "to", "date"], [(a, b, d.isoformat()) for a, b, d in rows])
    write_csv(out / "people.csv", ["name", "department", "role"], people + data_team)


def dependencies():
    """Packages and what they depend on; config and cache need each other."""
    out = HERE / "06-dependencies"
    deps = {
        "web-shop": ["api", "ui-kit", "auth", "logging"],
        "mobile-app": ["api", "auth", "ui-kit", "analytics"],
        "admin-panel": ["api", "auth", "ui-kit", "reports"],
        "api": ["auth", "database", "cache", "logging", "config", "payments", "search"],
        "payments": ["http-client", "crypto", "logging", "config"],
        "search": ["database", "cache", "logging", "text"],
        "reports": ["database", "pdf", "logging", "dates"],
        "analytics": ["http-client", "logging", "dates"],
        "auth": ["crypto", "database", "cache", "logging", "config"],
        "database": ["sql-driver", "logging", "config", "utils"],
        "cache": ["config", "utils", "logging"],
        "config": ["utils", "cache"],  # oops: config and cache need each other
        "http-client": ["utils", "logging", "json"],
        "crypto": ["utils"],
        "pdf": ["utils", "text"],
        "text": ["utils"],
        "dates": ["utils"],
        "logging": ["utils", "json"],
        "json": ["utils"],
        "sql-driver": ["utils"],
        "ui-kit": ["utils", "dates"],
        "utils": [],
    }
    rows = [(p, d) for p, ds in deps.items() for d in ds]
    write_csv(out / "dependencies.csv", ["package", "depends_on"], rows)


def outbreak():
    """Eight classes meeting every day, a few chance meetings, and a party on day 10."""
    rng = random.Random(3)
    out = HERE / "07-outbreak"
    people = [f"P{i:03d}" for i in range(1, 161)]
    classes = [people[i:i + 20] for i in range(0, 160, 20)]
    rows = []
    for d in range(1, 22):
        date = dt.date(2026, 5, d)
        for members in classes:
            for _ in range(6):
                a, b = rng.sample(members, 2)
                rows.append((a, b, date.isoformat(), rng.randint(5, 90)))
        for _ in range(4):
            a, b = rng.sample(people, 2)
            rows.append((a, b, date.isoformat(), rng.randint(5, 30)))
        if d == 10:  # a party: one person meets people from every class
            for p in rng.sample(people, 40):
                rows.append(("P077", p, date.isoformat(), rng.randint(20, 120)))
    write_csv(out / "contacts.csv", ["person_a", "person_b", "day", "minutes"], rows)


def subway():
    """Four subway lines; Central is where they all meet."""
    out = HERE / "08-subway"
    lines = {
        "Blue": ["Airport", "New Town", "Central", "Square", "Market", "University", "Park"],
        "Green": ["Bus Terminal", "Hospital", "Square", "Cathedral", "Stadium", "Lake"],
        "Red": ["Port", "Factory", "Central", "Cathedral", "Mall", "Uptown"],
        "Yellow": ["University", "Mall", "Stadium", "Garden"],
    }
    rng = random.Random(9)
    rows = []
    for line, stations in lines.items():
        for a, b in zip(stations, stations[1:]):
            rows.append((a, b, rng.randint(2, 6), line))
    write_csv(out / "links.csv", ["station_a", "station_b", "minutes", "line"], rows)


if __name__ == "__main__":
    for make in (transfers, supply_chain, shopping, email, dependencies, outbreak, subway):
        make()
        print("made", make.__name__)

"""Shopping baskets: what kinds of customer are there, and who buys X also buys what?

An Excel workbook with two sheets: "purchases" (customer, product, amount, date)
and "customers" (customer, segment, city). The data does not say who is similar
to whom; the projection links customers who buy the same things.

Run from the tareco folder:  python examples/recipes/04-shopping/shopping.py
"""

from pathlib import Path

import tareco

HERE = Path(__file__).parent
OUT = HERE / "out"
OUT.mkdir(exist_ok=True)

# %% 1. Read the workbook
# No pandas needed: tareco reads .xlsx on its own. sheet picks the sheet.
purchases = tareco.read_excel(HERE / "shopping.xlsx", sheet="purchases")
customers = tareco.read_excel(HERE / "shopping.xlsx", sheet="customers")
print(len(purchases), "purchases by", len(customers), "customers")
print()

# %% 2. Customers linked by the products they share
# method="newman": a product everybody buys (water, bread) barely counts; a niche
# product counts a lot. attrs brings each customer's segment and city along.
alike = tareco.project(purchases, nodes="customer", via="product", method="newman", attrs=customers)
print(alike)
print(alike.explain())
print()

# %% 3. Products linked by the customers they share: "who buys X also buys"
products = tareco.project(purchases, nodes="product", via="customer")
for product in ("diapers", "whey", "steak"):
    together = [other for other, _ in products.top_neighbors(product, n=3)]
    print(f"Who buys {product} also buys: {', '.join(together)}")
print()

# %% 4. See it
alike.save(OUT / "customers.html", title="Customers who buy alike")
products.save(OUT / "products.html", title="Products bought together")
print("Open:", OUT / "customers.html")

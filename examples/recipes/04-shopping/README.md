# 04. Shopping baskets: what kinds of customer are there?

**The question:** looking only at what each customer bought, can we find the
kinds of customer? And who buys diapers also buys what?

Here the data **does not say who is linked to whom**. It says "customer bought
product". This kind of two-sided data is everywhere: customer and product,
student and course, account and device, patient and doctor, actor and movie.
The **projection** handles it: it links two customers when they buy the same
things.

## The data

An Excel workbook, `shopping.xlsx`, with two sheets. You need neither pandas
nor Excel: tareco reads `.xlsx` on its own.

Sheet `purchases` (854 rows):

| customer | product | amount | date |
| --- | --- | --- | --- |
| customer 001 | chips | 77.39 | 2026-02-06 |
| customer 001 | rice | 71.99 | 2026-01-15 |

Sheet `customers` (120 rows):

| customer | segment | city |
| --- | --- | --- |
| customer 001 | fitness | Miami |
| customer 002 | barbecue | Denver |

## Run it

```bash
python examples/recipes/04-shopping/shopping.py
```

## Step by step

**1. Read the workbook.** `sheet` picks the sheet, by name or position.

```python
purchases = tareco.read_excel("shopping.xlsx", sheet="purchases")
customers = tareco.read_excel("shopping.xlsx", sheet="customers")
```

The result is a list of rows (dicts). Dates become dates and numbers become
numbers. You can also pass the file straight away: `tareco.Graph("book.xlsx")`
uses the first sheet.

**2. Link customers who buy the same things.**

```python
alike = tareco.project(purchases, nodes="customer", via="product",
                       method="newman", attrs=customers)
print(alike.explain())
```

- `nodes="customer"`: who becomes a node.
- `via="product"`: what links one to another.
- `method="newman"`: a product everybody buys (rice, bread) barely counts; a
  niche product (whey, charcoal) counts a lot. Without it, everybody ends up
  linked to everybody through the rice.
- `attrs=customers`: brings each customer's segment and city along, so tareco
  can say what sets each group apart.

```
- It forms 4 groups, but most connections (60%) cross from one group to another.
- Group 1 (31 nodes, 26%): segment: student in 97% (vs 25% overall). Key members: customer 075, customer 103 and customer 063.
- Group 2 (30 nodes, 25%): segment: fitness in 100% (vs 25% overall). ...
- Group 3 (30 nodes, 25%): segment: barbecue in 100% (vs 25% overall). ...
- Group 4 (29 nodes, 24%): segment: family in 100% (vs 25% overall). ...
- customer 009 is a bridge between groups: it links Group 2, Group 1, Group 4 and Group 3.
```

tareco did not know anyone's segment when it formed the groups: it found 4
groups from the purchases alone, and then checked that each group matches a
segment. With real data, this is how you discover a segment nobody had written
down. Customer 009, who links all four groups, buys a bit of everything.

**3. Who buys X also buys.** Now the other way around: products linked by the
customers they share.

```python
products = tareco.project(purchases, nodes="product", via="customer")
products.top_neighbors("diapers", n=3)
```

```
Who buys diapers also buys: cookies, milk, wet wipes
Who buys whey also buys: peanut butter, bananas, oats
Who buys steak also buys: beer, sausages, charcoal
```

`top_neighbors` returns the neighbors with the strongest link: here, the
products with the most customers in common.

**4. See it.** `out/customers.html` (customers colored by group) and
`out/products.html` (products bought together).

## What to look at in the page

- Hover a link between two customers: `shared` says how many products they have
  in common and `examples` shows a few.
- In the legend, each group shows its strongest trait (for example, "student").
- **Groups overview** button: each group becomes a bubble, linked to the others
  by how alike they are.

## With your own data

Any table with a "who" column and a "what" column. Products that almost
everybody buys are skipped above `max_item_size` (1,000 customers), with a
warning: they would link everybody to everybody.

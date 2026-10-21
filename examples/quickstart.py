"""A tour of tareco. Run from the repository root: python examples/quickstart.py"""

import tareco as tc

# The lazy way: one line, columns are guessed ("from"/"to"), everything else is an attribute.
tc.show("examples/friends.csv", nodes="examples/people.csv", title="Friends")

# The curious way: load once, ask questions.
g = tc.Graph("examples/friends.csv", nodes="examples/people.csv")
print(g)
print(g.summary())
print("Who holds the group together?", max(g.betweenness().items(), key=lambda kv: kv[1]))
print("Fastest gossip route Ana -> Otto:", g.shortest_path("Ana", "Otto"))
print("Friend groups:", g.communities())
print("Who should meet?", g.suggest_links(top=3))

# What the network shows, in plain words (lang="pt" for Portuguese).
print(g.explain(weight="messages"))
print(g.profile())

# Color by any attribute or metric, size by another one.
g.show(color="city", size="betweenness", edge_width="messages", title="Friends by city")

# Two-sided data: link people through the things they share.
purchases = [("Ana", "rice"), ("Bia", "rice"), ("Bia", "coffee"), ("Caio", "coffee"), ("Ana", "beans")]
shoppers = tc.project(purchases)
print(shoppers.edges["Ana", "Bia"])   # {'weight': 1, 'shared': 1, 'examples': 'rice'}

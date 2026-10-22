# Examples

Nine complete recipes, each with a real question, its data ready in the
folder and a script commented step by step. Run them from the tareco folder:

```bash
python examples/recipes/01-friends/friends.py
```

Each recipe saves interactive HTML pages to its `out/` folder. The scripts are
split into cells (`# %%`), so they also open as notebooks in VS Code, in Jupyter
(with jupytext) and in Databricks.

Never used graphs? Start with recipe 01 and read the [beginner's guide](../docs/guide.md).

| Recipe | The question | What you learn |
| --- | --- | --- |
| [01. Friends](recipes/01-friends/) | Who hangs out with whom, and who bridges the groups? | `Graph`, `explain`, `communities`, `shortest_path`, `top_neighbors`, `suggest_links`, `profile`, `save` |
| [02. Money transfers](recipes/02-transfers/) | Where does money move in a strange way? | `directed=True`, `patterns` (loop, many to one, chain), `timeline`, `neighborhood`, `report` |
| [03. Supply chain](recipes/03-supply-chain/) | How much can be delivered, and where is the bottleneck? | `max_flow` and the minimum cut, `remove_node`, `k_shortest_paths` |
| [04. Shopping baskets](recipes/04-shopping/) | What kinds of customer are there? Who buys X also buys what? | `read_excel`, `project` (two-sided data), `method="newman"`, `attrs` |
| [05. E-mail](recipes/05-email/) | Do the departments work in silos? What changed? | `profile(groups=...)`, bridges, `timeline(freq="month")`, `spread` |
| [06. Dependencies](recipes/06-dependencies/) | In what order to install? What breaks together? | `find_cycle`, `topological_sort`, `reverse`, `bfs`, `pagerank` |
| [07. Outbreak](recipes/07-outbreak/) | Who may have been exposed, and when? | `timeline(freq="day")`, `spread` in time order, `changes` |
| [08. Subway](recipes/08-subway/) | What is the fastest way? Which station is vital? | the weight, `distance`, `betweenness`, `components`, the `NoPath` error |
| [09. Bank statements](recipes/09-statements/) | What deserves a closer look, and how do I get back to the records? | `account=`/`counterparty=`, `add_links` and kinds, `keep=`, `splits`, `unusual_amounts`, `flows`, `misfits`, `near`, `why`, `similar_to`, `records` |

The data is synthetic, made up for each story by [make_data.py](recipes/make_data.py).
What the recipes find (the ring of transfers, the party in the outbreak, the new
team in the e-mail, the amounts split under a limit) was planted on purpose, so you can watch tareco find it on
its own.

The sentences tareco writes come out in your computer's language (English,
Portuguese or Spanish); `tareco.set_language("en")` fixes it to English.

## Other files

- [quickstart.py](quickstart.py): a quick tour with `friends.csv` and `people.csv`.
- [databricks_check.py](databricks_check.py): a notebook to import into
  Databricks to check that everything works there (`tareco.doctor(spark)` and
  one graph per cell).

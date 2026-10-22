# 06. Software dependencies: in what order to install?

**The question:** in a system with 22 packages that depend on each other, is
there a circular dependency? In what order should they be installed? If one
package breaks, what breaks with it? Which ones are the most critical?

It works for anything with "depends on": project tasks, courses with
prerequisites, steps of a process, jobs in a data pipeline.

## The data

`dependencies.csv`: one row per dependency.

| package | depends_on |
| --- | --- |
| web-shop | api |
| web-shop | ui-kit |

## Run it

```bash
python examples/recipes/06-dependencies/dependencies.py
```

## Step by step

**1. Load.** `package` and `depends_on` are not names tareco knows, so we say
which is which. Direction matters: "web-shop depends on api" is not the same as
the other way around.

```python
deps = tareco.Graph("dependencies.csv", source="package", target="depends_on", directed=True)
```

If you forget `source=` and `target=`, tareco uses the first two columns and
warns you which ones it picked.

**2. Is there a circular dependency?**

```python
deps.find_cycle()
```

```
Circular dependency: config -> cache -> config
```

`find_cycle()` returns one cycle (of any length) or `None`. `has_cycle()` only
answers yes or no. To see every package caught in a cycle:
`[c for c in deps.strong_components() if len(c) > 1]`.

**3. Install order.** `topological_sort()` puts each package before the ones it
points to. Here the arrows go from a package to what it needs, so we reverse
them (`reverse()`) to install the base first. With a cycle no order is
possible, so we drop the link that closes it first:

```python
no_cycle = deps.copy()
no_cycle.remove_edge("config", "cache")
no_cycle.reverse().topological_sort()
```

```
Install in this order: utils, config, crypto, text, dates, sql-driver, json, pdf, ui-kit, ...
```

**4. What breaks if a package fails?** Everything that depends on `utils`,
directly or not: follow the arrows backwards.

```python
deps.reverse().bfs("utils")[1:]
```

```
If 'utils' breaks, 21 packages break with it: ui-kit, logging, database, cache, config, ...
```

`bfs` (breadth-first search) returns everyone reachable from a node, nearest
first.

**5. The most critical.** PageRank on a dependency graph: the more important
things depend on a package, the higher it ranks.

```
Most critical: utils, logging, json, cache, config
```

**6. See it.** `out/dependencies.html`, with each package sized by PageRank.

## What to look at in the page

- Arrows point to the dependency.
- Click `utils`: its card shows who depends on it.
- The biggest circles are the packages that must not break.

## With your own data

A table of "item" and "depends on" is enough. For a project, `task` and
`depends_on` give the order to do things in with `topological_sort()`.

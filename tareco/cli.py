"""Command line: ``tareco edges.csv`` opens the interactive view."""

import argparse
import csv
import os
import sys

from . import __version__
from .errors import TarecoError
from .bipartite import project
from .graph import Graph
from .around import neighborhood
from .temporal import timeline


def main(argv=None):
    p = argparse.ArgumentParser(
        prog="tareco",
        description="Draw a graph from a CSV/JSON file as an interactive web page.",
    )
    p.add_argument("edges", nargs="?", help="edges file (.csv, .tsv, .json, .edges, .xlsx, .tareco)")
    p.add_argument("--nodes", help="optional nodes file with attributes")
    p.add_argument("-o", "--output", help="write this HTML file instead of opening the browser "
                                             "(.svg/.png for a picture, .tareco for the whole graph)")
    p.add_argument("-d", "--directed", action="store_true", help="edges have a direction")
    p.add_argument("--source", help="column with the edge source")
    p.add_argument("--target", help="column with the edge target")
    p.add_argument("--account", metavar="COLUMN", help="bank statement: the column with the account "
                                                       "(with --counterparty)")
    p.add_argument("--counterparty", metavar="COLUMN", help="bank statement: the column with the other side")
    p.add_argument("--amount", metavar="COLUMN", help="the column with the amount (in statements, money out "
                                                     "is negative)")
    p.add_argument("--kind", help="what the links are: transfer, call, login...")
    p.add_argument("--color", help="attribute or metric used for color (default: community)")
    p.add_argument("--size", help="attribute or metric used for size (default: pagerank)")
    p.add_argument("--label", help="attribute used as the node label")
    p.add_argument("--title", help="title shown on the page")
    p.add_argument("--3d", dest="dim", action="store_const", const=3, default=2, help="3D view")
    p.add_argument("--particles", action="store_true", help="animate flow along the edges")
    p.add_argument("--renderer", choices=("auto", "canvas", "webgl"), default="auto",
                   help="canvas for small graphs, WebGL for big ones (default: auto)")
    p.add_argument("--max-nodes", type=int, help="keep only this many of the most important nodes")
    p.add_argument("--summary", action="store_true", help="print headline numbers and exit")
    p.add_argument("--explain", action="store_true", help="print what the network shows, in plain words")
    p.add_argument("--lang", choices=("en", "pt"), help="language of the explanation and the page")
    p.add_argument("--project", nargs=2, metavar=("NODES", "VIA"),
                   help="two-sided table: link NODES that share VIA (e.g. --project customer product)")
    p.add_argument("--time", metavar="COLUMN", help="events with a time column: replay them on a time slider")
    p.add_argument("--around", nargs="+", metavar="NODE", help="only the neighborhood of these nodes")
    p.add_argument("--hops", type=int, default=2, help="steps out for --around (default: 2)")
    p.add_argument("--patterns", action="store_true", help="print loops, fans, chains, stars and cliques")
    p.add_argument("--check", action="store_true", help="print what in the table would mislead the graph "
                                                       "(exit code 1 when there is something to fix)")
    p.add_argument("--review", action="store_true", help="print the nodes worth a look, ranked "
                                                        "(-o list.csv writes it as a table)")
    p.add_argument("--since", metavar="FILE", help="with --review: what changed since an earlier list "
                                                  "(a CSV written by --review -o)")
    p.add_argument("--why", metavar="NODE", help="print what stands out about one node")
    p.add_argument("--watch", nargs="+", metavar="NODE", help="flagged nodes, for --review and --why")
    p.add_argument("--limit", type=float, metavar="AMOUNT", help="the amount people stay under, for "
                                                                "splits (e.g. 10000)")
    p.add_argument("--top", type=int, default=50, help="how many nodes --review lists (default: 50)")
    p.add_argument("--report", action="store_true", help="write a shareable report (with -o) instead of the bare view")
    p.add_argument("--doctor", action="store_true", help="check that tareco works in this environment")
    p.add_argument("--version", action="version", version=f"tareco {__version__}")
    args = p.parse_args(argv)
    if args.doctor:
        from .checkup import doctor
        report = doctor()
        print(report)
        return 0 if report.ok else 1
    if not args.edges:
        p.error("the edges file is required")

    try:
        if args.check:
            from .quality import check
            found = check(args.edges, source=args.source, target=args.target, account=args.account,
                          counterparty=args.counterparty, amount=args.amount, time=args.time, lang=args.lang)
            print(found)
            return 0 if found.ok else 1
        investigating = args.review or args.why is not None
        tl = None
        if args.time:
            tl = timeline(args.edges, time=args.time, source=args.source, target=args.target,
                          directed=args.directed, nodes=args.nodes)
            g = tl.union
        elif args.project:
            g = project(args.edges, nodes=args.project[0], via=args.project[1])
        elif args.around:
            g = neighborhood(args.edges, start=args.around, hops=args.hops, source=args.source,
                             target=args.target, directed=args.directed)
        else:
            g = Graph(args.edges, nodes=args.nodes, directed=args.directed or None,
                      source=args.source, target=args.target, account=args.account,
                      counterparty=args.counterparty, amount=args.amount, kind=args.kind,
                      keep=True if investigating or args.account else None)
        if args.summary:
            print(g.summary())
            return 0
        if args.explain:
            print((tl or g).explain(lang=args.lang, label=args.label))
            return 0
        if args.patterns:
            print(g.patterns(lang=args.lang, label=args.label))
            return 0
        watch = [_node(g, x) for x in args.watch] if args.watch else None
        if args.why is not None:
            print(g.why(_node(g, args.why), watch=watch, lang=args.lang, label=args.label))
            return 0
        if args.review:
            found = g.review(watch=watch, limit=args.limit, top=args.top, lang=args.lang, label=args.label)
            if args.since:
                print(found.compare(args.since))
            elif not args.output:
                print(found)
            if args.output:
                if not args.output.lower().endswith(".csv"):
                    raise TarecoError("--review writes a table: -o list.csv")
                print(_write_csv(found.table(), args.output))
            return 0
        if args.output and args.output.lower().endswith(".tareco"):
            print(g.save(args.output))
            return 0
        if args.report:
            if not args.output:
                raise TarecoError("--report needs -o FILE.html")
            print((tl or g).report(args.output, title=args.title, lang=args.lang, label=args.label))
            return 0
        view = dict(color=args.color, size=args.size, label=args.label, title=args.title,
                    dim=args.dim, particles=args.particles, renderer=args.renderer,
                    max_nodes=args.max_nodes, lang=args.lang)
        if args.around and view["color"] is None:
            view["color"] = "hop"
        if tl is not None:
            view.pop("lang")
            if args.output:
                print(tl.save(args.output, lang=args.lang, **view))
            else:
                tl.show(lang=args.lang, **view)
        elif args.output:
            print(g.save(args.output, **view))
        else:
            g.show(**view)
    except TarecoError as e:
        print(f"tareco: {e}", file=sys.stderr)
        return 1
    return 0


def _node(g, text):
    """The node a command-line id means: as typed, or as the number it looks like."""
    if text in g:
        return text
    for kind in (int, float):
        try:
            if kind(text) in g:
                return kind(text)
        except ValueError:
            pass
    raise TarecoError(f"node {text!r} is not in the graph")


def _write_csv(rows, path):
    columns = list(dict.fromkeys(k for r in rows for k in r)) or ["node", "score"]
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=columns)
        w.writeheader()
        w.writerows(rows)
    return os.path.abspath(path)


if __name__ == "__main__":
    sys.exit(main())

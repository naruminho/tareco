"""Command line: ``tareco edges.csv`` opens the interactive view."""

import argparse
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
    p.add_argument("edges", help="edges file (.csv, .tsv, .json, .edges)")
    p.add_argument("--nodes", help="optional nodes file with attributes")
    p.add_argument("-o", "--output", help="write this HTML file instead of opening the browser")
    p.add_argument("-d", "--directed", action="store_true", help="edges have a direction")
    p.add_argument("--source", help="column with the edge source")
    p.add_argument("--target", help="column with the edge target")
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
    p.add_argument("--report", action="store_true", help="write a shareable report (with -o) instead of the bare view")
    p.add_argument("--version", action="version", version=f"tareco {__version__}")
    args = p.parse_args(argv)

    try:
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
                      source=args.source, target=args.target)
        if args.summary:
            print(g.summary())
            return 0
        if args.explain:
            print((tl or g).explain(lang=args.lang, label=args.label))
            return 0
        if args.patterns:
            print(g.patterns(lang=args.lang, label=args.label))
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


if __name__ == "__main__":
    sys.exit(main())

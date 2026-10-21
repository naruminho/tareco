"""Command line: ``tareco edges.csv`` opens the interactive view."""

import argparse
import sys

from . import __version__
from .errors import TarecoError
from .graph import Graph


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
    p.add_argument("--summary", action="store_true", help="print headline numbers and exit")
    p.add_argument("--version", action="version", version=f"tareco {__version__}")
    args = p.parse_args(argv)

    try:
        g = Graph(args.edges, nodes=args.nodes, directed=args.directed or None,
                  source=args.source, target=args.target)
        if args.summary:
            print(g.summary())
            return 0
        view = dict(color=args.color, size=args.size, label=args.label, title=args.title,
                    dim=args.dim, particles=args.particles)
        if args.output:
            print(g.save(args.output, **view))
        else:
            g.show(**view)
    except TarecoError as e:
        print(f"tareco: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

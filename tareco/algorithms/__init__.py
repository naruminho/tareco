"""Graph algorithms written from scratch. Every one is also a ``Graph`` method."""

from .centrality import betweenness, closeness, degree_centrality, pagerank
from .community import louvain, modularity
from .components import components, is_connected, strong_components
from .flow import max_flow
from .paths import (bfs, dfs, diameter, distance, distances, eccentricity, k_shortest_paths,
                    shortest_path)
from .structure import (clustering, core_number, density, has_cycle, k_core, spanning_tree,
                        suggest_links, summary, topological_sort, transitivity, triangles)

__all__ = [
    "betweenness", "bfs", "closeness", "clustering", "components", "core_number",
    "degree_centrality", "density", "dfs", "diameter", "distance", "distances",
    "eccentricity", "has_cycle", "is_connected", "k_core", "k_shortest_paths", "louvain",
    "max_flow", "modularity",
    "pagerank", "shortest_path", "spanning_tree", "strong_components", "suggest_links",
    "summary", "topological_sort", "transitivity", "triangles",
]

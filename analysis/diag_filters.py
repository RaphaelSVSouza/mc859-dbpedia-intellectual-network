# diag.py
import igraph as ig

g = ig.Graph.Read("rede_intelectual.graphml", format="graphml")
print(f"Original: {g.vcount():,} nós, {g.ecount():,} arestas")

# Filtro 1: TOP_N
deg = g.degree(mode="all")
TOP_N = 500
keep = sorted(range(g.vcount()), key=lambda i: -deg[i])[:TOP_N]
g1 = g.subgraph(keep)
print(f"Após TOP_N={TOP_N}: {g1.vcount():,} nós, {g1.ecount():,} arestas")

# Filtro 2: MIN_DEGREE
deg1 = g1.degree(mode="all")
MIN_DEG = 2
keep = [i for i, d in enumerate(deg1) if d >= MIN_DEG]
g2 = g1.subgraph(keep)
print(f"Após MIN_DEGREE={MIN_DEG}: {g2.vcount():,} nós, {g2.ecount():,} arestas")

# Filtro 3: maior WCC
largest = max(g2.connected_components(mode="weak"), key=len)
g3 = g2.subgraph(largest)
print(f"Após maior WCC: {g3.vcount():,} nós, {g3.ecount():,} arestas")
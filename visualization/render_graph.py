"""
Renderização v4 da Rede Intelectual.
Diferenças vs. v3:
  - ARESTAS COM SETAS (FancyArrowPatch, respeita direção)
  - Setas terminam na borda do nó (não no centro), via shrink

Uso:
    pip install python-igraph matplotlib
    python render_graph_v4.py rede_intelectual.gexf

Variáveis de ambiente:
    TOP_N=500           top nós a manter pelo grau
    MIN_DEGREE=2        threshold mínimo de grau
    LAYOUT=auto         auto | fr | kk | drl
    LABEL_TOP=30        quantos nós recebem label
    LEGEND_NAMES=3      quantos nomes por comunidade na legenda
    ARROW_SIZE=10       tamanho da seta (ajuste se ficarem grandes/pequenas demais)
    EDGE_ALPHA=0.5      transparência das arestas (0-1)
    WIDTH=14            largura em polegadas
    HEIGHT=14           altura
    DPI=180
    OUTPUT=grafo.png
"""
import os, sys, math


def main():
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)

    src         = sys.argv[1]
    TOP_N       = int(os.environ.get("TOP_N", "500"))
    MIN_DEG     = int(os.environ.get("MIN_DEGREE", "2"))
    LAYOUT      = os.environ.get("LAYOUT", "auto")
    LABEL_TOP   = int(os.environ.get("LABEL_TOP", "30"))
    LEG_NAMES   = int(os.environ.get("LEGEND_NAMES", "3"))
    ARROW_SIZE  = float(os.environ.get("ARROW_SIZE", "10"))
    EDGE_ALPHA  = float(os.environ.get("EDGE_ALPHA", "0.5"))
    W           = float(os.environ.get("WIDTH",  "14"))
    H           = float(os.environ.get("HEIGHT", "14"))
    DPI         = int(os.environ.get("DPI", "180"))
    OUT         = os.environ.get("OUTPUT", "grafo.png")

    import igraph as ig
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patheffects as pe
    from matplotlib.patches import FancyArrowPatch
    from matplotlib.lines import Line2D

    print(f"Lendo {src}...")
    if src.endswith(".graphml") or src.endswith(".graphml.gz"):
        g = ig.Graph.Read_GraphML(src)
    else:
        g = ig.Graph.Read(src, format="gexf")

    # IMPORTANTE: garante que igraph trate como direcionado
    if not g.is_directed():
        print("AVISO: grafo carregado como não-direcionado. Convertendo para direcionado.")
        g.to_directed()

    print(f"V = {g.vcount():,}, E = {g.ecount():,}, direcionado = {g.is_directed()}")

    # ---- redução ----
    deg = g.degree(mode="all")
    if g.vcount() > TOP_N:
        keep = sorted(range(g.vcount()), key=lambda i: -deg[i])[:TOP_N]
        g = g.subgraph(keep)
    deg = g.degree(mode="all")
    keep = [i for i, d in enumerate(deg) if d >= MIN_DEG]
    g = g.subgraph(keep)
    largest = max(g.connected_components(mode="weak"), key=len)
    g = g.subgraph(largest)
    print(f"Subgrafo final: V = {g.vcount():,}, E = {g.ecount():,}")

    # ---- layout ----
    if LAYOUT == "auto":
        LAYOUT = "fr" if g.vcount() < 1500 else "drl"
    print(f"Layout '{LAYOUT}'...")
    if   LAYOUT == "fr":  layout = g.layout_fruchterman_reingold(niter=500)
    elif LAYOUT == "kk":  layout = g.layout_kamada_kawai()
    elif LAYOUT == "drl": layout = g.layout_drl()
    else: raise ValueError(LAYOUT)
    coords = list(layout)

    # ---- comunidades ----
    print("Louvain...")
    g_undir = g.as_undirected(combine_edges="ignore")
    comms = g_undir.community_multilevel()
    membership = comms.membership
    n_comms = len(comms)
    print(f"  {n_comms} comunidades")

    PALETTE = [
        "#1D9E75", "#D85A30", "#7F77DD", "#E8B547", "#378ADD",
        "#A04ABA", "#3FA89F", "#C6553F", "#9B7BC9", "#6B7280",
    ]
    comm_sizes = sorted([(i, len(c)) for i, c in enumerate(comms)],
                        key=lambda x: -x[1])
    comm_color = {}
    comm_rank  = {}
    for rank, (cid, size) in enumerate(comm_sizes):
        comm_color[cid] = PALETTE[rank] if rank < len(PALETTE) else "#cccccc"
        comm_rank[cid]  = rank

    deg_sub = g.degree(mode="all")
    label_attr = "label" if "label" in g.vs.attribute_names() else "name"
    labels_full = g.vs[label_attr]

    comm_top_names = {}
    for cid, members in enumerate(comms):
        sorted_members = sorted(members, key=lambda i: -deg_sub[i])
        comm_top_names[cid] = [labels_full[i] for i in sorted_members[:LEG_NAMES]]

    max_deg = max(deg_sub) if deg_sub else 1
    sizes = [60 + 600 * math.sqrt(d / max_deg) for d in deg_sub]
    colors = [comm_color[m] for m in membership]

    threshold = sorted(deg_sub, reverse=True)[min(LABEL_TOP, len(deg_sub) - 1)]
    show_label = [d >= threshold for d in deg_sub]

    # ---- desenho ----
    print("Renderizando...")
    fig, ax = plt.subplots(figsize=(W, H), dpi=DPI)
    ax.set_facecolor("white")

    # arestas com setas
    edge_color = "#999999"
    # raio aproximado dos nós em coordenadas de dados (estimativa pra setas pararem na borda)
    # sizes está em pontos² do scatter; pra coordenadas precisa converter, mas como aproximação
    # usamos shrink em pontos
    for e in g.es:
        s, t = e.source, e.target
        x0, y0 = coords[s]
        x1, y1 = coords[t]
        # raio do nó alvo em pontos (raiz quadrada do tamanho do scatter)
        # sizes[i] é a área em pontos²; raio ≈ sqrt(area/pi)
        target_radius_pt = math.sqrt(sizes[t] / math.pi)
        source_radius_pt = math.sqrt(sizes[s] / math.pi)

        arrow = FancyArrowPatch(
            (x0, y0), (x1, y1),
            arrowstyle="-|>",
            mutation_scale=ARROW_SIZE,
            color=edge_color,
            alpha=EDGE_ALPHA,
            linewidth=0.7,
            shrinkA=source_radius_pt,
            shrinkB=target_radius_pt + 1,  # +1 pra seta não tocar a borda
            connectionstyle="arc3,rad=0.06",  # leve curvatura
            zorder=1,
        )
        ax.add_patch(arrow)

    # nós
    xs = [c[0] for c in coords]
    ys = [c[1] for c in coords]
    ax.scatter(xs, ys, s=sizes, c=colors, edgecolors="white",
               linewidths=1.5, zorder=2)

    # labels com halo branco
    for i, (x, y) in enumerate(coords):
        if show_label[i]:
            txt = ax.text(x, y, labels_full[i],
                          fontsize=9, fontweight="medium",
                          color="#1a1a1a", ha="center", va="center",
                          zorder=3)
            txt.set_path_effects([
                pe.withStroke(linewidth=2.8, foreground="white"),
            ])

    # ---- legenda ----
    legend_elements, legend_labels = [], []
    for cid, _ in comm_sizes:
        rank = comm_rank[cid]
        if rank >= len(PALETTE):
            break
        names = " · ".join(comm_top_names[cid])
        size = len(comms[cid])
        legend_elements.append(
            Line2D([0], [0], marker="o", color="white",
                   markerfacecolor=comm_color[cid], markersize=12,
                   markeredgecolor="white", markeredgewidth=1)
        )
        legend_labels.append(f"{names}  ({size} nós)")

    legend = ax.legend(legend_elements, legend_labels,
                       loc="lower left",
                       fontsize=9,
                       frameon=True,
                       framealpha=0.92,
                       edgecolor="#dddddd",
                       title=f"Comunidades (Louvain) — {n_comms} no total",
                       title_fontsize=10,
                       labelspacing=0.7,
                       handletextpad=0.9)
    legend.get_title().set_fontweight("bold")

    # margem extra pras setas não cortarem
    ax.margins(0.05)
    ax.set_axis_off()
    ax.set_aspect("equal")
    plt.tight_layout()
    plt.savefig(OUT, dpi=DPI, bbox_inches="tight", facecolor="white")
    plt.close()
    print(f"Pronto: {OUT}")


if __name__ == "__main__":
    main()

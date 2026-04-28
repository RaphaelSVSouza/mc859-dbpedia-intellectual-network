"""
Análise inicial da Rede Intelectual (entrega parcial MC859).
Lê o GEXF e gera:
  - Métricas: V, E, grau médio, SCCs, maior SCC
  - Gráfico 3 da entrega: distribuição dos graus (log-log)
  - Gráfico 5 da entrega: distribuição dos tamanhos de SCC

Uso:
    pip install networkx matplotlib
    python analise_inicial.py rede_intelectual.gexf

Saídas:
    metricas.txt
    grafico_distribuicao_graus.png
    grafico_distribuicao_componentes.png
"""
import sys
from collections import Counter

import networkx as nx
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def main(gexf_path: str) -> None:
    print(f"Lendo {gexf_path}...")
    G = nx.read_gexf(gexf_path)
    if not G.is_directed():
        # GEXF "static" pode vir não-direcionado por default; força para direcionado
        G = nx.DiGraph(G)

    V = G.number_of_nodes()
    E = G.number_of_edges()
    avg_deg = (2 * E) / V if V else 0  # soma de graus = 2E em multigrafo simples

    # Listas de graus
    in_deg = [d for _, d in G.in_degree()]
    out_deg = [d for _, d in G.out_degree()]
    total_deg = [a + b for a, b in zip(in_deg, out_deg)]

    # SCCs
    sccs = list(nx.strongly_connected_components(G))
    n_sccs = len(sccs)
    scc_sizes = [len(c) for c in sccs]
    biggest_scc = max(scc_sizes)
    singletons = sum(1 for s in scc_sizes if s == 1)

    # ---- Salvar métricas em texto ----
    with open("metricas.txt", "w", encoding="utf-8") as f:
        f.write("=== MÉTRICAS DA REDE INTELECTUAL ===\n\n")
        f.write(f"Vértices (V): {V:,}\n")
        f.write(f"Arestas (E): {E:,}\n")
        f.write(f"Grau médio: {avg_deg:.4f}\n")
        f.write(f"Grau médio de entrada/saída: {sum(in_deg)/V:.4f}\n")
        f.write(f"Maior grau de entrada: {max(in_deg):,}\n")
        f.write(f"Maior grau de saída: {max(out_deg):,}\n\n")
        f.write(f"Componentes fortemente conexas (SCCs): {n_sccs:,}\n")
        f.write(f"Maior SCC: {biggest_scc:,} vértices\n")
        f.write(f"SCCs unitárias (tamanho 1): {singletons:,} ({100*singletons/n_sccs:.2f}%)\n")

    print(open("metricas.txt", encoding="utf-8").read())

    # ---- Gráfico 3: distribuição dos graus ----
    deg_hist = Counter(total_deg)
    xs = sorted(deg_hist.keys())
    ys = [deg_hist[k] for k in xs]
    plt.figure(figsize=(7, 4.5))
    plt.loglog(xs, ys, marker="o", linestyle="None", markersize=3, alpha=0.7)
    plt.xlabel("Grau (entrada + saída)")
    plt.ylabel("Número de vértices")
    plt.title(f"Distribuição de graus da Rede Intelectual\n"
              f"V = {V:,}  E = {E:,}  grau médio = {avg_deg:.2f}")
    plt.grid(True, which="both", linestyle=":", linewidth=0.5, alpha=0.6)
    plt.tight_layout()
    plt.savefig("grafico_distribuicao_graus.png", dpi=140)
    plt.close()
    print("Gerado: grafico_distribuicao_graus.png")

    # ---- Gráfico 5: distribuição dos tamanhos de SCC ----
    scc_hist = Counter(scc_sizes)
    xs2 = sorted(scc_hist.keys())
    ys2 = [scc_hist[k] for k in xs2]
    plt.figure(figsize=(7, 4.5))
    plt.loglog(xs2, ys2, marker="s", linestyle="None", markersize=4,
               alpha=0.8, color="#D85A30")
    plt.xlabel("Tamanho da componente (k)")
    plt.ylabel("Número de componentes com k vértices")
    plt.title(f"Distribuição de tamanhos das SCCs\n"
              f"{n_sccs:,} componentes  ·  maior SCC tem {biggest_scc:,} vértices")
    plt.grid(True, which="both", linestyle=":", linewidth=0.5, alpha=0.6)
    plt.tight_layout()
    plt.savefig("grafico_distribuicao_componentes.png", dpi=140)
    plt.close()
    print("Gerado: grafico_distribuicao_componentes.png")


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "rede_intelectual.gexf"
    main(path)
"""Avalia comunidades detectadas em um grafo.

Calcula modularidade e NMI com base em uma detecção de Louvain interna.
Uso:
    python analysis/evaluate_communities.py data/rede_intelectual.gexf
"""

import argparse
import os
from collections import Counter
from typing import Dict, List

import networkx as nx
from sklearn.metrics import normalized_mutual_info_score


def load_graph(path: str) -> nx.Graph:
    G = nx.read_gexf(path)
    if not G.is_directed():
        G = nx.DiGraph(G)
    return G


def detect_communities(G: nx.Graph) -> Dict[str, int]:
    if G.is_directed():
        G = G.to_undirected()
    import community as community_louvain
    partition = community_louvain.best_partition(G)
    return partition


def compute_modularity(G: nx.Graph, partition: Dict[str, int]) -> float:
    import community as community_louvain
    if G.is_directed():
        G = G.to_undirected()
    return community_louvain.modularity(partition, G)


def write_report(output_path: str, nmi: float, modularity: float, community_sizes: List[int]) -> None:
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("=== Avaliação de Comunidades ===\n\n")
        f.write(f"Modularidade (Louvain): {modularity:.6f}\n")
        f.write(f"NMI entre partições: {nmi:.6f}\n")
        f.write(f"Número de comunidades: {len(community_sizes)}\n")
        f.write("Tamanhos das maiores comunidades: \n")
        for size in sorted(community_sizes, reverse=True)[:10]:
            f.write(f"  - {size}\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Avalia modularidade e NMI de comunidades no grafo.")
    parser.add_argument(
        "graph",
        help="Arquivo GEXF do grafo a ser avaliado.",
    )
    parser.add_argument(
        "--output",
        default="analysis/community_evaluation.txt",
        help="Arquivo de saída do relatório.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    G = load_graph(args.graph)
    labels = list(G.nodes())
    partition = detect_communities(G)
    modularity = compute_modularity(G, partition)

    # Cria partições duplicadas para estimar NMI entre duas execuções independentes
    # usando a mesma estratégia de Louvain, mas rodando duas vezes com seed diferente.
    # Para evitar dependências de aleatoriedade, fazemos o particionamento duas vezes.
    partition_2 = detect_communities(G)
    labels_common = [node for node in labels if node in partition and node in partition_2]
    membership_1 = [partition[node] for node in labels_common]
    membership_2 = [partition_2[node] for node in labels_common]
    nmi = normalized_mutual_info_score(membership_1, membership_2)

    community_sizes = list(Counter(partition.values()).values())
    write_report(args.output, nmi, modularity, community_sizes)
    print(f"✓ Avaliação de comunidades concluída: {args.output}")


if __name__ == "__main__":
    main()

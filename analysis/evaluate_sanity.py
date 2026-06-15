"""Sanity check de PageRank comparando Neo4j com um PageRank interno.

Uso:
    python analysis/evaluate_sanity.py \
        --graph data/rede_intelectual.gexf \
        --neo4j-scores neo4j/pagerank_scores.tsv
"""

import argparse
from pathlib import Path
from typing import Dict

import networkx as nx


def load_neo4j_scores(path: str) -> Dict[str, float]:
    scores = {}
    with open(path, encoding="utf-8") as f:
        header = f.readline().strip().split("\t")
        if "label" not in header or "pageRank" not in header:
            raise ValueError("Arquivo de scores Neo4j deve conter colunas 'label' e 'pageRank'.")
        for line in f:
            label, score = line.strip().split("\t")
            scores[label] = float(score)
    return scores


def compute_internal_pagerank(graph_path: str, alpha: float = 0.85, max_iter: int = 100):
    G = nx.read_gexf(graph_path)
    if not G.is_directed():
        G = nx.DiGraph(G)
    if "label" in G.nodes[list(G.nodes())[0]]:
        labels = {n: G.nodes[n]["label"] for n in G.nodes}
    else:
        labels = {n: str(n) for n in G.nodes}
    scores = nx.pagerank(G, alpha=alpha, max_iter=max_iter)
    return {labels[node]: score for node, score in scores.items()}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sanity check do PageRank Neo4j usando PageRank interno.")
    parser.add_argument("--graph", required=True, help="Caminho para o arquivo GEXF do grafo.")
    parser.add_argument("--neo4j-scores", required=True, help="Arquivo TSV com PageRank gerado pelo Neo4j.")
    parser.add_argument("--alpha", type=float, default=0.85, help="Fator de amortecimento para PageRank interno.")
    parser.add_argument("--max-iter", type=int, default=100, help="Número máximo de iterações para PageRank interno.")
    parser.add_argument("--output", default="analysis/sanity_pagerank.txt", help="Arquivo de saída do relatório.")
    return parser.parse_args()


def write_report(output: str, overlap: float, size: int):
    with open(output, "w", encoding="utf-8") as f:
        f.write("=== Sanity Check de PageRank ===\n\n")
        f.write(f"Número de nós comparados: {size}\n")
        f.write(f"Overlap Top-10 entre PageRank Neo4j e interno: {overlap:.4f}\n")


def main() -> None:
    args = parse_args()
    neo4j_scores = load_neo4j_scores(args.neo4j_scores)
    internal_scores = compute_internal_pagerank(args.graph, alpha=args.alpha, max_iter=args.max_iter)

    top_neo4j = {label for label, _ in sorted(neo4j_scores.items(), key=lambda item: -item[1])[:10]}
    top_internal = {label for label, _ in sorted(internal_scores.items(), key=lambda item: -item[1])[:10]}
    overlap = len(top_neo4j & top_internal) / 10.0

    write_report(args.output, overlap, len(set(neo4j_scores) & set(internal_scores)))
    print(f"✓ Sanity check concluído: {args.output}")


if __name__ == "__main__":
    main()

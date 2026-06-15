"""Avalia scores de PageRank comparando Neo4j com uma referência ou com PageRank interno.

Uso:
    python analysis/evaluate_pagerank.py \
        --predictions neo4j/pagerank_scores.tsv \
        --graph data/rede_intelectual.gexf \
        --output analysis/pagerank_evaluation.txt

Também aceita uma referência em TSV com as mesmas colunas de label/score:
    --reference reference_scores.tsv
"""

import argparse
import csv
import math
import os
from collections import defaultdict
from typing import Dict, List, Tuple

import networkx as nx


def load_scores(path: str, label_column: str = "label", score_column: str = "pageRank") -> Dict[str, float]:
    scores = {}
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            if label_column not in row or score_column not in row:
                raise ValueError(
                    f"Arquivo {path} deve conter colunas '{label_column}' e '{score_column}'."
                )
            label = row[label_column].strip()
            try:
                score = float(row[score_column])
            except ValueError:
                continue
            scores[label] = score
    return scores


def rank_scores(scores: Dict[str, float]) -> Dict[str, float]:
    ordered = sorted(scores.items(), key=lambda x: (-x[1], x[0]))
    rank_map = {}
    rank = 1
    for position, (label, _) in enumerate(ordered, start=1):
        rank_map[label] = position
    return rank_map


def spearman_correlation(x: Dict[str, float], y: Dict[str, float]) -> float:
    common = sorted(set(x) & set(y))
    if len(common) < 2:
        return float("nan")
    x_rank = rank_scores({k: x[k] for k in common})
    y_rank = rank_scores({k: y[k] for k in common})
    n = len(common)
    diff_sum = sum((x_rank[label] - y_rank[label]) ** 2 for label in common)
    return 1 - (6 * diff_sum) / (n * (n * n - 1))


def top_k_overlap(x: Dict[str, float], y: Dict[str, float], k: int) -> float:
    top_x = {label for label, _ in sorted(x.items(), key=lambda item: (-item[1], item[0]))[:k]}
    top_y = {label for label, _ in sorted(y.items(), key=lambda item: (-item[1], item[0]))[:k]}
    if not top_x or not top_y:
        return 0.0
    return len(top_x & top_y) / k


def compute_networkx_pagerank(gexf_path: str, alpha: float = 0.85, max_iter: int = 100) -> Dict[str, float]:
    print(f"Lendo grafo para PageRank interno: {gexf_path}")
    G = nx.read_gexf(gexf_path)
    if not G.is_directed():
        G = nx.DiGraph(G)
    if "label" in G.nodes[list(G.nodes())[0]]:
        labels = {n: G.nodes[n]["label"] for n in G.nodes}
    else:
        labels = {n: str(n) for n in G.nodes}
    pagerank = nx.pagerank(G, alpha=alpha, max_iter=max_iter)
    return {labels[node]: score for node, score in pagerank.items()}


def write_report(
    output_path: str,
    predicted_path: str,
    reference_path: str,
    common_count: int,
    spearman: float,
    overlaps: Dict[int, float],
):
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("=== Avaliação de PageRank ===\n\n")
        f.write(f"Predições: {predicted_path}\n")
        f.write(f"Referência: {reference_path}\n")
        f.write(f"Nós em comum: {common_count}\n")
        f.write(f"Spearman Rank Correlation: {spearman:.6f}\n\n")
        for k, value in overlaps.items():
            f.write(f"Top-{k} overlap: {value:.4f}\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Avalia PageRank Neo4j contra referência ou PageRank interno.")
    parser.add_argument(
        "--predictions",
        default="neo4j/pagerank_scores.tsv",
        help="Arquivo TSV com resultados de PageRank Neo4j (label, pageRank).",
    )
    parser.add_argument(
        "--reference",
        default=None,
        help="Arquivo TSV com scores de referência (label, pageRank).",
    )
    parser.add_argument(
        "--graph",
        default=None,
        help="Arquivo GEXF para calcular PageRank interno como referência.",
    )
    parser.add_argument(
        "--alpha",
        type=float,
        default=0.85,
        help="Fator de amortecimento usado no PageRank interno (default: 0.85).",
    )
    parser.add_argument(
        "--max-iter",
        type=int,
        default=100,
        help="Número máximo de iterações para PageRank interno (default: 100).",
    )
    parser.add_argument(
        "--output",
        default="analysis/pagerank_evaluation.txt",
        help="Arquivo de saída do relatório.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    predicted = load_scores(args.predictions)

    if args.graph is None and args.reference is None:
        raise ValueError("Informe --graph ou --reference para definir a referência de comparação.")

    if args.graph is not None:
        reference = compute_networkx_pagerank(args.graph, alpha=args.alpha, max_iter=args.max_iter)
        reference_path = args.graph
    else:
        reference = load_scores(args.reference)
        reference_path = args.reference

    common_labels = set(predicted) & set(reference)
    if not common_labels:
        raise ValueError("Nenhum label em comum entre as previsões e a referência.")

    spearman = spearman_correlation(predicted, reference)
    overlaps = {1: top_k_overlap(predicted, reference, 1), 5: top_k_overlap(predicted, reference, 5), 10: top_k_overlap(predicted, reference, 10), 20: top_k_overlap(predicted, reference, 20)}

    write_report(
        args.output,
        args.predictions,
        reference_path,
        len(common_labels),
        spearman,
        overlaps,
    )

    print(f"✓ Avaliação concluída: {args.output}")


if __name__ == "__main__":
    main()

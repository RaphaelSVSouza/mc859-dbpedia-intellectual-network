"""Wrapper de pipeline para a Rede Intelectual.

Converte um arquivo .nt em .gexf e opcionalmente em .graphml.

Uso:
    python pipeline/run_pipeline.py \
        data/rede_intelectual_final.nt \
        data/rede_intelectual.gexf \
        --graphml data/rede_intelectual.graphml
"""

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import networkx as nx
import nt_to_gexf


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def convert_graphml(gexf_path: Path, graphml_path: Path) -> None:
    print(f"Lendo {gexf_path} para GraphML...")
    G = nx.read_gexf(gexf_path)
    if not G.is_directed():
        G = nx.DiGraph(G)
    ensure_parent(graphml_path)
    nx.write_graphml(G, graphml_path)
    print(f"Pronto: {graphml_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Converte um arquivo NT para GEXF e, opcionalmente, GraphML.")
    parser.add_argument("input_nt", help="Caminho do arquivo rede_intelectual_final.nt")
    parser.add_argument("output_gexf", help="Caminho do arquivo de saída .gexf")
    parser.add_argument(
        "--graphml", dest="graphml", default=None,
        help="Caminho opcional para gerar também um arquivo .graphml")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_nt = Path(args.input_nt)
    output_gexf = Path(args.output_gexf)
    ensure_parent(output_gexf)

    nt_to_gexf.main(str(input_nt), str(output_gexf))

    if args.graphml:
        convert_graphml(output_gexf, Path(args.graphml))


if __name__ == "__main__":
    main()

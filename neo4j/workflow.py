"""
Master workflow for Phase 2 — Neo4j Integration and Analysis.

Este script orquestra todo o fluxo de trabalho da Fase 2:
1. Carrega o grafo RDF em Neo4j
2. Divide arestas para treino/teste (90/10)
3. Computa PageRank no grafo completo
4. Computa Personalized PageRank para Link Prediction

Uso:
    python neo4j/workflow.py \
        --data-path data/rede_intelectual_final.nt \
        --uri neo4j://127.0.0.1:7687 \
        --user neo4j \
        --password <password> \
        --db Test_db \
        [--skip-load] [--skip-pagerank] [--skip-ppr]
"""

import argparse
import subprocess
import sys
from pathlib import Path


def run_command(cmd: list, description: str) -> bool:
    """Run a Python script and report status."""
    print(f"\n{'='*60}")
    print(f"Executando: {description}")
    print(f"{'='*60}")
    
    result = subprocess.run(cmd, capture_output=False)
    
    if result.returncode != 0:
        print(f"✗ Erro ao executar: {description}")
        return False
    
    print(f"✓ Concluído: {description}")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Orquestra o fluxo de trabalho completo da Fase 2 — Neo4j.",
    )
    parser.add_argument(
        "--data-path",
        default="data/rede_intelectual_final.nt",
        help="Caminho do arquivo RDF NT (padrão: data/rede_intelectual_final.nt)",
    )
    parser.add_argument(
        "--uri",
        default="neo4j://127.0.0.1:7687",
        help="URI de conexão do Neo4j (padrão: neo4j://127.0.0.1:7687)",
    )
    parser.add_argument("--user", default="neo4j", help="Usuário do Neo4j (padrão: neo4j)")
    parser.add_argument("--password", required=True, help="Senha do Neo4j")
    parser.add_argument("--db", default="neo4j", help="Nome da database (padrão: neo4j)")
    parser.add_argument(
        "--skip-load", action="store_true", help="Pular carregamento do grafo"
    )
    parser.add_argument(
        "--skip-split", action="store_true", help="Pular divisão de arestas"
    )
    parser.add_argument(
        "--skip-pagerank", action="store_true", help="Pular cálculo de PageRank"
    )
    parser.add_argument(
        "--skip-ppr", action="store_true", help="Pular cálculo de PPR"
    )
    
    args = parser.parse_args()
    
    # Verify data file exists
    if not Path(args.data_path).exists():
        print(f"✗ Arquivo não encontrado: {args.data_path}")
        sys.exit(1)
    
    script_dir = Path(__file__).resolve().parent
    commands = []
    
    # Step 1: Load graph
    if not args.skip_load:
        cmd = [
            sys.executable,
            str(script_dir / "load_graph.py"),
            args.data_path,
            "--uri", args.uri,
            "--user", args.user,
            "--password", args.password,
            "--db", args.db,
            "--clear",
        ]
        commands.append((cmd, "Carregamento do grafo"))
    
    # Step 2: Split edges for train/test
    if not args.skip_split:
        cmd = [
            sys.executable,
            str(script_dir / "split_edges.py"),
            "--uri", args.uri,
            "--user", args.user,
            "--password", args.password,
            "--db", args.db,
            "--test-ratio", "0.1",
            "--output", str(script_dir / "test_edges.tsv"),
        ]
        commands.append((cmd, "Divisão de arestas (treino/teste 90/10)"))
    
    # Step 3: Compute PageRank (3 Variações)
    if not args.skip_pagerank:
        experiments = [
            ("baseline", "pagerank_scores.tsv", "Cálculo de PageRank (Baseline)"),
            ("pessoas", "pagerank_pessoas.tsv", "Cálculo de PageRank Reverso (Pessoas)"),
            ("institucional", "pagerank_institucional.tsv", "Cálculo de PageRank Direto (Institucional)")
        ]
        for exp, out_file, desc in experiments:
            cmd = [
                sys.executable,
                str(script_dir / "pagerank.py"),
                "--uri", args.uri,
                "--user", args.user,
                "--password", args.password,
                "--db", args.db,
                "--iterations", "20",
                "--damping-factor", "0.85",
                "--experiment", exp,
                "--output", str(script_dir / out_file),
            ]
            commands.append((cmd, desc))
    
    # Step 4: Compute Personalized PageRank
    if not args.skip_ppr:
        cmd = [
            sys.executable,
            str(script_dir / "ppr.py"),
            "--uri", args.uri,
            "--user", args.user,
            "--password", args.password,
            "--db", args.db,
            "--test-edges", str(script_dir / "test_edges.tsv"),
            "--damping-factor", "0.85",
            "--output", str(script_dir / "ppr_predictions.tsv"),
            "--metrics-output", str(script_dir / "ppr_metrics.txt"),
        ]
        commands.append((cmd, "Cálculo de Personalized PageRank e Link Prediction"))
    
    # Execute all commands
    print(f"\n{'#'*60}")
    print("# FASE 2 — INTEGRAÇÃO NEO4J E ANÁLISES")
    print(f"{'#'*60}")
    print(f"Data:       {args.data_path}")
    print(f"URI Neo4j:  {args.uri}")
    print(f"Database:   {args.db}")
    print(f"Etapas:     {len(commands)}")
    
    failed = []
    for cmd, description in commands:
        if not run_command(cmd, description):
            failed.append(description)
    
    # Summary
    print(f"\n{'='*60}")
    print("RESUMO")
    print(f"{'='*60}")
    
    if failed:
        print(f"✗ {len(failed)} etapa(s) falharam:")
        for desc in failed:
            print(f"  - {desc}")
        sys.exit(1)
    else:
        print(f"✓ Todas as {len(commands)} etapas foram concluídas com sucesso!")
        print(f"\nArquivos de saída gerados em: {script_dir}/")
        print(f"  - pagerank_scores.tsv (baseline)")
        print(f"  - pagerank_pessoas.tsv")
        print(f"  - pagerank_institucional.tsv")
        print(f"  - ppr_predictions.tsv")
        print(f"  - ppr_metrics.txt")
        print(f"  - test_edges.tsv")


if __name__ == "__main__":
    main()

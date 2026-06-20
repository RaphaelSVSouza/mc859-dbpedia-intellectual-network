"""
Compute Personalized PageRank (PPR) for Link Prediction evaluation.
Versão Otimizada - Redução drástica de memória RAM, processamento em lote nativo e prevenção de Data Leakage.
"""

import argparse
import csv
import os
from collections import defaultdict
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable


class PPRPredictor:
    def __init__(self, uri: str, user: str, password: str, database: str):
        """Initialize Neo4j connection."""
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.database = database
        self._test_connection()
        self._ensure_indexes()
    
    def _test_connection(self):
        """Test the connection to Neo4j."""
        try:
            with self.driver.session(database=self.database) as session:
                session.run("RETURN 1")
            print("✓ Conexão com Neo4j estabelecida")
        except ServiceUnavailable as e:
            print(f"✗ Erro ao conectar ao Neo4j: {e}")
            raise

    def _ensure_indexes(self):
        """Garante a existência do índice no label."""
        print("Verificando/Criando índices de performance...")
        with self.driver.session(database=self.database) as session:
            try:
                session.run("CREATE INDEX resource_label_idx FOR (n:Resource) ON (n.label)")
                print("✓ Índice em :Resource(label) criado com sucesso!")
            except Exception as e:
                if "already exists" in str(e).lower() or "equivalent index" in str(e).lower():
                    print("✓ Índice em :Resource(label) já existente. Pulando criação.")
                else:
                    print(f"⚠ Nota sobre o índice: {e}")
    
    def load_test_edges(self, test_edges_path: str) -> dict:
        """Load test edges from file."""
        if not os.path.exists(test_edges_path):
            raise FileNotFoundError(f"Arquivo de testes não encontrado em: {test_edges_path}")
            
        test_edges = {}
        with open(test_edges_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter="\t")
            for row in reader:
                if "source_id" not in row or "target_id" not in row or "rel_type" not in row:
                    raise ValueError("Arquivo de arestas de teste deve incluir as colunas source_id, rel_type e target_id.")

                source_raw = row["source_id"]
                target_raw = row["target_id"]
                try:
                    source_id = int(source_raw)
                except (TypeError, ValueError):
                    source_id = source_raw
                try:
                    target_id = int(target_raw)
                except (TypeError, ValueError):
                    target_id = target_raw

                key = (source_id, row["rel_type"], target_id)
                test_edges[key] = {
                    "source_label": row.get("source_label", ""),
                    "target_label": row.get("target_label", ""),
                }
        
        print(f"✓ Carregadas {len(test_edges):,} arestas de teste do arquivo")
        return test_edges

    def compute_ppr_gds(
        self,
        test_edges_path: str,
        iterations: int = 20,
        damping_factor: float = 0.85,
        top_k: int = 100,
        batch_size: int = 20,
        train_filter: str = None
    ) -> tuple[dict, dict]:
        """
        Compute Personalized PageRank usando otimizações de memória agressivas e prevenindo Data Leakage.
        """
        test_edges = self.load_test_edges(test_edges_path)
        predictions = {}
        
        # Agrupa nós de origem pelo tipo de relacionamento
        rel_type_sources = defaultdict(set)
        for source_id, rel_type, _ in test_edges.keys():
            rel_type_sources[rel_type].add(source_id)
        
        for rel_type, sources_set in rel_type_sources.items():
            graph_name = f"ppr_graph_{rel_type}"
            sources_list = list(sources_set)
            
            with self.driver.session(database=self.database) as session:
                # 1. Limpa projeções antigas
                try:
                    session.run("CALL gds.graph.drop($graph_name, false) YIELD graphName", graph_name=graph_name)
                except Exception:
                    pass
                
                # 2. Cria a projeção (com ou sem filtro de treino para evitar vazamento de dados)
                print(f"\n-> Projetando grafo em memória para: '{rel_type}'")
                
                if train_filter:
                    # Cypher Projection: Carrega apenas arestas que passam no filtro (ex: r.split = 'train')
                    print(f"   [!] Usando Cypher Projection com filtro: {train_filter}")
                    node_query = "MATCH (n:Resource) RETURN id(n) AS id, n.label AS labels"
                    rel_query = f"MATCH (s:Resource)-[r:`{rel_type}`]->(t:Resource) WHERE {train_filter} RETURN id(s) AS source, id(t) AS target"
                    
                    session.run(
                        """
                        CALL gds.graph.project.cypher(
                            $graph_name,
                            $node_query,
                            $rel_query
                        ) YIELD graphName, nodeCount, relationshipCount
                        """,
                        graph_name=graph_name,
                        node_query=node_query,
                        rel_query=rel_query
                    )
                else:
                    # Native Projection: Carrega todas as arestas (Use apenas se as arestas de teste NÃO estiverem no DB)
                    print("   [!] Usando Native Projection (Atenção: Garanta que as arestas de teste não estão no banco para evitar vazamento!)")
                    node_config = {"Resource": {}}
                    relationship_config = {
                        rel_type: {
                            "type": rel_type,
                            "orientation": "NATURAL"
                        }
                    }
                    
                    session.run(
                        """
                        CALL gds.graph.project(
                            $graph_name,
                            $node_config,
                            $rel_config
                        ) YIELD graphName, nodeCount, relationshipCount
                        """,
                        graph_name=graph_name,
                        node_config=node_config,
                        rel_config=relationship_config
                    )
                
                print(f" -> Computando PPR de forma otimizada para {len(sources_list):,} nós...")
                
                # 3. Execução em lotes controlados
                for i in range(0, len(sources_list), batch_size):
                    batch_ids = sources_list[i:i + batch_size]
                    
                    if all(isinstance(x, int) for x in batch_ids):
                        id_mapping_res = session.run(
                            "MATCH (n:Resource) WHERE id(n) IN $ids RETURN id(n) AS original_id, id(n) AS internal_id, n.label AS label",
                            ids=batch_ids,
                        )
                    else:
                        id_mapping_res = session.run(
                            "MATCH (n:Resource) WHERE elementId(n) IN $ids RETURN elementId(n) AS original_id, id(n) AS internal_id, n.label AS label",
                            ids=batch_ids,
                        )
                    
                    nodes_to_process = [record for record in id_mapping_res]
                    
                    for node_info in nodes_to_process:
                        source_id = node_info["original_id"]
                        source_internal = node_info["internal_id"]
                        
                        if all(isinstance(x, int) for x, _, _ in test_edges.keys()):
                            target_id_expr = "id(targetNode)"
                            source_compare = source_internal
                        else:
                            target_id_expr = "elementId(targetNode)"
                            source_compare = source_id
                        
                        ppr_query = f"""
                        CALL gds.pageRank.stream($graph_name, {{
                            sourceNodes: [$source_internal],
                            dampingFactor: $damping_factor,
                            maxIterations: $iterations
                        }})
                        YIELD nodeId, score
                        WHERE score > 0
                        WITH gds.util.asNode(nodeId) AS targetNode, score
                        WHERE {target_id_expr} <> $source_compare
                        RETURN {target_id_expr} AS tgt_id, targetNode.label AS tgt_label, score
                        ORDER BY score DESC
                        LIMIT $top_k
                        """
                        
                        results = session.run(
                            ppr_query,
                            graph_name=graph_name,
                            source_internal=source_internal,
                            source_compare=source_compare,
                            damping_factor=damping_factor,
                            iterations=iterations,
                            top_k=top_k,
                        )
                        
                        key = (source_id, rel_type)
                        predictions[key] = [
                            {
                                "target_id": rec["tgt_id"],
                                "target_label": rec["tgt_label"],
                                "score": rec["score"],
                            }
                            for rec in results
                        ]
                    
                    processed = min(i + batch_size, len(sources_list))
                    print(f"    Progresso ({rel_type}): {processed}/{len(sources_list)} nós de origem processados")

                # 4. Desaloca o grafo imediatamente
                try:
                    session.run("CALL gds.graph.drop($graph_name, false) YIELD graphName", graph_name=graph_name)
                    print(f"✓ Projeção '{graph_name}' liberada da memória")
                except Exception:
                    pass
        
        return predictions, test_edges
    
    def evaluate_predictions(self, predictions: dict, test_edges: dict, k_values: list = None) -> dict:
        """Evaluate link prediction using HitRate@k and MRR."""
        if k_values is None:
            k_values = [1, 5, 10, 20]
        
        hit_rates_at_k = defaultdict(list)
        mrrs = []
        found_count = 0
        total_count = 0
        
        for source_id, rel_type, target_id in test_edges.keys():
            key = (source_id, rel_type)
            total_count += 1
            
            if key not in predictions:
                for k in k_values:
                    hit_rates_at_k[k].append(0.0)
                continue
            
            pred_list = predictions[key]
            pred_targets = [pred["target_id"] for pred in pred_list]
            
            if target_id in pred_targets:
                found_count += 1
                rank = pred_targets.index(target_id) + 1
                mrrs.append(1.0 / rank)
                
                for k in k_values:
                    hit_rates_at_k[k].append(1.0 if rank <= k else 0.0)
            else:
                for k in k_values:
                    hit_rates_at_k[k].append(0.0)
        
        metrics = {
            "coverage": found_count / total_count if total_count > 0 else 0.0,
            "found": found_count,
            "total": total_count,
            "mrr": sum(mrrs) / total_count if total_count > 0 else 0.0,
        }
        
        for k in k_values:
            metrics[f"hit_rate@{k}"] = sum(hit_rates_at_k[k]) / total_count if total_count > 0 else 0.0
            
        return metrics
    
    def save_predictions_to_file(self, predictions: dict, test_edges: dict, output_path: str):
        """Save PPR predictions to a TSV file."""
        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("source_id\tsource_label\trel_type\ttarget_id\ttarget_label\trank\tscore\tfound\n")
            
            for source_id, rel_type, target_id in sorted(test_edges.keys()):
                metadata = test_edges[(source_id, rel_type, target_id)]
                source_label = metadata.get("source_label", "")
                target_label = metadata.get("target_label", "")
                key = (source_id, rel_type)
                
                if key not in predictions:
                    f.write(f"{source_id}\t{source_label}\t{rel_type}\t{target_id}\t{target_label}\tN/A\tN/A\t0\n")
                    continue
                
                pred_list = predictions[key]
                found = False
                
                for rank, pred in enumerate(pred_list, 1):
                    if pred["target_id"] == target_id:
                        f.write(
                            f"{source_id}\t{source_label}\t{rel_type}\t{target_id}\t{target_label}\t{rank}\t{pred['score']:.6f}\t1\n"
                        )
                        found = True
                        break
                
                if not found:
                    f.write(f"{source_id}\t{source_label}\t{rel_type}\t{target_id}\t{target_label}\tN/A\tN/A\t0\n")
        
        print(f"✓ Predições salvas em: {output_path}")
    
    def close(self):
        """Close the database connection."""
        self.driver.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Calcula PPR Otimizado para avaliação de Link Prediction.")
    parser.add_argument("--uri", default="neo4j://127.0.0.1:7687", help="URI de conexão do Neo4j")
    parser.add_argument("--user", default="neo4j", help="Usuário do Neo4j")
    parser.add_argument("--password", required=True, help="Senha do Neo4j")
    parser.add_argument("--db", default="neo4j", help="Nome da database")
    parser.add_argument("--test-edges", default="neo4j/test_edges.tsv", help="Arquivo com arestas de teste")
    parser.add_argument("--damping-factor", type=float, default=0.85, help="Fator de amortecimento")
    parser.add_argument("--iterations", type=int, default=20, help="Número de iterações")
    parser.add_argument("--top-k", type=int, default=500, help="Top-K predições por nó")
    parser.add_argument("--output", default="neo4j/ppr_predictions.tsv", help="Arquivo para salvar predições")
    parser.add_argument("--metrics-output", default="neo4j/ppr_metrics.txt", help="Arquivo para salvar métricas")
    parser.add_argument("--batch-size", type=int, default=50, help="Tamanho do lote de nós processados em sequência")
    parser.add_argument("--train-filter", default=None, help="Ex: \"r.split = 'train'\". Filtro Cypher para evitar Data Leakage durante a projeção.")
    return parser.parse_args()


def main():
    args = parse_args()
    
    try:
        predictor = PPRPredictor(args.uri, args.user, args.password, args.db)
        
        print("Iniciando etapa de predição massiva...")
        predictions, test_edges = predictor.compute_ppr_gds(
            args.test_edges,
            iterations=args.iterations,
            damping_factor=args.damping_factor,
            top_k=args.top_k,
            batch_size=args.batch_size,
            train_filter=args.train_filter
        )
        
        print("\nAvaliando predições e consolidando métricas...")
        metrics = predictor.evaluate_predictions(predictions, test_edges)
        
        predictor.save_predictions_to_file(predictions, test_edges, args.output)
        
        print("\n--- Métricas de Link Prediction (PPR) ---")
        print(f"Arestas de teste totais: {metrics['total']}")
        print(f"Arestas encontradas no top-{args.top_k}: {metrics['found']} ({metrics['coverage']:.2%})")
        print(f"Mean Reciprocal Rank (MRR): {metrics['mrr']:.6f}")
        print(f"HitRate@1:           {metrics['hit_rate@1']:.6f}")
        print(f"HitRate@5:           {metrics['hit_rate@5']:.6f}")
        print(f"HitRate@10:          {metrics['hit_rate@10']:.6f}")
        print(f"HitRate@20:          {metrics['hit_rate@20']:.6f}")
        
        metrics_dir = os.path.dirname(args.metrics_output)
        if metrics_dir:
            os.makedirs(metrics_dir, exist_ok=True)
        with open(args.metrics_output, "w", encoding="utf-8") as f:
            f.write("=== Métricas de Link Prediction (Personalized PageRank) ===\n\n")
            f.write(f"Arestas de teste:    {metrics['total']}\n")
            f.write(f"Arestas encontradas: {metrics['found']} ({metrics['coverage']:.2%})\n")
            f.write(f"Mean Reciprocal Rank: {metrics['mrr']:.6f}\n")
            f.write(f"HitRate@1:           {metrics['hit_rate@1']:.6f}\n")
            f.write(f"HitRate@5:           {metrics['hit_rate@5']:.6f}\n")
            f.write(f"HitRate@10:          {metrics['hit_rate@10']:.6f}\n")
            f.write(f"HitRate@20:          {metrics['hit_rate@20']:.6f}\n")
        
        print(f"\n✓ Arquivo de relatório gerado em: {args.metrics_output}")
        
        predictor.close()
        print("✓ Processo de validação PPR concluído com sucesso!")
        
    except Exception as e:
        print(f"✗ Erro: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
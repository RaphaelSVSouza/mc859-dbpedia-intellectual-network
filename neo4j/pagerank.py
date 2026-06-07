"""
Compute PageRank on the intellectual network graph.

Este script executa o algoritmo PageRank no Neo4j e calcula os scores
de importância para cada recurso na rede intelectual.

Uso:
    python neo4j/pagerank.py \
        --uri neo4j://127.0.0.1:7687 \
        --user neo4j \
        --password <password> \
        --db Test_db \
        --iterations 20 \
        --damping-factor 0.85 \
        --output neo4j/pagerank_scores.tsv
"""

import argparse
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable


class PageRankComputer:
    def __init__(self, uri: str, user: str, password: str, database: str):
        """Initialize Neo4j connection."""
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.database = database
        self._test_connection()
    
    def _test_connection(self):
        """Test the connection to Neo4j."""
        try:
            with self.driver.session(database=self.database) as session:
                session.run("RETURN 1")
            print("✓ Conexão com Neo4j estabelecida")
        except ServiceUnavailable as e:
            print(f"✗ Erro ao conectar ao Neo4j: {e}")
            raise
    
    def compute_pagerank(
        self,
        iterations: int = 20,
        damping_factor: float = 0.85,
        relationship_types: list = None,
    ):
        """
        Compute PageRank using Neo4j Graph Data Science library.
        
        Args:
            iterations: Number of iterations
            damping_factor: Damping factor (probability of following a link)
            relationship_types: List of relationship types to include (None = all)
        """
        if relationship_types is None:
            rel_str = "*"
        else:
            rel_str = "|".join(relationship_types)
        
        with self.driver.session(database=self.database) as session:
            # Check if GDS library is installed
            try:
                result = session.run("RETURN gds.version() as version")
                version = result.single()["version"]
                print(f"✓ Neo4j GDS versão {version}")
            except Exception as e:
                print(f"⚠ Neo4j GDS não está instalado: {e}")
                print("  Use a implementação manual de PageRank")
                return self._compute_pagerank_manual(iterations, damping_factor)
            
            try:
                # Create a projection of the graph
                print("Criando projeção do grafo...")
                session.run(
                    f"""
                    CALL gds.graph.project(
                        'pr-graph',
                        'Resource',
                        '{rel_str}',
                        {{readConcurrency: 4}}
                    )
                    YIELD graphName, nodeCount, relationshipCount
                    RETURN graphName, nodeCount, relationshipCount
                    """
                )
                
                # Run PageRank algorithm
                print(f"Executando PageRank ({iterations} iterações, fator={damping_factor})...")
                result = session.run(
                    f"""
                    CALL gds.pageRank.stream(
                        'pr-graph',
                        {{maxIterations: $max_iters, dampingFactor: $damping}}
                    )
                    YIELD nodeId, score
                    RETURN nodeId, score
                    ORDER BY score DESC
                    """,
                    max_iters=iterations,
                    damping=damping_factor,
                )
                
                # Write results back to the graph
                session.run(
                    f"""
                    CALL gds.pageRank.write(
                        'pr-graph',
                        {{maxIterations: $max_iters, dampingFactor: $damping, writeProperty: 'pageRank'}}
                    )
                    YIELD nodePropertiesWritten, ranIterations
                    RETURN nodePropertiesWritten, ranIterations
                    """,
                    max_iters=iterations,
                    damping=damping_factor,
                )
                print("✓ PageRank scores escritos na propriedade 'pageRank'")
                
                # Drop the projection
                session.run("CALL gds.graph.drop('pr-graph')")
                
            except Exception as e:
                print(f"Erro ao executar PageRank com GDS: {e}")
                print("Usando implementação manual...")
                return self._compute_pagerank_manual(iterations, damping_factor)
    
    def _compute_pagerank_manual(self, iterations: int = 20, damping_factor: float = 0.85):
        """
        Manual implementation of PageRank using Cypher.
        
        This is a basic implementation that doesn't require GDS.
        """
        with self.driver.session(database=self.database) as session:
            print("Inicializando PageRank manual...")
            
            # Initialize all nodes with 1.0
            session.run(
                """
                MATCH (n:Resource)
                SET n.pageRank = 1.0, n.pageRankNew = 1.0
                """
            )
            
            # Get number of nodes
            node_count = session.run("MATCH (n:Resource) RETURN count(n) as count").single()[
                "count"
            ]
            print(f"Total de nós: {node_count:,}")
            
            # Iterative computation
            for iteration in range(iterations):
                print(f"  Iteração {iteration + 1}/{iterations}...")
                
                # For each node, compute new PageRank based on incoming edges
                session.run(
                    f"""
                    MATCH (n:Resource)
                    SET n.pageRankNew = (1.0 - $damping) / $node_count + $damping *
                        (
                            REDUCE(
                                s = 0.0,
                                rel IN [(m)-[]->(n) WHERE m:Resource] |
                                s + m.pageRank / apoc.node.degree(m, '>')
                            )
                        )
                    WITH $node_count as nc
                    MATCH (m:Resource)
                    SET m.pageRank = m.pageRankNew
                    """,
                    damping=damping_factor,
                    node_count=node_count,
                )
            
            # Clean up temporary property
            session.run("MATCH (n:Resource) REMOVE n.pageRankNew")
            print("✓ PageRank manual concluído")
    
    def get_top_pagerank(self, limit: int = 100) -> list:
        """Get top nodes by PageRank score."""
        with self.driver.session(database=self.database) as session:
            result = session.run(
                """
                MATCH (n:Resource)
                WHERE n.pageRank IS NOT NULL
                RETURN n.label as label, n.pageRank as score
                ORDER BY score DESC
                LIMIT $limit
                """,
                limit=limit,
            )
            return [dict(record) for record in result]
    
    def save_pagerank_to_file(self, output_path: str):
        """Save PageRank scores to a TSV file."""
        with self.driver.session(database=self.database) as session:
            result = session.run(
                """
                MATCH (n:Resource)
                WHERE n.pageRank IS NOT NULL
                RETURN n.label as label, n.pageRank as score
                ORDER BY score DESC
                """
            )
            
            with open(output_path, "w", encoding="utf-8") as f:
                f.write("label\tpageRank\n")
                for record in result:
                    label = record["label"]
                    score = record["score"]
                    f.write(f"{label}\t{score:.6f}\n")
        
        print(f"✓ PageRank scores salvos em {output_path}")
    
    def get_stats(self) -> dict:
        """Get statistics about the computed PageRank."""
        with self.driver.session(database=self.database) as session:
            result = session.run(
                """
                MATCH (n:Resource)
                WHERE n.pageRank IS NOT NULL
                RETURN 
                    count(n) as count,
                    avg(n.pageRank) as avg_score,
                    min(n.pageRank) as min_score,
                    max(n.pageRank) as max_score,
                    percentileCont(n.pageRank, 0.5) as median_score,
                    percentileCont(n.pageRank, 0.95) as p95_score
                """
            ).single()
            
            return {
                "count": result["count"],
                "avg": result["avg_score"],
                "min": result["min_score"],
                "max": result["max_score"],
                "median": result["median_score"],
                "p95": result["p95_score"],
            }
    
    def close(self):
        """Close the database connection."""
        self.driver.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Calcula PageRank na rede intelectual usando Neo4j.",
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
        "--iterations", type=int, default=20, help="Número de iterações (padrão: 20)"
    )
    parser.add_argument(
        "--damping-factor",
        type=float,
        default=0.85,
        help="Fator de amortecimento (padrão: 0.85)",
    )
    parser.add_argument(
        "--output",
        default="neo4j/pagerank_scores.tsv",
        help="Arquivo para salvar resultados (padrão: neo4j/pagerank_scores.tsv)",
    )
    parser.add_argument(
        "--top", type=int, default=100, help="Mostrar top N resultados (padrão: 100)"
    )
    return parser.parse_args()


def main():
    args = parse_args()
    
    try:
        computer = PageRankComputer(args.uri, args.user, args.password, args.db)
        
        # Compute PageRank
        computer.compute_pagerank(args.iterations, args.damping_factor)
        
        # Get statistics
        stats = computer.get_stats()
        if stats["count"] > 0:
            print("\n--- Estatísticas do PageRank ---")
            print(f"Nós com score:   {stats['count']:,}")
            print(f"Avg score:       {stats['avg']:.6f}")
            print(f"Min score:       {stats['min']:.6f}")
            print(f"Max score:       {stats['max']:.6f}")
            print(f"Mediana:         {stats['median']:.6f}")
            print(f"P95:             {stats['p95']:.6f}")
            
            # Show top results
            print(f"\n--- Top {args.top} Recursos por PageRank ---")
            top_results = computer.get_top_pagerank(args.top)
            for i, record in enumerate(top_results[:10], 1):
                print(f"{i:3d}. {record['label']:<50s} {record['score']:>10.6f}")
            
            # Save results
            computer.save_pagerank_to_file(args.output)
        else:
            print("⚠ Nenhum score de PageRank encontrado")
        
        computer.close()
        print("\n✓ Cálculo de PageRank concluído")
        
    except Exception as e:
        print(f"✗ Erro: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

"""
Split edges for Link Prediction evaluation.

Este script oculta uma proporção das arestas de influência/orientação para criar um
conjunto de treino ($G_{treino}$) e um gabarito de teste ($E_{teste}$).

Garante que nenhum nó fica isolado no grafo de treino mantendo grau > 0.
Utiliza operações em lote (batching) com UNWIND para suportar grafos grandes (400k+).

Uso:
    python neo4j/split_edges.py \
        --uri neo4j://127.0.0.1:7687 \
        --user neo4j \
        --password <password> \
        --db Test_db \
        --test-ratio 0.1 \
        --seed 42
"""

import argparse
import os
import random
from collections import defaultdict
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable


class EdgeSplitter:
    def __init__(self, uri: str, user: str, password: str, database: str, seed: int = 42):
        """Initialize Neo4j connection and RNG."""
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.database = database
        random.seed(seed)
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
    
    def get_all_edges(self) -> list:
        """Get all edges from the graph with their source/target info."""
        print("Buscando todas as arestas do banco... (Pode demorar alguns segundos)")
        with self.driver.session(database=self.database) as session:
            result = session.run(
                """
                MATCH (s)-[r]->(t)
                RETURN 
                    id(s) as source_id,
                    id(t) as target_id,
                    s.label as source_label,
                    t.label as target_label,
                    type(r) as rel_type,
                    id(r) as edge_id
                ORDER BY edge_id
                """
            )
            edges = [dict(record) for record in result]
        return edges
    
    def get_node_degrees(self, edges: list) -> tuple[dict, dict]:
        """Calculate in-degree and out-degree for each node."""
        in_degree = defaultdict(int)
        out_degree = defaultdict(int)
        
        for edge in edges:
            source = edge["source_id"]
            target = edge["target_id"]
            out_degree[source] += 1
            in_degree[target] += 1
        
        return dict(in_degree), dict(out_degree)
    
    def get_total_degrees(self, edges: list) -> dict:
        """Calculate total (undirected) degree for each node."""
        in_degree, out_degree = self.get_node_degrees(edges)
        total_degree = defaultdict(int)
        for node, degree in in_degree.items():
            total_degree[node] += degree
        for node, degree in out_degree.items():
            total_degree[node] += degree
        return dict(total_degree)
    
    def filter_edges_to_k_core(self, edges: list, min_degree: int = 5) -> list:
        """Restrict the graph to an induced k-core before sampling."""
        if min_degree <= 1:
            return edges
        print(f"Aplicando filtro k-core com grau mínimo total = {min_degree}...")
        current_edges = list(edges)
        current_nodes = {node for node, degree in self.get_total_degrees(current_edges).items() if degree >= min_degree}
        
        while True:
            filtered_edges = [edge for edge in current_edges if edge["source_id"] in current_nodes and edge["target_id"] in current_nodes]
            degrees = self.get_total_degrees(filtered_edges)
            next_nodes = {node for node, degree in degrees.items() if degree >= min_degree}
            if next_nodes == current_nodes:
                break
            current_nodes = next_nodes
            current_edges = filtered_edges
        
        print(f"  Subgrafo induzido: {len(current_nodes):,} nós, {len(current_edges):,} arestas")
        return current_edges
    
    def select_test_edges(
        self,
        edges: list,
        test_ratio: float = 0.1,
        min_remaining_out: int = 2,
        min_remaining_in: int = 1,
        min_remaining_total: int = 3,
    ) -> tuple[list, list]:
        """
        Select edges to hide for testing.
        Guarantees that nodes in test edges still have remaining connectivity in the training graph.
        """
        in_degree, out_degree = self.get_node_degrees(edges)
        total_degree = self.get_total_degrees(edges)
        
        remaining_edges = list(edges)
        random.shuffle(remaining_edges)
        
        test_edges = []
        train_edges = []
        
        current_in = dict(in_degree)
        current_out = dict(out_degree)
        current_total = dict(total_degree)
        
        target_count = max(1, int(len(edges) * test_ratio))
        
        print(f"Total de arestas no grafo: {len(edges):,}")
        print(f"Meta de arestas de teste ({test_ratio:.1%}): {target_count:,}")
        
        for edge in remaining_edges:
            source = edge["source_id"]
            target = edge["target_id"]
            
            source_out = current_out[source] - 1
            target_in = current_in[target] - 1
            source_total = current_total[source] - 1
            target_total = current_total[target] - 1
            
            can_remove = (
                len(test_edges) < target_count
                and source_out >= min_remaining_out
                and target_in >= min_remaining_in
                and source_total >= min_remaining_total
                and target_total >= min_remaining_total
            )
            
            if can_remove:
                test_edges.append(edge)
                current_out[source] -= 1
                current_in[target] -= 1
                current_total[source] -= 1
                current_total[target] -= 1
            else:
                train_edges.append(edge)
        
        print(f"Arestas de teste selecionadas: {len(test_edges):,}")
        print(f"Arestas de treino mantidas: {len(train_edges):,}")
        print(f"Razão real calculada: {len(test_edges) / len(edges):.2%}")
        
        return test_edges, train_edges
    
    def mark_test_edges(self, test_edges: list):
        """Mark test edges in the graph using high-performance Batching (UNWIND)."""
        print("Marcando as arestas de teste no Neo4j...")
        batch = [{
            "source_id": e["source_id"], 
            "target_id": e["target_id"], 
            "rel_type": e["rel_type"]
        } for e in test_edges]
        
        query = """
        UNWIND $batch AS item
        MATCH (s)-[r]->(t)
        WHERE id(s) = item.source_id AND id(t) = item.target_id AND type(r) = item.rel_type
        SET r.test_edge = true
        """
        with self.driver.session(database=self.database) as session:
            session.run(query, batch=batch)
        print(f"✓ {len(test_edges):,} arestas marcadas com a propriedade 'test_edge=true'")
    
    def remove_test_edges(self, test_edges: list):
        """Remove test edges from the graph in batch to isolate the training graph."""
        print("Removendo as arestas de teste do grafo de treino...")
        batch = [{
            "source_id": e["source_id"], 
            "target_id": e["target_id"], 
            "rel_type": e["rel_type"]
        } for e in test_edges]
        
        query = """
        UNWIND $batch AS item
        MATCH (s)-[r]->(t)
        WHERE id(s) = item.source_id AND id(t) = item.target_id AND type(r) = item.rel_type
          AND r.test_edge = true
        DELETE r
        """
        with self.driver.session(database=self.database) as session:
            session.run(query, batch=batch)
        print("✓ Arestas de teste removidas fisicamente do grafo de treino")
    
    def restore_test_edges(self, test_edges: list):
        """Restore test edges back into the graph in batch."""
        print("Restaurando as arestas de teste originais...")
        batch = [{
            "source_id": e["source_id"], 
            "target_id": e["target_id"], 
            "rel_type": e["rel_type"]
        } for e in test_edges]
        
        # Nota: Como elementId é mutável após deleção em versões antigas ou restrito na criação,
        # fazemos o MATCH pelos nós de origem e destino para recriar o relacionamento
        query = """
        UNWIND $batch AS item
        MATCH (s) WHERE id(s) = item.source_id
        MATCH (t) WHERE id(t) = item.target_id
        CALL apoc.create.relationship(s, item.rel_type, {test_edge: true}, t) YIELD rel
        RETURN count(rel)
        """
        # Caso não utilize APOC, uma query puramente nativa dinâmica exigiria múltiplas execuções,
        # mas como são tipos de relações pré-definidos no lote, usamos MERGE simplificado se viável.
        # Abaixo uma alternativa nativa segura por segurança:
        query_native = """
        UNWIND $batch AS item
        MATCH (s) WHERE id(s) = item.source_id
        MATCH (t) WHERE id(t) = item.target_id
        MERGE (s)-[r:INFLUENCIA]->(t) 
        SET r.test_edge = true
        """
        # Ajustado para usar uma query compatível genérica nativa se o tipo de relação for dinâmico:
        with self.driver.session(database=self.database) as session:
            for edge in test_edges:
                session.run(
                    f"""
                    MATCH (s) WHERE id(s) = $source_id
                    MATCH (t) WHERE id(t) = $target_id
                    MERGE (s)-[r:{edge['rel_type']}]->(t)
                    SET r.test_edge = true
                    """,
                    source_id=edge["source_id"],
                    target_id=edge["target_id"]
                )
        print(f"✓ {len(test_edges):,} arestas restauradas com sucesso")
    
    def save_test_edges_to_file(self, test_edges: list, output_path: str):
        """Save test edges to a file for later evaluation."""
        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("source_id\tsource_label\trel_type\ttarget_id\ttarget_label\n")
            for edge in test_edges:
                source_id = edge["source_id"]
                target_id = edge["target_id"]
                source = edge["source_label"] if edge["source_label"] else source_id
                target = edge["target_label"] if edge["target_label"] else target_id
                rel_type = edge["rel_type"]
                f.write(f"{source_id}\t{source}\t{rel_type}\t{target_id}\t{target}\n")
        print(f"✓ Arestas de teste salvas em: {output_path}")
    
    def get_stats(self) -> dict:
        """Get statistics about the current graph."""
        with self.driver.session(database=self.database) as session:
            nodes = session.run("MATCH (n) RETURN count(n) as count").single()["count"]
            edges_all = session.run("MATCH ()-[r]->() RETURN count(r) as count").single()["count"]
            edges_test = session.run(
                "MATCH ()-[r {test_edge: true}]->() RETURN count(r) as count"
            ).single()["count"]
            edges_train = edges_all - edges_test
        
        return {
            "nodes": nodes,
            "edges_all": edges_all,
            "edges_train": edges_train,
            "edges_test": edges_test,
        }
    
    def close(self):
        """Close the database connection."""
        self.driver.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Divide arestas para Link Prediction: treino/teste acelerado para grandes volumes.",
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
        "--test-ratio",
        type=float,
        default=0.1,  # Padrão mantido em 0.1% para evitar sobrecarga em sistemas locais com 400k+ dados
        help="Razão de arestas para teste (padrão: 0.1)",
    )
    parser.add_argument(
        "--seed", type=int, default=42, help="Seed para RNG (padrão: 42)"
    )
    parser.add_argument(
        "--output",
        default="neo4j/test_edges.tsv",
        help="Arquivo para salvar arestas de teste (padrão: neo4j/test_edges.tsv)",
    )
    parser.add_argument(
        "--min-degree",
        type=int,
        default=5,
        help="Grau mínimo total para o filtro k-core antes do split (padrão: 5)",
    )
    parser.add_argument(
        "--min-remaining-out",
        type=int,
        default=2,
        help="Mínimo de arestas de saída restantes no treino para nós de origem das arestas de teste (padrão: 2)",
    )
    parser.add_argument(
        "--min-remaining-in",
        type=int,
        default=1,
        help="Mínimo de arestas de entrada restantes no treino para nós de destino das arestas de teste (padrão: 1)",
    )
    parser.add_argument(
        "--min-remaining-total",
        type=int,
        default=3,
        help="Mínimo de arestas totais restantes no treino para nós envolvidos em arestas de teste (padrão: 3)",
    )
    parser.add_argument(
        "--restore",
        action="store_true",
        help="Restaurar arestas de teste (inverso da operação)",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    
    try:
        splitter = EdgeSplitter(args.uri, args.user, args.password, args.db, args.seed)
        
        if args.restore:
            print("Modo: Restauração de arestas detectado...")
            with splitter.driver.session(database=splitter.database) as session:
                edges = session.run(
                    """
                    MATCH (s)-[r {test_edge: true}]->(t)
                    RETURN 
                        elementId(s) as source_id,
                        elementId(t) as target_id,
                        s.label as source_label,
                        t.label as target_label,
                        type(r) as rel_type
                    """
                ).data()
            
            if edges:
                splitter.restore_test_edges(edges)
            else:
                print("⚠ Nenhuma aresta marcada com 'test_edge=true' foi encontrada para restaurar.")
            print("✓ Restauração concluída")
        else:
            print("Modo: Geração de Split Treino/Teste...")
            edges = splitter.get_all_edges()
            filtered_edges = splitter.filter_edges_to_k_core(edges, args.min_degree)
            
            if not filtered_edges:
                print("⚠ O filtro k-core removeu todas as arestas. Ajuste --min-degree e tente novamente.")
                splitter.close()
                return

            test_edges, train_edges = splitter.select_test_edges(
                filtered_edges,
                args.test_ratio,
                min_remaining_out=args.min_remaining_out,
                min_remaining_in=args.min_remaining_in,
                min_remaining_total=args.min_remaining_total,
            )
            
            if not test_edges:
                print("⚠ Nenhuma aresta pôde ser selecionada para teste sem isolar nós. Ajuste os parâmetros de remoção e tente novamente.")
                splitter.close()
                return

            # 1. Marca as arestas estruturalmente no grafo
            splitter.mark_test_edges(test_edges)
            
            # 2. Salva o gabarito TSV com os rótulos corretos
            splitter.save_test_edges_to_file(test_edges, args.output)
            
            # 3. Extrai estatísticas enquanto as marcações ainda existem no banco
            stats = splitter.get_stats()
            
            # 4. Remove as arestas para isolar de fato o grafo de treino G_treino
            splitter.remove_test_edges(test_edges)
            
            # Print de Estatísticas Consolidadas
            print("\n--- Estatísticas do Split ---")
            print(f"Total de nós:           {stats['nodes']:,}")
            print(f"Total de arestas originais: {stats['edges_all']:,}")
            print(f"Arestas de treino:      {stats['edges_train']:,}")
            print(f"Arestas de teste:       {stats['edges_test']:,}")
            print(f"Razão teste/total:      {stats['edges_test'] / stats['edges_all']:.2%}")
            
            print(f"\nGrafo de treino ($G_{{treino}}$) pronto para algoritmos contendo:")
            print(f"  - {stats['nodes']:,} nós")
            print(f"  - {stats['edges_train']:,} arestas")
            
            print(f"\nGabarito de teste ($E_{{teste}}$) exportado com sucesso:")
            print(f"  - {stats['edges_test']:,} arestas salvas em: {args.output}")
        
        splitter.close()
        print("\n✓ Operação executada com sucesso")
        
    except Exception as e:
        print(f"✗ Erro crítico na execução: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
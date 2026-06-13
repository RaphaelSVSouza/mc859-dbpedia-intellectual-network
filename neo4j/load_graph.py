"""
Load rede_intelectual_final.nt into Neo4j.

Este script carrega as triplas RDF do arquivo N-Triples em um grafo Neo4j,
criando nós para recursos e arestas para relações temáticas.

Uso:
    python neo4j/load_graph.py \
        data/rede_intelectual_final.nt \
        --uri neo4j://127.0.0.1:7687 \
        --user neo4j \
        --password <password> \
        --db Test_db
"""

import argparse
import sys
from pathlib import Path
from typing import Optional
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable


def extract_label(uri: str) -> str:
    """Extract resource label from DBpedia URI.
    
    <http://dbpedia.org/resource/Albert_Einstein> -> "Albert Einstein"
    <http://example.com/some_resource> -> "some_resource"
    """
    uri = uri.strip("<>")
    if "dbpedia.org/resource/" in uri:
        return uri.split("dbpedia.org/resource/")[-1].replace("_", " ")
    # For non-DBpedia resources, return last part of URI
    return uri.split("/")[-1]


def extract_predicate(uri: str) -> str:
    """Extract predicate name from ontology URI.
    
    <http://dbpedia.org/ontology/influenced> -> "INFLUENCED"
    """
    uri = uri.strip("<>")
    if "dbpedia.org/ontology/" in uri:
        return uri.split("dbpedia.org/ontology/")[-1].upper()
    return uri.split("/")[-1].upper()


class Neo4jLoader:
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
            print("[OK] Neo4j connection established")
        except ServiceUnavailable as e:
            print(f"[ERROR] Connection error: {e}")
            raise
    
    def clear_graph(self):
        """Delete all nodes and relationships from the graph."""
        with self.driver.session(database=self.database) as session:
            session.run("MATCH (n) DETACH DELETE n")
        print("[OK] Graph cleared")
    
    def load_triples(self, nt_path: str, batch_size: int = 5000):
        """Load N-Triples from file into Neo4j."""
        path = Path(nt_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {nt_path}")
        
        total_lines = 0
        batch = []
        
        print(f"[INFO] Reading {nt_path}...")
        
        with open(nt_path, encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line or not line.startswith("<"):
                    continue
                
                # Parse N-Triple format: <s> <p> <o> .
                try:
                    sp1 = line.find("> <")
                    if sp1 < 0:
                        continue
                    
                    subject = line[:sp1 + 1]
                    rest = line[sp1 + 2:]
                    
                    sp2 = rest.find("> <")
                    if sp2 < 0:
                        continue
                    
                    predicate = rest[:sp2 + 1]
                    o_part = rest[sp2 + 2:]
                    
                    end = o_part.rfind("> .")
                    if end < 0:
                        continue
                    
                    obj = o_part[:end + 1]
                    
                    batch.append((subject, predicate, obj))
                    total_lines += 1
                    
                    if len(batch) >= batch_size:
                        self._insert_batch(batch)
                        print(f"[INFO] {total_lines:,} triples loaded...")
                        batch = []
                except Exception as e:
                    print(f"[WARN] Error processing line {line_num}: {e}")
                    continue
            
            # Insert remaining batch
            if batch:
                self._insert_batch(batch)
        
        print(f"[OK] Total of {total_lines:,} triples loaded")
        self._create_indices()
    
    def _insert_batch(self, batch: list):
        """Insert a batch of triples into Neo4j."""
        with self.driver.session(database=self.database) as session:
            for subject, predicate, obj in batch:
                subject_label = extract_label(subject)
                object_label = extract_label(obj)
                predicate_type = extract_predicate(predicate)
                
                # Create or match subject node
                session.run(
                    """
                    MERGE (s:Resource {uri: $subject})
                    SET s.label = $subject_label
                    """,
                    subject=subject,
                    subject_label=subject_label,
                )
                
                # Create or match object node
                session.run(
                    """
                    MERGE (o:Resource {uri: $object})
                    SET o.label = $object_label
                    """,
                    object=obj,
                    object_label=object_label,
                )
                
                # Create relationship with dynamic relationship type
                session.run(
                    f"""
                    MATCH (s:Resource {{uri: $subject}})
                    MATCH (o:Resource {{uri: $object}})
                    MERGE (s)-[:{predicate_type}]->(o)
                    """,
                    subject=subject,
                    object=obj,
                )
    
    def _create_indices(self):
        """Create indices for better performance."""
        with self.driver.session(database=self.database) as session:
            session.run("CREATE INDEX IF NOT EXISTS FOR (n:Resource) ON (n.uri)")
            session.run("CREATE INDEX IF NOT EXISTS FOR (n:Resource) ON (n.label)")
        print("[OK] Indices created")
    
    def get_stats(self) -> dict:
        """Get basic statistics about the loaded graph."""
        with self.driver.session(database=self.database) as session:
            nodes = session.run("MATCH (n) RETURN count(n) as count").single()["count"]
            edges = session.run("MATCH ()-[r]->() RETURN count(r) as count").single()["count"]
            predicates = session.run(
                """
                CALL db.relationshipTypes() YIELD relationshipType
                RETURN collect(relationshipType) as predicates
                """
            ).single()["predicates"]
        
        return {
            "nodes": nodes,
            "edges": edges,
            "predicates": predicates,
        }
    
    def close(self):
        """Close the database connection."""
        self.driver.close()
        print("[OK] Connection closed")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Load RDF N-Triples to Neo4j graph database.",
    )
    parser.add_argument("input_nt", help="Path to rede_intelectual_final.nt file")
    parser.add_argument(
        "--uri",
        default="neo4j://127.0.0.1:7687",
        help="Neo4j connection URI (default: neo4j://127.0.0.1:7687)",
    )
    parser.add_argument("--user", default="neo4j", help="Neo4j username (default: neo4j)")
    parser.add_argument("--password", required=True, help="Neo4j password")
    parser.add_argument("--db", default="neo4j", help="Database name (default: neo4j)")
    parser.add_argument(
        "--clear", action="store_true", help="Clear graph before loading"
    )
    return parser.parse_args()


def main():
    args = parse_args()
    
    try:
        loader = Neo4jLoader(args.uri, args.user, args.password, args.db)
        
        if args.clear:
            loader.clear_graph()
        
        loader.load_triples(args.input_nt)
        
        # Print statistics
        stats = loader.get_stats()
        print("\n--- Graph Statistics ---")
        print(f"Nodes:     {stats['nodes']:,}")
        print(f"Edges:     {stats['edges']:,}")
        print(f"Predicates: {', '.join(sorted(stats['predicates']))}")
        
        loader.close()
        print("\n[OK] Loading completed")
        
    except Exception as e:
        print(f"[ERROR] Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

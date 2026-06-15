"""Test the Neo4j connection using local environment configuration."""

import os

from dotenv import load_dotenv
from neo4j import GraphDatabase


load_dotenv()

uri = os.getenv("NEO4J_URI", "neo4j://127.0.0.1:7687")
user = os.getenv("NEO4J_USER", "neo4j")
password = os.getenv("NEO4J_PASSWORD")
database = os.getenv("NEO4J_DATABASE", "neo4j")

if not password:
    raise RuntimeError("Defina NEO4J_PASSWORD no arquivo .env.")

try:
    with GraphDatabase.driver(uri, auth=(user, password)) as driver:
        driver.verify_connectivity()
        with driver.session(database=database) as session:
            result = session.run("RETURN 1 AS test")
            print("[OK] Conexão com Neo4j estabelecida com sucesso!")
            print(f"  URI: {uri}")
            print(f"  Database: {database}")
            print(f"  Result: {result.single()}")
except Exception as e:
    print(f"[ERRO] Falha ao conectar: {e}")
    import traceback

    traceback.print_exc()

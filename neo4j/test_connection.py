"""Test Neo4j connection."""
from neo4j import GraphDatabase

uri = "neo4j://127.0.0.1:7687"
user = "neo4j"
password = "ec0ieBhWzzqRbdDr0A6k"
database = "neo4j"

try:
    driver = GraphDatabase.driver(uri, auth=(user, password))
    with driver.session(database=database) as session:
        result = session.run("RETURN 1 as test")
        print("✓ Conexão com Neo4j estabelecida com sucesso!")
        print(f"  URI: {uri}")
        print(f"  Database: {database}")
        print(f"  Result: {result.single()}")
    driver.close()
except Exception as e:
    print(f"✗ Erro ao conectar: {e}")
    import traceback
    traceback.print_exc()

#!/usr/bin/env python3
"""Filter a candidate table to resources typed as people in DBpedia."""

import argparse
import json
import time
from pathlib import Path

import pandas as pd
import requests


DEFAULT_ENDPOINT = "https://dbpedia.org/sparql"


def read_table(path: Path) -> pd.DataFrame:
    separator = "," if path.suffix.lower() == ".csv" else "\t"
    return pd.read_csv(path, sep=separator)


def write_table(data: pd.DataFrame, path: Path) -> None:
    separator = "," if path.suffix.lower() == ".csv" else "\t"
    path.parent.mkdir(parents=True, exist_ok=True)
    data.to_csv(path, sep=separator, index=False)


def load_cache(path: Path) -> dict[str, bool]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_cache(path: Path, cache: dict[str, bool]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(cache, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def query_people(
    uris: list[str], endpoint: str, timeout: float
) -> set[str]:
    values = "\n".join(f"<{uri}>" for uri in uris)
    query = f"""
PREFIX dbo: <http://dbpedia.org/ontology/>
PREFIX schema: <http://schema.org/>
PREFIX wikidata: <http://www.wikidata.org/entity/>

SELECT DISTINCT ?uri WHERE {{
  VALUES ?uri {{
    {values}
  }}
  {{ ?uri a dbo:Person }}
  UNION {{ ?uri a schema:Person }}
  UNION {{ ?uri a wikidata:Q5 }}
}}
"""
    response = requests.get(
        endpoint,
        params={"query": query, "format": "application/sparql-results+json"},
        headers={
            "Accept": "application/sparql-results+json",
            "User-Agent": "MC859-DBpedia-person-filter/1.0",
        },
        timeout=(10, timeout),
    )
    response.raise_for_status()
    payload = response.json()
    return {
        item["uri"]["value"]
        for item in payload["results"]["bindings"]
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Filtra candidatos classificados como pessoas na DBpedia."
    )
    parser.add_argument("--input", required=True, help="CSV ou TSV com coluna uri.")
    parser.add_argument("--output", required=True, help="CSV ou TSV filtrado.")
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    parser.add_argument("--batch-size", type=int, default=75)
    parser.add_argument("--delay", type=float, default=0.5)
    parser.add_argument("--timeout", type=float, default=60)
    parser.add_argument(
        "--cache",
        default="analysis/.dbpedia_person_cache.json",
        help="Cache para retomar a classificação sem repetir consultas.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)
    cache_path = Path(args.cache)

    candidates = read_table(input_path)
    if "uri" not in candidates.columns:
        raise ValueError("O arquivo de candidatos precisa da coluna 'uri'.")

    candidates["uri"] = candidates["uri"].fillna("").astype(str)
    cache = load_cache(cache_path)
    uris = [uri.strip("<>") for uri in candidates["uri"] if uri]
    pending = list(dict.fromkeys(uri for uri in uris if uri not in cache))

    print(f"Candidatos: {len(candidates):,}")
    print(f"Já classificados no cache: {len(uris) - len(pending):,}")
    print(f"Pendentes: {len(pending):,}")

    for start in range(0, len(pending), args.batch_size):
        batch = pending[start : start + args.batch_size]
        people = query_people(batch, args.endpoint, args.timeout)
        for uri in batch:
            cache[uri] = uri in people
        save_cache(cache_path, cache)
        processed = min(start + len(batch), len(pending))
        print(f"Classificados: {processed:,}/{len(pending):,}")
        if processed < len(pending):
            time.sleep(args.delay)

    candidates["dbpedia_is_person"] = [
        cache.get(uri.strip("<>"), False) for uri in candidates["uri"]
    ]
    people = candidates[candidates["dbpedia_is_person"]].copy()
    write_table(people, output_path)

    print(f"Pessoas identificadas: {len(people):,}/{len(candidates):,}")
    print(f"Arquivo filtrado: {output_path}")


if __name__ == "__main__":
    main()

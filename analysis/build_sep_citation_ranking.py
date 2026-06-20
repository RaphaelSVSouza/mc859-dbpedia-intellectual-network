#!/usr/bin/env python3
import argparse
import hashlib
import os
import re
import time
import unicodedata
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urljoin

import pandas as pd
import requests
from bs4 import BeautifulSoup


COMMON_WORDS = {
    "and",
    "art",
    "church",
    "college",
    "history",
    "just",
    "language",
    "law",
    "less",
    "like",
    "long",
    "more",
    "read",
    "school",
    "science",
    "society",
    "state",
    "than",
    "that",
    "their",
    "then",
    "there",
    "these",
    "they",
    "this",
    "university",
    "what",
    "when",
    "where",
    "which",
    "will",
    "with",
    "world",
}


_PRIMARY_PATTERN: re.Pattern | None = None
_PRIMARY_CANDIDATES: dict[str, list[tuple[int, str]]] = {}
_SECONDARY_PATTERNS: dict[int, list[tuple[str, re.Pattern]]] = {}


def normalize_text(text: str) -> str:
    if not isinstance(text, str):
        return ""

    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def dedupe_repeated_tokens(label: str) -> str:
    """
    Corrige casos como:
      'Ramon Llull Ramon Llull' -> 'Ramon Llull'
    """
    tokens = label.split()

    changed = True
    while changed and len(tokens) % 2 == 0 and len(tokens) > 0:
        changed = False
        half = len(tokens) // 2

        if tokens[:half] == tokens[half:]:
            tokens = tokens[:half]
            changed = True

    return " ".join(tokens)


def clean_label(label: str) -> str:
    label = normalize_text(label)

    # Remove aspas externas, se vierem do export.
    label = label.strip('"').strip("'")

    # Remove sufixos numéricos estranhos.
    label = re.sub(r"\s+\d+$", "", label)

    # Remove desambiguação final: "Li Zhensheng (geneticist)" -> "Li Zhensheng"
    label = re.sub(r"\s*\([^)]*\)\s*$", "", label)

    label = dedupe_repeated_tokens(label)
    label = re.sub(r"\s+", " ", label).strip()

    return label


def get_surname(label: str) -> str | None:
    parts = label.split()

    if len(parts) < 2:
        return None

    return parts[-1]


def is_valid_alias(alias: str) -> bool:
    alias = normalize_text(alias).strip()
    alias_lower = alias.lower()

    return (
        len(alias) >= 4
        and alias_lower not in COMMON_WORDS
        and sum(ch.isalpha() for ch in alias) >= 4
    )


def build_candidate_aliases(
    labels: list[str],
) -> dict[int, dict[str, list[str]]]:
    """Build primary names and secondary surnames for each candidate."""
    clean_labels = [clean_label(label) for label in labels]

    surname_counts = {}

    for label in clean_labels:
        surname = get_surname(label)

        if surname:
            key = surname.lower()
            surname_counts[key] = surname_counts.get(key, 0) + 1

    aliases_by_index = {}

    for idx, label in enumerate(clean_labels):
        primary = set()
        secondary = set()
        parts = label.split()

        if is_valid_alias(label):
            primary.add(label)

        surname = get_surname(label)

        if surname:
            key = surname.lower()

            if (
                is_valid_alias(surname)
                and surname_counts.get(key, 0) == 1
            ):
                secondary.add(surname)

        aliases_by_index[idx] = {
            "primary": sorted(primary, key=lambda x: (-len(x), x)),
            "secondary": sorted(secondary, key=lambda x: (-len(x), x)),
        }

    return aliases_by_index


def compile_candidate_patterns(
    aliases_by_index: dict[int, dict[str, list[str]]],
) -> dict[int, dict[str, list[tuple[str, re.Pattern]]]]:
    patterns = {}

    for idx, groups in aliases_by_index.items():
        patterns[idx] = {"primary": [], "secondary": []}

        for group_name in ("primary", "secondary"):
            for alias in groups[group_name]:
                alias_norm = normalize_text(alias)

                pattern = (
                    r"(?<![A-Za-z])"
                    + re.escape(alias_norm)
                    + r"(?![A-Za-z])"
                )
                patterns[idx][group_name].append(
                    (alias, re.compile(pattern, flags=re.IGNORECASE))
                )

    return patterns


def initialize_match_worker(
    aliases_by_index: dict[int, dict[str, list[str]]],
) -> None:
    """Compile the matching structures once in each worker process."""
    global _PRIMARY_PATTERN, _PRIMARY_CANDIDATES, _SECONDARY_PATTERNS

    _PRIMARY_CANDIDATES = defaultdict(list)
    _SECONDARY_PATTERNS = {}
    primary_aliases = set()

    for candidate_idx, groups in aliases_by_index.items():
        for alias in groups["primary"]:
            alias_norm = normalize_text(alias)
            primary_aliases.add(alias_norm)
            _PRIMARY_CANDIDATES[alias_norm.casefold()].append(
                (candidate_idx, alias)
            )

        secondary_patterns = []
        for alias in groups["secondary"]:
            alias_norm = normalize_text(alias)
            pattern = (
                r"(?<![A-Za-z])"
                + re.escape(alias_norm)
                + r"(?![A-Za-z])"
            )
            secondary_patterns.append(
                (alias, re.compile(pattern, flags=re.IGNORECASE))
            )

        _SECONDARY_PATTERNS[candidate_idx] = secondary_patterns

    if not primary_aliases:
        _PRIMARY_PATTERN = None
        return

    alternatives = "|".join(
        re.escape(alias)
        for alias in sorted(primary_aliases, key=lambda value: (-len(value), value))
    )
    _PRIMARY_PATTERN = re.compile(
        rf"(?<![A-Za-z])(?:{alternatives})(?![A-Za-z])",
        flags=re.IGNORECASE,
    )


def analyze_cached_entry(
    task: tuple[int, int, str, str],
) -> tuple[int, str, list[tuple[int, int, tuple[str, ...]]]]:
    """Analyze one cached SEP entry and return its candidate matches."""
    entry_idx, _, url, cache_path = task
    html = Path(cache_path).read_text(encoding="utf-8", errors="ignore")
    text = html_to_text(html)

    if _PRIMARY_PATTERN is None:
        return entry_idx, url, []

    primary_hits = defaultdict(int)
    aliases_found = defaultdict(set)

    for match in _PRIMARY_PATTERN.finditer(text):
        alias_key = normalize_text(match.group(0)).casefold()

        for candidate_idx, alias in _PRIMARY_CANDIDATES.get(alias_key, []):
            primary_hits[candidate_idx] += 1
            aliases_found[candidate_idx].add(alias)

    if not primary_hits:
        return entry_idx, url, []

    secondary_text = _PRIMARY_PATTERN.sub(" ", text)
    matches = []

    for candidate_idx, hit_count in primary_hits.items():
        total_hits = hit_count

        for alias, pattern in _SECONDARY_PATTERNS[candidate_idx]:
            secondary_hits = len(pattern.findall(secondary_text))

            if secondary_hits:
                total_hits += secondary_hits
                aliases_found[candidate_idx].add(alias)

        matches.append(
            (
                candidate_idx,
                total_hits,
                tuple(sorted(aliases_found[candidate_idx])),
            )
        )

    return entry_idx, url, matches


def cache_path_for_url(url: str, cache_dir: Path) -> Path:
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()
    return cache_dir / f"{digest}.html"


def fetch_url(url: str, cache_dir: Path, delay: float) -> str:
    cache_dir.mkdir(parents=True, exist_ok=True)

    path = cache_path_for_url(url, cache_dir)

    if path.exists():
        return path.read_text(encoding="utf-8", errors="ignore")

    response = requests.get(
        url,
        timeout=30,
        headers={
            "User-Agent": "MC859-SEP-citation-ranking/1.0"
        },
    )
    response.raise_for_status()

    html = response.text
    path.write_text(html, encoding="utf-8")

    time.sleep(delay)

    return html


def ensure_url_cached(url: str, cache_dir: Path, delay: float) -> Path:
    """Download a URL only when needed and return its cache path."""
    path = cache_path_for_url(url, cache_dir)

    if not path.exists():
        fetch_url(url, cache_dir, delay)

    return path


def get_sep_entry_urls(contents_url: str, cache_dir: Path, delay: float) -> list[str]:
    html = fetch_url(contents_url, cache_dir, delay)
    soup = BeautifulSoup(html, "html.parser")

    urls = set()

    for a in soup.find_all("a", href=True):
        href = a["href"]

        if "entries/" not in href:
            continue

        url = urljoin(contents_url, href)
        url = url.split("#")[0]

        if "/entries/" in url:
            urls.add(url)

    return sorted(urls)


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()

    text = soup.get_text(" ")
    return normalize_text(text)


def count_sep_citations(
    candidates: pd.DataFrame,
    contents_url: str,
    cache_dir: Path,
    delay: float,
    max_entries: int | None = None,
    workers: int = 1,
) -> pd.DataFrame:
    labels = candidates["label"].fillna("").astype(str).tolist()

    aliases_by_index = build_candidate_aliases(labels)
    entry_urls = get_sep_entry_urls(contents_url, cache_dir, delay)

    if max_entries is not None:
        entry_urls = entry_urls[:max_entries]

    print(f"Entradas SEP encontradas: {len(entry_urls)}")
    print(f"Candidatos carregados: {len(candidates)}")
    print(f"Processos de análise: {workers}")

    sep_entry_citations = [0 for _ in range(len(candidates))]
    sep_raw_hits = [0 for _ in range(len(candidates))]
    matched_aliases = [set() for _ in range(len(candidates))]
    example_entries = [[] for _ in range(len(candidates))]

    tasks = []
    total_entries = len(entry_urls)

    for entry_idx, url in enumerate(entry_urls, start=1):
        print(f"[cache {entry_idx}/{total_entries}] {url}")

        try:
            cache_path = ensure_url_cached(url, cache_dir, delay)
        except Exception as exc:
            print(f"  erro ao baixar {url}: {exc}")
            continue

        tasks.append((entry_idx, total_entries, url, str(cache_path)))

    with ProcessPoolExecutor(
        max_workers=workers,
        initializer=initialize_match_worker,
        initargs=(aliases_by_index,),
    ) as executor:
        futures = {
            executor.submit(analyze_cached_entry, task): task
            for task in tasks
        }
        completed = 0

        for future in as_completed(futures):
            entry_idx, url, matches = future.result()
            completed += 1

            for candidate_idx, total_hits, aliases in matches:
                sep_entry_citations[candidate_idx] += 1
                sep_raw_hits[candidate_idx] += total_hits
                matched_aliases[candidate_idx].update(aliases)

                if len(example_entries[candidate_idx]) < 5:
                    example_entries[candidate_idx].append((entry_idx, url))

            print(f"[análise {completed}/{len(tasks)}] {url}")

    example_entries = [
        [url for _, url in sorted(entries)[:5]]
        for entries in example_entries
    ]

    result = candidates.copy()

    result["clean_label"] = result["label"].map(clean_label)
    result["sep_entry_citations"] = sep_entry_citations
    result["sep_raw_hits"] = sep_raw_hits
    result["sep_aliases"] = [
        "|".join(
            aliases_by_index[i]["primary"]
            + aliases_by_index[i]["secondary"]
        )
        for i in range(len(candidates))
    ]
    result["sep_matched_aliases"] = [
        "|".join(sorted(matched_aliases[i])) for i in range(len(candidates))
    ]
    result["sep_example_entries"] = [
        "|".join(example_entries[i]) for i in range(len(candidates))
    ]

    result = result.sort_values(
        by=["sep_entry_citations", "sep_raw_hits", "clean_label"],
        ascending=[False, False, True],
    ).reset_index(drop=True)

    result["sep_citation_rank"] = result.index + 1

    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Monta ranking derivado da SEP por citações/menções dos candidatos."
    )

    parser.add_argument(
        "--candidates",
        required=True,
        help="Arquivo TSV exportado do Neo4j com pelo menos as colunas: uri, label.",
    )

    parser.add_argument(
        "--output",
        default="analysis/sep_citation_ranking.tsv",
        help="Arquivo TSV de saída com ranking derivado da SEP.",
    )

    parser.add_argument(
        "--sep-contents-url",
        default="https://plato.stanford.edu/contents.html",
        help=(
            "URL da página de conteúdos da SEP. "
            "Para reprodutibilidade, prefira uma versão arquivada."
        ),
    )

    parser.add_argument(
        "--cache-dir",
        default="analysis/.sep_cache",
        help="Diretório de cache das páginas da SEP.",
    )

    parser.add_argument(
        "--delay",
        type=float,
        default=0.5,
        help="Delay entre downloads novos, em segundos.",
    )

    parser.add_argument(
        "--max-entries",
        type=int,
        default=None,
        help="Usar só as primeiras N entradas da SEP. Útil para teste.",
    )

    parser.add_argument(
        "--workers",
        type=int,
        default=os.process_cpu_count() or 1,
        help="Processos paralelos para análise local (padrão: todos os CPUs disponíveis).",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    candidates_path = Path(args.candidates)
    output_path = Path(args.output)
    cache_dir = Path(args.cache_dir)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    if args.workers < 1:
        raise ValueError("--workers deve ser pelo menos 1")

    if not candidates_path.is_file():
        raise FileNotFoundError(f"Arquivo de candidatos não encontrado: {candidates_path}")

    separator = "," if candidates_path.suffix.lower() == ".csv" else "\t"
    candidates = pd.read_csv(candidates_path, sep=separator)

    required_columns = {"label"}
    missing = required_columns - set(candidates.columns)

    if missing:
        raise ValueError(f"Arquivo de candidatos não possui colunas obrigatórias: {missing}")

    if "uri" not in candidates.columns:
        candidates["uri"] = ""

    candidates["label"] = candidates["label"].fillna("").astype(str)
    candidates["uri"] = candidates["uri"].fillna("").astype(str)

    result = count_sep_citations(
        candidates=candidates,
        contents_url=args.sep_contents_url,
        cache_dir=cache_dir,
        delay=args.delay,
        max_entries=args.max_entries,
        workers=args.workers,
    )

    result.to_csv(output_path, sep="\t", index=False)

    print(f"\nRanking SEP gerado em: {output_path}")
    print("\nTop 30 por citações na SEP:")
    print(
        result[
            [
                "sep_citation_rank",
                "label",
                "sep_entry_citations",
                "sep_raw_hits",
                "sep_aliases",
                "sep_matched_aliases",
            ]
        ].head(30).to_string(index=False)
    )


if __name__ == "__main__":
    main()

# Neo4j Integration — Rede Intelectual MC859

Este diretório contém scripts para carregar o grafo RDF em Neo4j, dividir arestas para treinamento/teste, executar PageRank e Personalized PageRank (PPR) e avaliar predição de links.

## Requisitos

- Neo4j 5.x instalado e em execução
- Python 3.11+
- Dependências do projeto instaladas:

```bash
python -m pip install -r requirements.txt
```

## 1. Carregar o grafo em Neo4j

O script `load_graph.py` lê `data/rede_intelectual_final.nt` e cria nós `:Resource` e relacionamentos para cada predicado temático.

Uso:

```bash
python neo4j/load_graph.py data/rede_intelectual_final.nt \
  --uri neo4j://127.0.0.1:7687 \
  --user neo4j \
  --password <senha> \
  --db neo4j \
  --clear
```

A opção `--clear` remove qualquer grafo existente na database antes do carregamento.

## 2. Dividir arestas em treino/teste

Use `split_edges.py` para ocultar 10% das arestas e gerar `neo4j/test_edges.tsv`.

```bash
python neo4j/split_edges.py \
  --uri neo4j://127.0.0.1:7687 \
  --user neo4j \
  --password <senha> \
  --db neo4j \
  --test-ratio 0.1 \
  --output neo4j/test_edges.tsv
```

O script garante que os nós envolvidos em arestas de teste permanecem conectados no grafo de treino, evitando nós isolados.

## 3. Executar PageRank

O script `pagerank.py` calcula PageRank no grafo completo. Ele tenta usar o Neo4j Graph Data Science (GDS) e recai para uma implementação manual se o GDS não estiver disponível.

```bash
python neo4j/pagerank.py \
  --uri neo4j://127.0.0.1:7687 \
  --user neo4j \
  --password <senha> \
  --db neo4j \
  --iterations 20 \
  --damping-factor 0.85 \
  --output neo4j/pagerank_scores.tsv
```

## 4. Executar Personalized PageRank (PPR)

O script `ppr.py` lê `neo4j/test_edges.tsv`, calcula PPR para cada origem de teste e avalia predição de links.

```bash
python neo4j/ppr.py \
  --uri neo4j://127.0.0.1:7687 \
  --user neo4j \
  --password <senha> \
  --db neo4j \
  --test-edges neo4j/test_edges.tsv \
  --top-k 500 \
  --output neo4j/ppr_predictions.tsv \
  --metrics-output neo4j/ppr_metrics.txt
```

## 5. Orquestrar o pipeline completo

O `workflow.py` combina todas as etapas:

```bash
python neo4j/workflow.py \
  --data-path data/rede_intelectual_final.nt \
  --uri neo4j://127.0.0.1:7687 \
  --user neo4j \
  --password <senha> \
  --db neo4j
```

Use as flags `--skip-load`, `--skip-split`, `--skip-pagerank` ou `--skip-ppr` se quiser pular etapas.

## 6. Scripts de avaliação adicionais

- `analysis/evaluate_pagerank.py`: compara PageRank Neo4j com referência ou com PageRank interno calculado via `networkx`.
- `analysis/evaluate_communities.py`: calcula modularidade e NMI usando Louvain.
- `analysis/evaluate_sanity.py`: sanity check de PageRank comparando neo4j vs PageRank interno.

## Output esperado

- `neo4j/pagerank_scores.tsv`
- `neo4j/test_edges.tsv`
- `neo4j/ppr_predictions.tsv`
- `neo4j/ppr_metrics.txt`

## Notas

- `load_graph.py` grava cada recurso como `:Resource` com propriedades `uri` e `label`.
- `split_edges.py` marca as arestas de teste com `test_edge=true` antes de removê-las da database de treino.
- `ppr.py` monta projeções GDS para cada tipo de relacionamento e processa nós em lotes para reduzir consumo de memória.

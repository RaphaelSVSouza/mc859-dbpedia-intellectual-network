# Rede Intelectual — MC859

Subgrafo direcionado da DBpedia construído a partir de **11 predicados temáticos**
relacionados a influência intelectual, formação acadêmica, religião e ideologia.
A pipeline parte do dump `mappingbased-objects` (lang = en), reorienta relações
inversas (`influencedBy → influenced`, `doctoralAdvisor → doctoralStudent`,
`academicAdvisor → academicStudent`), deduplica triplas e exporta o resultado
em **GEXF** e **GraphML**.

A entrega final do projeto aplica **PageRank**, **Personalized PageRank (PPR)**
e detecção de comunidades por **Louvain** sobre o grafo, executados no Neo4j.

## Autores

- Raphael Salles Vitor de Souza — RA 223641
- Lucas Félix — RA 247064

Disciplina: **MC859 — Projeto em Teoria da Computação** · UNICAMP · 2026
Professor: Ruben Interian Kovaliova

## Sumário do grafo

| Métrica                                | Valor       |
| -------------------------------------- | ----------- |
| Vértices (V)                           | 326.270     |
| Arestas (E)                            | 426.617     |
| Grau médio                             | 2,6151      |
| Grau médio de entrada / saída          | 1,3076      |
| Maior grau de entrada                  | 4.068       |
| Maior grau de saída                    | 237         |
| Componentes fortemente conexas (SCCs)  | 325.240     |
| Maior SCC                              | 840 vértices |
| SCCs unitárias (tamanho 1)             | 325.127 (99,97%) |

Os números completos estão em [`docs/metricas.txt`](docs/metricas.txt) e os
gráficos da entrega parcial em [`docs/figuras/`](docs/figuras/).

## Onde estão os dados

Os artefatos volumosos da pipeline **não** estão neste repositório — estão
hospedados no **Mendeley Data** sob DOI permanente:

| Arquivo                                       | Descrição                                | Tamanho |
| --------------------------------------------- | ---------------------------------------- | ------- |
| `mappingbased-objects_lang=en.ttl.bz2`        | Dump bruto da DBpedia (entrada)          | ~183 MB |
| `rede_intelectual_final.nt`                   | Triplas filtradas, reorientadas e únicas | ~58 MB  |
| `rede_intelectual.gexf`                       | Grafo direcionado em GEXF                | ~47 MB  |
| `rede_intelectual.graphml`                    | Grafo direcionado em GraphML             | ~82 MB  |

> **DOI:** `[a ser preenchido]`

## Como reproduzir o grafo

A reprodução é puramente em linha de comando — não há `build.sh`. Os passos
abaixo regeneram `rede_intelectual_final.nt` (e a partir dele, GEXF/GraphML).

### 1. Baixar o dump da DBpedia

```bash
wget https://databus.dbpedia.org/dbpedia/mappings/mappingbased-objects/2022.12.01/mappingbased-objects_lang=en.ttl.bz2
```

(Ajuste a versão do databus conforme necessário; o snapshot usado no projeto
é o de 2022-12-01.)

### 2. Filtrar pelos 11 predicados temáticos

A lista de predicados está em [`pipeline/preds.txt`](pipeline/preds.txt) e é
consumida via `grep -F -f` (busca literal, sem regex):

```bash
bzcat mappingbased-objects_lang=en.ttl.bz2 \
    | grep -F -f pipeline/preds.txt \
    > rede_intelectual_raw.nt
```

### 3. Reorientar relações inversas

Três predicados expressam a relação contrária ao sentido temático
desejado e são reescritos com inversão de sujeito/objeto:

- `influencedBy(A, B)`     → `influenced(B, A)`
- `doctoralAdvisor(A, B)`  → `doctoralStudent(B, A)`
- `academicAdvisor(A, B)`  → `academicStudent(B, A)`

```bash
awk '
BEGIN {
  inv["<http://dbpedia.org/ontology/influencedBy>"]    = "<http://dbpedia.org/ontology/influenced>"
  inv["<http://dbpedia.org/ontology/doctoralAdvisor>"] = "<http://dbpedia.org/ontology/doctoralStudent>"
  inv["<http://dbpedia.org/ontology/academicAdvisor>"] = "<http://dbpedia.org/ontology/academicStudent>"
}
{
  s = $1; p = $2; o = $3
  if (p in inv) print o, inv[p], s, "."
  else          print s, p,      o, "."
}' rede_intelectual_raw.nt > rede_intelectual_reoriented.nt
```

> Como o dump `mappingbased-objects` contém apenas objetos URI (sem literais),
> `$1 $2 $3` capturam corretamente sujeito, predicado e objeto.

### 4. Deduplicar

A reorientação pode gerar pares já existentes no sentido direto. Um
`sort -u` resolve:

```bash
sort -u rede_intelectual_reoriented.nt > rede_intelectual_final.nt
```

### 5. Converter para GEXF

```bash
python pipeline/nt_to_gexf.py rede_intelectual_final.nt rede_intelectual.gexf
```

O script imprime contagens por predicado como sanity check.

## Análise estrutural

O script de análise consome o GEXF, escreve `metricas.txt` e gera os dois
gráficos da entrega parcial (distribuição de graus em log-log e distribuição
de tamanhos de SCCs):

```bash
pip install networkx matplotlib
python analysis/analise_graph.py rede_intelectual.gexf
```

Saídas:
- `metricas.txt`
- `grafico_distribuicao_graus.png`
- `grafico_distribuicao_componentes.png`

O script auxiliar [`analysis/diag_filters.py`](analysis/diag_filters.py) é
didático: mostra, em três passos (top-N, grau mínimo, maior WCC), como cada
filtro reduz o grafo antes da renderização.

## Visualização

A renderização final usa `python-igraph` + `matplotlib`, com layout
Fruchterman–Reingold/DrL (escolhido automaticamente pelo tamanho), comunidades
de Louvain coloridas, e arestas com **setas direcionadas** terminando na
borda dos nós:

```bash
pip install python-igraph matplotlib
python visualization/render_graph.py rede_intelectual.gexf
```

A configuração é feita por variáveis de ambiente:

| Variável        | Default | Significado                                       |
| --------------- | ------- | ------------------------------------------------- |
| `TOP_N`         | 500     | Top nós a manter por grau                         |
| `MIN_DEGREE`    | 2       | Threshold de grau mínimo                          |
| `LAYOUT`        | auto    | `auto` \| `fr` \| `kk` \| `drl`                   |
| `LABEL_TOP`     | 30      | Quantos nós recebem rótulo                        |
| `LEGEND_NAMES`  | 3       | Quantos nomes por comunidade na legenda           |
| `ARROW_SIZE`    | 10      | Tamanho da seta (`mutation_scale`)                |
| `EDGE_ALPHA`    | 0.5     | Transparência das arestas                         |
| `WIDTH`         | 14      | Largura em polegadas                              |
| `HEIGHT`        | 14      | Altura em polegadas                               |
| `DPI`           | 180     | DPI de saída                                      |
| `OUTPUT`        | grafo.png | Caminho do PNG gerado                           |

Exemplo (corte para o subgrafo dos 19 filósofos centrais usado na entrega):

```bash
TOP_N=500 MIN_DEGREE=2 LAYOUT=fr LABEL_TOP=30 \
OUTPUT=docs/figuras/grafo_rede_intelectual.png \
    python visualization/render_graph.py rede_intelectual.gexf
```

## Estrutura do repositório

```
rede-intelectual-mc859/
├── README.md
├── LICENSE
├── .gitignore
├── pipeline/
│   ├── preds.txt              # 11 predicados temáticos (grep -F -f)
│   └── nt_to_gexf.py          # .nt → .gexf
├── analysis/
│   ├── analise_graph.py       # métricas + gráficos da entrega parcial
│   └── diag_filters.py        # diagnóstico didático dos filtros
├── visualization/
│   └── render_graph.py        # renderização com setas + Louvain
├── data/
│   └── README.md              # ponteiros: Mendeley Data + Databus + Drive
└── docs/
    ├── metricas.txt
    └── figuras/
        ├── grafico_distribuicao_graus.png
        ├── grafico_distribuicao_componentes.png
        └── grafo_rede_intelectual.png
```

## Licença

- **Código** (este repositório): MIT — ver [`LICENSE`](LICENSE).
- **Dados** (no Mendeley Data, fora deste repositório): CC BY 4.0.

## Citação

Se este trabalho for útil em pesquisa ou ensino, por favor cite o dataset:

```bibtex
@dataset{souza_felix_2026_rede_intelectual,
  author    = {Souza, Raphael Salles Vitor de and Félix, Lucas},
  title     = {Rede Intelectual: subgrafo direcionado da DBpedia
               (mappingbased-objects, lang=en) com 11 predicados temáticos},
  year      = {2026},
  publisher = {Mendeley Data},
  version   = {V1},
  doi       = {[a ser preenchido]},
  note      = {Disciplina MC859 — Projeto em Teoria da Computação, UNICAMP.
               Predicados: influenced, doctoralStudent, academicStudent,
               almaMater, knownFor, notableWork, field, religion, ideology
               (com reorientação de influencedBy, doctoralAdvisor
               e academicAdvisor).}
}
```

# data/

Esta pasta está intencionalmente vazia no repositório. Ela existe como ponto
de montagem convencional para os arquivos de dados — é o caminho esperado
pelos scripts ao reproduzir a pipeline localmente.

Os artefatos volumosos **não são versionados** e estão hospedados no
**Mendeley Data** sob DOI permanente:

| Arquivo                                       | Descrição                                |
| --------------------------------------------- | ---------------------------------------- |
| `mappingbased-objects_lang=en.ttl.bz2`        | Dump bruto da DBpedia (entrada)          |
| `rede_intelectual_final.nt`                   | Triplas filtradas, reorientadas e únicas |
| `rede_intelectual.gexf`                       | Grafo direcionado em GEXF                |
| `rede_intelectual.graphml`                    | Grafo direcionado em GraphML             |

> **DOI:** `[a ser preenchido]`

Para reproduzir a pipeline a partir do dump bruto, ver a seção
**"Como reproduzir o grafo"** no [`README.md`](../README.md) na raiz do
repositório.

Licença dos dados: **CC BY 4.0** (atribuição obrigatória).

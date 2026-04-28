# data/

Esta pasta está intencionalmente vazia no repositório. Ela existe como ponto
de montagem convencional para os arquivos de dados — é o caminho esperado
pelos scripts ao reproduzir a pipeline localmente.

Os artefatos são volumosos, adicionados nas extensões `.nt`, `.gexf` e `.graphml` estão com requisição de hospedagem no
**Mendeley Data** sob DOI permanente:

| Arquivo                                       | Descrição                                |
| --------------------------------------------- | ---------------------------------------- |
| `mappingbased-objects_lang=en.ttl.bz2`        | Dump bruto da DBpedia (entrada)          |
| `rede_intelectual_final.nt`                   | Triplas filtradas, reorientadas e únicas |
| `rede_intelectual.gexf`                       | Grafo direcionado em GEXF                |
| `rede_intelectual.graphml`                    | Grafo direcionado em GraphML             |

> **DOI:** `[a ser preenchido]`
> dataset original DBpedia/Databus: [mappingbased-objects](https://databus.dbpedia.org/dbpedia/mappings/mappingbased-objects/2022.12.01/mappingbased-objects_lang=en.ttl.bz2) — aproximadamente **6 milhões de nós** e **23 milhões de arestas** (o subgrafo deste projeto reduz para 326.270 nós e 426.617 arestas após o filtro de 11 predicados temáticos)
> link drive (alternativa): [drive/pasta-datasets](https://drive.google.com/drive/folders/1s8zgb1wgWI-WAhUEZvB0qDljOAyWN4BZ?usp=sharing) - Acesso já concedido ao professor e autores do repostório

Para reproduzir a pipeline a partir do dump bruto, ver a seção
**"Como reproduzir o grafo"** no [`README.md`](../README.md) na raiz do
repositório.    

Licença dos dados: **CC BY 4.0** (atribuição obrigatória).

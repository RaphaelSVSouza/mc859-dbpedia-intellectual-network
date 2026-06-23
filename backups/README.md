# Backups e Dumps do Neo4j

Esta pasta armazena o dump do banco de dados Neo4j utilizado no projeto. Como dumps são arquivos binários grandes, eles estão configurados no `.gitignore` para serem ignorados no repositório Git.

## Como inicializar os dados

Para que o Docker carregue os dados automaticamente na inicialização:

1. Faça o download do arquivo de dump em uma das seguintes opções:
   - [Google Drive - Dumps do Neo4j](https://drive.google.com/drive/folders/1s8zgb1wgWI-WAhUEZvB0qDljOAyWN4BZ?usp=sharing)
   - [Mendeley Data - Antology-Graph](https://data.mendeley.com/datasets/mx25zmdxg2/1) (em processo de revisão)
2. Faça o download do arquivo (ex: `neo4j-2026-06-07T13-24-35.dump` ou `neo4j.dump`).
3. Salve o arquivo nesta pasta (`backups/`) renomeando-o exatamente para:
   ```bash
   neo4j.dump
   ```
4. Ao subir o Docker Compose pela primeira vez com os volumes limpos (`docker compose down -v && docker compose up -d`), o script de boot detectará esse arquivo e fará a importação automática de todo o grafo.

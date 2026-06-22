#!/bin/bash

# Se a pasta de dados do banco "neo4j" não existir (primeira inicialização)
if [ ! -d "/data/databases/neo4j" ]; then
    echo "=== [AUTO-IMPORT] Iniciando importação automática do dump ==="
    if [ -f "/backups/neo4j.dump" ]; then
        # Executa o load. Se estiver rodando como root, garante a permissão correta dos arquivos.
        if [ "$(id -u)" = "0" ]; then
            chown -R neo4j:neo4j /data
            su-exec neo4j:neo4j neo4j-admin database load neo4j --from-path=/backups --overwrite-destination=true
            chown -R neo4j:neo4j /data
        else
            neo4j-admin database load neo4j --from-path=/backups --overwrite-destination=true
        fi
        echo "=== [AUTO-IMPORT] Importação concluída com sucesso! ==="
    else
        echo "=== [AUTO-IMPORT] Arquivo /backups/neo4j.dump não encontrado, pulando... ==="
    fi
else
    echo "=== [AUTO-IMPORT] Banco de dados já possui dados, pulando importação automática. ==="
fi

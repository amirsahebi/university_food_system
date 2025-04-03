#!/bin/bash
set -e
set -u

function create_multiple_databases() {
    local databases=${1}
    for db in $(echo ${databases} | tr ',' ' '); do
        echo "Creating database '$db'"
        psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
            CREATE DATABASE ${db};
            GRANT ALL PRIVILEGES ON DATABASE ${db} TO ${POSTGRES_USER};
EOSQL
    done
}

if [ -n "${POSTGRES_MULTIPLE_DATABASES:-}" ]; then
    echo "Multiple database creation requested: ${POSTGRES_MULTIPLE_DATABASES}"
    create_multiple_databases "${POSTGRES_MULTIPLE_DATABASES}"
fi

# Optional: Create additional users or set up extensions
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
    -- Create a read-only user for reporting
    CREATE USER readonly WITH PASSWORD 'readonly_password';
    GRANT CONNECT ON DATABASE university_food_system TO readonly;
    GRANT USAGE ON SCHEMA public TO readonly;
    GRANT SELECT ON ALL TABLES IN SCHEMA public TO readonly;

    -- Enable useful PostgreSQL extensions
    CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
    CREATE EXTENSION IF NOT EXISTS pgcrypto;
EOSQL

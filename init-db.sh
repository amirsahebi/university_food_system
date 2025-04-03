#!/bin/bash
set -e

# Create the djangouser role with the specified password
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    -- Drop the user if it exists (to reset permissions)
    DROP USER IF EXISTS djangouser;

    -- Create the user with the specified password
    CREATE USER djangouser WITH PASSWORD 'your_secure_postgres_password' CREATEDB CREATEROLE SUPERUSER;

    -- Grant necessary privileges
    GRANT ALL PRIVILEGES ON DATABASE "$POSTGRES_DB" TO djangouser;
    GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO djangouser;
    GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO djangouser;
    GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO djangouser;

    -- Ensure the user can create databases for testing
    ALTER USER djangouser CREATEDB;
EOSQL

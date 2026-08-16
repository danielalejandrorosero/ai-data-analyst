#!/usr/bin/env bash
# Crea el rol de Postgres que usa el agente para ejecutar SQL generado
# (RF-030: credenciales de solo lectura, nunca las de la plataforma).
# Solo SELECT sobre el schema "datasets" (donde viven las tablas fisicas
# de los datasets importados) - sin ningun permiso sobre "public", donde
# estan las tablas de la plataforma (password_hash, memberships, etc.).
#
# AGENT_READONLY_PASSWORD llega como env var del propio contenedor de
# postgres (ver docker-compose.yml) - nunca queda hardcodeado aca.

set -euo pipefail

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
DO \$\$
BEGIN
   IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'agent_readonly') THEN
      CREATE ROLE agent_readonly WITH LOGIN PASSWORD '${AGENT_READONLY_PASSWORD}';
   END IF;
END
\$\$;

CREATE SCHEMA IF NOT EXISTS datasets;

REVOKE ALL ON SCHEMA public FROM agent_readonly;
GRANT USAGE ON SCHEMA datasets TO agent_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA datasets TO agent_readonly;
ALTER DEFAULT PRIVILEGES IN SCHEMA datasets GRANT SELECT ON TABLES TO agent_readonly;
EOSQL

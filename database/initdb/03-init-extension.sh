#!/usr/bin/env bash
set -e

PGPASSWORD=strong-password psql -v ON_ERROR_STOP=1 --username "postgres" --dbname "vectordb" <<-EOSQL
	CREATE EXTENSION vector;
EOSQL

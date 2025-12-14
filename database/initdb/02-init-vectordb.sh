#!/usr/bin/env bash
set -e

PGPASSWORD=strong-password psql -v ON_ERROR_STOP=1 --username "postgres" --dbname "postgres" <<-EOSQL
	CREATE DATABASE vectordb;
	GRANT ALL PRIVILEGES ON DATABASE vectordb TO beyondtheloopuser;
	\c vectordb postgres
	GRANT ALL PRIVILEGES ON SCHEMA public TO beyondtheloopuser;
EOSQL

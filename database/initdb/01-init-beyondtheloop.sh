#!/usr/bin/env bash
set -e

PGPASSWORD=strong-password psql -v ON_ERROR_STOP=1 --username "postgres" --dbname "postgres" <<-EOSQL
	CREATE DATABASE beyondtheloopdb;
	CREATE USER beyondtheloopuser WITH ENCRYPTED PASSWORD 'beyondthelooppassword';
	GRANT ALL PRIVILEGES ON DATABASE beyondtheloopdb TO beyondtheloopuser;
	\c beyondtheloopdb postgres
	GRANT ALL PRIVILEGES ON SCHEMA public TO beyondtheloopuser;
EOSQL

#!/bin/sh
# Restore the database from R2, then run the app under Litestream replication.
set -e

DB_PATH=/data/charlestech.db

litestream restore -config /etc/litestream.yml -if-db-not-exists -if-replica-exists "$DB_PATH"

# First start without any backup: create an empty WAL database for Litestream to watch.
if [ ! -f "$DB_PATH" ]; then
	python -c "import sqlite3; sqlite3.connect('$DB_PATH').execute('PRAGMA journal_mode=WAL').fetchall()"
fi

export DATABASE_REPLICATED=true
exec litestream replicate -config /etc/litestream.yml -exec "python serve.py"

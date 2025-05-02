#!/bin/bash

# Create data directory for ClickHouse
mkdir -p ~/.clickhouse/data
mkdir -p ~/.clickhouse/metadata
mkdir -p ~/.clickhouse/logs

# Start ClickHouse server
clickhouse server --config-file=/etc/clickhouse-server/config.xml \
                 --pid-file=~/.clickhouse/clickhouse.pid \
                 --daemon

# Wait for server to start
sleep 2

# Create database and tables
clickhouse client --query "CREATE DATABASE IF NOT EXISTS telecom"
clickhouse client --query "CREATE TABLE IF NOT EXISTS telecom.log_entries
(
    id UInt32,
    timestamp String,
    level String,
    message String,
    service String,
    additional_fields String,
    created_at DateTime
)
ENGINE = MergeTree()
ORDER BY timestamp"

clickhouse client --query "CREATE TABLE IF NOT EXISTS telecom.analysis_queries
(
    id UInt32,
    query_text String,
    suggestion String,
    confidence_score UInt32,
    created_at DateTime
)
ENGINE = MergeTree()
ORDER BY id"

clickhouse client --query "CREATE TABLE IF NOT EXISTS telecom.analysis_log_associations
(
    analysis_id UInt32,
    log_id UInt32
)
ENGINE = MergeTree()
ORDER BY (analysis_id, log_id)"

echo "ClickHouse started and initialized successfully."
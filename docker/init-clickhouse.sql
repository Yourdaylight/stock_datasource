-- Initialize stock_datasource database for Stock Platform
-- Langfuse uses 'default' database, we use 'stock_datasource' for isolation

CREATE DATABASE IF NOT EXISTS stock_datasource;

-- Grant permissions
GRANT ALL ON stock_datasource.* TO 'clickhouse';

-- Initialize stock_data database for Stock Platform
-- Langfuse uses 'default' database, we use 'stock_data' for isolation

CREATE DATABASE IF NOT EXISTS stock_data;

-- Grant permissions
GRANT ALL ON stock_data.* TO 'clickhouse';

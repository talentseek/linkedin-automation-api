-- Create webhook_data table to store raw webhook requests
CREATE TABLE IF NOT EXISTS webhook_data (
    id VARCHAR(36) PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
    method VARCHAR(10) NOT NULL,
    url VARCHAR(500) NOT NULL,
    headers TEXT,
    raw_data TEXT,
    json_data TEXT,
    content_type VARCHAR(100),
    content_length INTEGER
);

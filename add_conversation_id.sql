-- Add conversation_id column to leads table
ALTER TABLE leads ADD COLUMN conversation_id VARCHAR(255);

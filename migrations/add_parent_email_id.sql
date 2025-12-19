-- Migration: Add parent_email_id for email threading
-- Links reply emails to their original thread

ALTER TABLE emails ADD COLUMN parent_email_id INTEGER;

-- Migration: Add Link Intelligence Columns
-- Adds rich threat intelligence fields to the links table

-- Add risk assessment columns
ALTER TABLE links ADD COLUMN risk_score INTEGER;
ALTER TABLE links ADD COLUMN risk_level VARCHAR(20);

-- Add brand impersonation columns
ALTER TABLE links ADD COLUMN impersonated_brand VARCHAR(100);
ALTER TABLE links ADD COLUMN brand_logo_url VARCHAR(500);

-- Add sandbox analysis columns
ALTER TABLE links ADD COLUMN sandbox_verdict TEXT;
ALTER TABLE links ADD COLUMN final_url VARCHAR(1000);
ALTER TABLE links ADD COLUMN redirect_count INTEGER DEFAULT 0;

-- Add geolocation columns
ALTER TABLE links ADD COLUMN country_code VARCHAR(10);
ALTER TABLE links ADD COLUMN country_flag VARCHAR(10);
ALTER TABLE links ADD COLUMN hosting_ip VARCHAR(50);

-- Add campaign tracking columns
ALTER TABLE links ADD COLUMN campaign_id VARCHAR(50);
ALTER TABLE links ADD COLUMN first_seen TIMESTAMP;

-- Add analysis metadata columns
ALTER TABLE links ADD COLUMN analysis_complete BOOLEAN DEFAULT 0;
ALTER TABLE links ADD COLUMN analyzed_at TIMESTAMP;

-- Update existing links to have analysis_complete = FALSE
UPDATE links SET analysis_complete = FALSE WHERE analysis_complete IS NULL;

-- Create index for faster campaign queries
CREATE INDEX IF NOT EXISTS idx_links_campaign_id ON links(campaign_id);
CREATE INDEX IF NOT EXISTS idx_links_risk_level ON links(risk_level);
CREATE INDEX IF NOT EXISTS idx_links_analysis_complete ON links(analysis_complete);

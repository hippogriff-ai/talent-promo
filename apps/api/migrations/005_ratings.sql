-- Migration: 005_ratings.sql
-- Purpose: Create draft ratings table for user feedback
-- Created: 2025-01-15

-- Draft ratings table
CREATE TABLE IF NOT EXISTS draft_ratings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    thread_id VARCHAR(255) NOT NULL,
    -- Ratings
    overall_quality INTEGER CHECK (overall_quality BETWEEN 1 AND 5),
    ats_satisfaction BOOLEAN,
    would_send_as_is BOOLEAN,
    -- Optional feedback
    feedback_text TEXT,
    -- Job context (for analytics)
    job_title VARCHAR(255),
    company_name VARCHAR(255),
    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_draft_ratings_user_id ON draft_ratings(user_id);
CREATE INDEX IF NOT EXISTS idx_draft_ratings_thread_id ON draft_ratings(thread_id);
CREATE INDEX IF NOT EXISTS idx_draft_ratings_created ON draft_ratings(created_at);
CREATE UNIQUE INDEX IF NOT EXISTS idx_draft_ratings_unique_thread ON draft_ratings(thread_id) WHERE user_id IS NOT NULL;

-- Trigger to auto-update updated_at
CREATE OR REPLACE FUNCTION update_ratings_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_update_ratings_timestamp ON draft_ratings;
CREATE TRIGGER trigger_update_ratings_timestamp
    BEFORE UPDATE ON draft_ratings
    FOR EACH ROW
    EXECUTE FUNCTION update_ratings_updated_at();

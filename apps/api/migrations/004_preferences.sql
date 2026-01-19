-- Migration: 004_preferences.sql
-- Purpose: Create user preferences and preference events tables
-- Created: 2025-01-15

-- User preferences (aggregated settings per user)
CREATE TABLE IF NOT EXISTS user_preferences (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    -- Writing style preferences
    tone VARCHAR(50),  -- formal, conversational, confident, humble
    structure VARCHAR(50),  -- bullets, paragraphs, mixed
    sentence_length VARCHAR(50),  -- concise, detailed, mixed
    first_person BOOLEAN,  -- true = "I led", false = "Led"
    -- Content choices
    quantification_preference VARCHAR(50),  -- heavy_metrics, qualitative, balanced
    achievement_focus BOOLEAN,  -- true = achievements, false = responsibilities
    -- Raw preferences JSON for extensibility
    custom_preferences JSONB DEFAULT '{}',
    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id)
);

-- Preference events (for learning from user behavior)
CREATE TABLE IF NOT EXISTS preference_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    thread_id VARCHAR(255),  -- Which resume session this happened in
    event_type VARCHAR(50) NOT NULL,  -- edit, suggestion_accept, suggestion_reject
    event_data JSONB NOT NULL,  -- Details of the event
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_user_preferences_user_id ON user_preferences(user_id);
CREATE INDEX IF NOT EXISTS idx_preference_events_user_id ON preference_events(user_id);
CREATE INDEX IF NOT EXISTS idx_preference_events_thread_id ON preference_events(thread_id);
CREATE INDEX IF NOT EXISTS idx_preference_events_type ON preference_events(event_type);
CREATE INDEX IF NOT EXISTS idx_preference_events_created ON preference_events(created_at);

-- Trigger to auto-update updated_at
CREATE OR REPLACE FUNCTION update_preferences_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_update_preferences_timestamp ON user_preferences;
CREATE TRIGGER trigger_update_preferences_timestamp
    BEFORE UPDATE ON user_preferences
    FOR EACH ROW
    EXECUTE FUNCTION update_preferences_updated_at();

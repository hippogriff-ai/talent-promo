-- Arena comparisons table for A/B testing
CREATE TABLE IF NOT EXISTS arena_comparisons (
    arena_id TEXT PRIMARY KEY,
    variant_a_thread_id TEXT NOT NULL,
    variant_b_thread_id TEXT NOT NULL,
    status TEXT DEFAULT 'running',
    sync_point TEXT,
    winner TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    created_by TEXT,
    input_data JSONB DEFAULT '{}',
    metadata JSONB DEFAULT '{}'
);

-- Preference ratings table
CREATE TABLE IF NOT EXISTS arena_ratings (
    rating_id TEXT PRIMARY KEY,
    arena_id TEXT NOT NULL REFERENCES arena_comparisons(arena_id) ON DELETE CASCADE,
    step TEXT NOT NULL,
    aspect TEXT NOT NULL,
    preference TEXT NOT NULL,
    reason TEXT,
    rated_by TEXT NOT NULL,
    rated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Variant metrics table
CREATE TABLE IF NOT EXISTS arena_variant_metrics (
    metric_id TEXT PRIMARY KEY,
    arena_id TEXT NOT NULL REFERENCES arena_comparisons(arena_id) ON DELETE CASCADE,
    variant TEXT NOT NULL,
    thread_id TEXT NOT NULL,
    total_duration_ms INTEGER,
    total_llm_calls INTEGER DEFAULT 0,
    total_input_tokens INTEGER DEFAULT 0,
    total_output_tokens INTEGER DEFAULT 0,
    ats_score INTEGER,
    step_metrics JSONB DEFAULT '[]',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_arena_comparisons_status ON arena_comparisons(status);
CREATE INDEX IF NOT EXISTS idx_arena_comparisons_created_at ON arena_comparisons(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_arena_ratings_arena_id ON arena_ratings(arena_id);
CREATE INDEX IF NOT EXISTS idx_arena_variant_metrics_arena_id ON arena_variant_metrics(arena_id);

-- Unique constraint for upsert support
CREATE UNIQUE INDEX IF NOT EXISTS idx_arena_variant_metrics_unique ON arena_variant_metrics(arena_id, variant);

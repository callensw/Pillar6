-- Supabase schema for the Research Assistant
-- Run this in the Supabase SQL editor to create the required tables.

CREATE TABLE IF NOT EXISTS research_jobs (
    id TEXT PRIMARY KEY,
    question TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    result TEXT DEFAULT '',
    trace JSONB DEFAULT '{}',
    costs JSONB DEFAULT '{}',
    created_at DOUBLE PRECISION DEFAULT 0.0,
    completed_at DOUBLE PRECISION DEFAULT 0.0
);

CREATE TABLE IF NOT EXISTS research_events (
    id BIGSERIAL PRIMARY KEY,
    job_id TEXT NOT NULL REFERENCES research_jobs(id),
    timestamp DOUBLE PRECISION DEFAULT 0.0,
    agent TEXT DEFAULT '',
    event_type TEXT DEFAULT '',
    message TEXT DEFAULT '',
    data JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_events_job_id ON research_events(job_id);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON research_jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON research_jobs(created_at DESC);

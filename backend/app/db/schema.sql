CREATE TABLE IF NOT EXISTS sessions (
    id VARCHAR PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_active_at TIMESTAMPTZ DEFAULT NOW(),
    message_count INTEGER DEFAULT 0,
    user_agent TEXT,
    ip_address VARCHAR,
    channel VARCHAR DEFAULT 'text'
);

CREATE TABLE IF NOT EXISTS messages (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR REFERENCES sessions(id),
    role VARCHAR NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    latency_ms INTEGER,
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    model VARCHAR,
    tts_characters INTEGER,
    audio_duration_ms INTEGER
);

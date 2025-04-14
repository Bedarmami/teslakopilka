CREATE TABLE IF NOT EXISTS balances (
    user_id TEXT PRIMARY KEY,
    total INTEGER NOT NULL,
    last_update TIMESTAMP NOT NULL
);

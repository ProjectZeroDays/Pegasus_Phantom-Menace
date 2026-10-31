CREATE TABLE IF NOT EXISTS journal (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    step_type TEXT NOT NULL,
    timestamp REAL NOT NULL,
    input_digest TEXT,
    action TEXT NOT NULL,
    proof_hash TEXT,
    rollback_target TEXT,
    phase_gate TEXT,
    autonomy_mode TEXT,
    created_at REAL DEFAULT (strftime('%s','now'))
);
CREATE INDEX IF NOT EXISTS idx_journal_step ON journal(step_type);
CREATE INDEX IF NOT EXISTS idx_journal_phase ON journal(phase_gate);
CREATE INDEX IF NOT EXISTS idx_journal_time ON journal(timestamp);
-- Invariant: every frame satisfies clear+length2 ≡ 0 mod 16
CREATE TRIGGER IF NOT EXISTS invariant_header_check
BEFORE INSERT ON journal
BEGIN
    SELECT CASE
        WHEN NEW.step_type = 'frame_parsed' AND (CAST(New.action AS INTEGER) % 16 != 0)
        THEN RAISE(ABORT, 'Invariant violated: header length not aligned to 16')
    END;
END;

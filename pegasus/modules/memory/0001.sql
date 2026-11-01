CREATE TABLE episode (id INTEGER PRIMARY KEY, ts REAL, case_id TEXT, host TEXT,
  kind TEXT, body TEXT, importance REAL DEFAULT 0.5, source TEXT, last_access REAL);
CREATE TABLE fact (id INTEGER PRIMARY KEY, key TEXT, value TEXT, valid_from REAL,
  valid_to REAL, confidence REAL, source TEXT);
CREATE TABLE proc (id INTEGER PRIMARY KEY, signature TEXT UNIQUE, command TEXT,
  verdict TEXT, uses INTEGER DEFAULT 0, wins INTEGER DEFAULT 0);
CREATE TABLE block (name TEXT, case_id TEXT, body TEXT, updated REAL,
  PRIMARY KEY(name, case_id));
CREATE VIRTUAL TABLE vec USING vec0(embedding float[384], kind TEXT, ref_id INTEGER);
CREATE VIRTUAL TABLE mem_fts USING fts5(body, tokenize='porter');

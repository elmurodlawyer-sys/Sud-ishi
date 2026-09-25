CREATE TABLE IF NOT EXISTS cases (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  case_number     TEXT NOT NULL,
  court           TEXT NOT NULL,
  category        TEXT NOT NULL,
  role            TEXT NOT NULL,
  region          TEXT NOT NULL,
  plaintiff       TEXT NOT NULL DEFAULT '',
  defendant       TEXT NOT NULL DEFAULT '',
  subject         TEXT NOT NULL DEFAULT '',
  claim_amount    REAL,
  judge           TEXT NOT NULL DEFAULT '',
  responsible     TEXT NOT NULL DEFAULT '',
  status          TEXT NOT NULL DEFAULT 'yangi',
  outcome         TEXT NOT NULL DEFAULT '',
  filed_at        TEXT,
  decision_date   TEXT,
  appeal_deadline TEXT,
  notes           TEXT NOT NULL DEFAULT '',
  created_at      TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
  updated_at      TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS hearings (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  case_id      INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
  scheduled_at TEXT NOT NULL,
  location     TEXT NOT NULL DEFAULT '',
  result       TEXT,
  notes        TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS case_events (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  case_id    INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
  created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
  text       TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_cases_status ON cases(status);
CREATE INDEX IF NOT EXISTS idx_hearings_case ON hearings(case_id);
CREATE INDEX IF NOT EXISTS idx_hearings_date ON hearings(scheduled_at);
CREATE INDEX IF NOT EXISTS idx_events_case ON case_events(case_id);

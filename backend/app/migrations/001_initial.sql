CREATE TABLE sync_configurations (
    id TEXT PRIMARY KEY,
    year INTEGER NOT NULL UNIQUE CHECK(year BETWEEN 1900 AND 9999),
    identity TEXT NOT NULL DEFAULT '[]',
    initialized INTEGER NOT NULL DEFAULT 0 CHECK(initialized IN (0, 1)),
    revision INTEGER NOT NULL DEFAULT 0,
    title TEXT NOT NULL DEFAULT 'EINGO Kudeaketa'
);
CREATE TABLE events (
    id TEXT PRIMARY KEY,
    configuration_id TEXT NOT NULL REFERENCES sync_configurations(id),
    date TEXT NOT NULL,
    date_label TEXT NOT NULL,
    town TEXT NOT NULL CHECK(length(trim(town)) > 0),
    nor TEXT NOT NULL DEFAULT '',
    time TEXT NOT NULL DEFAULT '',
    billing TEXT NOT NULL DEFAULT '',
    confirmation TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    wawa TEXT NOT NULL DEFAULT '',
    wewe TEXT NOT NULL DEFAULT '',
    position INTEGER NOT NULL,
    version INTEGER NOT NULL DEFAULT 1 CHECK(version > 0),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    deleted_at TEXT
);
CREATE INDEX events_calendar ON events(configuration_id, deleted_at, date, position);
CREATE TABLE sync_states (
    event_id TEXT PRIMARY KEY REFERENCES events(id),
    configuration_id TEXT NOT NULL REFERENCES sync_configurations(id),
    ordinal INTEGER NOT NULL,
    values_json TEXT NOT NULL,
    sheet_row INTEGER NOT NULL,
    document_row INTEGER NOT NULL,
    verified_at TEXT NOT NULL,
    UNIQUE(configuration_id, ordinal)
);
CREATE TABLE sync_operations (
    id TEXT PRIMARY KEY,
    configuration_id TEXT NOT NULL REFERENCES sync_configurations(id),
    status TEXT NOT NULL CHECK(status IN ('pending', 'completed', 'cancelled')),
    payload TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE UNIQUE INDEX one_pending_sync ON sync_operations(configuration_id) WHERE status = 'pending';
CREATE TABLE sync_conflicts (
    id TEXT PRIMARY KEY,
    configuration_id TEXT NOT NULL REFERENCES sync_configurations(id),
    event_id TEXT REFERENCES events(id),
    code TEXT NOT NULL,
    snapshots TEXT NOT NULL,
    created_at TEXT NOT NULL,
    resolved_at TEXT
);
CREATE UNIQUE INDEX one_open_conflict ON sync_conflicts(configuration_id) WHERE resolved_at IS NULL;
CREATE TABLE event_changes (
    id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL REFERENCES events(id),
    action TEXT NOT NULL CHECK(action IN ('created', 'updated', 'deleted')),
    origin TEXT NOT NULL CHECK(origin IN ('web', 'google', 'import', 'reconciliation')),
    before_json TEXT,
    after_json TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX event_changes_event ON event_changes(event_id, created_at);

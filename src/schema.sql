PRAGMA journal_mode = DELETE;
PRAGMA synchronous = FULL;
PRAGMA busy_timeout = 60000;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS experiments (
    experiment_id         TEXT PRIMARY KEY NOT NULL,

    -- Frozen scientific definition
    spec_hash             TEXT UNIQUE NOT NULL,
    spec_json             TEXT NOT NULL,
    hypothesis_ref        TEXT,
    code_commit           TEXT NOT NULL,

    -- Current execution state
    status                TEXT NOT NULL DEFAULT 'PENDING'
                          CHECK (status IN (
                              'PENDING', 'RUNNING', 'COMPLETED', 'CANCELLED'
                          )),
    dispatch_id           TEXT UNIQUE,
    scheduler_ref         TEXT,
    command               TEXT,
    device_info           TEXT,

    -- UTC timestamps
    created_at            TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at            TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at            TEXT,
    completed_at          TEXT,

    -- Latest operational explanations
    last_execution_issue  TEXT,
    cancellation_reason   TEXT,

    CHECK (
        status != 'RUNNING'
        OR (dispatch_id IS NOT NULL AND command IS NOT NULL)
    ),
    CHECK (
        status != 'COMPLETED'
        OR completed_at IS NOT NULL
    ),
    CHECK (
        status != 'CANCELLED'
        OR cancellation_reason IS NOT NULL
    )
);

CREATE INDEX IF NOT EXISTS idx_experiments_status
ON experiments(status);

CREATE INDEX IF NOT EXISTS idx_experiments_hypothesis
ON experiments(hypothesis_ref);

CREATE TRIGGER IF NOT EXISTS trg_experiments_updated_at
AFTER UPDATE ON experiments
FOR EACH ROW
WHEN NEW.updated_at IS OLD.updated_at
BEGIN
    UPDATE experiments
    SET updated_at = CURRENT_TIMESTAMP
    WHERE experiment_id = NEW.experiment_id
      AND updated_at IS NOT CURRENT_TIMESTAMP;
END;

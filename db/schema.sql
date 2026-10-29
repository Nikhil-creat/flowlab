CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE workflows(id TEXT PRIMARY KEY, name TEXT NOT NULL, input BYTEA,
  status TEXT NOT NULL DEFAULT 'RUNNING' CHECK(status IN('RUNNING','COMPLETED','FAILED','COMPENSATING')),
  created_at TIMESTAMPTZ DEFAULT now());
CREATE TABLE events(workflow_id TEXT REFERENCES workflows(id), seq BIGINT, type TEXT NOT NULL, step_id TEXT,
  attempt INT DEFAULT 1, payload BYTEA, idem_key TEXT UNIQUE, created_at TIMESTAMPTZ DEFAULT now(),
  PRIMARY KEY(workflow_id, seq));
CREATE TABLE steps(workflow_id TEXT REFERENCES workflows(id), step_id TEXT, status TEXT, attempts INT DEFAULT 0,
  started_at TIMESTAMPTZ, duration_ms INT, ai_insight TEXT, PRIMARY KEY(workflow_id, step_id));
CREATE TABLE activity_log(id BIGSERIAL PRIMARY KEY, workflow_id TEXT, step_id TEXT, idem_key TEXT UNIQUE,
  outcome TEXT, detail JSONB, created_at TIMESTAMPTZ DEFAULT now());
CREATE TABLE dlq(id BIGSERIAL PRIMARY KEY, workflow_id TEXT, step_id TEXT, error TEXT, created_at TIMESTAMPTZ DEFAULT now());
CREATE TABLE documents(id BIGSERIAL PRIMARY KEY, content TEXT, embedding vector(384));
CREATE INDEX ON documents USING hnsw (embedding vector_cosine_ops);
-- the event log is append-only: history can never be rewritten
CREATE FUNCTION no_mutate() RETURNS trigger AS $$ BEGIN RAISE EXCEPTION 'events are append-only'; END $$ LANGUAGE plpgsql;
CREATE TRIGGER events_immutable BEFORE UPDATE OR DELETE ON events FOR EACH ROW EXECUTE FUNCTION no_mutate();

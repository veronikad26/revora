-- Revora SQLite schema (PRD Section 11 — Data Model).
--
-- Tables to define, one per entity in app/models/:
--   failure_event, checkout_event, root_cause_classification,
--   consent_flag, retry_attempt, ptp_record, message,
--   policy_decision, outcome_event, audit_log_entry
--
-- audit_log_entry is append-only: no UPDATE/DELETE statements should
-- ever target this table.
--
-- No table definitions populated yet — skeleton only.
-- Revora Phase 1 SQLite schema. ORM metadata is the canonical mapping;
-- this SQL file is also executable for SQL-first initialization.
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS failure_event (
  id VARCHAR(64) PRIMARY KEY, payment_id VARCHAR(128) NOT NULL UNIQUE,
  gateway_code VARCHAR(64), gateway_reason VARCHAR(128), amount NUMERIC(18,2) NOT NULL,
  currency VARCHAR(3) NOT NULL DEFAULT 'INR', method VARCHAR(32) NOT NULL,
  timestamp DATETIME NOT NULL, customer_id VARCHAR(128) NOT NULL, raw_payload TEXT,
  created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_failure_event_customer_id ON failure_event(customer_id);
CREATE INDEX IF NOT EXISTS ix_failure_event_gateway_reason ON failure_event(gateway_reason);

CREATE TABLE IF NOT EXISTS checkout_event (
  id VARCHAR(64) PRIMARY KEY, cart_id VARCHAR(128) NOT NULL, customer_id VARCHAR(128) NOT NULL,
  cart_value NUMERIC(18,2) NOT NULL, currency VARCHAR(3) NOT NULL DEFAULT 'INR',
  funnel_stage_reached VARCHAR(64) NOT NULL, created_at DATETIME NOT NULL,
  last_activity_at DATETIME NOT NULL, prior_abandonment_count INTEGER NOT NULL DEFAULT 0,
  updated_at DATETIME NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_checkout_event_customer_id ON checkout_event(customer_id);

CREATE TABLE IF NOT EXISTS root_cause_classification (
  id VARCHAR(64) PRIMARY KEY, event_id VARCHAR(128) NOT NULL, event_type VARCHAR(32) NOT NULL,
  category VARCHAR(64) NOT NULL, confidence REAL NOT NULL CHECK(confidence >= 0 AND confidence <= 1),
  reason TEXT NOT NULL, created_at DATETIME NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_root_cause_classification_event_id ON root_cause_classification(event_id);
CREATE INDEX IF NOT EXISTS ix_root_cause_classification_category ON root_cause_classification(category);

CREATE TABLE IF NOT EXISTS consent_flag (
  id VARCHAR(64) PRIMARY KEY, customer_id VARCHAR(128) NOT NULL, channel VARCHAR(32) NOT NULL,
  consent BOOLEAN NOT NULL DEFAULT 0, updated_at DATETIME NOT NULL,
  UNIQUE(customer_id, channel)
);
CREATE TABLE IF NOT EXISTS retry_attempt (
  id VARCHAR(64) PRIMARY KEY, failure_event_id VARCHAR(64) NOT NULL, attempt_number INTEGER NOT NULL,
  already_attempted BOOLEAN NOT NULL DEFAULT 0, scheduled_time DATETIME, executed_time DATETIME,
  result TEXT, created_at DATETIME NOT NULL, UNIQUE(failure_event_id, attempt_number),
  FOREIGN KEY(failure_event_id) REFERENCES failure_event(id)
);
CREATE TABLE IF NOT EXISTS ptp_record (
  id VARCHAR(64) PRIMARY KEY, case_id VARCHAR(64) NOT NULL, customer_id VARCHAR(128) NOT NULL,
  invoice_payment_ref VARCHAR(128) NOT NULL, amount NUMERIC(18,2) NOT NULL, promised_date DATE,
  state VARCHAR(32) NOT NULL DEFAULT 'DETECTED', conversation_id VARCHAR(128),
  negotiation_limit_max_date DATE, dispute_flag BOOLEAN NOT NULL DEFAULT 0,
  renegotiation_count INTEGER NOT NULL DEFAULT 0, created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_ptp_record_case_id ON ptp_record(case_id);
CREATE TABLE IF NOT EXISTS message (
  id VARCHAR(64) PRIMARY KEY, case_id VARCHAR(64) NOT NULL, ptp_id VARCHAR(64),
  direction VARCHAR(8) NOT NULL CHECK(direction IN ('in','out')), channel VARCHAR(32) NOT NULL DEFAULT 'whatsapp',
  content TEXT NOT NULL, trust_firewall_result VARCHAR(16), blocked_reason TEXT, created_at DATETIME NOT NULL
);
CREATE TABLE IF NOT EXISTS policy_decision (
  id VARCHAR(64) PRIMARY KEY, case_id VARCHAR(64) NOT NULL, action_proposed VARCHAR(64) NOT NULL,
  proposing_node VARCHAR(64) NOT NULL, authorized BOOLEAN NOT NULL, reason TEXT NOT NULL, created_at DATETIME NOT NULL
);
CREATE TABLE IF NOT EXISTS outcome_event (
  id VARCHAR(64) PRIMARY KEY, case_id VARCHAR(64) NOT NULL, outcome_type VARCHAR(64) NOT NULL,
  observed_value TEXT, recovered_amount NUMERIC(18,2), created_at DATETIME NOT NULL
);
CREATE TABLE IF NOT EXISTS audit_log_entry (
  id VARCHAR(64) PRIMARY KEY, case_id VARCHAR(64) NOT NULL, entity_type VARCHAR(64) NOT NULL,
  entity_id VARCHAR(128) NOT NULL, action VARCHAR(64) NOT NULL, actor VARCHAR(32) NOT NULL,
  reason TEXT NOT NULL, customer_visible_reason TEXT, created_at DATETIME NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_audit_log_entry_case_id ON audit_log_entry(case_id);

-- Audit entries are immutable: corrections must be represented as new entries.
CREATE TRIGGER IF NOT EXISTS audit_log_entry_no_update
BEFORE UPDATE ON audit_log_entry
BEGIN
  SELECT RAISE(ABORT, 'audit_log_entry is append-only');
END;
CREATE TRIGGER IF NOT EXISTS audit_log_entry_no_delete
BEFORE DELETE ON audit_log_entry
BEGIN
  SELECT RAISE(ABORT, 'audit_log_entry is append-only');
END;

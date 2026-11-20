-- Reference PostgreSQL 16 DDL for Relationship & Impact Engine v0.
-- Codex: implement using Alembic migrations and ORM models; adjust naming for existing Threadnote DB only via documented migration.
-- All timestamps UTC (timestamptz); event and snapshot as-of constraints enforced in application tests.
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS rie_entities (
  id TEXT PRIMARY KEY,
  entity_type TEXT NOT NULL CHECK (entity_type IN ('company','product_market','driver','financial_metric','policy_or_constraint')),
  display_name TEXT NOT NULL,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS rie_entity_aliases (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  entity_id TEXT NOT NULL REFERENCES rie_entities(id),
  symbol TEXT NOT NULL, exchange TEXT,
  alias_kind TEXT NOT NULL DEFAULT 'ticker',
  effective_from DATE, effective_until DATE,
  external_id TEXT, -- CIK or other provider identifier (with issuer type)
  UNIQUE(entity_id, symbol, alias_kind, effective_from)
);
CREATE INDEX IF NOT EXISTS ix_rie_alias_symbol ON rie_entity_aliases(symbol);

CREATE TABLE IF NOT EXISTS rie_sources (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  origin TEXT NOT NULL,
  rights_status TEXT NOT NULL CHECK (rights_status IN ('approved','pending','blocked')),
  citation_url TEXT NOT NULL,
  rights_note TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS rie_documents (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source_id TEXT NOT NULL REFERENCES rie_sources(id),
  external_id TEXT,
  primary_entity_id TEXT REFERENCES rie_entities(id),
  filing_form TEXT,
  source_url TEXT NOT NULL,
  title TEXT,
  content_sha256 TEXT NOT NULL,
  published_at TIMESTAMPTZ NOT NULL,
  first_seen_at TIMESTAMPTZ NOT NULL,
  available_at TIMESTAMPTZ NOT NULL,
  retrieved_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  is_synthetic BOOLEAN NOT NULL DEFAULT false,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  UNIQUE(source_id, source_url, content_sha256)
);
CREATE INDEX IF NOT EXISTS ix_rie_docs_available ON rie_documents(available_at);
CREATE TABLE IF NOT EXISTS rie_evidence (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id UUID NOT NULL REFERENCES rie_documents(id),
  text_start INTEGER, text_end INTEGER,
  excerpt TEXT, -- only store text excerpts if source rights allow it
  quoted_claim TEXT NOT NULL,
  url TEXT NOT NULL,
  verified_by TEXT,
  verified_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS rie_relationships (
  id TEXT PRIMARY KEY,
  from_entity_id TEXT NOT NULL REFERENCES rie_entities(id),
  to_entity_id TEXT NOT NULL REFERENCES rie_entities(id),
  relation_family TEXT NOT NULL CHECK (relation_family IN ('CUSTOMER_DEMAND','SUPPLIER_COST','COMPETITOR_SUPPLY','PRODUCT_MARKET','MACRO_POLICY','FINANCIAL_TRANSMISSION')),
  mechanism TEXT NOT NULL,
  sign TEXT NOT NULL CHECK(sign IN ('positive','negative','conditional','unknown')),
  lag TEXT NOT NULL CHECK(lag IN ('immediate','short','long','variable')),
  strength NUMERIC(5,4) CHECK (strength BETWEEN 0 AND 1),
  confidence NUMERIC(5,4) NOT NULL DEFAULT 0 CHECK (confidence BETWEEN 0 AND 1),
  status TEXT NOT NULL DEFAULT 'candidate' CHECK(status IN ('candidate','verified','rejected','stale')),
  valid_from TIMESTAMPTZ, valid_until TIMESTAMPTZ,
  recorded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  verified_at TIMESTAMPTZ,
  verified_by TEXT,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  CHECK(from_entity_id <> to_entity_id),
  CHECK(status <> 'verified' OR (verified_at IS NOT NULL AND verified_by IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS ix_rie_edges_from ON rie_relationships(from_entity_id,status);
CREATE INDEX IF NOT EXISTS ix_rie_edges_to ON rie_relationships(to_entity_id,status);
CREATE TABLE IF NOT EXISTS rie_relationship_evidence (
  relationship_id TEXT NOT NULL REFERENCES rie_relationships(id),
  evidence_id UUID NOT NULL REFERENCES rie_evidence(id),
  PRIMARY KEY(relationship_id,evidence_id)
);
-- Application gate also requires at least one approved cite before candidate -> verified;
-- implement with transactional validation in service, since above CHECK cannot span tables.
CREATE TABLE IF NOT EXISTS rie_relationship_revisions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(), relationship_id TEXT NOT NULL REFERENCES rie_relationships(id),
  before JSONB, after JSONB NOT NULL, reviewer_id TEXT,
  reason TEXT NOT NULL, changed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS rie_narratives (
  id TEXT PRIMARY KEY, ticker_entity_id TEXT NOT NULL REFERENCES rie_entities(id),
  owner_user_id TEXT, -- null for published template
  is_template BOOLEAN NOT NULL DEFAULT false,
  status TEXT NOT NULL CHECK (status IN ('template_draft','draft','active','paused','archived')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK(is_template OR owner_user_id IS NOT NULL)
);
CREATE TABLE IF NOT EXISTS rie_narrative_versions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(), narrative_id TEXT NOT NULL REFERENCES rie_narratives(id),
  version_number INTEGER NOT NULL, title TEXT NOT NULL, thesis TEXT NOT NULL,
  horizon_months INTEGER NOT NULL CHECK (horizon_months BETWEEN 1 AND 60),
  config JSONB NOT NULL,
  published_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  available_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  approved_by TEXT,
  UNIQUE(narrative_id,version_number)
);
CREATE TABLE IF NOT EXISTS rie_narrative_drivers (
  narrative_version_id UUID NOT NULL REFERENCES rie_narrative_versions(id),
  driver_entity_id TEXT NOT NULL REFERENCES rie_entities(id),
  priority SMALLINT NOT NULL CHECK(priority BETWEEN 1 AND 5),
  config JSONB NOT NULL DEFAULT '{}'::jsonb,
  PRIMARY KEY(narrative_version_id,driver_entity_id)
);

CREATE TABLE IF NOT EXISTS rie_events (
  id TEXT PRIMARY KEY, canonical_event_key TEXT NOT NULL UNIQUE,
  issuer_entity_id TEXT REFERENCES rie_entities(id),
  event_type TEXT NOT NULL,
  occurred_at TIMESTAMPTZ,
  published_at TIMESTAMPTZ NOT NULL,
  first_seen_at TIMESTAMPTZ NOT NULL,
  available_at TIMESTAMPTZ NOT NULL,
  is_synthetic BOOLEAN NOT NULL DEFAULT false,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_rie_events_available ON rie_events(available_at);
CREATE TABLE IF NOT EXISTS rie_event_versions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(), event_id TEXT NOT NULL REFERENCES rie_events(id),
  version_number INTEGER NOT NULL,
  factual_headline TEXT NOT NULL, normalized_claim JSONB NOT NULL,
  metric_id TEXT REFERENCES rie_entities(id),
  extraction_model TEXT, document_id UUID REFERENCES rie_documents(id),
  evidence_quality NUMERIC(5,4) CHECK(evidence_quality BETWEEN 0 AND 1),
  available_at TIMESTAMPTZ NOT NULL,
  is_correction BOOLEAN NOT NULL DEFAULT false,
  supersedes_version_id UUID REFERENCES rie_event_versions(id),
  UNIQUE(event_id,version_number)
);
CREATE TABLE IF NOT EXISTS rie_event_evidence (
  event_version_id UUID NOT NULL REFERENCES rie_event_versions(id),
  evidence_id UUID NOT NULL REFERENCES rie_evidence(id),
  PRIMARY KEY(event_version_id,evidence_id)
);

CREATE TABLE IF NOT EXISTS rie_match_decisions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  event_version_id UUID NOT NULL REFERENCES rie_event_versions(id),
  narrative_version_id UUID NOT NULL REFERENCES rie_narrative_versions(id),
  as_of TIMESTAMPTZ NOT NULL,
  chosen_path JSONB NOT NULL DEFAULT '[]'::jsonb,
  gate_results JSONB NOT NULL DEFAULT '{}'::jsonb,
  score_components JSONB NOT NULL DEFAULT '{}'::jsonb,
  score NUMERIC(6,3) CHECK(score BETWEEN 0 AND 100),
  materiality_status TEXT NOT NULL CHECK(materiality_status IN ('KNOWN','UNKNOWN','REVIEW_REQUIRED')),
  stance TEXT NOT NULL CHECK(stance IN ('SUPPORTS','CHALLENGES','MIXED','NO_CHANGE','INSUFFICIENT_EVIDENCE')),
  decision TEXT NOT NULL CHECK(decision IN ('push','digest','storybook','suppressed','review_required')),
  explanation JSONB NOT NULL DEFAULT '{}'::jsonb,
  policy_version TEXT NOT NULL, model_version TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(event_version_id,narrative_version_id,as_of,policy_version)
);
CREATE INDEX IF NOT EXISTS ix_rie_decision_nav ON rie_match_decisions(narrative_version_id,as_of DESC);
CREATE TABLE IF NOT EXISTS rie_subscriptions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id TEXT NOT NULL,
  thread_kind TEXT NOT NULL CHECK(thread_kind IN ('stock','narrative')),
  stock_entity_id TEXT REFERENCES rie_entities(id),
  narrative_id TEXT REFERENCES rie_narratives(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  disabled_at TIMESTAMPTZ,
  preferences JSONB NOT NULL DEFAULT '{}'::jsonb,
  CHECK((thread_kind='stock' AND stock_entity_id IS NOT NULL AND narrative_id IS NULL) OR
        (thread_kind='narrative' AND narrative_id IS NOT NULL AND stock_entity_id IS NULL))
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_rie_active_stock_sub ON rie_subscriptions(user_id,stock_entity_id) WHERE disabled_at IS NULL AND thread_kind='stock';
CREATE UNIQUE INDEX IF NOT EXISTS ux_rie_active_nav_sub ON rie_subscriptions(user_id,narrative_id) WHERE disabled_at IS NULL AND thread_kind='narrative';
CREATE TABLE IF NOT EXISTS rie_alerts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id TEXT NOT NULL, canonical_event_key TEXT NOT NULL,
  event_version_id UUID NOT NULL REFERENCES rie_event_versions(id),
  primary_decision_id UUID NOT NULL REFERENCES rie_match_decisions(id),
  related_thread_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
  dispatch_kind TEXT NOT NULL CHECK(dispatch_kind IN ('push','digest','storybook')),
  delivery_status TEXT NOT NULL DEFAULT 'dry_run' CHECK(delivery_status IN ('dry_run','queued','sent','failed','cancelled')),
  sent_at TIMESTAMPTZ, provider_message_id TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(user_id,canonical_event_key,dispatch_kind,event_version_id)
);
CREATE TABLE IF NOT EXISTS rie_feedback (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(), alert_id UUID NOT NULL REFERENCES rie_alerts(id),
  user_id TEXT NOT NULL,
  label TEXT NOT NULL CHECK(label IN ('USEFUL','ALREADY_KNEW','NOT_RELEVANT','UNCLEAR','WRONG')),
  reason_code TEXT, free_text TEXT,
  active BOOLEAN NOT NULL DEFAULT true,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_rie_feedback_active ON rie_feedback(user_id,alert_id) WHERE active=true;
CREATE TABLE IF NOT EXISTS rie_story_entries (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  narrative_id TEXT NOT NULL REFERENCES rie_narratives(id),
  narrative_version_id UUID NOT NULL REFERENCES rie_narrative_versions(id),
  event_version_id UUID NOT NULL REFERENCES rie_event_versions(id),
  decision_id UUID NOT NULL REFERENCES rie_match_decisions(id),
  available_at TIMESTAMPTZ NOT NULL,
  state_delta TEXT NOT NULL,
  correction_of UUID REFERENCES rie_story_entries(id),
  is_public BOOLEAN NOT NULL DEFAULT false,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(narrative_version_id,event_version_id)
);
CREATE TABLE IF NOT EXISTS rie_metric_observations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(), entity_id TEXT NOT NULL REFERENCES rie_entities(id),
  metric_id TEXT NOT NULL, period_start DATE, period_end DATE NOT NULL,
  value NUMERIC NOT NULL, unit TEXT NOT NULL, accounting_basis TEXT,
  first_available_at TIMESTAMPTZ NOT NULL, evidence_id UUID REFERENCES rie_evidence(id),
  adjustment_metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS ix_rie_metrics_asof ON rie_metric_observations(entity_id,metric_id,first_available_at);
CREATE TABLE IF NOT EXISTS rie_review_queue (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  item_kind TEXT NOT NULL CHECK(item_kind IN ('relation','event','source','claim','policy')),
  item_id TEXT NOT NULL,
  priority INTEGER NOT NULL DEFAULT 3,
  reason TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','resolved','rejected')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(), resolved_at TIMESTAMPTZ
);
CREATE TABLE IF NOT EXISTS rie_replay_runs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  as_of TIMESTAMPTZ NOT NULL,
  dataset_version TEXT NOT NULL, policy_version TEXT NOT NULL,
  model_version TEXT, metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
  started_at TIMESTAMPTZ NOT NULL DEFAULT now(), finished_at TIMESTAMPTZ,
  status TEXT NOT NULL DEFAULT 'started', artifacts JSONB NOT NULL DEFAULT '{}'::jsonb
);

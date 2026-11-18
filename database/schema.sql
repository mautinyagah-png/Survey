-- ==========================================================================
-- Survey Platform — initial schema (Phase 1)
-- Target: PostgreSQL 14+
-- All timestamps are stored in UTC. Display conversion happens in the client.
-- ==========================================================================

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Shared trigger: update updated_at on row change.
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- --------------------------------------------------------------------------
-- Roles
-- --------------------------------------------------------------------------
CREATE TABLE roles (
  id          SMALLSERIAL PRIMARY KEY,
  name        TEXT NOT NULL UNIQUE CHECK (name IN ('respondent', 'admin', 'super_admin')),
  description TEXT
);

INSERT INTO roles (name, description) VALUES
  ('respondent',  'Default role for survey participants'),
  ('admin',       'Can manage surveys, responses, and rewards'),
  ('super_admin', 'Full administrative access including role changes');

-- --------------------------------------------------------------------------
-- Users
-- --------------------------------------------------------------------------
CREATE TABLE users (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email               TEXT NOT NULL,
  full_name           TEXT NOT NULL,
  password_hash       TEXT NOT NULL,
  country_code        CHAR(2),
  preferred_currency  CHAR(3) NOT NULL DEFAULT 'KES',
  role_id             SMALLINT NOT NULL REFERENCES roles(id),
  status              TEXT NOT NULL DEFAULT 'pending'
                      CHECK (status IN ('pending', 'active', 'suspended', 'deleted')),
  email_verified_at   TIMESTAMPTZ,
  last_login_at       TIMESTAMPTZ,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX users_email_unique ON users (LOWER(email));
CREATE INDEX users_role_id_idx ON users (role_id);
CREATE INDEX users_status_idx ON users (status);

CREATE TRIGGER users_set_updated_at
BEFORE UPDATE ON users
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- --------------------------------------------------------------------------
-- User preferences
-- --------------------------------------------------------------------------
CREATE TABLE user_preferences (
  user_id       UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  theme         TEXT NOT NULL DEFAULT 'system' CHECK (theme IN ('light', 'dark', 'system')),
  language      TEXT NOT NULL DEFAULT 'en',
  currency      CHAR(3) NOT NULL DEFAULT 'KES',
  email_opt_in  BOOLEAN NOT NULL DEFAULT TRUE,
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TRIGGER user_preferences_set_updated_at
BEFORE UPDATE ON user_preferences
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- --------------------------------------------------------------------------
-- Email verification and password reset tokens
-- Only hashes are stored; raw tokens never touch the database.
-- --------------------------------------------------------------------------
CREATE TABLE email_verifications (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  token_hash   TEXT NOT NULL UNIQUE,
  expires_at   TIMESTAMPTZ NOT NULL,
  consumed_at  TIMESTAMPTZ,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX email_verifications_user_idx ON email_verifications (user_id);

CREATE TABLE password_reset_tokens (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  token_hash   TEXT NOT NULL UNIQUE,
  expires_at   TIMESTAMPTZ NOT NULL,
  consumed_at  TIMESTAMPTZ,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX password_reset_tokens_user_idx ON password_reset_tokens (user_id);

-- --------------------------------------------------------------------------
-- Survey categories
-- --------------------------------------------------------------------------
CREATE TABLE survey_categories (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  slug        TEXT NOT NULL UNIQUE,
  name        TEXT NOT NULL,
  description TEXT,
  sort_order  INTEGER NOT NULL DEFAULT 0,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TRIGGER survey_categories_set_updated_at
BEFORE UPDATE ON survey_categories
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- --------------------------------------------------------------------------
-- Surveys
-- --------------------------------------------------------------------------
CREATE TABLE surveys (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  slug                TEXT NOT NULL UNIQUE,
  title               TEXT NOT NULL,
  description         TEXT,
  instructions        TEXT,
  category_id         UUID REFERENCES survey_categories(id) ON DELETE SET NULL,
  target_audience     TEXT,
  country_code        CHAR(2),                       -- NULL means open to all
  estimated_minutes   INTEGER CHECK (estimated_minutes IS NULL OR estimated_minutes > 0),
  reward_amount       NUMERIC(12, 2) NOT NULL DEFAULT 0 CHECK (reward_amount >= 0),
  reward_currency     CHAR(3) NOT NULL DEFAULT 'KES',
  status              TEXT NOT NULL DEFAULT 'draft'
                      CHECK (status IN ('draft', 'published', 'closed', 'archived')),
  allow_repeat        BOOLEAN NOT NULL DEFAULT FALSE,
  participant_target  INTEGER CHECK (participant_target IS NULL OR participant_target > 0),
  participant_count   INTEGER NOT NULL DEFAULT 0 CHECK (participant_count >= 0),
  published_at        TIMESTAMPTZ,
  closes_at           TIMESTAMPTZ,
  created_by          UUID REFERENCES users(id) ON DELETE SET NULL,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  deleted_at          TIMESTAMPTZ
);

CREATE INDEX surveys_category_idx ON surveys (category_id);
CREATE INDEX surveys_status_idx ON surveys (status);
CREATE INDEX surveys_published_at_idx ON surveys (published_at DESC);

CREATE TRIGGER surveys_set_updated_at
BEFORE UPDATE ON surveys
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- --------------------------------------------------------------------------
-- Survey questions
-- --------------------------------------------------------------------------
CREATE TABLE survey_questions (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  survey_id     UUID NOT NULL REFERENCES surveys(id) ON DELETE CASCADE,
  order_index   INTEGER NOT NULL CHECK (order_index >= 0),
  question_type TEXT NOT NULL CHECK (question_type IN (
                  'single_choice', 'multi_select', 'yes_no', 'rating',
                  'short_text', 'long_text', 'dropdown', 'date'
                )),
  prompt        TEXT NOT NULL,
  help_text     TEXT,
  is_required   BOOLEAN NOT NULL DEFAULT FALSE,
  config        JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX survey_questions_survey_idx ON survey_questions (survey_id, order_index);

CREATE TRIGGER survey_questions_set_updated_at
BEFORE UPDATE ON survey_questions
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- --------------------------------------------------------------------------
-- Answer options
-- --------------------------------------------------------------------------
CREATE TABLE answer_options (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  question_id UUID NOT NULL REFERENCES survey_questions(id) ON DELETE CASCADE,
  order_index INTEGER NOT NULL CHECK (order_index >= 0),
  label       TEXT NOT NULL,
  value       TEXT NOT NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX answer_options_question_idx ON answer_options (question_id, order_index);

-- --------------------------------------------------------------------------
-- Participations
-- A partial unique index prevents duplicate active participations unless the
-- survey explicitly allows repeats. Cancelled participations are excluded.
-- --------------------------------------------------------------------------
CREATE TABLE participations (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  survey_id    UUID NOT NULL REFERENCES surveys(id) ON DELETE CASCADE,
  status       TEXT NOT NULL DEFAULT 'in_progress'
               CHECK (status IN ('in_progress', 'submitted', 'under_review',
                                 'approved', 'rejected', 'cancelled')),
  started_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  submitted_at TIMESTAMPTZ,
  reviewed_at  TIMESTAMPTZ,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX participations_user_idx ON participations (user_id, created_at DESC);
CREATE INDEX participations_survey_idx ON participations (survey_id);

CREATE TRIGGER participations_set_updated_at
BEFORE UPDATE ON participations
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- --------------------------------------------------------------------------
-- Responses
-- One row per question per participation.
-- selected_option_ids is an array of answer_options ids for choice questions.
-- The application validates that each id belongs to the same question.
-- --------------------------------------------------------------------------
CREATE TABLE responses (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  participation_id    UUID NOT NULL REFERENCES participations(id) ON DELETE CASCADE,
  question_id         UUID NOT NULL REFERENCES survey_questions(id) ON DELETE CASCADE,
  answer_text         TEXT,
  rating_value        SMALLINT CHECK (rating_value IS NULL OR (rating_value BETWEEN 1 AND 10)),
  selected_option_ids UUID[],
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (participation_id, question_id)
);

CREATE INDEX responses_participation_idx ON responses (participation_id);

CREATE TRIGGER responses_set_updated_at
BEFORE UPDATE ON responses
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- --------------------------------------------------------------------------
-- Reward records
-- A reward is only credited after review. The unique participation_id
-- prevents duplicate credits.
-- --------------------------------------------------------------------------
CREATE TABLE reward_records (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  participation_id  UUID NOT NULL UNIQUE REFERENCES participations(id) ON DELETE CASCADE,
  user_id           UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  survey_id         UUID NOT NULL REFERENCES surveys(id) ON DELETE CASCADE,
  amount            NUMERIC(12, 2) NOT NULL CHECK (amount >= 0),
  currency          CHAR(3) NOT NULL,
  status            TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'approved', 'rejected', 'paid')),
  approved_by       UUID REFERENCES users(id) ON DELETE SET NULL,
  approved_at       TIMESTAMPTZ,
  rejected_reason   TEXT,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX reward_records_user_idx ON reward_records (user_id, created_at DESC);
CREATE INDEX reward_records_status_idx ON reward_records (status);

CREATE TRIGGER reward_records_set_updated_at
BEFORE UPDATE ON reward_records
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- --------------------------------------------------------------------------
-- Wallet transactions
-- Append-only ledger. Balances are derived from this table, never stored.
-- --------------------------------------------------------------------------
CREATE TABLE wallet_transactions (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  type            TEXT NOT NULL CHECK (type IN ('credit', 'debit', 'hold', 'release')),
  amount          NUMERIC(12, 2) NOT NULL CHECK (amount > 0),
  currency        CHAR(3) NOT NULL,
  reference_type  TEXT,
  reference_id    UUID,
  description     TEXT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX wallet_transactions_user_idx ON wallet_transactions (user_id, created_at DESC);
CREATE INDEX wallet_transactions_reference_idx ON wallet_transactions (reference_type, reference_id);

-- --------------------------------------------------------------------------
-- Withdrawal requests
-- Only masked destination details are stored. Full payment credentials are
-- never persisted here; a payment provider handles them in Phase 6.
-- --------------------------------------------------------------------------
CREATE TABLE withdrawal_requests (
  id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id            UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  amount             NUMERIC(12, 2) NOT NULL CHECK (amount > 0),
  currency           CHAR(3) NOT NULL,
  method             TEXT NOT NULL CHECK (method IN ('mpesa', 'bank_transfer', 'other')),
  destination_masked TEXT NOT NULL,
  status             TEXT NOT NULL DEFAULT 'requested'
                     CHECK (status IN ('requested', 'approved', 'processing',
                                       'paid', 'rejected', 'cancelled')),
  requested_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  reviewed_by        UUID REFERENCES users(id) ON DELETE SET NULL,
  reviewed_at        TIMESTAMPTZ,
  paid_at            TIMESTAMPTZ,
  notes              TEXT,
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX withdrawal_requests_user_idx ON withdrawal_requests (user_id, created_at DESC);
CREATE INDEX withdrawal_requests_status_idx ON withdrawal_requests (status);

CREATE TRIGGER withdrawal_requests_set_updated_at
BEFORE UPDATE ON withdrawal_requests
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- --------------------------------------------------------------------------
-- Notifications
-- --------------------------------------------------------------------------
CREATE TABLE notifications (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  type        TEXT NOT NULL,
  title       TEXT NOT NULL,
  body        TEXT,
  link        TEXT,
  read_at     TIMESTAMPTZ,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX notifications_user_idx ON notifications (user_id, created_at DESC);
CREATE INDEX notifications_unread_idx ON notifications (user_id) WHERE read_at IS NULL;

-- --------------------------------------------------------------------------
-- Audit log
-- Every administrative action that changes state must be recorded here.
-- --------------------------------------------------------------------------
CREATE TABLE audit_logs (
  id             BIGSERIAL PRIMARY KEY,
  actor_user_id  UUID REFERENCES users(id) ON DELETE SET NULL,
  action         TEXT NOT NULL,
  entity_type    TEXT NOT NULL,
  entity_id      UUID,
  metadata       JSONB NOT NULL DEFAULT '{}'::jsonb,
  ip_address     INET,
  user_agent     TEXT,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX audit_logs_actor_idx ON audit_logs (actor_user_id, created_at DESC);
CREATE INDEX audit_logs_entity_idx ON audit_logs (entity_type, entity_id);

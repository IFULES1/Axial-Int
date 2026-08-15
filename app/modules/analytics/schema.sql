-- ==========================================================================
-- Axial Intelligence — ANALYTICS schema (user tracking & KPIs)
-- Apply to the analytics Supabase project (or a dedicated schema in an
-- existing project). Safe to run multiple times (idempotent).
--
-- Security model: all tables live under schema `analytics` with RLS ON.
-- Writes come only from the API using the service_role key (bypasses RLS).
-- Reads are restricted to admins (auth.jwt() -> is_admin). No client ever
-- reads another user's data. No sensitive report content is stored here.
-- ==========================================================================

CREATE SCHEMA IF NOT EXISTS analytics;

-- --- 1. user_profiles : one light row per user (mirror of auth) -------------
CREATE TABLE IF NOT EXISTS analytics.user_profiles (
    user_id       uuid PRIMARY KEY,               -- same UUID as Supabase auth
    email         text,
    first_seen_at timestamptz,                     -- première connexion
    last_seen_at  timestamptz,                     -- dernière connexion
    signup_at     timestamptz,
    company_name  text,
    sector        text,
    plan          text DEFAULT 'free_beta',
    is_admin      boolean DEFAULT false,
    created_at    timestamptz NOT NULL DEFAULT now(),
    updated_at    timestamptz NOT NULL DEFAULT now()
);

-- --- 2. usage_counters : quota d'utilisation agrégé par période ------------
CREATE TABLE IF NOT EXISTS analytics.usage_counters (
    user_id           uuid NOT NULL,
    period            text NOT NULL,               -- 'YYYY-MM'
    analyses_run      integer NOT NULL DEFAULT 0,
    credits_consumed  integer NOT NULL DEFAULT 0,
    reports_generated integer NOT NULL DEFAULT 0,
    agent_messages    integer NOT NULL DEFAULT 0,
    updated_at        timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, period)
);

-- --- 3. events : journal générique extensible (base des KPI futurs) --------
CREATE TABLE IF NOT EXISTS analytics.events (
    id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id    uuid,
    event_type text NOT NULL,                      -- login, signup, analysis_started, ...
    properties jsonb NOT NULL DEFAULT '{}'::jsonb, -- nouveau KPI = nouvelle clé, zéro migration
    ts         timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_events_user_ts   ON analytics.events (user_id, ts DESC);
CREATE INDEX IF NOT EXISTS idx_events_type_ts   ON analytics.events (event_type, ts DESC);
CREATE INDEX IF NOT EXISTS idx_profiles_lastseen ON analytics.user_profiles (last_seen_at DESC);

-- --- RLS : deny by default, admin-only reads, service_role writes ----------
ALTER TABLE analytics.user_profiles  ENABLE ROW LEVEL SECURITY;
ALTER TABLE analytics.usage_counters ENABLE ROW LEVEL SECURITY;
ALTER TABLE analytics.events         ENABLE ROW LEVEL SECURITY;

-- Admin read policy (JWT claim is_admin = true). service_role bypasses RLS.
DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY['user_profiles','usage_counters','events'] LOOP
    EXECUTE format(
      'DROP POLICY IF EXISTS admin_read ON analytics.%I;', t);
    EXECUTE format(
      'CREATE POLICY admin_read ON analytics.%I FOR SELECT TO authenticated '
      'USING (COALESCE((auth.jwt() -> ''user_metadata'' ->> ''is_admin'')::boolean, false));',
      t);
  END LOOP;
END $$;

-- Forecast update e-mails to landing page subscribers (send_emails.py, same Render Cron Job).
-- Run once in the Supabase SQL editor BEFORE deploying the code that uses these columns.

-- 1. Subscription state on the existing table
ALTER TABLE public.tbl_landing_emails
  ADD COLUMN IF NOT EXISTS updates_active  boolean     NOT NULL DEFAULT true,
  ADD COLUMN IF NOT EXISTS unsubscribed_at timestamptz NULL,
  ADD COLUMN IF NOT EXISTS last_update_key text        NULL;

COMMENT ON COLUMN public.tbl_landing_emails.updates_active IS
  'False after the subscriber unsubscribes from forecast updates; a new sign-up on the page sets it back to true.';
COMMENT ON COLUMN public.tbl_landing_emails.unsubscribed_at IS
  'When the subscriber last unsubscribed from forecast updates; cleared by a new sign-up.';
COMMENT ON COLUMN public.tbl_landing_emails.last_update_key IS
  'Start (UTC, ISO) of the Moon sign period the subscriber was last sent (or first seen in); claimed before sending so nothing is sent twice.';

-- 2. One row per update e-mail attempt
CREATE TABLE IF NOT EXISTS public.tbl_landing_email_log (
  id                  bigint      NOT NULL GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  landing_email_id    bigint      NULL REFERENCES public.tbl_landing_emails(id) ON DELETE SET NULL,
  email               text        NOT NULL,          -- copied, so the log survives a deleted subscriber
  update_key          text        NOT NULL,          -- Moon sign period start (UTC, ISO)
  sent_at             timestamptz NOT NULL DEFAULT now(),
  status              text        NOT NULL CHECK (status IN ('sent', 'failed', 'dry_run')),
  moon_sign           text        NULL,              -- English sign name
  sun_sign            text        NULL,
  house               smallint    NULL,              -- 1-12, counted from the Sun sign
  forecast_group      smallint    NULL,              -- 1-2
  subject             text        NULL,
  provider_message_id text        NULL,              -- Brevo message id
  error               text        NULL
);
CREATE INDEX IF NOT EXISTS tbl_landing_email_log_sent_at_idx ON public.tbl_landing_email_log (sent_at DESC);

-- Same security as the other tables: RLS on, no access through Supabase's public API roles
ALTER TABLE public.tbl_landing_email_log ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.tbl_landing_email_log FROM anon, authenticated;

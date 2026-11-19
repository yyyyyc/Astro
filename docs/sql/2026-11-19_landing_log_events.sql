-- Log subscription changes (unsubscribe / sign-up again / admin edits) in tbl_landing_email_log, next to the sends.
-- Run once in the Supabase SQL editor. The code works before it is run; only these log rows fail (logged as errors).

-- 1. New statuses
ALTER TABLE public.tbl_landing_email_log DROP CONSTRAINT IF EXISTS tbl_landing_email_log_status_check;
ALTER TABLE public.tbl_landing_email_log ADD CONSTRAINT tbl_landing_email_log_status_check
  CHECK (status IN ('sent', 'failed', 'dry_run', 'unsubscribed', 'resubscribed', 'admin_edit'));

-- 2. A subscription change belongs to no Moon sign period
ALTER TABLE public.tbl_landing_email_log ALTER COLUMN update_key DROP NOT NULL;

-- 3. Where it came from
ALTER TABLE public.tbl_landing_email_log ADD COLUMN IF NOT EXISTS note text NULL;
COMMENT ON COLUMN public.tbl_landing_email_log.note IS
  'For subscription changes: link | one-click | sign-up | admin, plus what the admin changed. NULL for e-mails.';

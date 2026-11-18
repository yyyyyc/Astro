-- Adds the visitor's Sun sign to landing page e-mails, so update e-mails can carry each subscriber's
-- own Moon of Transit forecast. Only the sign is stored, never the date of birth.
-- Run once in the Supabase SQL editor BEFORE deploying the code that writes this column.

ALTER TABLE public.tbl_landing_emails
  ADD COLUMN IF NOT EXISTS sun_sign text NULL
  CHECK (sun_sign IN ('Aries', 'Taurus', 'Gemini', 'Cancer', 'Leo', 'Virgo',
                      'Libra', 'Scorpio', 'Sagittarius', 'Capricorn', 'Aquarius', 'Pisces'));

COMMENT ON COLUMN public.tbl_landing_emails.sun_sign IS
  'Sun sign (English name) from the date of birth entered at sign-up; the date itself is not stored. NULL for rows saved before this column existed.';

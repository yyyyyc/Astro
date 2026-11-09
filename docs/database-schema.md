-- Security: every table below has row level security on, and anon/authenticated have no access.
-- The app reaches them through its own database role (ASTRO_DB_URL), not the Supabase API.

public.tbl_signs
  id        bigint       NOT NULL PRIMARY KEY
  sign_id   smallint     NOT NULL UNIQUE CHECK (sign_id BETWEEN 1 AND 12)
  sign_name varchar      NOT NULL

public.tbl_secondary_progression_forecasts
  id          bigint     NOT NULL PRIMARY KEY
  sign_id     smallint   NULL CHECK (sign_id BETWEEN 1 AND 12)
  degree      smallint   NULL CHECK (degree BETWEEN 0 AND 29)
  forecast_id integer    NULL

public.tbl_secondary_progression_forecasts_texts
  forecast_id   integer  NOT NULL PRIMARY KEY
  forecast_text text     NULL

public.tbl_tertiary1_forecasts
  id          bigint     NOT NULL PRIMARY KEY
  sign_id     smallint   NOT NULL CHECK (sign_id BETWEEN 1 AND 12)
  degree      smallint   NOT NULL CHECK (degree BETWEEN 0 AND 29)
  forecast_id integer    NOT NULL

public.tbl_tertiary1_forecasts_texts
  forecast_id   integer  NOT NULL PRIMARY KEY
  forecast_text text     NOT NULL

public.tbl_tertiary2_forecasts
  id          bigint     NOT NULL PRIMARY KEY
  sign_id     smallint   NOT NULL CHECK (sign_id BETWEEN 1 AND 12)
  tertiary    smallint   NOT NULL CHECK (tertiary BETWEEN 1 AND 3)
  degree      smallint   NOT NULL CHECK (degree BETWEEN 0 AND 29)
  forecast_id integer    NOT NULL

public.tbl_tertiary2_forecasts_texts
  forecast_id   integer  NOT NULL PRIMARY KEY
  forecast_text text     NOT NULL

public.tbl_moon_of_transit_daily_forecasts
  id             bigint  NOT NULL PRIMARY KEY
  moon_location  integer NOT NULL CHECK (moon_location BETWEEN 1 AND 12)
  forecast_group integer NOT NULL CHECK (forecast_group BETWEEN 1 AND 10)
  forecast_id    integer NOT NULL UNIQUE

public.tbl_moon_of_transit_daily_forecasts_texts
  forecast_id   integer  NOT NULL PRIMARY KEY
  forecast_text text     NULL

public.tbl_landing_emails
  -- E-mail addresses entered on the landing page (/lp/moon). One row per address, lower case.
  id         bigint      NOT NULL PRIMARY KEY GENERATED ALWAYS AS IDENTITY
  email      text        NOT NULL UNIQUE CHECK (char_length(email) <= 254 AND email = lower(email))
  created_at timestamptz NOT NULL DEFAULT now()
  marketing_consent boolean NOT NULL DEFAULT false  -- True once the visitor ticks the consent checkbox; send marketing only to these

public.tbl_test_recipients
  -- Test recipients of the scheduled Moon of Transit e-mails (send_emails.py, Render Cron Job every 5 minutes).
  -- Managed on /admin/recipients. A recipient is due when a run time on a run day (in its timezone) has passed
  -- within the last hour and last_run is earlier than that moment.
  id                bigint      NOT NULL PRIMARY KEY GENERATED ALWAYS AS IDENTITY
  email             text        NOT NULL UNIQUE CHECK (char_length(email) <= 254 AND email = lower(email))
  first_name        text        NULL
  last_name         text        NULL
  dob               date        NOT NULL                          -- gives the Sun sign
  birth_time        time        NOT NULL DEFAULT '12:00'          -- local time at the birth place; not used by the e-mails yet
  birth_place       text        NULL                              -- place name chosen from the /geocode list
  birth_lat         double precision NULL CHECK (birth_lat BETWEEN -90 AND 90)
  birth_lon         double precision NULL CHECK (birth_lon BETWEEN -180 AND 180)
                                                                  -- place, lat and lon are all set or all NULL
  timezone          text        NOT NULL DEFAULT 'Asia/Jerusalem' -- IANA name; run_times are local to it
  run_times         time[]      NOT NULL CHECK (cardinality(run_times) > 0)   -- e.g. {08:00,20:00}
  run_days          smallint[]  NOT NULL CHECK (cardinality(run_days) > 0 AND run_days <@ {1..7})  -- ISO 1=Mon ... 7=Sun
  last_run          timestamptz NULL                              -- set when a scheduled slot is claimed, before sending
  forecast_type     text        NOT NULL DEFAULT 'moon_transit' CHECK (forecast_type IN ('moon_transit'))  -- ignored for now
  language          text        NOT NULL DEFAULT 'he'             -- he | en: wording around the (Hebrew) forecast text
  marketing_consent boolean     NOT NULL DEFAULT false            -- stored; does not affect sending yet
  active            boolean     NOT NULL DEFAULT true             -- only active recipients are sent to
  created_at        timestamptz NOT NULL DEFAULT now()

public.tbl_test_email_log
  -- One row per send attempt to a test recipient (scheduled, or the admin page's Send button).
  id                  bigint      NOT NULL PRIMARY KEY GENERATED ALWAYS AS IDENTITY
  recipient_id        bigint      NULL REFERENCES tbl_test_recipients(id) ON DELETE SET NULL
  email               text        NOT NULL                        -- copied, so the log survives a deleted recipient
  trigger             text        NOT NULL CHECK (trigger IN ('schedule', 'manual'))
  scheduled_for       timestamptz NULL                            -- the slot that was due; NULL for manual
  sent_at             timestamptz NOT NULL DEFAULT now()          -- indexed (DESC)
  status              text        NOT NULL CHECK (status IN ('sent', 'failed', 'dry_run'))
  forecast_type       text        NOT NULL
  moon_sign           text        NULL                            -- English sign name
  house               smallint    NULL                            -- 1-12, counted from the Sun sign
  forecast_group      smallint    NULL                            -- 1-2
  subject             text        NULL
  provider_message_id text        NULL                            -- Brevo message id
  error               text        NULL

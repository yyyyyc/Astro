"""Scheduled Moon of Transit e-mails.

Render Cron Job entry point: run every 5 minutes (schedule "*/5 * * * *") with the command
    python send_emails.py

Each run does two independent jobs:

1. Test e-mails: reads the active rows of tbl_test_recipients, sends the current Moon of Transit
   forecast to every recipient whose scheduled time has arrived, sets last_run and writes one row per
   attempt to tbl_test_email_log. forecast_type is ignored for now: every recipient gets Moon of Transit.

2. Landing page updates: once per Moon sign, between 08:00 and 21:00 Israel time, sends each active
   subscriber in tbl_landing_emails (with a known sun_sign) their own forecast for the new Moon sign,
   with an unsubscribe link. last_update_key is claimed before sending; one row per attempt goes to
   tbl_landing_email_log. A subscriber seen for the first time is only marked (no e-mail), so the first
   update comes with the next Moon sign. Controlled by LANDING_UPDATES (default off).

The welcome e-mail sent right after sign-up (send_welcome) is also defined here, but the web service
sends it, in a background thread, when LANDING_WELCOME (on the web service) is dry_run or on.

Environment:
    ASTRO_DB_URL        database connection (same as the web service)
    BREVO_API_KEY       Brevo API key used to send the e-mails (Settings > SMTP & API > API Keys)
    EMAIL_FROM          sender e-mail address; must be a verified sender in Brevo
    EMAIL_FROM_NAME     sender name shown to recipients (default "Astro Forecast")
    EMAIL_DRY_RUN       "1" = do everything except the actual send; log status "dry_run" (both jobs)
    LANDING_UPDATES     off (default) | dry_run | on — the landing page update job
    UNSUBSCRIBE_SECRET  signs unsubscribe links; required for LANDING_UPDATES=on (same value on the web service)
    SITE_URL            public site address used in e-mail links (default https://tertiary-progression.onrender.com)

Options:
    --dry-run        same as EMAIL_DRY_RUN=1 for this run
    --check          only print who is due right now; nothing is sent, claimed or logged
"""
import argparse
import html
import os
import sys
from collections import namedtuple
from datetime import datetime, timedelta

import pytz
import requests
from sqlalchemy import text

import app as astro

# A scheduled time is sent only up to this long after it passed, so an outage never sends stale forecasts.
MAX_LATENESS = timedelta(hours=1)
BREVO_URL = "https://api.brevo.com/v3/smtp/email"
DEFAULT_FROM_NAME = "Astro Forecast"
DATE_FMT = "%d/%m %H:%M"

TEXTS = {
    "he": {
        "dir": "rtl",
        "subject": "תחזית הירח שלך: הירח במזל {moon}",
        "greeting": "שלום {name},",
        "greeting_anon": "שלום,",
        "intro": "הירח נמצא כעת במזל <b>{moon}</b>, בבית ה-{house} ממזל השמש שלך ({sun}), מ-{start} עד {end}.",
        "footer": "קיבלת מייל זה במסגרת בדיקה של שירות התחזיות.",
        "signs": astro.ZODIAC_SIGNS_HE,
    },
    "en": {
        "dir": "ltr",
        "subject": "Your Moon forecast: the Moon is in {moon}",
        "greeting": "Hello {name},",
        "greeting_anon": "Hello,",
        "intro": "The Moon is now in <b>{moon}</b>, your house {house} counted from your Sun sign ({sun}), "
                 "from {start} to {end}.",
        "footer": "You received this e-mail as part of a test of the forecast service.",
        "signs": {s: s for s in astro.ZODIAC_SIGNS},
    },
}

RECIPIENT_COLUMNS = """id, email, first_name, last_name, dob, timezone, run_times, run_days, last_run,
                       forecast_type, language, marketing_consent, active"""


def env_dry_run():
    return os.environ.get("EMAIL_DRY_RUN", "").strip().lower() in ("1", "true", "yes")


def latest_due_slot(run_times, run_days, tz_name, last_run, now_utc):
    """The latest scheduled moment (UTC) that has passed within MAX_LATENESS and was not yet covered by
    last_run, or None. run_times are local times in tz_name; run_days are ISO weekdays (1=Mon ... 7=Sun).
    Yesterday is checked too, so a 23:58 slot still sends when the run comes just after midnight."""
    tz = pytz.timezone(tz_name)
    today = now_utc.astimezone(tz).date()
    best = None
    for day in (today, today - timedelta(days=1)):
        if day.isoweekday() not in run_days:
            continue
        for t in run_times:
            slot = astro.localize(tz, datetime.combine(day, t)).astimezone(pytz.utc)
            if slot <= now_utc and now_utc - slot <= MAX_LATENESS and (best is None or slot > best):
                best = slot
    if best is None or (last_run is not None and last_run >= best):
        return None
    return best


def build_email(recipient, now_utc):
    """Subject, HTML and plain text of the Moon of Transit e-mail, plus the values that go to the log."""
    t = TEXTS.get(recipient.language, TEXTS["he"])
    tz = pytz.timezone(recipient.timezone)
    moon = astro.moon_transit_for_dob(recipient.dob, now_utc)
    period = moon["period"]
    forecast_text = astro.fetch_moon_transit_forecast(moon["house"], moon["group"])
    if not forecast_text:
        raise RuntimeError(f"No forecast text for house {moon['house']} group {moon['group']}")

    values = {
        "moon": t["signs"][period["sign"]],
        "sun": t["signs"][moon["sun_sign"]],
        "house": moon["house"],
        "start": period["start"].astimezone(tz).strftime(DATE_FMT),
        "end": period["end"].astimezone(tz).strftime(DATE_FMT),
    }
    subject = t["subject"].format(**values)
    name = (recipient.first_name or "").strip()
    greeting = t["greeting"].format(name=name) if name else t["greeting_anon"]
    intro = t["intro"].format(**{k: html.escape(str(v)) for k, v in values.items()})
    body_html = html.escape(forecast_text).replace("\n", "<br>")

    html_doc = f"""<!doctype html>
<html dir="{t['dir']}"><body style="font-family:Arial,sans-serif;line-height:1.6;color:#222;max-width:600px;margin:auto">
  <p>{html.escape(greeting)}</p>
  <p>{intro}</p>
  <div style="padding:12px 16px;background:#f4f2fb;border-radius:8px">{body_html}</div>
  <p style="color:#888;font-size:12px">{html.escape(t['footer'])}</p>
</body></html>"""
    plain = "\n\n".join([greeting, intro.replace("<b>", "").replace("</b>", ""), forecast_text, t["footer"]])
    log = {"moon_sign": period["sign"], "house": moon["house"], "forecast_group": moon["group"]}
    return subject, html_doc, plain, log


def send_via_brevo(to, subject, html_doc, plain, headers=None):
    """Send one e-mail through Brevo's transactional API; returns the provider's message id.
    headers: extra e-mail headers (e.g. List-Unsubscribe). Raises RuntimeError on failure."""
    api_key = os.environ.get("BREVO_API_KEY", "").strip()
    sender = os.environ.get("EMAIL_FROM", "").strip()
    if not api_key or not sender:
        raise RuntimeError("BREVO_API_KEY or EMAIL_FROM is not set")
    payload = {
        "sender": {"email": sender, "name": os.environ.get("EMAIL_FROM_NAME", "").strip() or DEFAULT_FROM_NAME},
        "to": [{"email": to}],
        "subject": subject,
        "htmlContent": html_doc,
        "textContent": plain,
    }
    if headers:
        payload["headers"] = headers
    resp = requests.post(
        BREVO_URL,
        headers={"api-key": api_key, "accept": "application/json"},
        json=payload,
        timeout=20,
    )
    if resp.status_code >= 300:
        raise RuntimeError(f"Brevo {resp.status_code}: {resp.text[:300]}")
    return resp.json().get("messageId")


def deliver(engine, recipient, trigger, scheduled_for, dry_run, now_utc=None):
    """Build and send the e-mail to one recipient and log the attempt. Returns the logged status."""
    now_utc = now_utc or datetime.now(pytz.utc)
    log = {"moon_sign": None, "house": None, "forecast_group": None}
    subject = message_id = error = None
    try:
        subject, html_doc, plain, log = build_email(recipient, now_utc)
        if dry_run:
            status = "dry_run"
        else:
            message_id = send_via_brevo(recipient.email, subject, html_doc, plain)
            status = "sent"
    except Exception as exc:
        status, error = "failed", f"{type(exc).__name__}: {exc}"[:1000]

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO tbl_test_email_log
                    (recipient_id, email, trigger, scheduled_for, status, forecast_type,
                     moon_sign, house, forecast_group, subject, provider_message_id, error)
                VALUES (:rid, :email, :trigger, :scheduled_for, :status, :forecast_type,
                        :moon_sign, :house, :forecast_group, :subject, :message_id, :error)
                """
            ),
            {
                "rid": recipient.id, "email": recipient.email, "trigger": trigger,
                "scheduled_for": scheduled_for, "status": status, "forecast_type": "moon_transit",
                "subject": subject, "message_id": message_id, "error": error, **log,
            },
        )
    return status


def fetch_recipients(engine, recipient_id=None):
    sql = f"SELECT {RECIPIENT_COLUMNS} FROM tbl_test_recipients WHERE "
    sql += "id = :id" if recipient_id is not None else "active ORDER BY id"
    with engine.connect() as conn:
        return conn.execute(text(sql), {"id": recipient_id}).fetchall()


def claim(engine, recipient_id, slot, now_utc):
    """Set last_run before sending, only if no other run did so for this slot. Returns True if claimed,
    so a crash after the send can never cause the same slot to be sent twice."""
    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                UPDATE tbl_test_recipients SET last_run = :now
                WHERE id = :id AND active AND (last_run IS NULL OR last_run < :slot)
                RETURNING id
                """
            ),
            {"now": now_utc, "id": recipient_id, "slot": slot},
        ).fetchone()
    return row is not None


def run(dry_run=False, check_only=False):
    engine = astro.get_engine()
    if engine is None:
        print("ASTRO_DB_URL is not set", file=sys.stderr)
        return 2
    now_utc = datetime.now(pytz.utc)
    counts = {"due": 0, "sent": 0, "dry_run": 0, "failed": 0}
    for r in fetch_recipients(engine):
        try:
            slot = latest_due_slot(r.run_times, r.run_days, r.timezone, r.last_run, now_utc)
        except pytz.UnknownTimeZoneError:
            print(f"recipient {r.id}: unknown timezone {r.timezone!r}, skipped", file=sys.stderr)
            counts["failed"] += 1
            continue
        if slot is None:
            continue
        counts["due"] += 1
        if check_only:
            print(f"due: recipient {r.id} <{r.email}> slot {slot.isoformat()}")
            continue
        if not claim(engine, r.id, slot, now_utc):
            continue
        status = deliver(engine, r, "schedule", slot, dry_run, now_utc)
        counts[status] += 1
        print(f"recipient {r.id}: {status}")
    print(f"{now_utc:%Y-%m-%d %H:%M} UTC - " + ", ".join(f"{k} {v}" for k, v in counts.items()))
    return 1 if counts["failed"] else 0


# ── 2. Landing page forecast updates ─────────────────────────────────────────
UPDATES_TZ = pytz.timezone("Asia/Jerusalem")
UPDATES_WINDOW = (8, 21)  # send only from 08:00 until 21:00 local time; a night change waits for the morning
# The Moon's period start is found to within about a second, so two runs can compute slightly different
# values for the same period. A stored start within this tolerance is the same Moon sign.
SAME_PERIOD_TOLERANCE = timedelta(hours=1)

UPDATE_TEXTS = {
    "subject": "הירח עבר למזל {moon} – התחזית שלכם, בני מזל {sun}",
    "intro": "הירח נכנס עכשיו למזל <b>{moon}</b>, לבית ה-{house} ממזל השמש שלכם ({sun}), עד {end}.",
    "cta": "לתחזית באתר",
    "footer": "קיבלתם מייל זה כי ביקשתם לקבל עדכון כשתחזית הירח משתנה.",
    "unsubscribe": "להפסקת העדכונים",
}


def updates_mode():
    mode = os.environ.get("LANDING_UPDATES", "").strip().lower()
    return mode if mode in ("off", "dry_run", "on") else "off"


def update_key(period):
    """Stored in last_update_key: the start of the Moon sign period, in UTC, to the minute."""
    return astro.moon_update_key(period)


def is_same_period(stored_key, period):
    if not stored_key:
        return False
    try:
        stored = pytz.utc.localize(datetime.strptime(stored_key, astro.UPDATE_KEY_FMT))
    except ValueError:
        return False
    return abs(stored - period["start"].astimezone(pytz.utc)) <= SAME_PERIOD_TOLERANCE


def in_send_window(now_utc):
    local = now_utc.astimezone(UPDATES_TZ)
    return UPDATES_WINDOW[0] <= local.hour < UPDATES_WINDOW[1]


WELCOME_TEXTS = {
    "subject": "נרשמתם לעדכוני תחזית הירח – התחזית שלכם עכשיו, בני מזל {sun}",
    "intro": "תודה שנרשמתם! מעכשיו נשלח לכם את התחזית בכל פעם שהירח עובר למזל חדש (בערך כל יומיים וחצי). "
             "כרגע הירח במזל <b>{moon}</b>, בבית ה-{house} ממזל השמש שלכם ({sun}), עד {end}. זו התחזית שלכם:",
    "cta": "לתחזית באתר",
    "footer": "קיבלתם מייל זה כי נרשמתם באתר לעדכון כשתחזית הירח משתנה.",
    "unsubscribe": "להפסקת העדכונים",
}

Subscriber = namedtuple("Subscriber", "id email sun_sign")


def build_welcome_email(subscriber, now_utc):
    return build_update_email(subscriber, now_utc, WELCOME_TEXTS)


def send_welcome(landing_email_id, email, sun_sign, dry_run=False, now_utc=None):
    """Welcome e-mail right after sign-up (called by the web service in a background thread):
    the current forecast and an unsubscribe link. Logged to tbl_landing_email_log. Returns the status."""
    engine = astro.get_engine()
    if engine is None:
        raise RuntimeError("ASTRO_DB_URL is not set")
    now_utc = now_utc or datetime.now(pytz.utc)
    key = update_key(astro.moon_period_at(now_utc))
    return deliver_update(engine, Subscriber(landing_email_id, email, sun_sign), key,
                          dry_run or env_dry_run(), now_utc, build=build_welcome_email)


def build_update_email(subscriber, now_utc, texts=None):
    """Subject, HTML, plain text and List-Unsubscribe headers of one subscriber's update (or, with
    WELCOME_TEXTS, the welcome e-mail), plus log values."""
    t = texts or UPDATE_TEXTS
    signs = astro.ZODIAC_SIGNS_HE
    moon = astro.moon_transit_for_sun_sign(subscriber.sun_sign, now_utc)
    period = moon["period"]
    forecast_text = astro.fetch_moon_transit_forecast(moon["house"], moon["group"])
    if not forecast_text:
        raise RuntimeError(f"No forecast text for house {moon['house']} group {moon['group']}")
    unsub = astro.unsubscribe_url(subscriber.id)
    if unsub is None:
        raise RuntimeError("UNSUBSCRIBE_SECRET is not set")
    site = astro.visit_url(subscriber.id)  # opens the page with this subscriber's forecast on any device

    values = {
        "moon": signs[period["sign"]],
        "sun": signs[subscriber.sun_sign],
        "house": moon["house"],
        "end": period["end"].astimezone(UPDATES_TZ).strftime(DATE_FMT),
    }
    subject = t["subject"].format(**values)
    intro = t["intro"].format(**{k: html.escape(str(v)) for k, v in values.items()})
    body_html = html.escape(forecast_text).replace("\n", "<br>")
    html_doc = f"""<!doctype html>
<html dir="rtl"><body style="font-family:Arial,sans-serif;line-height:1.6;color:#222;max-width:600px;margin:auto">
  <p>{intro}</p>
  <div style="padding:12px 16px;background:#f4f2fb;border-radius:8px">{body_html}</div>
  <p><a href="{html.escape(site)}">{html.escape(t['cta'])}</a></p>
  <p style="color:#888;font-size:12px">{html.escape(t['footer'])}
    <a href="{html.escape(unsub)}" style="color:#888">{html.escape(t['unsubscribe'])}</a></p>
</body></html>"""
    plain = "\n\n".join([
        intro.replace("<b>", "").replace("</b>", ""), forecast_text,
        f"{t['cta']}: {site}", t["footer"], f"{t['unsubscribe']}: {unsub}",
    ])
    headers = {"List-Unsubscribe": f"<{unsub}>", "List-Unsubscribe-Post": "List-Unsubscribe=One-Click"}
    log = {"moon_sign": period["sign"], "house": moon["house"], "forecast_group": moon["group"]}
    return subject, html_doc, plain, headers, log


def deliver_update(engine, subscriber, key, dry_run, now_utc, build=build_update_email):
    """Build and send one update (or welcome) and log the attempt. Returns the logged status."""
    log = {"moon_sign": None, "house": None, "forecast_group": None}
    subject = message_id = error = None
    try:
        subject, html_doc, plain, headers, log = build(subscriber, now_utc)
        if dry_run:
            status = "dry_run"
        else:
            message_id = send_via_brevo(subscriber.email, subject, html_doc, plain, headers)
            status = "sent"
    except Exception as exc:
        status, error = "failed", f"{type(exc).__name__}: {exc}"[:1000]

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO tbl_landing_email_log
                    (landing_email_id, email, update_key, status, moon_sign, sun_sign, house, forecast_group,
                     subject, provider_message_id, error)
                VALUES (:lid, :email, :key, :status, :moon_sign, :sun_sign, :house, :forecast_group,
                        :subject, :message_id, :error)
                """
            ),
            {
                "lid": subscriber.id, "email": subscriber.email, "key": key, "status": status,
                "sun_sign": subscriber.sun_sign, "subject": subject, "message_id": message_id,
                "error": error, **log,
            },
        )
    return status


def claim_update(engine, subscriber_id, old_key, new_key):
    """Move last_update_key from old_key to new_key, only if no other run changed it first. Returns True
    if claimed, so a crash after the send can never cause the same Moon sign to be sent twice."""
    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                UPDATE tbl_landing_emails SET last_update_key = :new
                WHERE id = :id AND updates_active AND last_update_key IS NOT DISTINCT FROM :old
                RETURNING id
                """
            ),
            {"id": subscriber_id, "old": old_key, "new": new_key},
        ).fetchone()
    return row is not None


def run_updates(dry_run=False, check_only=False, now_utc=None):
    mode = updates_mode()
    if mode == "off" and not check_only:
        print("landing updates: off (LANDING_UPDATES)")
        return 0
    dry_run = dry_run or mode == "dry_run"
    engine = astro.get_engine()
    if engine is None:
        print("ASTRO_DB_URL is not set", file=sys.stderr)
        return 2
    now_utc = now_utc or datetime.now(pytz.utc)
    if not in_send_window(now_utc):
        print(f"landing updates: outside {UPDATES_WINDOW[0]:02d}:00-{UPDATES_WINDOW[1]:02d}:00 Israel time")
        return 0
    if not dry_run and not check_only and astro.unsubscribe_token(0) is None:
        print("landing updates: UNSUBSCRIBE_SECRET is not set; nothing sent", file=sys.stderr)
        return 1

    period = astro.moon_period_at(now_utc)
    key = update_key(period)
    with engine.connect() as conn:
        subscribers = conn.execute(
            text(
                """
                SELECT id, email, sun_sign, last_update_key FROM tbl_landing_emails
                WHERE updates_active AND sun_sign IS NOT NULL ORDER BY id
                """
            )
        ).fetchall()

    counts = {"due": 0, "new": 0, "sent": 0, "dry_run": 0, "failed": 0}
    for s in subscribers:
        if is_same_period(s.last_update_key, period):
            continue
        if s.last_update_key is None:
            # First time seen: they just saw the current forecast on the page; start from the next sign
            counts["new"] += 1
            if not check_only:
                claim_update(engine, s.id, None, key)
            continue
        counts["due"] += 1
        if check_only:
            print(f"update due: subscriber {s.id} <{s.email}> {s.sun_sign}, Moon in {period['sign']}")
            continue
        if not claim_update(engine, s.id, s.last_update_key, key):
            continue
        status = deliver_update(engine, s, key, dry_run, now_utc)
        counts[status] += 1
    print(f"landing updates ({'dry run' if dry_run else mode}), Moon in {period['sign']} since {key} - "
          + ", ".join(f"{k} {v}" for k, v in counts.items()))
    return 1 if counts["failed"] else 0


def main():
    parser = argparse.ArgumentParser(description="Send scheduled Moon of Transit e-mails.")
    parser.add_argument("--dry-run", action="store_true", help="do everything except the actual send")
    parser.add_argument("--check", action="store_true", help="only list who is due; change nothing")
    args = parser.parse_args()
    dry_run = args.dry_run or env_dry_run()
    results = [run(dry_run=dry_run, check_only=args.check)]
    try:
        results.append(run_updates(dry_run=dry_run, check_only=args.check))
    except Exception as exc:  # the update job must never stop the test job's result from being reported
        print(f"landing updates failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        results.append(1)
    return max(results)


if __name__ == "__main__":
    sys.exit(main())

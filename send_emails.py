"""Scheduled Moon of Transit e-mails (test phase).

Render Cron Job entry point: run every 5 minutes (schedule "*/5 * * * *") with the command
    python send_emails.py

Each run reads the active rows of tbl_test_recipients, sends the current Moon of Transit forecast to
every recipient whose scheduled time has arrived, sets last_run and writes one row per attempt to
tbl_test_email_log. forecast_type is ignored for now: every recipient gets Moon of Transit.

Environment:
    ASTRO_DB_URL     database connection (same as the web service)
    BREVO_API_KEY    Brevo API key used to send the e-mails (Settings > SMTP & API > API Keys)
    EMAIL_FROM       sender e-mail address; must be a verified sender in Brevo
    EMAIL_FROM_NAME  sender name shown to recipients (default "Astro Forecast")
    EMAIL_DRY_RUN    "1" = do everything except the actual send; log status "dry_run"

Options:
    --dry-run        same as EMAIL_DRY_RUN=1 for this run
    --check          only print who is due right now; nothing is sent, claimed or logged
"""
import argparse
import html
import os
import sys
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


def send_via_brevo(to, subject, html_doc, plain):
    """Send one e-mail through Brevo's transactional API; returns the provider's message id.
    Raises RuntimeError on failure."""
    api_key = os.environ.get("BREVO_API_KEY", "").strip()
    sender = os.environ.get("EMAIL_FROM", "").strip()
    if not api_key or not sender:
        raise RuntimeError("BREVO_API_KEY or EMAIL_FROM is not set")
    resp = requests.post(
        BREVO_URL,
        headers={"api-key": api_key, "accept": "application/json"},
        json={
            "sender": {"email": sender, "name": os.environ.get("EMAIL_FROM_NAME", "").strip() or DEFAULT_FROM_NAME},
            "to": [{"email": to}],
            "subject": subject,
            "htmlContent": html_doc,
            "textContent": plain,
        },
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


def main():
    parser = argparse.ArgumentParser(description="Send scheduled Moon of Transit e-mails.")
    parser.add_argument("--dry-run", action="store_true", help="do everything except the actual send")
    parser.add_argument("--check", action="store_true", help="only list who is due; change nothing")
    args = parser.parse_args()
    return run(dry_run=args.dry_run or env_dry_run(), check_only=args.check)


if __name__ == "__main__":
    sys.exit(main())

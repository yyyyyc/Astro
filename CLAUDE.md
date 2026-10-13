# Tertiary Progression Project

## Project overview

This is a Python Flask application that calculates astrological
tertiary progressions.

The application uses Supabase PostgreSQL as its database.

## Database

The database schema and business meaning of the tables are documented in:

`docs/database-schema.md`

Before modifying:

- SQL queries
- Supabase access code
- database models
- forecast selection logic
- inserts or updates

read `docs/database-schema.md`.

## Database rules

- Supabase uses PostgreSQL syntax.
- The primary database schema is `public`.
- Do not invent table or column names.
- Verify every table and column against `docs/database-schema.md`.
- Use parameterized queries.
- Do not expose the Supabase service role key in source code.
- Environment variables must be used for credentials.
- Do not change the database structure unless explicitly requested.

## Main application files

- `app.py` — Flask application and calculation logic
- `templates/index.html` — main UI
- `docs/database-schema.md` — Supabase database documentation

## Versioning

The main page shows the version and release date-time from `version.json`.

- Before every `git push`, run `python bump_version.py` (patch bump; `minor`/`major` for larger releases)
  and commit `version.json` together with the changes being pushed.
- Never push without bumping the version.

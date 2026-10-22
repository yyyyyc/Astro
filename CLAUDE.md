# Tertiary Progression Project

## Project overview

This is a Python Flask application that calculates astrological
tertiary progressions, secondary progression and the Moon of Transit.

The application uses Supabase PostgreSQL as its database.

The website's business logic (purpose, user workflows, inputs, calculation methods,
forecast mapping, database use, business rules, open questions) is documented in:

`docs/PROJECT_LOGIC.md`

- Read it before changing calculation, forecast, or validation logic.
- Update it whenever that logic, a feature, a route, or a business rule changes.
- It is written in English AND Hebrew (one file, two sections). Any change must be
  made in both languages.
- Mark each item as implemented (✅), not implemented (❌), or needing clarification (❓),
  based on the actual code, not on assumptions.
- When a ❓ item is answered, update the document and remove it from the open list.

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
- `templates/index.html` — main UI (Tertiary I and II)
- `templates/moon_transit.html` — Moon of Transit page
- `templates/secondary_progression.html` — Secondary Progression page
- `docs/database-schema.md` — Supabase database documentation
- `docs/PROJECT_LOGIC.md` — business logic documentation (English + Hebrew)

## Versioning

The main page shows the version and release date-time from `version.json`.

- Before every `git push`, run `python bump_version.py` (patch bump; `minor`/`major` for larger releases)
  and commit `version.json` together with the changes being pushed.
- Never push without bumping the version.

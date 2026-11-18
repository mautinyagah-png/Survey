# Survey Platform

A modern, professional survey platform. Built in phases so every feature is real, tested, and secure.

## Status

- **Phase 1 — Foundation** (this commit): folder structure, design system, minimal homepage, backend skeleton, initial database schema, configuration, documentation.
- Phase 2 — Visual frontend (auth pages, full homepage sections, dashboards).
- Phase 3 — Backend & database (models, migrations, auth, permissions).
- Phase 4 — Survey management & import.
- Phase 5 — Respondent experience.
- Phase 6 — Rewards & wallet.
- Phase 7 — Administration.
- Phase 8 — Testing, hardening, deployment, backups.

## Repository layout

- `frontend/` — static HTML, CSS, and vanilla JavaScript modules.
- `backend/` — FastAPI application, Alembic migrations, tests.
- `database/` — schema and seed SQL.
- `backups/` — backup policy and restoration notes (no real data).

## Prerequisites

- Python 3.11+
- PostgreSQL 14+
- A modern browser

## Local setup (backend)

1. Create a virtual environment:
   ```bash
   cd backend
   python -m venv .venv
   source .venv/bin/activate    # Windows: .venv\Scripts\activate
Install dependencies:

bash
pip install -r requirements.txt
Copy .env.example to .env at the repository root and fill in real values.

Create the database and apply the schema:

bash
psql -U postgres -c "CREATE DATABASE survey;"
psql -U postgres -d survey -f ../database/schema.sql
Run the API:

bash
uvicorn app.main:app --reload --port 8000
Open http://localhost:8000/docs for the OpenAPI documentation.

Local setup (frontend)
Serve the frontend/ folder with any static server, for example:

bash
cd frontend
python -m http.server 5500
Then open http://localhost:5500.

Security notes
Never commit .env or real credentials.

Passwords will be hashed server-side in Phase 3.

Admin permissions will be enforced by the backend, never by the browser.

No payment is ever marked as sent without provider confirmation.

Phase 1 acceptance checks
Homepage loads with light and dark themes.

Theme choice persists across reloads.

Mobile menu opens and closes.

GET /api/health returns {"status":"ok"}.

database/schema.sql applies cleanly to a fresh PostgreSQL database.

text

### `backups/README.md` — new
Backup policy outline. Nothing here claims a backup has been tested.

```markdown
# Backups

This folder must never contain real production data. It exists to hold policy and documentation only.

## Goals

- Automated `pg_dump` backups of the PostgreSQL database.
- Encrypted at rest before leaving the primary provider.
- Stored in a second provider (e.g. S3, Backblaze B2, Cloudflare R2).
- Retention policy defined and enforced.
- Documented, repeatable restore procedure.
- Periodic restore testing on an isolated database.

## Planned backup procedure (to be implemented in Phase 8)

1. Run `pg_dump --format=custom --no-owner --no-privileges` against a read replica where possible.
2. Encrypt with `age` or `gpg` using a key stored outside the repository.
3. Upload to independent object storage with a timestamped filename.
4. Record checksum and size.
5. Retain daily for 14 days, weekly for 8 weeks, monthly for 12 months.

## Planned restore procedure (to be implemented and tested in Phase 8)

1. Provision a fresh PostgreSQL instance.
2. Decrypt the backup.
3. `pg_restore --clean --if-exists` into the new database.
4. Run smoke checks: row counts, latest audit log entry, health endpoint.
5. Only then repoint application configuration.

## Status

Not yet implemented. Do not claim backups are working until a restore has been performed and verified.

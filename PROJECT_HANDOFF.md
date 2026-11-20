# SURVEYKE — MASTER PROJECT HANDOFF
## Permanent Development Memory and AI Handover Guide

Last updated: 19 November 2026
Repository: /workspaces/Survey
Current branch: main

==================================================
1. PROJECT IDENTITY
==================================================

Project name: SurveyKE

SurveyKE is a survey platform designed to connect survey creators
with respondents who complete surveys and earn rewards.

The project is being developed as an existing application.
Any AI assisting with development must continue the existing
repository rather than creating a replacement application.

Primary development environment:
- VS Code / GitHub Codespaces
- Repository: /workspaces/Survey
- Branch: main

==================================================
2. TECHNOLOGY STACK
==================================================

Backend:
- Python
- FastAPI
- SQLAlchemy ORM

Database:
- PostgreSQL

Testing:
- pytest
- FastAPI TestClient
- SQLAlchemy database sessions

Other:
- Git and GitHub
- Python virtual environment: .venv

==================================================
3. EXISTING PROJECT STRUCTURE
==================================================

Important backend locations:

backend/
    app/
        models/
        routes/
        security/
    tests/

Known model files:

- backend/app/models/identity.py
- backend/app/models/surveys.py
- backend/app/models/participations.py
- backend/app/models/subscriptions.py

Known integration test:

- backend/tests/test_subscription_access.py

IMPORTANT:
This is not necessarily the complete project structure.
Inspect the repository before assuming that a file or feature
does not exist.

==================================================
4. USER ACCOUNTS AND IDENTITY
==================================================

The User model is defined in:

backend/app/models/identity.py

Known user fields include:

- id
- email
- full_name
- password_hash
- country_code
- preferred_currency
- role_id
- status
- email_verified_at
- last_login_at
- created_at
- updated_at

User statuses include:

- pending
- active
- suspended
- deleted

The application also contains identity-related models such as
UserPreference, EmailVerification, PasswordResetToken and
UserSession.

Inspect the existing authentication implementation before
changing anything.

==================================================
5. SUBSCRIPTION SYSTEM
==================================================

Subscription hierarchy:

1. Basic
2. Bronze
3. Silver
4. Gold
5. Platinum

The hierarchy is:

Basic < Bronze < Silver < Gold < Platinum

Access rules:

- Every respondent can see the survey catalogue.
- Survey cards above the respondent's tier are locked.
- Locked surveys cannot be opened or completed.
- Locked survey descriptions and instructions must not be exposed.
- Locked survey questions must not be exposed.
- Users can access surveys belonging to their tier and all
  lower tiers.
- Basic users can access Basic surveys.
- Platinum users can access all tiers.

Security requirements:

- Frontend locking is not sufficient.
- Backend endpoints must independently enforce subscription access.
- Unauthorized access returns HTTP 403.
- Upgrade responses identify the error using:
  upgrade_required

Existing test:

backend/tests/test_subscription_access.py

The test covers:
- Anonymous catalogue access.
- Anonymous Basic survey access.
- Anonymous restrictions on higher tiers.
- Basic respondent restrictions.
- Platinum respondent access.

LATEST VERIFIED TEST RESULT:

PYTHONPATH=backend pytest -q

Result:
1 passed

==================================================
6. SURVEY SYSTEM
==================================================

Main survey model:

backend/app/models/surveys.py

Known Survey fields include:

- id
- slug
- title
- required_tier
- description
- instructions
- category_id
- target_audience
- country_code
- estimated_minutes
- reward_amount
- reward_currency
- status
- allow_repeat
- participant_target
- participant_count
- published_at
- closes_at
- created_by
- created_at
- updated_at
- deleted_at

Survey statuses:

- draft
- published
- closed
- archived

SurveyQuestion supports:

- single_choice
- multi_select
- yes_no
- rating
- short_text
- long_text
- dropdown
- date

Survey questions have:
- order_index
- question_type
- prompt
- help_text
- is_required
- config

AnswerOption is also an existing model.

Do not recreate these models unnecessarily.

==================================================
7. PARTICIPATION AND RESPONSES
==================================================

File:

backend/app/models/participations.py

Existing Participation model statuses:

- in_progress
- submitted
- under_review
- approved
- rejected
- cancelled

Known Participation fields:

- id
- user_id
- survey_id
- status
- started_at
- submitted_at
- reviewed_at
- created_at
- updated_at

Existing Response model:

- id
- participation_id
- question_id
- answer_text
- rating_value
- selected_option_ids
- created_at
- updated_at

The Response model has a uniqueness constraint on:

participation_id + question_id

The existing participation implementation must be inspected
before adding submission or review functionality.

==================================================
8. CRITICAL REWARD AND WALLET REQUIREMENTS
==================================================

THIS IS A NON-NEGOTIABLE BUSINESS RULE.

When a respondent completes and submits an eligible survey:

1. The submission must be recorded.
2. The earned reward must be credited to the respondent's
   PENDING balance.
3. Pending rewards must NOT be withdrawable.
4. An authorized administrator must review the submission.
5. If approved, the pending reward moves into the
   WITHDRAWABLE balance.
6. If rejected, the reward must not become withdrawable.
7. Duplicate submissions or repeated requests must never
   produce duplicate reward credits.
8. Every reward movement must be auditable.

Important distinction:

PENDING BALANCE != WITHDRAWABLE BALANCE

Submitting a survey does not mean the respondent has received
withdrawable money.

Only authorized approval can release the reward.

Before implementing anything, inspect existing:
- Wallet models
- Reward models
- Transactions
- Ledger
- Balance calculations
- Admin approval routes
- Database migrations
- Existing tests

Never create duplicate wallet or reward systems.

==================================================
9. DATABASE AND MIGRATION RULES
==================================================

The project uses PostgreSQL and SQLAlchemy.

Before changing database models:

- Inspect existing models.
- Inspect existing Alembic migrations.
- Check the current database schema.
- Identify existing constraints and indexes.
- Make migrations consistent with the current project.

Never assume that changing a Python model automatically
changes the PostgreSQL database.

Never delete existing database data to solve an ordinary
development problem.

==================================================
10. DEVELOPMENT AND TESTING RULES
==================================================

All AI assistants must follow these instructions:

1. Inspect existing code before editing.
2. Do not rebuild the project from scratch.
3. Do not replace working files unnecessarily.
4. Preserve existing features.
5. Avoid introducing duplicate models or endpoints.
6. Make small, controlled changes.
7. Explain what each change accomplishes.
8. Add tests for important functionality.
9. Run tests after implementation.
10. Report actual test results honestly.
11. Never claim a feature works without verifying it.
12. Protect existing database records.
13. Check security at the backend, not just the frontend.
14. Avoid unnecessary changes to unrelated modules.

The developer is learning software development.

Therefore:
- Give terminal commands one step at a time.
- Explain commands in understandable language.
- Wait for terminal output before proceeding.
- Do not assume the developer knows advanced Python,
  SQLAlchemy, Git or PostgreSQL.
- Prefer complete, safe commands that can be copied.
- Clearly identify the project directory before commands.

==================================================
11. LATEST DEVELOPMENT CHECKPOINT
==================================================

Date: 19 November 2026

The latest development work involved subscription-tier
access enforcement and integration testing.

The developer inspected these files:

1. backend/tests/test_subscription_access.py
2. backend/app/models/participations.py
3. backend/app/models/identity.py
4. backend/app/models/surveys.py

The existing subscription integration test passed:

PYTHONPATH=backend pytest -q

Output:

. [100%]
1 passed

The latest terminal inspection confirmed the structures
documented in sections 4, 5, 6 and 7.

The next intended development task is:

INSPECT THE EXISTING WALLET AND REWARD IMPLEMENTATION.

Start by locating existing wallet, reward, transaction,
ledger and balance files.

Then inspect existing tests and models.

Do not immediately create new models or migrations.
First establish what already exists and what is missing.

==================================================
12. FIRST INSTRUCTIONS FOR A NEW AI ASSISTANT
==================================================

You are taking over an existing software project.

Before doing any development:

1. Read this entire PROJECT_HANDOFF.md file.
2. Inspect the actual repository.
3. Verify the current Git branch and working-tree status.
4. Inspect the existing wallet and reward implementation.
5. Compare the actual code with the requirements above.
6. Report what is implemented, incomplete and missing.
7. Recommend the smallest safe next development step.

Do not edit files until you have presented your findings.

The repository is the source of truth.
This handoff file records project decisions and known progress,
but it does not replace inspection of the current code.

If the actual repository differs from this document,
identify the difference and update this document after
confirming the correct state with the developer.

==================================================
13. PERMANENT PROJECT CONTINUITY
==================================================

After every significant development milestone, update this file.

Record:

- Date of update
- Features completed
- Files created or modified
- Database migrations created or applied
- Tests executed
- Actual test results
- Outstanding bugs
- Security considerations
- Exact next development task

Keep this document accurate and concise enough to be
shared with any coding AI.

END OF MASTER PROJECT HANDOFF
==================================================

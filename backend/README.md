# PayScope backend

Use [uv](https://docs.astral.sh/uv/) and an empty PostgreSQL database. Run these commands from `backend/`.

1. Run `uv sync --locked`.
2. Copy `.env.example` to `.env` and set `DATABASE_URL` to your database. Set `DEMO_HR_PASSWORD` to a password of at least 12 characters.
3. Run `uv run --locked alembic upgrade head`.
4. Run `uv run --locked python -m payscope.seed`.
5. Run `uv run --locked uvicorn payscope.main:app`. Check `GET /health` at `http://127.0.0.1:8000/health`.

For a Supabase transaction-pooler URL on port `6543`, paste the database password into the URL and percent-encode any URL-reserved characters in it. The backend defaults to TLS for this connection.

The seed creates the `hr@payscope.example` account and fills in 10,000 fictional employees with localized names and annual salaries that vary by country and role. Re-running the seed preserves existing employees, salaries, and the account password. The report revision advances only when seeding inserts data used by reports.

Run `uv run --locked pytest` for the tests. Set `TEST_DATABASE_URL` to a separate, empty PostgreSQL database to include the integration test. That test applies and rolls back the Alembic migration.

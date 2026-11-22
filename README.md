# PayScope

PayScope is a salary management and compensation analytics workspace for HR teams. It was built for the Incubyte engineering assessment and includes a fictional demo of 10,000 employees. The core workflow is to find an employee, review or update their compensation, and verify how recorded pay appears in a report.

## Features

| Area | What you can do |
| --- | --- |
| **Workforce overview** | See which employees have base pay on file, compare coverage by country, and open the missing-pay cohort. |
| **Employees** | Search by name or employee ID, filter by country, department, job title, or pay status, and move through server-paginated results. Preview annual compensation changes before saving. |
| **Compensation rules** | Define fixed and percentage components, preview calculations, publish immutable rule versions, and apply rules to employee packages. Existing packages keep their assigned versions. |
| **Salary insights** | Explore pay distribution, compensation mix, country comparison, guaranteed vs. target cost to company (CTC), payroll concentration, role bands, equity timeline, and headcount vs. payroll. Check chart marks against exact values. |
| **Ask about pay** | Ask a group-level pay question, follow live report activity, and open the underlying report. Reconnect to an interrupted response from its last received event. |
| **Saved reports** | Keep an independent snapshot of a completed answer and its figures. Search the library, edit report metadata, open current data for comparison, or delete and undo. |
| **Admin** | With the relevant permissions, inspect agent runs or review and publish prompt versions. |

The workspace supports light and dark themes. Reports keep currencies separate and distinguish missing data from recorded zeroes.

## Run locally

### Prerequisites

- Node.js 24 with npm for the frontend.
- Python 3.14 and [uv](https://docs.astral.sh/uv/) for the backend.
- A PostgreSQL database you can migrate and populate with fictional data.
- Redis and a supported model-provider credential for **Ask about pay**. The employee, compensation, and analytics workflows run without an agent provider.

### 1. Start the API

From the repository root, open a terminal and enter the backend directory.

```sh
cd backend
uv sync --locked
```

Copy `.env.example` to `.env` in `backend/`. Use `Copy-Item .env.example .env` in PowerShell or `cp .env.example .env` in a POSIX shell. Set `DATABASE_URL` to your PostgreSQL connection string and choose a `DEMO_HR_PASSWORD` of at least 12 characters. Keep `backend/.env` local.

Apply the migrations and populate a fresh fictional demo, including compensation packages.

```sh
uv run --locked alembic upgrade head
uv run --locked python -m payscope.seed --compensation apply
uv run --locked uvicorn payscope.main:app
```

Check the [health endpoint](http://127.0.0.1:8000/health) or open the [interactive API docs](http://127.0.0.1:8000/docs). To populate the Equity timeline for a review, follow the [demo equity setup](backend/README.md#populate-the-fictional-demo).

### 2. Start the UI

Open a second terminal at the repository root.

```sh
cd ui
npm ci
npm run dev
```

Open [PayScope locally](http://localhost:5173). Sign in as `hr@payscope.example` using the password you set in `backend/.env`. Use `localhost` for the browser URL. Vite proxies `/api` to the API on port 8000.

### 3. Enable Ask about pay

In `backend/.env`, configure `REDIS_URL`, `AGENT_OPENAI_API_KEY`, `AGENT_OPENAI_MODEL`, and a positive `AGENT_USER_QUOTA` at or below `AGENT_GLOBAL_QUOTA`. Restart the API afterward. The backend guide documents supported connectors, optional model escalation, and streaming requirements. [Agent runtime setup](backend/README.md#ask-about-pay-runtime)

## Reviewer walkthrough

1. **Find an employee.** Open Employees, filter to India and Engineering, and open a result’s compensation record. Check the currency and pay basis, then preview a change to a fictional package. Save only if you want to alter the demo.
2. **Read a report.** In Salary insights, choose Pay distribution or Headcount vs. payroll and set a currency. Focus or select a mark to inspect it, then check the numbers under **Exact values**. Try Payroll concentration to drill from countries to departments or roles.
3. **Verify an agent answer.** If the agent is configured, ask “Which Engineering role in India has the highest median annual base pay in INR?” Follow Report activity, then open the source report and inspect the figures.
4. **Save the evidence.** Save the completed report and reopen it from Saved reports. Compare the stored revision with **Open current report** when the underlying data changes.

## Architecture

- **Frontend:** React, Vite, React Router, and shadcn/Radix components. PayScope’s theme tokens are shared across the workspace, interactive charts, and report tables.
- **API and storage:** FastAPI, async SQLAlchemy, PostgreSQL, and Alembic. The server validates and recalculates compensation. Monetary API values use decimal strings, and writes use version checks where a concurrent edit could overwrite data.
- **Agent workflow:** Microsoft Agent Framework with streamed server-sent events. A report tool validates filters and reads aggregate pay figures. The answer is checked against that report evidence, and persisted events support replay. Redis provides coordination for agent execution and an optional cache for report aggregates.
- **Report provenance:** Saved reports copy completed server-side evidence. Editing a report changes its title or description. The saved figures remain available even if the source chat is deleted.
- **Authentication:** Sessions use HTTP-only cookies and mutations require CSRF protection. Admin routes are controlled by separate permissions for prompt management and run observability.

## Checks

Run these commands from `ui/`.

```sh
npm run lint
npm run build
npx playwright install chromium
npm test
```

Run backend checks from `backend/`.

```sh
uv run --locked pytest
```

Set `TEST_DATABASE_URL` to a separate, empty PostgreSQL database for backend integration tests. Use a disposable Redis instance for cache and agent integration tests. The UI guide documents the optional live tests and the fixture data they require. [UI verification](ui/README.md) · [Backend verification](backend/README.md#hr-api)

For deployment, serve the frontend and `/api` from the same HTTPS origin. Route frontend deep links to `index.html` and configure the proxy to pass agent SSE responses through without buffering.

## Repository guide

| Path | Contents |
| --- | --- |
| [`ui/`](ui/) | React application and browser tests |
| [`backend/`](backend/) | API, migrations, demo seed, and Python tests |
| [`artifacts/requirements/`](artifacts/requirements/) | Assessment requirements and acceptance criteria |
| [`artifacts/design/`](artifacts/design/) | UI theme, database design, reporting, and agent workflow |
| [`artifacts/verification/`](artifacts/verification/) | Smoke-test scripts and verification captures |

For the assessment context, start with the [product requirements](artifacts/requirements/product-requirements.md), [design guide](artifacts/design/DESIGN.md), and [agent streaming design](artifacts/design/agent-streaming-design.md).

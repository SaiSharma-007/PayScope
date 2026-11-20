# Salary Management Backend Requirements

## Purpose

The Salary Management app gives an HR Manager one place to maintain current salaries and understand how pay varies across a 10,000-employee organization in multiple countries.

## Product behavior

### Compensation extension (Plan 1)

HR defines reusable country/currency rules with custom components. Each component has a stable code, label, category (earnings, employer cost, or employee deduction), guaranteed/target commitment, explicit cost inclusion, and either a fixed annual amount or a percentage of basic pay. Rule versions are immutable; publishing a version does not change existing packages. Deactivation prevents new applications while saved packages retain their version.

An employee package records annual basic pay, currency, effective date, applied rule version or manual definitions, and saved component amounts. Employee overrides require a reason. One backend calculator powers preview and save, and the UI requires reviewing a preview before saving. Employee deductions stay outside company-cost totals. Guaranteed cost and cost including target components are separate; neither is take-home pay. Equity is not configured until Plan 2, so this release labels totals as annual cash and benefit costs.

Amounts use decimal strings and half-up rounding to two places per line. Basic pay is 0.01–999,999,999.99; components and each subtotal cannot exceed 999,999,999.99. Packages/rules allow at most 32 components. Percentages allow four decimal places from zero through 10,000; fixed amounts and overrides allow two. Component codes are unique, basic pay cannot be duplicated, and arbitrary expressions or references to other components are unsupported. Effective dates are date-only, today or earlier; changes apply immediately rather than being scheduled. Package saves and report revisions commit atomically. Stale package/rule version writes return 409.

The user approved reframing the 10,000 fictional employees by treating each old recorded amount as total company cost and distributing it into illustrative country components while preserving the total exactly. Employee identities and legacy salary rows remain intact. The opt-in seed enrichment inserts only missing packages, records its balancing allowance as an override with a reason, and never overwrites an HR-edited package. Its country percentages are synthetic examples, not statutory contribution rates.

The legacy `annual_gross_base` field and salary-summary endpoint remain compatibility interfaces over the original recorded amounts. They must not be interpreted as the new package basic pay or as live package cost reporting. Legacy writes return 409 after a package exists. Plan 2 adds package-based compensation reports, equity, and coverage-aware CTC.

### Original core and future workflow

- **Access.** One HR Manager account can sign in and sign out of the deployed demo. Employee, salary, analytics, and agent run endpoints require an authenticated HR session.
- **Employee directory.** Every employee has a required, unique Employee ID. HR can search by name or Employee ID, combine country, department, and job title filters, and browse results in a consistent order with server-side pagination and a total matching count.
- **Salary records.** HR can view, enter, or replace an employee's current annual gross base salary. Each salary has a validated amount and an explicit currency code. Monetary values retain decimal precision.
- **Pay analytics.** HR can combine country, department, and job title filters and optionally compare groups by one of those dimensions. The API returns minimum, maximum, median, mean, and the number of employees with a salary for each group and currency. Results cover the full matching population with a recorded salary and support interactive charts. A query with no matching salaries returns an empty result.
- **Ask about pay.** A Microsoft Agent Framework (MAF) Workflow Orchestrator coordinates a Pay Analyst and an Answer Writer inside FastAPI. The orchestrator owns stage transitions, tool dispatch, limits, cancellation, and the final result. The analyst chooses validated report filters and grouping through read-only tools. The writer streams an explanation grounded in calculated results, with report settings for verification. Supported questions include summaries and highest or lowest comparisons by average or median within a currency.

## Data and service requirements

- The deployed REST API uses async FastAPI endpoints and async PostgreSQL and Redis clients. PostgreSQL stores employee, salary, and session data. The demo uses HTTPS, secure session cookies, and CSRF protection for requests that change data.
- Redis caches analytics by filter combination and grouping. The next report request after a committed salary edit reflects that edit. Reports remain available from PostgreSQL during a Redis outage.
- Every agent model call uses MAF streaming. FastAPI publishes ordered Server-Sent Events (SSE) for run acceptance, agent stages, real tool start and completion, report readiness, answer text, and the terminal outcome. Complete tool arguments are validated before execution. The workflow is bounded by tool, model-call, output, and time limits defined in the design.
- Runs support explicit cancellation, authenticated event replay, and idempotent creation. Reconnecting continues the existing run. Tool results and model answers remain bound to that run and report revision. Reports stay available during model failures.
- Each run executes in its own async task with private MAF workflow, sessions, tool state, and cancellation. Separate conversations can run concurrently, with one active turn per conversation. Shared admission enforces global and per-user capacity across instances. A busy chat receives 409, a user at quota receives 429, and a full global pool receives 503. Owned chats and framework state are persisted for reopening and checkpoint recovery.
- Ambiguous questions receive clarification, including when multiple currencies match an unspecified currency. Unsupported requests receive an explanation. Validated numeric evidence drives the report card, while the final explanation is checked against that evidence.
- Each quantitative answer statement identifies its group, currency, metric, and report evidence. The backend verifies the requested statement and renders its amount from the report, including tied rankings. Invalid statements produce a computed report summary.
- A repeatable seed command generates exactly 10,000 fictional employees with salaries across multiple countries, currencies, departments, and job titles. Deployment credentials are managed outside Git.

## Salary rules

The proposed demo currencies are INR, USD, GBP, and EUR. Annual gross base salary must be between 0.01 and 999,999,999.99 in its recorded currency, with at most two fractional digits. Invalid amounts receive a field error. Salaries retain their entered precision, and report amounts use two decimal places with half-up rounding after calculation and ranking. These are candidate-defined demo rules for review.

## Acceptance criteria

- Fast, deterministic unit tests cover amount validation, combined filters, grouping, odd and even medians, and currency separation. Integration tests cover access controls, CSRF protection, salary updates, cache hits, report freshness, and Redis fallback.
- Agent tests use a streaming stub to verify tool validation, currency clarification, ties, numeric evidence, intermediate events, limits, and failures. Integration checks cover event ordering, cancellation, disconnect and replay, and idempotent creation. A deployed check verifies real MAF tool use and incremental delivery through the hosting proxy.
- Concurrent-run checks interleave five chats under a suitable test quota and verify independent history, tool results, streams, and cancellation. Same-chat admissions are serialized. Tests distinguish user quota from global pool saturation and verify expiration and ownership of shared reservations.
- A fixed agent evaluation set covers summaries, filtered rankings, ties, ambiguous currency, empty results, and unsupported requests. Each case records expected tool arguments, outcome, report evidence, and answer. Deterministic cases pass before release, and live model results record successes and failures against the same expectations.
- The project publishes the API contract and documents local setup, seeding, test execution, and reviewer access. A performance check records median and p95 latency and error rates for directory and analytics requests with one and five concurrent sessions, including cold and warm analytics cache runs.

## Deliberate exclusions

Monthly pay, bonuses, salary history, payroll, currency conversion, and multiple HR roles are outside this release. Agent tools read report options and aggregate salary statistics. Salary changes use the salary form. Agentic AI also supports development, with key decisions and verification recorded in the project artifacts.

[Streaming workflow design](../design/agent-streaming-design.md)

[Runtime limits](../design/runtime-limits.md)

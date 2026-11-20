# Salary Management Frontend Requirements

## Purpose

The React app gives an HR Manager a clear path from opening the demo to finding an employee, updating annual base pay, and comparing salaries across groups.

## Product behavior

### Compensation extension (Plan 1)

The Compensation rules page supports country/currency/status filters, custom component entry, an example annual-basic-pay calculator, immutable version inspection, new-version publication, and deactivation/reactivation. Country and currency are fixed for a rule; a different pairing requires a new rule. Example previews are labeled as unsaved and do not modify employees.

Employees have a Compensation action on desktop and mobile. The drawer shows the saved package, annual basic pay, currency, effective date, a compatible rule selector or manual component editor, and overrides with required reasons. Changing currency explicitly clears the incompatible draft structure. The before/after preview identifies all included and excluded lines, guaranteed and target costs, and employee deductions. The UI saves only after a successful preview and invalidates that preview whenever inputs change. Saved changes update the employee row without resetting filters, pagination, or table scroll.

Unsaved changes require confirmation on closing or navigating away, including browser back. The drawer restores focus to its employee action. Stale-save conflicts retain entered values and offer an explicit reload with discard confirmation. Loading, field errors, failed requests, retries, session expiry, and duplicate-save protection follow the existing authentication patterns. Dropdown portals remain inside a modal drawer so keyboard and pointer interaction work in both. Light/dark themes, narrow widths, reduced motion, and exact decimal/currency labels apply throughout.

The reframed demo uses fictional country splits preserving each old total, with visibly named demo rules and components. Equity remains not configured; the UI shows cash/benefit cost rather than claiming a complete equity-inclusive CTC. Pay Analytics, Ask about pay, and manual equity remain scheduled work after Plan 1.

### Original core and future workflow

- **Landing page.** The public page introduces salary management and pay analytics, identifies the demo data as synthetic, and provides a prominent **Sign in** action. Employee and salary information is available only after sign-in.
- **Access and navigation.** The HR Manager can sign in and sign out. A successful sign-in opens **Employees**, with **Pay Analytics** accessible from the main navigation. Sign-out and session expiry clear protected data from the interface and return to sign-in.
- **Employee directory.** The table shows employee ID, name, country, department, job title, and current annual gross base salary with its currency. HR can search by name or ID, combine and clear filters, and browse paginated results with a visible result count. A search or filter change resets pagination to page one.
- **Salary editing.** An **Edit salary** action opens a side panel with the employee's identity, current salary, editable amount, and currency. The form prevents duplicate saves, shows field errors while keeping entered values, and asks before discarding unsaved changes. A confirmed save updates the row while preserving the directory's search, filters, and page.
- **Amount and currency rules.** The form uses the backend's supported currencies and amount limits, identifies the amount as annual gross base salary, and explains invalid decimal precision. Salary and report values display two decimal places and an explicit currency code. Selecting a different currency labels the entered amount in that currency.
- **Pay analytics.** HR can combine country, department, and job title filters, group by one of those dimensions, and select a currency. An interactive horizontal chart shows each group's minimum-to-maximum range with a median marker. A table provides exact minimum, median, maximum, average, and salaried headcount. The next report after a confirmed edit uses the updated salary.
- **Ask about pay.** Pay Analytics includes a question field and example questions. A live activity panel shows the Pay Analyst and Answer Writer stages, actual tool names, validated filters, execution status, duration, and a summary of returned aggregates. Answer text appears incrementally beside a report card containing the verified figures and settings. **Open report** applies those settings to the chart and table, and indicates when a later salary edit has changed the report revision.
- **Run controls.** HR can stop an active run, answer a clarification, or reconnect after interruption. Received text and completed activity stay visible, and each run clearly ends as completed, awaiting clarification, unsupported, failed, cancelled, or interrupted. A compatible saved checkpoint offers Resume. Reconnect attaches to the same run, and repeated events appear once.
- **Saved chats and concurrency.** HR can reopen an owned chat or start another conversation. Independent chats can run concurrently, and the UI keeps their messages and activity keyed by conversation and run. A busy conversation identifies its active run. Stop and reconnect apply to the selected run. User quota and full-pool responses have distinct messages and an explicit retry action using the server's retry hint.

## Interaction and accessibility

- The directory and report retain a stable layout during loading, explain when no results match, and offer a retry after a recoverable error. A late response cannot replace results for a newer search or filter selection.
- The desktop-first layout aligns salary figures for easy scanning and keeps core actions usable at narrow widths. Controls have visible keyboard focus, chart values are available without hover, and the salary panel respects reduced-motion preferences.
- Live activity follows real execution events, including the orchestrator's handoffs and each agent's start and completion. Tool details are expandable, keyboard accessible, and labeled in plain language. Streaming text preserves the reader's scroll position, batches screen-reader announcements, and is marked provisional until the final validated response arrives. Agent errors retain received content and offer a clear recovery action.

## Acceptance criteria

- A reviewer can start on the landing page, sign in, find an employee, save a salary, and verify the updated average for the corresponding group and currency.
- A reviewer can ask which Engineering job title in India has the highest median base salary in INR, observe the tool execution and streamed explanation, then open the source report and verify the result.
- Stop, reconnect, clarification, and provider failure are exercised with deterministic streams, including interrupted tool execution and repeated events.
- Interleaved chat streams are checked for correct routing, and stopping one chat preserves progress in the others.
- The deployed app is checked at desktop and narrow widths for keyboard access, invalid input, empty results, failed requests, and session expiry.

## Deliberate exclusions

Bulk salary editing, salary history, and customizable dashboards are outside the release so the interface stays focused on the individual edit and pay comparison workflows.

[Backend requirements](backend-requirements.md)

[Streaming workflow design](../design/agent-streaming-design.md)

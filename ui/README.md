# PayScope UI

The React app includes the public landing page, HR sign-in, session restoration, sign-out, and the employee directory.

The signed-in workspace has a collapsible sidebar and mobile navigation drawer. Overview reads employee and compensation coverage by country. Activity contains labeled sample content. The employee directory uses live data with search, filters, and page sizes of 10, 25, or 50.

## Reviewer walkthrough

1. Open **Salary insights** and select **Headcount vs. payroll**. Choose a currency under **Workforce filters**. Read the sentence above the chart, then hover or focus a row to inspect the two shares beside it. Compare the share gap in the chart details with **Exact values**. Use the info button beside **Payroll share** to see its denominator.
2. Switch to **Payroll concentration**. Click or tap a country tile to pin its values, then choose **View departments**. Select a department and choose **View roles**. Use Escape to close a pinned card, and use the breadcrumb or a shared URL to revisit the drill-down.
3. In the seeded demo, open **Equity timeline** and select a currency and reporting years. Focus or tap a year to read RSU and stock-option allocations. Compare a recorded zero, a partial total, or an unavailable amount with **Exact values**. In **Guaranteed vs. target CTC**, read the coverage breakdown for any excluded employees. [Prepare the fictional demo](../backend/README.md#populate-the-fictional-demo)

Compensation rules and employee compensation are live. HR can define custom fixed or percentage components, preview calculations, publish immutable versions, apply rules to matching employees, enter manual breakdowns, and override components with reasons. Employee saves require a reviewed preview and preserve directory position. Guaranteed costs and costs including target components are distinct; employee deductions and unconfigured equity are explained separately. Seeded employees use illustrative country packages preserving their original totals.

Run the backend on port 8000, then run these commands from `ui/`.

```sh
npm ci
npm run dev
```

Open `http://localhost:5173`. Vite proxies `/api` to the backend. The demo HR email is `hr@payscope.example`; its password is configured in the backend's ignored `.env` file. Sessions use secure HTTP-only cookies, and CSRF tokens stay in memory.

`npm run lint` checks the source and `npm run build` produces `dist/`. Production hosting must serve the UI and `/api` from the same HTTPS origin and route UI deep links to `index.html`.

Run `npx playwright install chromium` once, then `npm test` to start a test server on port 4176 and run the isolated browser fixtures. Set `PAYSCOPE_CHROME_PATH` to use an installed Chromium-based browser. The optional live test uses `PAYSCOPE_LIVE_API_URL`, `PAYSCOPE_LIVE_EMAIL`, `PAYSCOPE_LIVE_PASSWORD`, and `PAYSCOPE_LIVE_EMPLOYEE_ID`. Use an isolated database with recorded INR equity and a manual base-pay-only INR package for the fixture employee. The test saves a temporary package change and restores the original amount after verifying the refresh.

Visual tokens implement the [theme specification](../artifacts/design/DESIGN.md). Fonts are self-hosted. The theme follows the system preference until a light or dark choice is saved.

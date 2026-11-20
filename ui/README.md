# PayScope UI

The React app includes the public landing page, HR sign-in, session restoration, sign-out, and the employee directory.

The signed-in workspace has a collapsible sidebar and mobile navigation drawer. Overview reads employee and compensation coverage by country. Activity contains labeled sample content. The employee directory uses live data with search, filters, and page sizes of 10, 25, or 50.

## Reviewer walkthrough

1. Open **Salary insights** and select **Pay distribution**. Under **Workforce filters**, choose a country and currency. Focus, hover over, or tap a box plot to see P10, P25, P50, P75, and P90. Compare P50 in **Selected values** with the same group's P50 in **Exact values**. Check the eligible and missing employee counts above the chart.
2. Switch to **Payroll concentration**. Select a country tile and choose **View departments**. Select a department and choose **View roles**. Use the breadcrumb to return to the country view, or reload a copied URL to reopen the same drill-down.
3. In a fixture environment, open an employee with a saved package, choose **Equity and annual CTC**, and add an RSU or stock option with a calendar-year allocation in the package currency. Open **Equity timeline**, select the corresponding country, currency, and year range, then choose **Refresh report**. Check the award type's recorded amount and its missing and recorded-zero counts in **Exact values**. **Guaranteed vs. target CTC** includes an employee once every applicable award has a recorded allocation for that year or HR has marked equity not applicable.

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

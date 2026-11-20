# PayScope UI

The React app includes the public landing page, HR sign-in, session restoration, sign-out, and the employee directory.

The signed-in workspace has a collapsible sidebar and mobile navigation drawer. Overview reads employee and compensation coverage by country. Salary insights shows live basic pay, cash and benefits, annual equity, and CTC by currency. Activity contains labeled sample content. The employee directory uses live data with search, filters, and page sizes of 10, 25, or 50.

To verify an equity-inclusive report, open an employee with a saved package, choose **Equity and annual CTC**, and add an RSU or stock option. Record the annual allocation in the employee's package currency. Compare the resulting CTC with **Salary insights** filtered to that country, currency, and calendar year. Every applicable award must have a recorded allocation for the selected year. HR can also mark equity not applicable for an employee with no awards.

Compensation rules and employee compensation are live. HR can define custom fixed or percentage components, preview calculations, publish immutable versions, apply rules to matching employees, enter manual breakdowns, and override components with reasons. Employee saves require a reviewed preview and preserve directory position. Guaranteed costs and costs including target components are distinct; employee deductions and unconfigured equity are explained separately. Seeded employees use illustrative country packages preserving their original totals.

Run the backend on port 8000, then run these commands from `ui/`.

```sh
npm ci
npm run dev
```

Open `http://localhost:5173`. Vite proxies `/api` to the backend. The demo HR email is `hr@payscope.example`; its password is configured in the backend's ignored `.env` file. Sessions use secure HTTP-only cookies, and CSRF tokens stay in memory.

`npm run lint` checks the source and `npm run build` produces `dist/`. Production hosting must serve the UI and `/api` from the same HTTPS origin and route UI deep links to `index.html`.

Visual tokens implement the [theme specification](../artifacts/design/DESIGN.md). Fonts are self-hosted. The theme follows the system preference until a light or dark choice is saved.

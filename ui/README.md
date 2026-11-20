# PayScope UI

The React app includes the public landing page, HR sign-in, session restoration, sign-out, and the employee directory.

The signed-in workspace has a collapsible sidebar and mobile navigation drawer. Overview, Salary insights, and Activity contain labeled sample content. The employee directory uses live data with search, filters, and page sizes of 10, 25, or 50.

Run the backend on port 8000, then run these commands from `ui/`.

```sh
npm ci
npm run dev
```

Open `http://localhost:5173`. Vite proxies `/api` to the backend. The demo HR email is `hr@payscope.example`; its password is configured in the backend's ignored `.env` file. Sessions use secure HTTP-only cookies, and CSRF tokens stay in memory.

`npm run lint` checks the source and `npm run build` produces `dist/`. Production hosting must serve the UI and `/api` from the same HTTPS origin and route UI deep links to `index.html`.

Visual tokens implement the [theme specification](../artifacts/design/DESIGN.md). Fonts are self-hosted. The theme follows the system preference until a light or dark choice is saved.

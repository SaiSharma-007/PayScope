---
version: alpha
name: PayScope
description: A porcelain, periwinkle, and orchid neumorphic theme for employee compensation and salary analytics, in light and dark.
colors:
  background: "#F0EFF6"
  background-dark: "#191724"
  foreground: "#211E32"
  foreground-dark: "#F2EFFA"
  card: "#F6F4FA"
  card-dark: "#252233"
  popover: "#F9F7FC"
  popover-dark: "#302C40"
  primary: "#5357C6"
  primary-dark: "#A6AAFF"
  primary-foreground: "#FFFFFF"
  primary-foreground-dark: "#191724"
  secondary: "#E9E6F1"
  secondary-dark: "#302C40"
  muted: "#EBE8F2"
  muted-dark: "#2B283A"
  muted-foreground: "#5D5773"
  muted-foreground-dark: "#C2BBD2"
  accent: "#E4E4FA"
  accent-dark: "#38395E"
  accent-foreground: "#373A91"
  accent-foreground-dark: "#DDDEFF"
  destructive: "#373147"
  destructive-dark: "#ECE7F7"
  destructive-foreground: "#FFFFFF"
  destructive-foreground-dark: "#191724"
  border: "#D7D2E3"
  border-dark: "#49435A"
  input: "#827A96"
  input-dark: "#8E85A4"
  ring: "#5357C6"
  ring-dark: "#A6AAFF"
  sidebar: "#EBE8F2"
  sidebar-dark: "#201D2D"
  sidebar-border: "#D7D2E3"
  sidebar-border-dark: "#49435A"
  chart-1: "#5357C6"
  chart-1-dark: "#A6AAFF"
  chart-2: "#8B4BB2"
  chart-2-dark: "#D5A1F4"
  chart-3: "#625975"
  chart-3-dark: "#B9B0CD"
  chart-4: "#41449C"
  chart-4-dark: "#C1C3FF"
  chart-5: "#746A87"
  chart-5-dark: "#9D94B1"
  success: "#494259"
  success-dark: "#DDD7E9"
  success-surface: "#E9E6F1"
  success-surface-dark: "#302C40"
  warning: "#433B56"
  warning-dark: "#E4DCEF"
  warning-surface: "#E9E6F1"
  warning-surface-dark: "#302C40"
  error-surface: "#E5E0EF"
  error-surface-dark: "#373145"
typography:
  display:
    fontFamily: "Instrument Sans, system-ui, sans-serif"
  sans:
    fontFamily: "Instrument Sans, system-ui, sans-serif"
  mono:
    fontFamily: "IBM Plex Mono, ui-monospace, monospace"
rounded:
  DEFAULT: "0.75rem"
  field: "0.75rem"
  panel: "1.5rem"
  compact-panel: "1rem"
  pill: "999px"
spacing:
  xs: "0.375rem"
  sm: "0.75rem"
  md: "1.125rem"
  lg: "1.5rem"
  xl: "1.875rem"
  section-gap: "3rem"
  page-max: "90rem"
  nav-width: "13.5rem"
  drawer-width: "27rem"
components:
  app-shell: { backgroundColor: "{colors.background}", textColor: "{colors.foreground}", typography: "{typography.sans}" }
  app-shell-dark: { backgroundColor: "{colors.background-dark}", textColor: "{colors.foreground-dark}" }
  button-primary: { backgroundColor: "{colors.primary}", textColor: "{colors.primary-foreground}", rounded: "{rounded.DEFAULT}", padding: "{spacing.sm}" }
  button-primary-dark: { backgroundColor: "{colors.primary-dark}", textColor: "{colors.primary-foreground-dark}" }
  input: { backgroundColor: "{colors.card}", textColor: "{colors.foreground}", rounded: "{rounded.field}" }
  input-dark: { backgroundColor: "{colors.card-dark}", textColor: "{colors.foreground-dark}" }
  table-header: { backgroundColor: "{colors.secondary}", textColor: "{colors.muted-foreground}" }
  table-header-dark: { backgroundColor: "{colors.secondary-dark}", textColor: "{colors.muted-foreground-dark}" }
  range-band: { backgroundColor: "{colors.chart-1}" }
  range-band-dark: { backgroundColor: "{colors.chart-1-dark}" }
  median-marker: { backgroundColor: "{colors.chart-2}" }
  median-marker-dark: { backgroundColor: "{colors.chart-2-dark}" }
  drawer: { backgroundColor: "{colors.card}", textColor: "{colors.foreground}", width: "{spacing.drawer-width}", rounded: "{rounded.panel}" }
  drawer-dark: { backgroundColor: "{colors.card-dark}", textColor: "{colors.foreground-dark}" }
  theme-switch: { backgroundColor: "{colors.secondary}", rounded: "{rounded.pill}" }
  theme-switch-dark: { backgroundColor: "{colors.secondary-dark}" }
  status-success: { textColor: "{colors.success}" }
  status-success-dark: { textColor: "{colors.success-dark}" }
  status-warning: { textColor: "{colors.warning}" }
  status-warning-dark: { textColor: "{colors.warning-dark}" }
  status-error: { textColor: "{colors.destructive}" }
  status-error-dark: { textColor: "{colors.destructive-dark}" }
---

# PayScope Theme

## Overview

PayScope helps HR find employees, update annual base pay, and compare how the organization pays its people. Three color families govern both modes. Violet-neutral does most of the work, from porcelain surfaces to violet-charcoal text and dark surfaces. Periwinkle identifies primary actions, focus, selection, and pay ranges. Orchid is reserved for the median diamond and value.

This document specifies the approved theme for future screen adoption. The current application still uses its existing styles in `ui/src/styles/tokens.css`. During adoption, move the approved values into the shared global stylesheet and preserve the root `data-theme` selector and stored preference. English is the current UI language. Currency stays explicit and follows the record. [Frontend requirements](../requirements/frontend-requirements.md)

## Colors

| Role | Application |
| --- | --- |
| `background`, `sidebar`, `card`, `popover` | Porcelain canvas and a softly differentiated rail in light mode. Violet-charcoal canvas and gently lifted violet-neutral work surfaces in dark mode. Floating menus and dialogs use the overlay surface. |
| `foreground`, `muted-foreground` | Primary text and readable supporting labels. Card, overlay, secondary, and sidebar foregrounds inherit the main foreground. |
| `primary`, `primary-foreground` | Deeper periwinkle in light mode and lighter periwinkle in dark mode. Use for the primary action. |
| `secondary`, `muted`, `accent`, `accent-foreground` | Quiet surfaces, subdued fills, and tinted selection. Pair selected styling with a persistent label or state. |
| `border`, `input`, `sidebar-border`, `ring` | Use fine separators for structure and the stronger input color where the boundary identifies a control. Use a 2 px focus ring with 2 px offset. |
| `chart-1`, `chart-2` | Expose these as `--pay-range` and `--pay-median`. Use a periwinkle stroke and an orchid diamond with a 2 px surface-colored outline where the marks cross. Pair them with labels and exact values. |
| `chart-3` through `chart-5` | Additional series use neutral or periwinkle tones. Identify each by label and distinguish overlapping series by shape or stroke pattern. |
| `success`, `warning`, `destructive` | Use violet-neutral tones, distinct icons, and explicit labels for success, warning, and error. Use `destructive-foreground` for text on solid destructive actions. |

Sidebar action, selection, and focus tokens inherit their matching shared roles. Verify at least 4.5:1 for normal text and 3:1 for meaningful control boundaries, focus indicators, and chart marks against adjacent colors. Check both modes and use system colors in forced-colors mode. [WCAG text contrast](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html) · [WCAG non-text contrast](https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html)

## Typography

| Role | Family and scale |
| --- | --- |
| Landing headline | Instrument Sans 600, `clamp(2.75rem, 5vw, 4.5rem)`, line height 1.06, tracking -0.04em. |
| Workspace heading | Instrument Sans 650, 28/34 px, tracking -0.025em. |
| Panel heading | Instrument Sans 650, 18/24 px. Align the heading and its relevant action on one row. |
| Body, forms, and controls | Instrument Sans 400, 14/20 px. Use 16 px inputs on touch widths. |
| Table secondary labels | Instrument Sans 500, 12/16 px. |
| IDs and technical traces | IBM Plex Mono. |
| Monetary values | Instrument Sans with tabular lining numerals. Right-align amounts and keep the currency code visible. |
| Report headline figure | Instrument Sans 600, 36/40 px with tabular numerals. Put the currency and metric label beside the value. |

Use sentence case for controls and headers. Format amounts to two decimal places with grouping appropriate to the active locale. Use the stored decimal string as the formatting input and keep the full label or figure available at narrow widths.

## Layout

Use a 6 px spacing rhythm. Center the desktop shell inside `page-max` with 30 px gutters, 24 px panel gaps, and a persistent 216 px navigation rail. Give major panels 24 px padding. Use 18 px inside smaller inset groups. Below 960 px, use a horizontal header with Employees and Pay Analytics as the primary destinations. Below 720 px, use 18 px outer gutters, 18 px panel padding, and stacked filter controls.

Use a twelve-column workspace grid. Employees uses one full-width directory panel. Pay Analytics uses an eight-column report panel and a four-column Ask about pay panel at widths of 1200 px and above. From 960 through 1199 px, put both panels on separate full-width rows. The contents determine panel height. Keep the whole page naturally scrollable.

### Employee workspace

Put the title, matching result count, and filter controls at the top of a rounded directory panel. Keep the directory as a continuous table with a calm header, 54 px desktop rows, aligned monetary columns, and a small Edit salary action per row. Show a missing salary with an explicit label. Keep employee identity, salary, and Edit salary visible in the narrow layout, with country, department, and job title in labeled rows.

Group pagination with the table footer. Opening the salary drawer preserves the current search, filters, page, and underlying row position. Reserve table geometry while loading, and show errors and Retry within the panel that requested the data.

### Pay Analytics workspace

Place filters and the currency selector across the report panel's top. Use the report's actual selected currency and population in the header. Underneath, stack the range chart and exact-values table. Put Ask about pay in a neighboring panel with a labeled question field, useful example questions, and an answer area that grows with the response.

```text
Navigation    Pay Analytics                         Theme and HR account

              Report panel                         Ask about pay
              Filters and currency                 Question field
              Salary range chart                   Example questions
              Exact-values table                   Answer and tool activity
```

The chart and assistant share the report settings. Open report applies the returned settings to the report panel. On narrow screens, place Ask about pay after the report and keep a clear link between its answer and Open report.

Every card heading describes its own task. Place an overflow menu only where secondary actions exist. Use actual report values and supported actions to populate the workspace.

## Elevation & Depth

Use a consistent light source from the upper left. A broad raised report or preview gets a soft upper-left highlight and lower-right shadow. A recessed filter well or field reverses those edges. Both use violet-neutral tones. Recess the pay-range track and preserve the position of its median marker from the underlying data. Keep table rows, tool activity, report text, and labels flat so the values remain easy to scan.

| Token | Light | Dark |
| --- | --- | --- |
| `--shadow-raised` | `inset 0 1px 1px rgb(255 255 255 / 85%), 0 12px 24px rgb(79 65 119 / 17%)` | `inset 0 1px 1px rgb(221 211 251 / 15%), 0 12px 24px rgb(12 9 21 / 50%)` |
| `--shadow-recessed` | `inset 2px 3px 8px rgb(79 65 119 / 16%), inset 0 -1px 2px rgb(255 255 255 / 75%)` | `inset 2px 3px 8px rgb(12 9 21 / 48%), inset 0 -1px 2px rgb(221 211 251 / 12%)` |
| `--shadow-overlay` | `0 12px 28px rgb(79 65 119 / 20%)` | `0 12px 28px rgb(12 9 21 / 50%)` |

Assign one dominant depth treatment to each group. Use raised depth for a primary working surface or the public preview, recessed depth for a compact input or control group within it, and overlay elevation for floating menus and dialogs. Keep primary actions solid periwinkle with a clear label. Use the input border where it identifies a control, the accent fill and a persistent indicator for selection, and an independent focus ring. In forced colors, retain native borders and outlines as depth drops away. Drawer backdrops dim the surrounding content while the drawer stays opaque.

## Shapes

Use 24 px corners for the main molded surfaces, 16 px for compact report panels, and 12 px for fields and buttons. Use 36 px controls by default and 32 px controls in dense desktop groups. Give standalone touch controls at least a 44 px target and retain consistent Lucide icon sizes across each control family.

## Components

### Button shape and depth

Use a softly raised pill as the default for standalone actions with room to breathe, including primary calls to action and prominent secondary actions such as **Review salary update**. Use a soft upper highlight and a lower cast shadow. Filled primary buttons such as **Open HR workspace** use a clean edge and a shadow beneath the button. On press, reduce the cast shadow and make the surface feel recessed. Keep the keyboard focus ring distinct from the resting edge.

Use rounded rectangular buttons where straight edges help controls align or group, such as compact table actions, toolbar groups, and form controls that sit beside inputs. Keep low-emphasis navigation and in-text actions as ghost buttons or links. Choose the treatment based on the action’s role and its neighbors. Verify the resting, hover, pressed, focus, and disabled states in both themes.

Use official source-owned shadcn components with Radix for UI controls and component surfaces as screens are updated. Map the semantic variables to Tailwind v4 utilities with `@theme inline` and use the existing root `data-theme` state for dark mode. Reconcile the legacy role names before replacing runtime tokens, especially `--surface` versus `--card` and the old `--border` versus `--input`. Configure raised, recessed, and flat treatments centrally in the shared component styles.

Use Button, Field with Input or Select, Table, Tabs, Sidebar, Dialog, Sheet, AlertDialog, Alert, Empty, Skeleton, and Spinner where their semantics fit. Use Chart for compatible visualizations and retain the shared pay range renderer and exact-value table. Preserve existing keyboard behavior, focus restoration, validation, and loading geometry during adoption.

| Component | Visual and interaction rules |
| --- | --- |
| Button | Use a solid fill for the primary action. Follow the button shape and depth guidance above. Busy preserves button width, shows a concise progress label, and guards the action. Disabled and read-only states retain readable labels and show the appropriate state. |
| Filters and search | Put labeled fields inside a quiet inset group. The shared `SelectField` uses Radix Select for country, department, job title, and page size, with visible labels, type-ahead, arrow keys, Escape, and focus restoration. Keep previous rows visible during refresh with an explicit status. Show a clear no-results message and retain rows with Retry after a failed refresh. |
| Salary drawer | Open from the right at 432 px on desktop with rounded leading corners and a soft shadow. Use a full-width sheet on narrow screens. Keep the surface opaque, with a visible title, sticky actions, inline validation, and focus restoration to Edit salary. Keep the entered amount visible during errors and show success after the save is confirmed. |
| Charts and tables | Keep scales and labels stable during refreshes. Use a horizontal band from minimum to maximum, a diamond for the median, and the exact-values table for keyboard and touch access. Preserve currency separation and use a visible label for missing pay. |
| Ask about pay | Use a flat working surface and make useful example questions individually pressable with quiet shared button variants. Keep tool activity and answer text readable during a stream. Announce meaningful status changes in batches and keep already received content visible on interruption. |

| Surface | Application |
| --- | --- |
| Public and sign-in | Raise the product preview or sign-in surface. Recess editable fields and keep the workspace action visually direct. |
| Employees and Rules | Group results in one work surface. Use recessed search and filter controls with clean table rows and an opaque editor sheet. |
| Salary Insights and Saved reports | Give the main report shallow depth. Use fine internal rules, tabular figures, and the periwinkle range with orchid median. |
| Ask about pay and Admin | Use a recessed composer or filter group, flat conversation and trace content, and shared overlay elevation for focused dialogs. |

### Compensation rules and employee editing

Compensation rules are a live workspace section. The rule list uses the established inset filters and a single continuous list with country, currency, version, and active status. A rule editor pairs the reusable definition with an explicitly unsaved annual calculation preview. Component rows expose readable names and stable codes, category, fixed amount or percentage of annual basic pay, guaranteed/target commitment, and cost inclusion. Use the shared palette, field geometry, and dropdown behavior.

Inspect immutable versions through a version selector. Entering edit mode never publishes or submits a form. Publishing requires a deliberate save after a change, creates a new version, and leaves existing packages attached to their saved version. Inactive rules remain inspectable and can be reactivated.

The employee Compensation action opens a 680 px right drawer, becoming full width on narrow screens. Its header and actions remain visible while the content scrolls. The saved package, entered basic pay, applicable rule, and before/after preview stay separate. Calculated lines explain their formula. Overrides expose the original calculation, the entered amount, and a required reason. The Equity section shows the selected calendar year, saved cash and benefits, annual equity, guaranteed CTC, and CTC including targets. Award valuation and annual allocation have separate labels and currencies. Missing allocations remain visible as incomplete.

The drawer puts guaranteed and target costs at the top beside an expandable saved breakdown. Editable rule components share one list, with short field labels and a multiline reason for overrides. A successful preview moves focus to the review and makes Save the primary action. Any input change invalidates that preview. A confirmed save updates only the matching row and preserves search, filters, page, and table scroll. Conflicts retain entries and offer an explicit reload. Discarding requires confirmation. Native modal dialogs contain focus, support Escape and restore the trigger. Shared dropdown portals mount inside the open drawer. Date entry uses the native date input for this English-only iteration, with date-only storage and a typed entry path. Saves apply immediately and accept today or earlier dates.

Seeded packages use clearly named demo country rules and components. Each old amount is interpreted as the original total cost and is preserved exactly through a synthetic split. Fixed and percentage figures represent example company policies, not statutory calculations.

### Theme preference behavior

The signed-in workspace has a persistent sidebar and top navbar with the current section, theme control, HR identity, and sign-out action. Desktop navigation collapses to icons. Below 1100 px, a modal navigation drawer supports Escape, focus containment, and focus restoration. Overview shows live workforce coverage and links into country reports. Activity is labeled as a preview.

The workspace shell uses straight outer edges where the sticky navbar and sidebar meet. A hairline and inset highlight define the seam. The violet porcelain sidebar has a diagonal tonal facet at its foot and a recessed current-page state. Rounded profiles give controls their tactile shape. Keep route labels upright and the active styling tied to the route. The slimmer navbar carries the current section, theme switch, account, and sign out. Use raised pill or circular controls for its utility actions. Keep the drawer in the same material and preserve Escape, focus return, and reduced-motion behavior.

Salary insights keeps the selected view, workforce filters, reporting period, and payroll drill-down in the URL. Each currency panel presents coverage, the chart, the selected group's figures, and an exact-values table from the same response. Horizontal charts use the range and median tokens. Cost and equity series use periwinkle and neutral chart roles with text legends. Payroll tiles show the distribution among visible groups, with shares computed against the full filtered currency total. On narrow screens, the shared select replaces the view links, charts stack their labels, and exact values become labeled rows. The equity chart owns its horizontal scroll when the selected years exceed the available width.

Each insights view states the question it answers. Definitions sit beside controls, legends, and table values, with a column glossary on narrow screens. Preview values follow pointer or keyboard focus beside the chart mark. Click or tap pins the card, and Escape returns focus to the mark. The panel keeps the report's interpretation and exact table visible independently of the card.

Resolve the saved preference before first paint and follow the device theme when no choice is saved. Apply `data-theme` and `color-scheme` together. Keep the switch labeled **Dark theme**, expose its checked state, and persist changes.

Crossfade the outgoing page snapshot over 240 ms using the browser View Transition API, applying all theme tokens together underneath. Fade opacity with no page movement. If another toggle arrives, finish the outgoing transition and apply the latest choice immediately. Browsers without this API transition surface, text, border, and shadow colors over 220 ms. Keyboard and reduced-motion switches apply immediately. Preserve the pre-paint preference so reloads start in the chosen theme.

The directory scrolls with the page and keeps column headers visible beneath the workspace bar on desktop. Below 700 px, labeled employee cards place the compensation amount beside its View action. Page size defaults to 10, with 25 and 50 as options. Changing pages returns focus to the results. Initial loads, pagination, filters, and retries show skeletons in the shape of the results. Rows, counts, and pagination metadata appear together from the same response. Keep a screen-reader loading status outside busy results and keep skeletons static under reduced motion.

### Motion

Use `cubic-bezier(0.23, 1, 0.32, 1)` for fast feedback and `cubic-bezier(0.32, 0.72, 0, 1)` for drawers. Animate transform and opacity on individual elements. Use CSS transitions for interactions that can reverse. A drawer closing during entry should reverse immediately from its current position.

| Trigger | Treatment | Timing |
| --- | --- | --- |
| Pointer press | Change the control fill, returning to rest on release | 110 ms |
| Popover | Opacity and `scale(0.97 → 1)` from the trigger | 150 ms in, 100 ms out |
| Salary drawer | Translate from the edge with a separate backdrop fade | 240 ms in, 170 ms out |
| Save confirmation | Small opacity entrance for the confirmed status | 150 ms |
| Explicit chart grouping change | Crossfade the plot as a single layer | 150 ms |
| Keyboard actions, filtering, pagination, streamed text | Render the new state immediately and keep focus or scroll anchored | 0 ms |

With reduced motion, show the same states, remove translations and scale changes, and keep only short opacity changes that aid comprehension. Gate hover motion to fine pointers. [W3C guidance on interaction motion](https://www.w3.org/WAI/WCAG22/Understanding/animation-from-interactions.html)

### Landing illustration

Use the periwinkle range and orchid median diamond in a recessed track on a raised report surface. Keep chart geometry and labels clear at narrow widths. Label fictional figures as demo data.

## Do's and Don'ts

- Spend the strongest contrast and largest type on the primary task.
- Keep transitions interruptible, focus visible, and salary values readable throughout data updates.
- Verify light and dark system themes, forced colors, reduced motion, rapid switch reversal, keyboard control, 200% zoom, and 320 px width when the theme is implemented. Check long names and currency values with a missing salary, a loading table, and a failed save.

### Agent workspace

Keep the conversation list beside a viewport-height transcript on desktop, with a compact heading and a persistent bottom composer. On narrow screens, use a compact horizontal conversation list above the transcript. Use the workspace surface and accent tokens. Keep report activity expandable and put the exact-value report link beside the saved evidence it verifies. Follow new messages while the reader is at the end of the transcript and preserve their position while they review earlier messages.

Adopting a new conversation ID updates the URL without replacing the live stream or reloading history. Enter sends, Shift+Enter inserts a line, and IME composition never submits. Keep the composer editable during generation so HR can draft the next question; only one request may be submitted per conversation. Interrupted turns retain a readable outcome and recovery action rather than an empty assistant message.

Activity uses actual execution events for the orchestrator, Pay Analyst, report validation tools, Answer Writer, and final verification. Pair tool start and completion by call ID. Show elapsed time, named handoffs, tool details, and model timing and usage when available. Expand activity during execution and keep it available after completion and when a saved chat is reopened. Private model reasoning is never displayed.

Cache the conversation list and recently visited threads in memory for the current authenticated session. Show cached content immediately, preserve drafts, deduplicate concurrent reads, and revalidate expired entries. Clear the cache when the authentication session changes; do not persist salary chats in browser storage. Invalidate deleted chats and prevent late requests from restoring evicted data. A chat's Delete action offers Undo; running chats must be stopped first. Deletion hides the conversation and its runs from normal reads while preserving durable records for restoration.

Render interactive charts directly from each verified report snapshot using the shared `InsightChart`, `SelectField`, and anchored detail primitives. Support average/median comparison and individual pay or headcount measures, with highest/lowest/name sorting. Keep currencies separate, expose exact values on hover, keyboard focus, or pinned click/tap, and retain the exact-value table and source revision. Reuse this visualization on Open report with its fresh data. Do not invent historical series or statistics absent from the evidence.

The prompt editor uses the workspace form controls and unsaved-change dialog. Use monospaced prompt text and a side-by-side review of the saved draft and published version, with stacked panels on narrow screens. Publish is a separate action after review.

### Saved report library

Saved reports are independent, owned snapshots copied from completed server-side report evidence. Deleting the source chat does not delete its saved reports. Preserve generation time, revision, answer summary, exact figures and chart preferences. Save once per source run; repeated saves return the existing snapshot. Metadata editing changes only title and description. Saved reports have their own Delete and Undo lifecycle. Reuse shared report charts and exact-value tables; Open current report reads fresh data separately. Search and type filtering use the canonical SelectField, and mutations retain form contents on errors. Plans live in `.codex/saved-reports-01-backend-and-storage.md` and `.codex/saved-reports-02-ui-and-verification.md`.

### Chat and saved-report density

The agent workspace uses a compact product variant of the workspace surfaces: 16 px panels and report frames and 12 px action and control corners. Keep the global palette and Instrument Sans typography. Conversations have single-line titles with an end fade, a quiet adjacent Delete action and full-title previews on hover or keyboard focus. The report title and one right-aligned Open/Save/View toolbar precede the chart; actions never fall below the plot. Use neutral report surfaces rather than another large tinted panel. On wide screens, put the source report beside the conversation so the transcript can stay in view. On narrower screens, open the source from its answer in a labeled sheet and return focus to the answer link on close. Use a themed recessed Report activity disclosure with a visible keyboard focus ring.

The bottom composer owns one bordered frame with the textarea and Send/Stop action integrated inside it. Keep its visible label accessible but visually quiet, preserve immediate keyboard submission and reserve pointer press feedback for pointer use. Mobile input text is 16 px and action targets are at least 44 px.

Saved reports uses one aligned search/type/action bar, a two-column desktop library and a single mobile column. Card metadata and Delete share a separated footer. Report details use clear title/summary/date hierarchy, aligned source/current links and a separate destructive action. The save dialog places its primary/secondary actions in one footer. Use the shared theme tokens, reduced-motion behavior and canonical SelectField; no marketing hero motion, new fonts or theme replacement belong in these task-focused screens.

Chat exchanges use a consistent spacing rhythm: 28 px between desktop turns, 20 px between user and assistant within an exchange, 8 px between assistant identity and content, and 20 px before the report card. Report padding is 20 px, with 16 px control/section separation. Mobile uses 24/16 px turn/exchange spacing and 16 px report padding. User bubble paragraphs have no extra margins. The composer is separated from the scroll area by 16 px on desktop and 12 px on mobile.

### Removal confirmations

All Delete and Remove actions use `useDeleteConfirmation` and `delete-confirmation.css`. Name the item and explain the actual consequence: chat deletion preserves saved reports; report deletion preserves the original chat; compensation component and equity row removal affects the current draft until publication or saving. Keep existing Undo for chats and reports. Use a native modal alert dialog with Cancel initially focused, Escape to cancel, focus restoration, a busy guard against duplicate requests, and inline errors that retain the confirmation for retry. Use contextual icons and labels, compact spacing, and full-width mobile footer actions. Draft removals use a warning icon; persisted deletions use the danger treatment.


### Agent administration

Prompt catalog retains the existing two-role draft/review/publish workflow. Agent observability is a separate permission-controlled run table and trace detail. Read runs independently of source chat visibility; show a deleted-source badge instead of a broken link. Preserve historical prompt version references, nullable token usage, explicit status labels, selectable events and expandable tool evidence. Reuse workspace surfaces, typography, SelectField and narrow-screen stacking.

### Workforce overview

The Overview opens with one connected, asymmetrical porcelain composition. Set the base-pay coverage percentage and its denominator beside a horizontal workforce rail. Divide the rail into three exclusive categories: saved package basic pay, recorded salary only, and missing base pay. Size each segment from live counts and give missing pay a recognizable pattern as well as a label. Keep exact counts readable outside segments that are too narrow for text.

Run a thin periwinkle connector from the missing-pay segment to a slightly offset, raised follow-up panel. Show the total needing attention and up to three countries with the most missing records. Each country links to its filtered employee directory. Use the raised **Review missing pay** button for the full missing-pay cohort. Give the summary and follow-up surfaces the soft upper highlight and cast shadow used on the landing page. Keep text and controls level and the workspace navigation quiet. Carry the same hierarchy into dark mode.

Place **Pay coverage by country** immediately below, with flat rows, a shared chart scale, and aligned exact counts. Default to **People** and retain **Share** for proportional comparison. Use shadcn Card, Chart, Table, Toggle Group, and Button, drawing the rail and connector from the live data. On narrow screens, stack the summary, follow-up, and country breakdown in reading order. Keep the connector decorative and keyboard selection immediate, and honor reduced motion.

Distinguish loading, error with retry, all pay recorded, and no employees states. Show the missing-pay connector and action when records need attention. Use the existing Overview data and directory filters. The approved light-mode concept illustrates composition and depth with fictional counts.

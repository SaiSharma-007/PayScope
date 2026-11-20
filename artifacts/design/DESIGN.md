---
version: alpha
name: PayScope
description: A soft, rounded workspace for employee pay and salary analytics with layered panels and fluid accents.
colors:
  canvas: "#F4F0FA"
  canvas-dark: "#181326"
  surface: "#FFFDFD"
  surface-dark: "#221B34"
  surface-subtle: "#ECE6F7"
  surface-subtle-dark: "#302542"
  foreground: "#211735"
  foreground-dark: "#F5F0FF"
  muted: "#5A4D70"
  muted-dark: "#CABFD9"
  border: "#504264"
  border-dark: "#A296B9"
  divider: "#D5CBDF"
  divider-dark: "#514560"
  primary: "#4D35C5"
  primary-dark: "#CBBEFF"
  on-primary: "#FFFFFF"
  on-primary-dark: "#25174A"
  focus: "#6441D1"
  focus-dark: "#BCA8FF"
  range: "#694FD0"
  range-dark: "#B59BFA"
  median: "#9A5E12"
  median-dark: "#FFD477"
  highlight: "#F8DD7C"
  highlight-dark: "#FFD477"
  on-highlight: "#302310"
  success: "#206447"
  success-dark: "#8DDBB3"
  warning: "#83510D"
  warning-dark: "#FFD477"
  danger: "#A12A4B"
  danger-dark: "#FF9EB8"
  shadow: "#2B2040"
  shadow-dark: "#100B1A"
  wash-start: "#DCCEFF"
  wash-start-dark: "#39275F"
  wash-middle: "#EEE0F1"
  wash-middle-dark: "#4B3067"
  wash-end: "#FBDAB8"
  wash-end-dark: "#67454E"
  liquid-violet: "#AA89EC"
  liquid-violet-dark: "#8263C9"
  liquid-amber: "#F4B97F"
  liquid-amber-dark: "#A96C55"
typography:
  display:
    fontFamily: "Instrument Sans, system-ui, sans-serif"
  sans:
    fontFamily: "Instrument Sans, system-ui, sans-serif"
  mono:
    fontFamily: "IBM Plex Mono, ui-monospace, monospace"
rounded:
  DEFAULT: "0.875rem"
  field: "0.875rem"
  panel: "1.75rem"
  inset: "1.25rem"
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
  app-shell: { backgroundColor: "{colors.canvas}", textColor: "{colors.foreground}", typography: "{typography.sans}" }
  app-shell-dark: { backgroundColor: "{colors.canvas-dark}", textColor: "{colors.foreground-dark}" }
  button-primary: { backgroundColor: "{colors.primary}", textColor: "{colors.on-primary}", rounded: "{rounded.DEFAULT}", padding: "{spacing.sm}" }
  button-primary-dark: { backgroundColor: "{colors.primary-dark}", textColor: "{colors.on-primary-dark}" }
  input: { backgroundColor: "{colors.surface}", textColor: "{colors.foreground}", rounded: "{rounded.field}" }
  input-dark: { backgroundColor: "{colors.surface-dark}", textColor: "{colors.foreground-dark}" }
  table-header: { backgroundColor: "{colors.surface-subtle}", textColor: "{colors.muted}" }
  table-header-dark: { backgroundColor: "{colors.surface-subtle-dark}", textColor: "{colors.muted-dark}" }
  range-band: { backgroundColor: "{colors.range}" }
  range-band-dark: { backgroundColor: "{colors.range-dark}" }
  median-marker: { backgroundColor: "{colors.median}" }
  median-marker-dark: { backgroundColor: "{colors.median-dark}" }
  highlighted-figure: { backgroundColor: "{colors.highlight}", textColor: "{colors.on-highlight}", typography: "{typography.mono}" }
  highlighted-figure-dark: { backgroundColor: "{colors.highlight-dark}", textColor: "{colors.on-highlight}" }
  drawer: { backgroundColor: "{colors.surface}", textColor: "{colors.foreground}", width: "{spacing.drawer-width}", rounded: "{rounded.panel}" }
  drawer-dark: { backgroundColor: "{colors.surface-dark}", textColor: "{colors.foreground-dark}" }
  theme-switch: { backgroundColor: "{colors.surface-subtle}", rounded: "{rounded.pill}" }
  theme-switch-dark: { backgroundColor: "{colors.surface-subtle-dark}" }
  status-success: { textColor: "{colors.success}" }
  status-success-dark: { textColor: "{colors.success-dark}" }
  status-warning: { textColor: "{colors.warning}" }
  status-warning-dark: { textColor: "{colors.warning-dark}" }
  status-error: { textColor: "{colors.danger}" }
  status-error-dark: { textColor: "{colors.danger-dark}" }
---

# PayScope Theme

## Overview

PayScope helps an HR manager find an employee, update annual base pay, and compare pay across countries, departments, and job titles. The visual direction follows the supplied dashboard reference's soft panels, generous curves, inset controls, and clear grouping. Large rounded surfaces float above a tinted canvas. Smaller surfaces group related actions inside them, while readable type and aligned figures establish hierarchy.

The reference guides spatial arrangement, depth, and control treatment. PayScope uses lilac and plum themes, with amber identifying the median or a selected figure. The current direction adopts soft neumorphic depth across the workspace. Light borders and tonal differences keep interactive boundaries visible in both themes.

The public landing page can be expressive. Its signature is a fixed salary-range illustration over a slowly moving liquid wash. Use fictional examples and label them as demo data. Sign-in, Employees, Pay Analytics, and Ask about pay share the rounded surfaces, aligned controls, and soft lighting. English is the current UI language. Currency remains explicit and follows the record, regardless of display locale.

This document owns the visual specification. Runtime tokens live in the repository's `ui/src/styles/tokens.css`, with a single semantic CSS variable per role and theme overrides on the root `data-theme` attribute. Components use the unsuffixed names and resolve the `-dark` values in the dark override. Shared controls and surfaces consume those variables. Keep this specification and the runtime tokens aligned when changing the palette. The existing frontend requirements govern workflow, validation, recovery, and streaming behavior. [Frontend requirements](../requirements/frontend-requirements.md)

## Colors

| Role | Application |
| --- | --- |
| `canvas`, `surface`, `surface-subtle` | App background, reading and editing surfaces, and quiet selected or hover fills. |
| `foreground`, `muted` | Primary copy and secondary labels. Use muted text for context that still needs to be legible. |
| `border`, `divider` | A fine visible boundary for inputs and meaningful controls. Use the quieter divider for row separators and panel edges, with tonal separation establishing the larger surfaces. |
| `primary`, `on-primary` | One main action per panel, including Sign in or Save salary. |
| `highlight`, `on-highlight` | Selected figures and compact annotations. Pair the color with a label or marker shape. |
| `range`, `median` | Violet range bar and distinct median diamond. Give the diamond a 2 px surface-colored outline where it crosses the bar. |
| `success`, `warning`, `danger` | Status icons and adjacent text. Keep status backgrounds quiet and use explicit messages. |
| `focus` | 2 px focus ring with 2 px of offset. The offset exposes the surrounding surface on filled controls. |

Use `linear-gradient(138deg, var(--wash-start) 0%, var(--wash-middle) 48%, var(--wash-end) 100%)` behind the landing illustration and within the assistant's small decorative emblem. Keep text and chart labels on solid surfaces. Use the gradient on one expressive area per screen and retain a solid primary fill on Save salary.

Verify at least 4.5:1 for normal text and 3:1 for meaningful control boundaries, focus indicators, and chart marks against adjacent colors. Test both themes and use system colors in forced-colors mode. [WCAG text contrast](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html) · [WCAG non-text contrast](https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html)

## Typography

| Role | Family and scale |
| --- | --- |
| Landing headline | Instrument Sans 600, `clamp(2.75rem, 5vw, 4.5rem)`, line height 1.06, tracking -0.04em. |
| Workspace heading | Instrument Sans 600, 30/36 px desktop and 26/32 px narrow, tracking -0.025em. |
| Panel heading | Instrument Sans 600, 17/24 px. Align the heading and its relevant action on one row. |
| Body, forms, and controls | Instrument Sans 400–600, 15/22 px. Use 16 px inputs on touch widths. |
| Table secondary labels | Instrument Sans 500, 13/18 px. |
| IDs and table figures | IBM Plex Mono 500, 13/19 px with tabular numerals. Right-align monetary values and keep the currency code visible. |
| Report headline figure | Instrument Sans 600, 36/40 px with tabular numerals. Put the currency and metric label beside the value. |

Use sentence case for controls and headers. Format amounts to two decimal places with grouping appropriate to the active locale. Use the stored decimal string as the formatting input and keep the full label or figure available at narrow widths.

## Layout

Use a 6 px spacing rhythm. Center the desktop shell inside `page-max` with 30 px gutters, 24 px panel gaps, and a persistent 216 px navigation rail. Give major panels 24 px padding. Use 18 px inside smaller inset groups. Below 960 px, use a horizontal header with Employees and Pay Analytics as the primary destinations. Below 720 px, use 18 px outer gutters, 18 px panel padding, and stacked filter controls.

Use a twelve-column workspace grid. Employees uses one full-width directory panel. Pay Analytics uses an eight-column report panel and a four-column Ask about pay panel at widths of 1200 px and above. From 960 through 1199 px, put both panels on separate full-width rows. The contents determine panel height. Keep the whole page naturally scrollable.

### Employee workspace

Put the title, matching result count, and filter controls at the top of a rounded directory panel. Keep the directory as a continuous table with a calm header, 54 px desktop rows, aligned monetary columns, and a small Edit salary action per row. Show a missing salary with an explicit label. Keep employee identity, salary, and Edit salary visible in the narrow layout, with country, department, and job title in labeled rows.

Group pagination with the table footer. Opening the salary drawer preserves the current search, filters, page, and underlying row position. Reserve table geometry while loading, and show errors and Retry within the panel that requested the data.

### Pay Analytics workspace

Place filters and the currency selector across the report panel's top. Use the report's actual selected currency and population in the header. Underneath, stack the range chart and exact-values table. Put Ask about pay in a neighboring panel with a compact emblem, a labeled question field, useful example questions, and an answer area that grows with the response.

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

Use a soft directional shadow beneath each major panel, a delicate top highlight, and a quieter shadow for nested controls. Resolve shadow colors from the theme's `shadow` token with alpha. Light theme panels sit on the tinted canvas. Dark theme panels use brighter surface tones and a restrained top edge so their grouping remains visible.

| Surface | Light theme | Dark theme |
| --- | --- | --- |
| Major panel | `0 12px 32px rgb(43 32 64 / 0.08)`, plus `inset 0 1px 0 rgb(255 255 255 / 0.8)` | `0 12px 32px rgb(16 11 26 / 0.26)`, plus `inset 0 1px 0 rgb(245 240 255 / 0.08)` |
| Raised inner control | `0 4px 12px rgb(43 32 64 / 0.07)` | `0 4px 12px rgb(16 11 26 / 0.22)` |
| Inset track | `inset 0 2px 4px rgb(43 32 64 / 0.08)` | `inset 0 2px 4px rgb(16 11 26 / 0.28)` |

Apply raised inner controls to theme switches, useful suggestion buttons, and compact action groups. Use flat inset surfaces for table headers and filter groups. Keep inputs, focus rings, and status marks legible through color and visible boundaries. Drawer backdrops dim the surrounding content while the drawer stays opaque.

## Shapes

Use 28 px outer panel corners, 20 px inset group corners, and 14 px field and button corners. Pills suit the theme track, currency selector, and compact statuses. Give grouped controls consistent heights and a visible separation between their hit areas. Use a consistent 1.75 px icon stroke with 20 px control icons and 16 px inline icons. Give touch controls at least a 44 px target.

## Components

| Component | Visual and interaction rules |
| --- | --- |
| Button | Primary uses a solid fill and a small soft shadow. Secondary uses a raised surface with a fine boundary. A hover on fine pointers changes the fill subtly. Pressed reduces scale to `0.98`. Busy preserves button width, shows a concise progress label, and guards the action. Disabled and read-only states retain readable labels and show the appropriate state. |
| Filters and search | Put labeled fields inside a quiet inset group. The shared `SelectField` uses Radix Select for country, department, job title, and page size, with visible labels, type-ahead, arrow keys, Escape, and focus restoration. Keep previous rows visible during refresh with an explicit status. Show a clear no-results message and retain rows with Retry after a failed refresh. |
| Salary drawer | Open from the right at 432 px on desktop with rounded leading corners and a soft shadow. Use a full-width sheet on narrow screens. Keep the surface opaque, with a visible title, sticky actions, inline validation, and focus restoration to Edit salary. Keep the entered amount visible during errors and show success after the save is confirmed. |
| Charts and tables | Keep scales and labels stable during refreshes. Use a horizontal band from minimum to maximum, a diamond for the median, and the exact-values table for keyboard and touch access. Preserve currency separation and use a visible label for missing pay. |
| Ask about pay | Use a rounded outer panel and a small gradient emblem. Make useful example questions individually pressable in softly raised rows. Keep tool activity and answer text readable during a stream. Announce meaningful status changes in batches and keep already received content visible on interruption. |

### Compensation rules and employee editing

Compensation rules are a live workspace section. The rule list uses the established inset filters and a single continuous list with country, currency, version, and active status. A rule editor pairs the reusable definition with an explicitly unsaved annual calculation preview. Component rows expose readable names and stable codes, category, fixed amount or percentage of annual basic pay, guaranteed/target commitment, and cost inclusion. Use the existing palette, field geometry, and shared dropdown owner rather than another control system.

Inspect immutable versions through a version selector. Entering edit mode never publishes or submits a form. Publishing requires a deliberate save after a change, creates a new version, and leaves existing packages attached to their saved version. Inactive rules remain inspectable and can be reactivated.

The employee Compensation action opens a 680 px right drawer, becoming full width on narrow screens. Its header and actions remain visible while the content scrolls. The saved package, entered basic pay, applicable rule, and before/after preview stay separate. Calculated lines explain their formula. Overrides expose the original calculation, the entered amount, and a required reason. The Equity section shows the selected calendar year, saved cash and benefits, annual equity, guaranteed CTC, and CTC including targets. Award valuation and annual allocation have separate labels and currencies. Missing allocations remain visible as incomplete.

The drawer puts guaranteed and target costs at the top beside an expandable saved breakdown. Editable rule components share one list, with short field labels and a multiline reason for overrides. A successful preview moves focus to the review and makes Save the primary action. Any input change invalidates that preview. A confirmed save updates only the matching row and preserves search, filters, page, and table scroll. Conflicts retain entries and offer an explicit reload. Discarding requires confirmation. Native modal dialogs contain focus, support Escape and restore the trigger. Shared dropdown portals mount inside the open drawer. Date entry uses the native date input for this English-only iteration, with date-only storage and a typed entry path. Saves apply immediately and accept today or earlier dates.

Seeded packages use clearly named demo country rules and components. Each old amount is interpreted as the original total cost and is preserved exactly through a synthetic split. Fixed and percentage figures represent example company policies, not statutory calculations.

### Theme preference behavior

The signed-in workspace has a persistent sidebar and top navbar with the current section, theme control, HR identity, and sign-out action. Desktop navigation collapses to icons. Below 1100 px, a modal navigation drawer supports Escape, focus containment, and focus restoration. Overview shows live workforce coverage and links into country reports. Salary insights separates monetary comparisons by currency, pairs selectable range charts with exact-value tables, and shows country cost composition with expandable components. Activity is labeled as a preview. Settings is labeled Soon and unavailable.

Resolve the saved preference before first paint and follow the device theme when no choice is saved. Apply `data-theme` and `color-scheme` together. Keep the switch labeled **Dark theme**, expose its checked state, and persist changes.

Crossfade the outgoing page snapshot over 240 ms using the browser View Transition API, applying all theme tokens together underneath. Fade opacity with no page movement. If another toggle arrives, finish the outgoing transition and apply the latest choice immediately. Browsers without this API transition surface, text, border, and shadow colors over 220 ms. Keyboard and reduced-motion switches apply immediately. Preserve the pre-paint preference so reloads start in the chosen theme.

The directory scrolls with the page and keeps column headers visible beneath the workspace bar on desktop. Below 700 px, labeled employee cards place the compensation amount beside its View action. Page size defaults to 10, with 25 and 50 as options. Changing pages returns focus to the results. Initial loads, pagination, filters, and retries show skeletons in the shape of the results. Rows, counts, and pagination metadata appear together from the same response. Keep a screen-reader loading status outside busy results and keep skeletons static under reduced motion.

### Motion

Use `cubic-bezier(0.23, 1, 0.32, 1)` for fast feedback and `cubic-bezier(0.32, 0.72, 0, 1)` for drawers. Animate transform and opacity on individual elements. Use CSS transitions for interactions that can reverse. A drawer closing during entry should reverse immediately from its current position.

| Trigger | Treatment | Timing |
| --- | --- | --- |
| Pointer press | `scale(0.98)`, returning to rest on release | 110 ms |
| Popover | Opacity and `scale(0.97 → 1)` from the trigger | 150 ms in, 100 ms out |
| Salary drawer | Translate from the edge with a separate backdrop fade | 240 ms in, 170 ms out |
| Save confirmation | Small opacity entrance for the confirmed status | 150 ms |
| Explicit chart grouping change | Crossfade the plot as a single layer | 150 ms |
| Keyboard actions, filtering, pagination, streamed text | Render the new state immediately and keep focus or scroll anchored | 0 ms |

With reduced motion, show the same states, remove translations and scale changes, and keep only short opacity changes that aid comprehension. Gate hover motion to fine pointers. [W3C guidance on interaction motion](https://www.w3.org/WAI/WCAG22/Understanding/animation-from-interactions.html)

### Liquid illustration

Place two elliptical radial gradients inside the landing illustration. Center `liquid-violet` at 32% 45% and `liquid-amber` at 72% 54%. Leave the chart geometry fixed while the color pools slide past each other. Run the drift once on the initial landing view and settle after 3.6 seconds. Use the settled image on narrow screens and under reduced motion. Clip the decorative layers to the illustration and keep them out of the accessibility tree and pointer hit testing.

Use each color as a fixed radial gradient that fades to transparent by 72%. Hold its shape and gradient stops while moving the layer with `transform`. Example keyframes for the violet layer:

```css
@keyframes liquid-drift {
  0% { transform: translate3d(-7%, 4%, 0) scale(1.04); }
  52% { transform: translate3d(5%, -4%, 0) scale(1.10); }
  100% { transform: translate3d(0, 0, 0) scale(1); }
}
```

Give the amber layer opposite offsets, use `cubic-bezier(0.45, 0, 0.55, 1)` for the drift, and start both layers at the same time. Keep motion isolated to those layers so chart, page scrolling, and form interaction stay stable. The assistant emblem can use the same settled gradient and play a single 180 ms opacity acknowledgement when a question is accepted. Its text status follows actual execution events.

## Do's and Don'ts

- Spend the strongest contrast and largest type on the primary task. Let the landing illustration carry the decorative motion.
- Keep transitions interruptible, focus visible, and salary values readable throughout data updates.
- Verify light and dark system themes, forced colors, reduced motion, rapid switch reversal, keyboard control, 200% zoom, and 320 px width when the theme is implemented. Check long names and currency values with a missing salary, a loading table, and a failed save.

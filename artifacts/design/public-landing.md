# PayScope public landing page

The public page introduces PayScope to HR managers and assessment reviewers. The selected composition leads an illustrative pay question through its answer and supporting report, then offers the authenticated workspace.

## Composition and theme

The opening pairs **Every pay answer should show its numbers.** with an **Open HR workspace** action and three offset surfaces labeled Question, Answer, and Annual base pay. The surfaces follow the approved porcelain neumorphic treatment with violet-neutral depth, periwinkle actions and range, and orchid reserved for the median. The steps stack in reading order below 768 px, and the geometry is mirrored in light and dark. [Theme specification](DESIGN.md)

The example asks for median annual base pay for Engineering in India. It identifies the figures as illustrative and uses the same local INR fixture to display ₹8,40,000 minimum, ₹16,80,000 median, and ₹29,00,000 maximum. The numeric scale places the diamond at about 40.8% of the range. The exact-value table accompanies the chart. **Show how the answer was checked** expands the sample filter and verification steps.

Below the opening, three short steps describe the workflow of finding an employee, updating annual base pay, and checking the figures in Salary Insights. The workspace link opens sign-in for signed-out users and Employees for active sessions. The example itself runs locally.

## shadcn and motion

The public header uses shadcn NavigationMenu, Button, and Switch. MessageScroller, Message, and Bubble present the question. Card, Chart, Table, and Trace present the answer and its evidence. Tailwind utilities load without preflight, and the new palette is scoped to the landing route. The theme switch uses the existing stored preference and device fallback. [shadcn AI Elements](https://ui.shadcn.com/docs/ai-elements/radix/chat)

The opening enters once over 420 ms with short staggers. Pointer disclosure sends a signal from the answer to the report while revealing the 360 ms range and 160 ms median. Keyboard activation and reduced motion show the final state immediately. Exact values remain available during the animation.

## Acceptance

Check both themes, keyboard focus and disclosure, reduced motion, forced colors, responsive layout down to 320 px, and theme persistence. The example makes no salary or model requests. The signed-out and signed-in links must point to the corresponding existing routes.

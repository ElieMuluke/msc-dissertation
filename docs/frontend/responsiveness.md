# Responsive Layout & Sidebar Design

The AML Compliance Platform frontend is fully optimized to provide an excellent user experience across a wide range of devices and viewport sizes. Responsive behaviors are driven by Tailwind CSS utility classes targeting key breakpoints (`sm`, `md`, `lg`, `xl`), combined with collapsible state panels, a sticky side navigation column, and mobile content prioritizing.

---

## Breakpoint Map & Layout Behavior

| Breakpoint | Viewport Range | Layout Configuration | Description |
|---|---|---|---|
| **Default (Mobile)** | `< 640px` | Single Column Prioritized Stack | The main Workspace (Search/Chat) panel is prioritized and rendered first (`order-1`). The Administration sidebar stacks below it (`order-2`). Spacing is kept neat at `px-4 py-6`. Header title and status indicators are compacted to fit. |
| **`sm` (Tablet Portrait)** | `640px` - `767px` | Nested 2-Column Grid (Admin) | Left administration panel components (`UploadDocs`, `UploadTabular`, `FileManager`, `ManageDatabase`) arrange side-by-side in a 2-column grid. Main search/chat panel flows below. |
| **`md` (Tablet Landscape / Laptop)** | `768px` - `1279px` | Sticky 4/8 Split Grid | Sidebar column layout. The left column spans 4 columns, and the right workspace column spans 8 columns. The left sidebar is sticky and scrolls internally if content overflows. Layout orders swap back to standard (`md:order-1` / `md:order-2`). Chat and citations render side-by-side (60% / 40%). |
| **`xl` (Large Displays)** | `>= 1280px` | Sticky 3/9 Split Grid | Left column spans 3 columns, and the right workspace column spans 9 columns. The left sidebar remains sticky. Chat thread scales to 70% width, leaving 30% for the citation reference panel to prevent text lines from becoming too wide. |

---

## Premium UX Features

### Mobile Order Prioritizing
- Swapped column ordering on mobile screens using Tailwind order utilities (`order-1 md:order-2` on workspace, `order-2 md:order-1` on admin settings). This ensures the primary user function (Query Workspace) renders directly under the header on mobile viewports, keeping configuration settings secondary.

### Compact Status Badges
- **Title**: Collapses from `AML Compliance Platform` to `AML Compliance` on mobile screens (`< sm`) by hiding the `Platform` suffix. Text size is scaled to `text-base` on mobile.
- **Indicators**: Status labels render as constant `DB` and `LLM` abbreviation badges next to their respective connection status dots on all screen sizes to fit neatly on mobile screens and keep clean visual aesthetics.
- Added visual divider (`|`) between indicators to structure connections clearly.

### Column Alignment & Uniform Sizing
- Flex alignment changed to `items-stretch` and `min-w-0` on the sidebar column container.
- Added `min-w-0 w-full` to the outer `<section>` and inner wrappers of all four administrative components. This forces all sidebar cards to stretch to identical widths, and enables CSS Flexbox text truncation on long PDF filenames in the Ingested Corpus, keeping action buttons positioned inside the card boundary.

### Sticky Sidebar with Internal Scroll
- Set `md:sticky md:top-20 md:max-h-[calc(100vh-7rem)] md:overflow-y-auto` on the left administration panel wrapper.
- This anchors the sidebar controls on the desktop viewport so they do not scroll away. If the panels exceed the screen height, they scroll internally using a thin, minimalist Apple-style scrollbar, ensuring the right workspace panel never leaves a blank space below it.

### Collapsible Side Panels
- All four sidebar administration panels support expansion/collapse states managed by local React state:
  1. **Import Documents** (Expanded by default)
  2. **Import Tabular Data** (Expanded by default)
  3. **Ingested Corpus** (Expanded by default)
  4. **Database Control** (Collapsed by default to save space)
- Headers are fully clickable and feature dynamic chevron icons that rotate smoothly (`rotate-180`) on toggle. Collapsing unused modules keeps the workspace layout incredibly clean and focused.

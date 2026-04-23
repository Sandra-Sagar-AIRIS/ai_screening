# AIRIS design system

**Version**: 2.0
**Date**: 2026-04-18
**Framework**: Next.js + Tailwind CSS + shadcn/ui
**Status**: Foundation for Phase 1 MVP

---

## Purpose

This document defines the visual language for AIRIS. Every developer building any module or service must reference this system. The goal is visual consistency across all screens without requiring a dedicated designer on each team.

If a component you need is not listed here, use the closest shadcn/ui primitive and follow the token system. Do not invent new colours, spacing values, or typography scales.

---

## 1. Brand tokens

### Colour palette

AIRIS uses a clean, bright blue palette inspired by modern recruiting platforms. The aesthetic is light, airy, and professional with a soft blue-tinted background. Colours are defined as HSL values for Tailwind's CSS variable system.

**Primary (blue)**: used for primary actions, active states, navigation highlights, sidebar active items.

| Token | HSL | Hex | Usage |
|-------|-----|-----|-------|
| `primary-50` | 213 100% 97% | #EFF6FF | Hover backgrounds, selected row tint, page background tint |
| `primary-100` | 213 93% 93% | #DBEAFE | Light badges, active sidebar item bg, info banners |
| `primary-200` | 213 86% 84% | #BFDBFE | Borders on active elements, toggle track (off) |
| `primary-300` | 213 82% 72% | #93C5FD | Secondary icons, stage progress unfilled |
| `primary-400` | 213 90% 62% | #60A5FA | Link text, active tabs |
| `primary-500` | 213 94% 54% | #3B82F6 | Primary buttons, sidebar active, main accent |
| `primary-600` | 213 97% 46% | #2563EB | Primary button hover |
| `primary-700` | 213 96% 38% | #1D4ED8 | Focus rings, active tab underline |
| `primary-800` | 213 90% 30% | #1E40AF | Dark text on light backgrounds |
| `primary-900` | 213 85% 22% | #1E3A5F | Heading emphasis |

**Neutral (slate)**: used for text, borders, backgrounds, and structural elements.

| Token | HSL | Hex | Usage |
|-------|-----|-----|-------|
| `neutral-0` | 0 0% 100% | #FFFFFF | Card background, sidebar background, topbar background |
| `neutral-50` | 210 40% 97% | #F0F5FA | Page background (light blue tint), table stripes |
| `neutral-100` | 210 30% 94% | #E8EDF4 | Input backgrounds, sidebar hover |
| `neutral-200` | 210 20% 89% | #DEE2E8 | Borders, dividers, card borders |
| `neutral-300` | 210 14% 78% | #BFC4CC | Disabled text, placeholder text |
| `neutral-400` | 210 10% 62% | #949AA4 | Secondary text, icons |
| `neutral-500` | 210 10% 46% | #6B7280 | Body text (secondary) |
| `neutral-600` | 210 12% 36% | #525B67 | Body text (primary) |
| `neutral-700` | 210 14% 26% | #3A4250 | Headings |
| `neutral-800` | 210 18% 18% | #262E3B | Strong emphasis |
| `neutral-900` | 210 22% 10% | #141A23 | Highest contrast text |

**Semantic colours**: used for status, feedback, and alerts.

| Token | Hex | Usage |
|-------|-----|-------|
| `success-50` | #ECFDF5 | Success background |
| `success-500` | #10B981 | Success text, icons, badges |
| `success-700` | #047857 | Success text on light bg |
| `warning-50` | #FFFBEB | Warning background |
| `warning-500` | #F59E0B | Warning text, icons, badges |
| `warning-700` | #B45309 | Warning text on light bg |
| `error-50` | #FEF2F2 | Error background |
| `error-500` | #EF4444 | Error text, icons, validation |
| `error-700` | #B91C1C | Error text on light bg |
| `info-50` | #EFF6FF | Info background |
| `info-500` | #3B82F6 | Info text, icons |

**Pipeline stage colours** (AIRIS-specific — each hiring stage has a distinct colour):

| Token | Hex | Background | Usage |
|-------|-----|-----------|-------|
| `stage-screening` | #10B981 | #ECFDF5 | Phone screening, screening stages |
| `stage-interview` | #3B82F6 | #EFF6FF | Interview, 1st/2nd interview |
| `stage-test` | #8B5CF6 | #F3F0FF | Tests, assessments |
| `stage-offer` | #F59E0B | #FFFBEB | Offer stage |
| `stage-hired` | #EF4444 | #FEF2F2 | Hired, placed |

Stage badges use white text on the solid colour background (e.g. white text on `#10B981` for screening).

**Urgency indicators**:

| Token | Hex | Usage |
|-------|-----|-------|
| `urgency-standard` | #6B7280 | Standard priority badge |
| `urgency-urgent` | #F59E0B | Urgent priority badge |
| `urgency-critical` | #EF4444 | Critical priority badge |

**Star rating**: used for candidate ratings. Stars are `#F59E0B` (filled) and `#DEE2E8` (unfilled). Sizes: 16px inline, 20px in cards.

### Typography

**Font stack**: `'Inter', system-ui, -apple-system, sans-serif`

Inter is used because it was designed for screens, has excellent readability at small sizes, and is available on Google Fonts. Do not use decorative or serif fonts anywhere in the application.

**Type scale** (rem-based, 1rem = 16px):

| Token | Size | Weight | Line height | Usage |
|-------|------|--------|-------------|-------|
| `text-xs` | 0.75rem (12px) | 400 | 1rem | Timestamps, fine print, badge text |
| `text-sm` | 0.875rem (14px) | 400 | 1.25rem | Table cells, secondary labels, form hints |
| `text-base` | 1rem (16px) | 400 | 1.5rem | Body text, form inputs, descriptions |
| `text-lg` | 1.125rem (18px) | 500 | 1.75rem | Card titles, section subheadings |
| `text-xl` | 1.25rem (20px) | 600 | 1.75rem | Page section headers |
| `text-2xl` | 1.5rem (24px) | 600 | 2rem | Page titles |
| `text-3xl` | 1.875rem (30px) | 700 | 2.25rem | Dashboard metric values |

**Rules**:
- Body text is always `neutral-600` on white/light backgrounds.
- Headings are `neutral-800`.
- Never use font weights below 400 or above 700.
- Links are `primary-400` with underline on hover.
- Use sentence case for all headings and labels. Never all-caps except for very short badge text (e.g. 'URGENT').

### Spacing scale

Based on a 4px grid. Use only these values for margins, padding, and gaps.

| Token | Value | Common usage |
|-------|-------|-------------|
| `space-0` | 0px | - |
| `space-0.5` | 2px | Subtle adjustments |
| `space-1` | 4px | Inline icon gaps |
| `space-1.5` | 6px | Tight padding |
| `space-2` | 8px | Badge padding, compact lists |
| `space-3` | 12px | Form field padding, small card padding |
| `space-4` | 16px | Standard padding, gap between elements |
| `space-5` | 20px | Card padding |
| `space-6` | 24px | Section padding |
| `space-8` | 32px | Large section gaps |
| `space-10` | 40px | Page-level vertical spacing |
| `space-12` | 48px | Major section separation |
| `space-16` | 64px | Page margins on large screens |

### Border radius

| Token | Value | Usage |
|-------|-------|-------|
| `rounded-sm` | 4px | Badges, small tags |
| `rounded-md` | 6px | Buttons, inputs, cards |
| `rounded-lg` | 8px | Modals, dropdowns |
| `rounded-xl` | 12px | Large cards, feature sections |
| `rounded-full` | 9999px | Avatars, circular indicators |

Do not mix radius values on the same card. If a card uses `rounded-lg`, elements inside it should use `rounded-md` or smaller.

### Shadows

| Token | Value | Usage |
|-------|-------|-------|
| `shadow-sm` | 0 1px 2px rgba(0,0,0,0.05) | Subtle lift on inputs, small cards |
| `shadow-md` | 0 4px 6px rgba(0,0,0,0.07) | Cards, dropdowns |
| `shadow-lg` | 0 10px 15px rgba(0,0,0,0.1) | Modals, popovers |
| `shadow-none` | none | Flat elements, table rows |

---

## 2. Layout

### Page structure

Every page in AIRIS follows this layout:

```
┌────────────────────────────────────────────────────┐
│ Top bar (fixed, 56px height)                       │
├──────────┬─────────────────────────────────────────┤
│ Sidebar  │ Main content area                       │
│ (240px,  │                                         │
│ fixed)   │ ┌─────────────────────────────────────┐ │
│          │ │ Page header (title + actions)        │ │
│          │ ├─────────────────────────────────────┤ │
│          │ │ Page body                           │ │
│          │ │                                     │ │
│          │ │                                     │ │
│          │ └─────────────────────────────────────┘ │
│          │                                         │
└──────────┴─────────────────────────────────────────┘
```

**Top bar**: white background, bottom border `neutral-200`, contains AIRIS logo (left), global search bar with rounded input (centre), notification bell and user avatar with dropdown (right). Height: 56px.

**Sidebar**: white background (`neutral-0`), light and clean. Contains logo/brand (top), navigation section labelled 'MENU' (middle), a 'GENERAL' section for settings (bottom), and a collapse toggle button at the very bottom. Active navigation item has `primary-500` background with white text and `rounded-lg`. Inactive items are `neutral-600` text with Lucide icons. Width: 240px expanded, 64px collapsed (icon-only mode with circular blue icon backgrounds for active). The collapse toggle is a small `primary-500` circular button with chevron arrows.

**Main content**: `neutral-50` background (light blue-grey tint, not pure white). Cards and content panels are white (`neutral-0`) with `shadow-sm`. Max-width 1280px, centred with `space-8` horizontal padding. On screens below 1024px, sidebar collapses and content fills full width.

**Three-column dashboard layout**: The ATS/dashboard view uses a three-column layout: sidebar (240px) + main content (flexible) + right panel (320px). The right panel contains candidate summaries, inbox messages, or a calendar widget. This right panel scrolls independently and is hidden on screens below 1280px.

### Grid

Use a 12-column CSS grid for page layouts. Common patterns:

- **Dashboard**: 4 metric cards in a row (3 cols each), chart below (12 cols), table below (12 cols).
- **Detail page**: main content (8 cols), sidebar panel (4 cols).
- **List page**: full width table (12 cols) with filters above.
- **Form page**: centred form (6 cols), help text in remaining space.

Gap between grid items: `space-6` (24px).

### Responsive breakpoints

| Breakpoint | Width | Behaviour |
|-----------|-------|-----------|
| `sm` | 640px | Single column, sidebar hidden |
| `md` | 768px | Sidebar icon-only, content fills |
| `lg` | 1024px | Full sidebar, content beside |
| `xl` | 1280px | Content max-width reached |

---

## 3. Components

All components are built on shadcn/ui primitives. Do not build custom components from scratch when a shadcn/ui component exists. Customise via the token system instead.

### Buttons

| Variant | Background | Text | Border | Usage |
|---------|-----------|------|--------|-------|
| Primary | `primary-500` | white | none | Main CTA per page (one per view) |
| Secondary | white | `neutral-700` | `neutral-200` | Secondary actions |
| Ghost | transparent | `neutral-600` | none | Tertiary actions, toolbar items |
| Destructive | `error-500` | white | none | Delete, remove, reject actions |
| Link | transparent | `primary-400` | none | Inline navigation actions |

**Sizes**: `sm` (32px height, `text-sm`), `md` (36px height, `text-sm`), `lg` (40px height, `text-base`).

**Rules**:
- Only one primary button per visible area.
- Destructive actions require a confirmation dialog.
- Buttons always have a visible focus ring (`primary-200`, 2px offset).
- Loading state shows a spinner icon replacing the button text. Button width does not change.

### Form inputs

All inputs use shadcn/ui `Input`, `Select`, `Textarea`, `Checkbox`, `RadioGroup`.

- Height: 36px for single-line inputs.
- Border: `neutral-200`, on focus: `primary-400` with `primary-100` ring.
- Error state: `error-500` border with error message in `text-sm` `error-500` below the input.
- Labels: `text-sm` `neutral-700` font-medium, positioned above the input with `space-1.5` gap.
- Placeholder text: `neutral-300`.
- Disabled: `neutral-100` background, `neutral-300` text, no interaction.

### Cards

Used for dashboard metrics, candidate profiles, and job summaries.

- Background: white.
- Border: `neutral-200`.
- Radius: `rounded-lg`.
- Shadow: `shadow-sm` at rest, `shadow-md` on hover (if clickable).
- Padding: `space-5` (20px).
- Cards that are clickable have `cursor-pointer` and a subtle border colour change on hover (`primary-200`).

### Tables

Used for candidate lists, job lists, recruiter activity.

- Use shadcn/ui `Table` component.
- Header row: `neutral-50` background, `text-sm` `neutral-500` uppercase tracking-wide text.
- Body rows: white background, `neutral-200` bottom border. Alternate row striping with `neutral-50` on even rows.
- Row hover: `primary-50` background.
- Cell padding: `space-3` vertical, `space-4` horizontal.
- Sortable columns show a sort indicator icon (up/down chevrons).
- Always include pagination below the table. Show total count, rows-per-page selector, and page numbers. Active page number uses `primary-500` background with white text, `rounded-md`.
- Each row can have an avatar (candidate photo or initials), a stage indicator, star rating, and a three-dot action menu.
- The three-dot action menu (kebab) opens a dropdown with actions: edit, email, schedule interview, delete. Use shadcn/ui `DropdownMenu`.
- Table/pipeline view toggle: provide a toggle in the top right of candidate list pages to switch between table view and pipeline (Kanban) view.

### Badges and tags

Used for status indicators, skill tags, urgency levels, and pipeline stages.

- Radius: `rounded-sm` for skill tags, `rounded-md` for stage badges.
- Padding: `space-0.5` vertical, `space-2` horizontal.
- Font: `text-xs` font-medium.

**Skill and status badges** (light background, dark text):

| Type | Background | Text |
|------|-----------|------|
| Skill tag | `primary-50` | `primary-700` |
| Status: Active | `success-50` | `success-700` |
| Status: On hold | `warning-50` | `warning-700` |
| Status: Rejected | `error-50` | `error-700` |
| Status: Draft | `neutral-100` | `neutral-500` |
| Urgency: Standard | `neutral-100` | `neutral-600` |
| Urgency: Urgent | `warning-50` | `warning-700` |
| Urgency: Critical | `error-50` | `error-700` |

**Pipeline stage badges** (solid colour, white text): Used in the hiring pipeline table to show which stage a candidate is in, with the candidate count inside.

| Stage | Background | Text |
|-------|-----------|------|
| Screening / Phone screening | `stage-screening` (#10B981) | white |
| Interview | `stage-interview` (#3B82F6) | white |
| Tests / Assessment | `stage-test` (#8B5CF6) | white |
| Offer | `stage-offer` (#F59E0B) | white |
| Hired / Placed | `stage-hired` (#EF4444) | white |

**Stage progress indicator**: A row of small numbered squares (1, 2, 3, 4, 5) showing how far a candidate has progressed. Completed steps use their stage colour; remaining steps are `neutral-200`. Used in candidate summary cards and table rows.

### Pipeline (Kanban board)

The pipeline is the most AIRIS-specific component.

- Board container: horizontal scroll on overflow.
- Column: 280px wide, `neutral-50` background, `rounded-lg`, `space-3` padding.
- Column header: `text-sm` font-semibold, candidate count badge on the right.
- Cards within columns: white background, `shadow-sm`, `rounded-md`, `space-3` padding. Show candidate name, top 3 skill tags, and time-in-stage.
- Drag handle: left edge grip indicator (three horizontal dots), visible on hover.
- Drop zone: `primary-50` background with dashed `primary-300` border when a card is dragged over.

### Hiring pipeline table view

An alternative to the Kanban view, used on the ATS/dashboard page. Shows jobs as rows with stage badges inline.

- Each row shows: job title, total applications count, then a horizontal row of stage badges.
- Each stage badge is the solid stage colour with white text showing the stage name and candidate count (e.g. 'Phone screening / 87 candidates').
- Stages flow left to right in pipeline order.
- The table includes a search bar above to filter jobs.

### Vacancy cards

Used on the recruiter space / vacancies page. Displayed in a 3-column grid.

- White card, `rounded-xl`, `shadow-sm`.
- Header: 'Position' label in `text-xs` `neutral-400`, job title in `text-base` font-semibold.
- Toggle switch (shadcn/ui `Switch`) in the top right to activate/deactivate the listing. Active: `primary-500`. Inactive: `neutral-300`. Closed/expired: `error-500`.
- Metadata: deadline (calendar icon), views count (eye icon), in `text-sm` `neutral-500`.
- Applicant count in `success-500` (green) or `error-500` (red if high volume) text, `text-sm` font-medium.
- Footer: three icon buttons (kebab menu, view, edit) in `neutral-400`, hover `neutral-600`.

### Dashboard metric cards

- Height: auto (content-driven).
- White card on the `neutral-50` page background. Icon (Lucide, 24px) in a light circle above the label.
- Layout: icon (top), metric label (`text-sm` `neutral-500`), value (`text-lg` `neutral-800` font-semibold) on the right or below.
- For the summary row style (as in the screenshots): icon, label, and value in a single horizontal card. Four cards in a row.
- Trend charts (line charts) use red and blue dual lines with goal markers. Use Recharts library.
- Optional sparkline chart below the value.

### Modals and dialogs

- Use shadcn/ui `Dialog`.
- Overlay: black at 50% opacity.
- Modal: white background, `rounded-lg`, `shadow-lg`, max-width 480px for confirmation dialogs, 640px for forms, 800px for complex views.
- Header: `text-xl` title with close (X) button.
- Footer: action buttons right-aligned. Cancel (secondary) on left, confirm (primary or destructive) on right.

### Toast notifications

- Use shadcn/ui `Toast` (via sonner).
- Position: bottom-right.
- Auto-dismiss after 5 seconds (errors persist until dismissed).
- Types: success (green left border), error (red), warning (amber), info (blue).

### Empty states

When a list, table, or dashboard section has no data:

- Centred illustration or icon (use Lucide icons, 48px, `neutral-300`).
- Heading: `text-lg` `neutral-700`.
- Description: `text-sm` `neutral-500`, one to two sentences.
- CTA button if there is a clear next action (e.g. 'Create your first job').

### Avatar

- Sizes: `sm` (32px), `md` (40px), `lg` (48px).
- Shape: `rounded-full`.
- Fallback: initials on `primary-100` background in `primary-700` text.

---

## 4. Iconography

Use Lucide React icons exclusively. Do not use Font Awesome, Heroicons, or custom SVGs.

- Size: 16px for inline with text, 20px for buttons and navigation, 24px for page headers, 48px for empty states.
- Colour: inherit from parent text colour. Do not hardcode icon colours unless for semantic indicators (success/error/warning).
- Stroke width: 1.5px (Lucide default).

---

## 5. Motion and transitions

Keep animations minimal and functional. AIRIS is a productivity tool; motion should not slow users down.

- **Hover transitions**: 150ms ease-out for background colour, border colour, and shadow.
- **Modal open/close**: 200ms fade + scale (0.95 to 1.0).
- **Sidebar collapse**: 200ms ease-in-out width transition.
- **Toast enter/exit**: 300ms slide from right.
- **Pipeline card drag**: native HTML5 drag with 100ms opacity transition.
- **No page transition animations**. Route changes are instant.

---

## 6. Accessibility

- All interactive elements must be keyboard accessible.
- Focus indicators: `primary-200` ring, 2px, offset 2px. Never remove focus outlines.
- Colour contrast: all text meets WCAG 2.1 AA (4.5:1 for normal text, 3:1 for large text). The token pairs in this system meet these ratios.
- Form errors are announced via `aria-describedby` linking the input to its error message.
- Tables include proper `<th>` scope attributes.
- Modals trap focus and return focus to the trigger on close.
- Images and icons that convey meaning have alt text. Decorative icons use `aria-hidden="true"`.

---

## 7. Rules for developers

1. **Use tokens, not raw values.** Never write `color: #28808F` or `padding: 20px`. Use `text-primary-500` and `p-5`.
2. **Use shadcn/ui components.** Do not build a custom button, input, select, table, dialog, or toast. Customise the existing ones.
3. **One primary button per view.** If you have two equally important actions, make one secondary.
4. **Consistent page structure.** Every page has a page header (title + breadcrumb + action buttons) and a page body. No exceptions.
5. **Mobile last for MVP.** Design for 1024px+ first. Responsive adaptations are a Phase 2 concern, but do not break on smaller screens.
6. **No custom fonts.** Inter only. Load from Google Fonts or bundle locally.
7. **No gradients.** No gradient backgrounds anywhere. Solid colours only. The aesthetic is light, clean, and flat.
8. **Sentence case everywhere.** 'Create new job', not 'Create New Job'.
9. **Error messages are specific.** 'Email address is required', not 'This field is required'.
10. **Empty states are mandatory.** Every list, table, and dashboard section must handle the zero-data case gracefully.

# Design System

## Overview
AIRIS uses a standardized design system built on Tailwind tokens and shadcn/ui primitives. The goal is consistent UX across all recruiting workflows without ad-hoc styling drift.

This module defines visual foundations (color, type, spacing, layout), component usage rules, and accessibility expectations for frontend implementation.

## Responsibilities
Primary responsibilities:
- Define and version design tokens (color, typography, spacing, radius, shadows).
- Standardize layout patterns (top bar, sidebar, content zones, dashboard grids).
- Define component behavior for buttons, forms, cards, tables, badges, pipeline boards, dialogs, and toasts.
- Enforce implementation guardrails (token-only styles, shadcn-first component strategy).

## Data Model
Not applicable as a database model.

Token model references:
- Brand and semantic color scales (primary, neutral, success/warning/error/info, stage colors).
- Type scale and font stack (`Inter` + system fallback).
- Spacing on 4px grid.
- Fixed radius and shadow tiers.

## API Endpoints
Not applicable.

## Business Logic
Implementation rules that drive UI behavior:
- Use tokens only; avoid raw hex/spacing literals in feature code.
- Prefer shadcn/ui primitives and extend via composition.
- Keep one primary CTA per local view context.
- Pipeline and urgency visuals are semantic and must remain consistent with domain statuses.
- Empty states are required for all data-driven views.
- Accessibility rules are mandatory (focus visibility, semantic tables, modal focus trap, contrast compliance).

## Notes / Constraints
- Mobile behavior is supported, but product priority is desktop-first for Phase 1.
- Do not introduce unsupported icon packs; use Lucide consistently.
- No gradients/custom font experimentation in product UI.
- Any design-token or shared-component changes should pass explicit review due to broad blast radius.
- Component library and token config must stay aligned with implementation repository.

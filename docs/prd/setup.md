# Setup

## Overview
This document describes project bootstrap and team workflow setup for AIRIS so engineers and AI coding tools can implement features against stable contracts.

## Responsibilities
Setup responsibilities:
- Initialize repository and baseline contract docs.
- Scaffold frontend stack and shared component foundation.
- Enforce governance for design-system and architecture changes.
- Configure linting and team workflow to keep implementation consistent.

## Data Model
Not applicable.

## API Endpoints
Not applicable.

## Business Logic
Recommended setup flow:
1. Create repository and commit architecture + service specs + design-system assets as the contract baseline.
2. Scaffold Next.js + Tailwind + shadcn/ui; apply AIRIS token configuration.
3. Establish shared component structure under `src/components` and require feature teams to compose from it.
4. Add branch protections and CODEOWNERS for foundational assets (design system, shared UI, architecture).
5. Add lint checks to discourage hardcoded visual values and maintain token usage.
6. Publish or host component reference material for team visibility.
7. Standardize service-by-service branch workflow: read spec -> implement -> test -> review.
8. Keep a root `CLAUDE.md` that points AI tools to architecture/spec/design constraints before code generation.

## Notes / Constraints
- Setup guidance assumes private repository and CI-enabled pull request workflow.
- Shared component governance is required to avoid style/system drift.
- Service specs are contract-first artifacts; implementation should follow them, not reinterpret them ad hoc.
- AI-assisted development works best when architecture, specs, and design system are versioned and discoverable in predictable paths.

---
name: frontend-router
description: Splits a frontend request into routed sub-tasks and dispatches each to the right specialist (frontend-implementer, frontend-documenter, frontend-cleaner). Use when a request has multiple separable parts or follows implement→cleanup→document.
---

# frontend-router

Split a frontend development request into distinct sub-tasks; route each to a specialist.

## Routing

- Implementation / refactor (React/TS components, hooks, `api.ts`) → `frontend-implementer`.
- Final cleanup (strip console.log, dead JSX, unused imports) → `frontend-cleaner`.
- Docs at completion (TSDoc, `docs/frontend/<feature>.md`, README) → `frontend-documenter`.

## Rules

- Run independent sub-tasks in parallel; document/cleanup come after implementation.
- Stay inside `frontend/`. Any backend need → record in `backend_spec.md`, do not implement.
- Return the routing plan and consolidated results.

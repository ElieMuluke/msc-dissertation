---
name: frontend-documenter
description: Writes documentation for a completed frontend feature — TSDoc on exported components/hooks/api functions, docs/frontend/<feature>.md, and README updates. Final step of a feature.
---

# frontend-documenter

Document a finished frontend feature (GEMINI.md rule 3). Run the `/document-feature` flow.

## Steps

1. TSDoc/JSDoc on every exported component, hook, type, and `src/api.ts` function.
2. `docs/frontend/<feature>.md`: what / usage / public surface / design notes / limitations.
3. README feature-list bullet if user-facing.
4. DRY docs — link, don't restate. Match existing style. Verify examples match real signatures.

Stay inside `frontend/`. Don't change behavior — docs only.

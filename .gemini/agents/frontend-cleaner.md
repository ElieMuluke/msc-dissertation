---
name: frontend-cleaner
description: Removes frontend experimentation/scratch code so only the final implementation remains — console.log debug, commented-out JSX, unused imports/state/props, scratch components. Use before finalizing a feature.
---

# frontend-cleaner

Strip experiment residue from frontend files (GEMINI.md rule 6). Run the
`/cleanup-experiment` flow.

## Steps

1. Find residue: `console.log` debug, commented-out JSX, dead branches, unused
   imports/vars/state/props, scratch components, hardcoded sample data.
2. Remove it. Useful bits → extract into a proper component/hook, or move a demo into
   `docs/frontend/<feature>.md`.
3. Re-verify `npm run build` passes.
4. Report the removal list.

## Guard

Do NOT delete files you didn't create or that look like real source without flagging.
Stay inside `frontend/`.

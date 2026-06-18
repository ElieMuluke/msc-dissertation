# GEMINI.md — Frontend Operating Rules

Multi-Agent System for Regulatory Risk and Compliance in Banking Workflows.
**Gemini owns the FRONTEND only** (`frontend/` — React + Vite + TypeScript + Tailwind).
Claude owns the backend (`backend/` — FastAPI + Python). Stay on your side.

These rules are binding for every session. They are self-improving: when the user
gives a remark, capture it to `.gemini/LEARNINGS.md` and apply it from then on.

---

## 0. Session continuity (read first, every session)

Gemini CLI auto-loads this file. At the start of every session, also read:
- `.gemini/LEARNINGS.md` — standing rules from user remarks. **Honor every entry.**
- `.gemini/SESSION_LOG.md` — where frontend work was left off. Resume from its "Next" section.

**Before ending a session** (or when the user says you're wrapping up), update
`.gemini/SESSION_LOG.md`: what was done, current state, and the next step.

## 1. Ownership boundary (REQUIRED — read twice)

- **Edit only `frontend/`.** Never edit `backend/`, backend tests, or Python source.
- The frontend↔backend API contract is `backend_spec.md` (repo root). It is your
  **handoff document to Claude (backend)**.
  - When the frontend needs a backend capability that doesn't exist yet, **do not
    implement it** — record the requirement in `backend_spec.md` (endpoint, request/
    response schema, status `⏳ Pending`) and consume it once Claude marks it done.
  - Treat existing `backend_spec.md` entries as the source of truth for the API shape
    (URLs, payloads, status codes). Match them exactly in `frontend/src/api.ts`.
- Until a backend endpoint exists, it is acceptable to ship a graceful local fallback
  (e.g. `localStorage`) in the UI, but the real requirement still goes in `backend_spec.md`.

## 2. Capturing remarks (self-improvement loop)

A "remark" = user feedback/correction/preference about *how to work* (style, process,
conventions, tooling) — not a one-off task.

When the user gives a remark:
1. Apply it immediately in the current work.
2. Append it to `.gemini/LEARNINGS.md` via the `/remark` command (dedupe — update an
   existing entry instead of duplicating).
3. Confirm in one line that it was captured.

Never let a remark live only in chat.

## 3. Documentation at feature end (REQUIRED)

When a frontend feature is complete, **before declaring done**, run `/document-feature`:
- TSDoc/JSDoc on exported components, hooks, and `api.ts` functions.
- A markdown doc under `docs/frontend/<feature>.md`: what it does, how to use, design notes.
- Update `README.md` feature list if user-facing.

A feature is not "done" until its docs exist.

## 4. SOLID + DRY (REQUIRED, frontend flavor)

- **S**ingle responsibility: one component = one concern. Split big components.
- **O**pen/closed: extend via new components/props, not edits to stable shared ones.
- **L**iskov: component variants honor the base prop contract.
- **I**nterface segregation: small, focused prop interfaces; no god-props.
- **D**ependency inversion: components depend on typed interfaces (`api.ts`, props/context),
  not on hardcoded fetch URLs scattered in JSX. All network calls go through `src/api.ts`.
- **DRY**: extract shared UI (buttons, badges, hooks) before copy-pasting a 2nd time.

## 4a. Minimal code (YAGNI, REQUIRED)

Smallest correct implementation. No speculative components, no unrequested extras.
Lean over complete. SOLID/DRY/modular + docs still apply — but keep them tight.

## 5. Modular features (REQUIRED)

- All frontend code under `frontend/src/`. Network access centralized in `src/api.ts`
  (typed functions returning typed results). Components in `src/components/`.
- No backend reach-ins. Communicate with the backend only through `api.ts` ↔ documented
  HTTP/WebSocket endpoints from `backend_spec.md`.
- Keep side effects (fetch, WS, localStorage) at the edges; keep render logic pure.

## 6. Cleanup after experimentation (REQUIRED)

Strip experiment residue before a feature is final via `/cleanup-experiment`:
- Remove `console.log` debug, commented-out JSX, dead props, unused imports/state,
  scratch components. Keep only the final, documented implementation.

## 7. Subagents for routing AND routine tasks (REQUIRED)

Delegate to the frontend specialists in `.gemini/agents/` instead of doing everything inline:
- `frontend-router` — split a request into routed sub-tasks.
- `frontend-implementer` — SOLID/DRY/modular React/TS implementation.
- `frontend-documenter` — feature docs at completion.
- `frontend-cleaner` — strip experiment code.
- `frontend-session-closer` — end-of-work routine (cleanup → docs → DoD → build/lint →
  capture remarks → update SESSION_LOG → report).

Run independent sub-tasks in parallel.

## 8. Track feature-request status: FEATURES.md (REQUIRED)

`FEATURES.md` (repo root, shared with Claude) is the durable status tracker. When a
frontend feature is requested add a row (🔵), update on start (🟡) and completion (✅)
or block (⛔). Keep it in sync with `backend_spec.md`.

## 9. Definition of Done (checklist)

A frontend feature is done only when ALL hold:
- [ ] Stayed inside `frontend/`; backend needs recorded in `backend_spec.md` (rule 1).
- [ ] SOLID + DRY respected (rule 4); calls go through `api.ts`.
- [ ] Lives in a modular component/module (rule 5).
- [ ] Experiment/debug code removed (rule 6).
- [ ] Docs written (rule 3).
- [ ] `npm run build` (and lint if configured) passes.
- [ ] `.gemini/SESSION_LOG.md` updated (rule 0).
- [ ] Any new remark captured to `.gemini/LEARNINGS.md` (rule 2).

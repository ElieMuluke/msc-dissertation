# CLAUDE.md — Project Operating Rules

Multi-Agent System for Regulatory Risk and Compliance in Banking Workflows.
Python. RAG via ChromaDB + sentence-transformers. Source under `src/`.

These rules are binding for every session. They are self-improving: when the user
gives a remark, it is captured to `.claude/LEARNINGS.md` and applied from then on.

---

## 0. Session continuity (read first, every session)

- A SessionStart hook injects `.claude/LEARNINGS.md` and `.claude/SESSION_LOG.md`
  into context automatically. **Honor every entry in LEARNINGS.md as a standing rule.**
- `SESSION_LOG.md` is where work was left off. Resume from its "Next" section.
- **Before ending a session** (or when the user says you're wrapping up), update
  `.claude/SESSION_LOG.md`: what was done, current state, and the next step.

## 1. Capturing remarks (self-improvement loop)

A "remark" = any user feedback, correction, preference, or instruction about *how to
work* (style, process, tooling, conventions) — not a one-off task.

When the user gives a remark:
1. Apply it immediately in the current work.
2. Append it to `.claude/LEARNINGS.md` via the `remark` skill (dedupe — update an
   existing entry instead of duplicating).
3. Confirm in one line that it was captured.

This makes preferences persist across sessions. Never let a remark live only in chat.

## 2. Documentation at feature end (REQUIRED)

When a feature implementation is complete, **before declaring done**, write/update
documentation via the `document-feature` skill:
- Module docstring + public-API docstrings in the code.
- A markdown doc under `docs/<feature>.md`: what it does, how to use, design notes.
- Update `README.md` feature list if user-facing.

A feature is not "done" until its docs exist.

## 3. SOLID + DRY (REQUIRED)

- **S**ingle responsibility per module/class/function.
- **O**pen/closed: extend via new code, not edits to stable code.
- **L**iskov: subtypes honor base contracts.
- **I**nterface segregation: small, focused interfaces (Protocols/ABCs).
- **D**ependency inversion: depend on abstractions; inject dependencies, don't hardcode
  clients/models inside business logic.
- **DRY**: no copy-paste logic. Extract shared code before it's duplicated a 2nd time.

## 3a. Minimal code (YAGNI, REQUIRED)

Write the smallest correct implementation. No speculative abstraction, no unrequested
extras (CLIs, demos, seed data) unless asked. Lean over complete. SOLID/DRY/modular and
docs still apply — but keep them tight. When in doubt, less code.

## 4. Modular features (REQUIRED)

- Code is split into `backend/` (FastAPI + Python) and `frontend/` (React+Vite+TS).
- Each backend feature is a self-contained package under `backend/app/<domain>/<feature>/`
  with a clear public surface in its `__init__.py`; the FastAPI layer in `backend/app/api`
  is a thin wrapper that calls it. Run backend commands (uvicorn, pytest, cli) from `backend/`.
- No cross-feature reach-ins; communicate through defined interfaces.
- Config, I/O, and side effects isolated from core logic (pure core, thin shell).

## 4b. Frontend↔backend contract: backend_spec.md (REQUIRED)

Backend features required by the frontend are tracked in `backend_spec.md` (repo root).
- When the frontend starts calling a backend capability that doesn't exist yet, record it
  in `backend_spec.md` (endpoint, schema, status).
- Consult `backend_spec.md` for pending work; implement from it; mark items done there.
- It is the source of truth for the frontend↔backend API. Keep it current.
- When implementing its items, still honor SOLID (rule 3): add domain-typed methods on
  `RagSystem` (e.g. `list_sources`, `delete_by_source`) — do not leak the raw Chroma
  collection through the API layer, even if the spec sketch does.

## 4c. Track feature-request status: FEATURES.md (REQUIRED)

`FEATURES.md` (repo root) is the durable status tracker for every feature request, so it
survives across sessions (the in-session task list is the working view; FEATURES.md is the
record). When a feature is requested, add a row (🔵 requested). Update it on start
(🟡 in progress) and completion (✅ done) or when blocked (⛔). Keep it in sync with the
task list and `backend_spec.md`.

## 5. Cleanup after experimentation (REQUIRED)

Experimentation (spikes, prints, throwaway scripts, `test_*` scratch, commented blocks)
must be removed before a feature is final. Use the `cleanup-experiment` skill:
- Delete dead code, debug prints, scratch files, commented-out experiments.
- Keep only the final, documented, tested implementation.
- Convert any useful scratch test into a real test under `tests/`.

## 6. Subagents for routing AND routine tasks (REQUIRED)

Delegate to project subagents instead of doing everything inline — both for **routing**
(splitting a request) and for **routine/repetitive end-of-work** tasks.

Use the `task-router` agent to split a request into routed sub-tasks, dispatching each to:
- `feature-implementer` — SOLID/DRY/modular implementation.
- `feature-documenter` — feature docs at completion.
- `experiment-cleaner` — strip experiment code.

Use the `session-closer` agent for the recurring end-of-work routine (cleanup → docs →
Definition-of-Done check → sanity/tests → capture remarks → update SESSION_LOG → report).
Run it when finishing a feature, a work block, or a session.

Run independent sub-tasks in parallel. The router decides the split; specialists execute.

## 7. Definition of Done (checklist)

A feature is done only when ALL hold:
- [ ] SOLID + DRY respected (rule 3).
- [ ] Lives in a modular package (rule 4).
- [ ] Experiment/debug code removed (rule 5).
- [ ] Documentation written (rule 2).
- [ ] `SESSION_LOG.md` updated (rule 0).
- [ ] Any new remark captured to `LEARNINGS.md` (rule 1).

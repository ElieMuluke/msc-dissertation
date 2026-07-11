# LEARNINGS — Persistent Remarks & Improvements

Standing rules captured from user remarks. Loaded into context every session via the
SessionStart hook. Honor all entries. Newest at top. Dedupe — update, don't duplicate.

Format per entry:
```
## <YYYY-MM-DD> — <short title>
**Remark:** <what the user said / the preference>
**Apply:** <how to act on it going forward>
```

---

## 2026-06-17 — Track feature-request status
**Remark:** Keep track of the status of feature requests.
**Apply:** Maintain `FEATURES.md` (repo root) — durable status of every feature request
(🔵 requested / 🟡 in progress / ✅ done / ⛔ blocked). Add a row on request, update on
start/finish/block. Keep in sync with the task list and backend_spec.md. See CLAUDE.md
rule 4c.

## 2026-07-03 — backend_spec.md vs frontend_spec.md direction (don't cross the streams)
**Remark:** Confirmed I never implemented tabular-ingestion UI on the frontend (correct —
must never touch `frontend/`, that's Gemini/Antigravity's job). Told to add the frontend
feature request to `frontend_spec.md` for Antigravity to pick up, and clean the equivalent
writeup out of `backend_spec.md` where I'd wrongly put it. "Remember this distinction for
every operation."
**Apply:** Two files, opposite directions — don't cross them.
- `backend_spec.md` = frontend's asks OF the backend + Claude's implementation status.
  Only content that originated as a frontend requirement belongs here.
- `frontend_spec.md` = backend's writeups of capabilities it exposes, for the frontend
  (Gemini/Antigravity) to build UI against. Any "here's an endpoint, build this UI for it"
  content belongs here, never in `backend_spec.md`.
Never write/edit files under `frontend/` — frontend implementation is Gemini/Antigravity's
job, always, with no exceptions. When a backend feature needs frontend UI, record the
request in `frontend_spec.md` and stop there. See CLAUDE.md rule 4b. When implementing
backend_spec.md items, keep SOLID — domain methods on RagSystem, don't leak the Chroma
collection through the API.

## 2026-06-17 — Minimal code
**Remark:** Don't write too much code. Straight to the point — good code, but not too much.
**Apply:** Prefer the smallest correct implementation. No speculative abstraction, no
unrequested extras (CLIs, seed data, demos) unless asked. YAGNI over completeness. Still
keep SOLID/DRY/modular + docs, but lean. When in doubt, less code.

## 2026-06-17 — Subagents for routine tasks too
**Remark:** Subagents are for not only routing tasks but also routine/repetitive
end-of-work tasks.
**Apply:** Use `session-closer` agent for the recurring closing routine (cleanup, docs,
DoD check, tests, capture remarks, update SESSION_LOG). Delegate repetitive wrap-up
work to subagents, don't do it inline. See CLAUDE.md rule 6.

## 2026-06-17 — Bootstrap
**Remark:** Set up a self-improving agent that captures remarks, documents features,
follows SOLID/DRY, keeps features modular, cleans up experiments, and routes work to
subagents. Make all of this persist across sessions.
**Apply:** Follow CLAUDE.md rules 0–7. Append every future remark here.

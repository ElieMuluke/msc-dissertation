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

## 2026-06-17 — backend_spec.md is the frontend↔backend contract
**Remark:** Features required from the backend by the frontend are stored in
`backend_spec.md`. Track them there.
**Apply:** Treat `backend_spec.md` (repo root) as source of truth for frontend-required
backend features. Record new ones there, implement from it, mark done. See CLAUDE.md
rule 4b. When implementing, keep SOLID — domain methods on RagSystem, don't leak the
Chroma collection through the API.

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

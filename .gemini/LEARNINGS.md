# LEARNINGS — Persistent Remarks & Improvements (Frontend / Gemini)

Standing rules captured from user remarks. Read every session (GEMINI.md rule 0).
Honor all entries. Newest at top. Dedupe — update, don't duplicate.

Format per entry:
```
## <YYYY-MM-DD> — <short title>
**Remark:** <what the user said / the preference>
**Apply:** <how to act on it going forward>
```

---

## 2026-06-17 — Frontend/backend ownership split
**Remark:** Gemini agents are responsible only for the frontend; Claude is responsible
for the backend.
**Apply:** Edit only `frontend/`. Never touch `backend/`. Backend needs go into
`backend_spec.md` as requests; consume them once Claude implements. See GEMINI.md rule 1.

## 2026-06-17 — backend_spec.md is the frontend↔backend contract
**Remark:** Features required from the backend by the frontend are stored in
`backend_spec.md`.
**Apply:** Source of truth for the API. Record new backend needs there; match existing
entries exactly in `src/api.ts`. Don't implement backend yourself.

## 2026-06-17 — Track feature-request status
**Remark:** Keep track of the status of feature requests.
**Apply:** Maintain `FEATURES.md` (repo root) — 🔵 requested / 🟡 in progress / ✅ done /
⛔ blocked. Update on request/start/finish/block.

## 2026-06-17 — Minimal code
**Remark:** Don't write too much code. Straight to the point — good code, but not too much.
**Apply:** Smallest correct implementation. No speculative components/extras. YAGNI. Keep
SOLID/DRY/modular + docs, but lean.

## 2026-06-17 — Subagents for routine tasks too
**Remark:** Subagents are for not only routing tasks but also routine/repetitive
end-of-work tasks.
**Apply:** Use `frontend-session-closer` for the closing routine (cleanup, docs, DoD,
build/lint, capture remarks, update SESSION_LOG). Delegate wrap-up, don't redo by hand.

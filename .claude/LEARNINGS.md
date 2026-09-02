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

## 2026-08-26 — /unslop and /stop-slop: don't split sentences just for clause count
**Remark:** "now, 7.2 sounds harder to read compared to before. and it seems you did not
use /unslop or /stop-slop . revert back" — followed by confirmation that the same
mechanical fix had been applied across the rest of the Discussion and Conclusion chapters
too. The applied fix (splitting every sentence with 2+ clauses into several short ones)
made the prose choppier, not clearer, and had to be fully reverted.
**Apply:** Dense-but-grammatically-sound academic prose (parallel "and" lists, compound
"but...and" clauses, a colon followed by a semicolon-separated list) is not slop. Splitting
it on sentence length or clause count alone is not what stop-slop/unslop ask for and makes
things worse. When running these skills on manuscript prose, only fix genuine problems:
comma splices (3+ independent clauses joined only by commas), true sentence fragments (no
main verb), ambiguous referents ("under it" — under what?), and unnamed-but-nameable
subjects ("the model that..." when the model is already known). Leave everything else
exactly as written, even if a sentence runs long. When asked to re-check something already
reverted for the same issue, apply this narrower bar before touching any text.

## 2026-08-24 — Manuscript terminology: "architecture", not "arm"
**Remark:** "I am not using the word arm, I want to use the word architecture
(single- and multi-agent) and we should be explicit about that."
**Apply:** In all dissertation/manuscript prose, write "the single-agent architecture"
and "the multi-agent architecture" (or "both architectures", "per architecture"), never
"arm/Arm A/Arm B". The code keeps `arm` with values `single`/`mas` (adapter, journals,
manifests); when prose must reference those artifacts, bridge once at first use, e.g.
"the harness records the architecture as `arm` (`single`/`mas`) in its journals", then
use "architecture" throughout. Do not rename anything in code for this.

## 2026-08-21 — Manuscript prose style: no em dashes, short sentences
**Remark:** "I do not like em dashes and too long sentences... it feels hard to read
and get the point." Also: give ONE suggestion when asked for text, not multiple choices.
(The user invoked a "/humanize" skill that does not exist in this environment; the
intent is plain, readable prose.)
**Apply:** When drafting or revising dissertation/manuscript text: no em dashes
(restructure into separate sentences or use a colon/comma); keep sentences short, one
idea each; prefer plain wording over dense academic phrasing. When the user asks for
suggested text, provide exactly one version, not alternatives.
**Formatting:** Never wrap suggested manuscript text in markdown blockquotes (`>`) or
any other prefix decoration - it breaks copy-paste. Output it as plain paragraphs.
**Separate copy from commentary:** Always mark which part of a reply is manuscript text
to paste and which part is commentary to read. Use a heading before each block (e.g.
"Copy into <section>" and "Read only, not for the manuscript"). Never mix notes,
verdicts, or rationale into the paste-ready prose.
**Skills:** `/humanizer-zh` and `/stop-slop` are installed in ~/.claude/skills and are
the user's preferred tools for de-AI-ing prose; load them when asked to humanize.

## 2026-07-13 — Don't commit automatically by default
**Remark:** "I do not want you to keep on commiting automatically. it was a one time
request." A prior turn asked for one commit per recommendation while implementing a
specific batch of fixes ("make a commit for each... while implementing this fix"); that
was scoped to that task, not a standing workflow preference. Committing again on the very
next, unrelated fix without being asked was wrong.
**Apply:** Never infer a standing "commit as you go" policy from one past instance, even
within the same session. Only commit when the user explicitly asks for that specific
piece of work. CLAUDE.md/global git-safety guidance already says "only commit when
requested" — this remark exists because that rule was violated by over-generalizing a
scoped instruction; treat each commit request as scoped to the work it named.

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

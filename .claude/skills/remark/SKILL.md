---
name: remark
description: Capture a user remark, correction, or preference about HOW to work into the persistent LEARNINGS log so it survives across sessions. Trigger when the user gives feedback on style/process/conventions/tooling ("from now on", "always", "stop doing X", "prefer Y", "I like when you..."), or invokes /remark.
---

# remark — persist a remark across sessions

Goal: never let a "how to work" preference live only in chat. Record it so the
SessionStart hook re-injects it every future session.

## Steps

1. Identify the remark's essence in one sentence (the rule, not the one-off task).
2. Open `.claude/LEARNINGS.md`. Check for an existing entry on the same topic.
   - If found: update it in place (refine the rule). Do not duplicate.
   - Else: prepend a new entry directly under the `---` separator (newest first):
     ```
     ## <today YYYY-MM-DD> — <short title>
     **Remark:** <what the user said / the preference>
     **Apply:** <how to act on it going forward>
     ```
3. If the remark changes a workflow rule, also reflect it in `CLAUDE.md`.
4. Apply the remark to the current work immediately.
5. Confirm in one line: `Captured: <title>`.

## Scope guard

Only capture standing preferences. A one-off task ("add a function here") is NOT a
remark — do the task, don't log it.

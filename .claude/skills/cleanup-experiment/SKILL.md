---
name: cleanup-experiment
description: Remove experimentation/scratch code so only the final implementation remains. Trigger when a spike/experiment is concluding, before finalizing a feature, when the user says "clean up", "remove the experiment code", "keep only final code", or invokes /cleanup-experiment.
---

# cleanup-experiment — keep only final code

After experimentation, strip everything that isn't the final, documented implementation.

## Steps

1. Scan the feature's files for experiment residue:
   - `print()` / debug logging used for poking around.
   - Commented-out code blocks and dead branches.
   - Scratch scripts, `tmp_*`, `scratch_*`, ad-hoc `if __name__ == "__main__":` demos.
   - Unused imports, vars, functions; hardcoded sample/test data in production paths.
2. Remove them. If a piece is genuinely useful:
   - A sanity check → convert to a real test under `tests/`.
   - A demo → move to `docs/<feature>.md` usage section or an `examples/` script.
3. Re-verify the feature still imports/runs after removal.
4. Confirm what was removed in a short list.

## Guard

Do NOT delete files you didn't create or that look like real source without flagging
first. Show the user the removal list if anything is ambiguous.

---
name: document-feature
description: Write documentation for a feature at the END of its implementation, before declaring it done. Trigger when a feature/module is finished, when the user says "document this", "write docs", or invokes /document-feature.
---

# document-feature — docs at feature completion

A feature is not done until documented. Run this as the last implementation step.

## Steps

1. **In-code docs**: add/refresh module docstring and docstrings for every public
   class/function (purpose, args, returns, raises, example if non-obvious).
2. **Feature doc**: create/update `docs/<feature>.md`:
   - **What** it does (one paragraph).
   - **Usage**: minimal runnable example.
   - **Public API**: the exported surface from the feature's `__init__.py`.
   - **Design notes**: SOLID/DRY choices, dependencies injected, extension points.
   - **Limitations / TODO**.
3. **README**: if user-facing, add a bullet to `README.md`'s feature list.
4. Keep docs DRY — link, don't restate. Match existing doc style.
5. Verify the usage example actually matches the code's public API.

## Done check

- [ ] Public API has docstrings.
- [ ] `docs/<feature>.md` exists and is accurate.
- [ ] README updated if user-facing.

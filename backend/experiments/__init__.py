"""PRD-A repeatability experiment harness.

Layout (per PRD-A "Components to build", relocated 2026-08-06 into the same
package tree as ``app``):

- ``backend/experiments/harness``  — DFAH integration, adapter, checkpointed
  runner, gates.
- ``backend/experiments/single``   — arm A (monolithic) prompts and builder.
- ``backend/experiments/mas``      — arm B (LangGraph pipeline) prompts and
  builder.
- ``backend/experiments/analysis`` — metrics module and analysis report script.
- ``backend/experiments/results``  — manifest, journals, progress, figures
  (git-synced).

The measured agent modules live in ``backend/app/agents`` (shared with
PRD-B). Both packages sit under ``backend/``, so run everything from there
(or with ``PYTHONPATH=backend``): imports of ``app.*`` and ``experiments.*``
resolve naturally, with no path shims.
"""

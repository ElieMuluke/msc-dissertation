"""Locked design constants and harness configuration for PRD-A.

Every value that can influence a measured run lives here so that
``experiments/harness/manifest.py`` can hash the full configuration into
``results/manifest.json`` before run 1. Changing any locked constant after
run 1 invalidates the pre-registration (see PRD-A); edits before launch
require a dated note in ``backend/experiments/CHANGELOG.md``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

# backend/experiments/config.py -> parents: [0]=experiments, [1]=backend, [2]=repo root
EXPERIMENTS_DIR = Path(__file__).resolve().parent
BACKEND_DIR = EXPERIMENTS_DIR.parent
REPO_ROOT = BACKEND_DIR.parent
RESULTS_DIR = EXPERIMENTS_DIR / "results"

#: DFAH benchmark clone (dfah-bench 0.1.1 source checkout).
DFAH_REPO = Path("/home/el/projects/dfah-repo")
ALERTS_JSON = DFAH_REPO / "econometrics/benchmarks/compliance_triage/data/alerts.json"
PERTURBATION_JSON = EXPERIMENTS_DIR / "perturbation_cases.json"

#: Decision ontology, in canonical order (used for tie-breaks and entropy).
DECISIONS = ("escalate", "dismiss", "investigate")
#: Outcome categories = decisions + malformed. Malformed is never excluded.
OUTCOMES = DECISIONS + ("malformed",)

ARMS = ("single", "mas")

#: Fixed seed used by the T=0 determinism conditions.
FIXED_SEED = 42
#: Master seed from which all varied per-run seeds are pre-generated.
MASTER_SEED = 20260805


@dataclass(frozen=True)
class Condition:
    """One pre-registered experimental condition.

    ``fixed_seed`` of ``None`` means the seed varies per repeat and is drawn
    from the pre-generated list in the manifest.
    """

    name: str
    block: str  # "primary" | "perturbation"
    temperature: float
    repeats: int
    fixed_seed: int | None


CONDITIONS: tuple[Condition, ...] = (
    Condition("t0-fixed", "primary", 0.0, 5, FIXED_SEED),
    Condition("t07-varied", "primary", 0.7, 15, None),
    Condition("pert-t0", "perturbation", 0.0, 5, FIXED_SEED),
    Condition("pert-t05", "perturbation", 0.5, 5, None),
    Condition("pert-t10", "perturbation", 1.0, 5, None),
)


@dataclass(frozen=True)
class ExperimentConfig:
    """Everything the runner and manifest need, in one injectable object."""

    model: str = "qwen3.5:9b"
    #: Wire ``think`` parameter: ``False`` sends ``think: false`` (required
    #: for thinking models — qwen3.5 thinks by default, see G0); ``None``
    #: omits the parameter entirely (for models without a thinking mode,
    #: where sending it could be rejected — captured per-model by the
    #: replication mini-gate).
    think: bool | None = False
    #: One Ollama server per arm (PRD-A execution constant).
    #: Arm A moved :11434 -> :11437 on 2026-08-06 (gate day): the machine's
    #: systemd Ollama (unpinned env) owns :11434 and cannot be stopped
    #: without interactive sudo — see CHANGELOG. :11434 is now the
    #: dev/analysis server and must receive no sweep traffic.
    arm_base_urls: dict[str, str] = field(
        default_factory=lambda: {
            "single": "http://localhost:11437",
            "mas": "http://localhost:11435",
        }
    )
    #: Context window; recorded in the manifest. Multi-turn tool loops do not
    #: fit Ollama's default context, so this is set explicitly and held fixed.
    num_ctx: int = 16384
    #: Generation cap per LLM call, recorded in the manifest.
    num_predict: int = 2048
    #: Max tool-loop iterations per agent before it is forced to answer.
    max_iterations: int = 8
    #: Hard per-run timeout; expiry is journalled as an error, never retried.
    run_timeout_s: float = 900.0
    #: git commit+push of results/ every N completed runs.
    git_sync_every: int = 25
    results_dir: Path = RESULTS_DIR

    def base_url(self, arm: str) -> str:
        return self.arm_base_urls[arm]


#: Which tools each arm-B node may call (arm A always gets the full set).
#: The union equals arm A's tool set — same tools overall, partitioned by role.
MAS_TOOL_PARTITION: dict[str, tuple[str, ...]] = {
    "orchestrator": (),
    "data": ("search_precedents", "get_customer_profile", "check_sanctions_list"),
    "policy_risk": ("calculate_risk_score",),
    "reporting": (),
}

DEFAULT_CONFIG = ExperimentConfig()

# --- Replication extension (2026-08-06, owner-approved) ----------------------
#: model tag -> (results dirname, wire think parameter). qwen3.5:9b is the
#: headline pre-registered sweep; the other two replicate the identical
#: design as robustness checks (same conditions, cases, metrics, and the
#: SAME planned seed schedule — planned_runs() derives seeds from
#: MASTER_SEED only, independent of model, so per-(condition, case, repeat)
#: seeds are identical across models for cross-model comparability).
REPLICATION_MODELS: dict[str, tuple[str, bool | None]] = {
    "qwen3.5:9b": ("results", False),
    "qwen2.5:7b-instruct": ("results-qwen2.5-7b", None),
    "mistral-nemo:latest": ("results-mistral-nemo", None),
    # substituted for gate-failed mistral-nemo (see CHANGELOG 2026-08-06 late)
    "mistral-small3.2:24b": ("results-mistral-small3.2", None),
    # candidate third model after both mistrals gate-failed (Ollama template bug)
    "llama3.1:8b": ("results-llama3.1-8b", None),
    "qwen2.5:14b-instruct": ("results-qwen2.5-14b", None),
    "gemma3:27b": ("results-gemma3-27b", None),
    "granite4:latest": ("results-granite4", None),
    "gpt-oss:20b": ("results-gpt-oss-20b", None),
}


def config_for_model(model: str) -> ExperimentConfig:
    """The full experiment configuration for one replication model.

    Each model gets its own sibling results dir (own manifest, journals,
    progress, gates evidence) so sweeps can never contaminate each other.
    """
    import dataclasses

    if model not in REPLICATION_MODELS:
        raise KeyError(
            f"unknown replication model {model!r}; add it to REPLICATION_MODELS"
        )
    dirname, think = REPLICATION_MODELS[model]
    return dataclasses.replace(
        DEFAULT_CONFIG,
        model=model,
        think=think,
        results_dir=EXPERIMENTS_DIR / dirname,
    )

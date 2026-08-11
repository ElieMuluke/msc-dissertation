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
    #: Wire ``think`` parameter, tri-state (langchain-ollama ``reasoning``
    #: is passed straight through as the wire ``think`` field —
    #: ``langchain_ollama/chat_models.py:804``, and the ollama client
    #: serialises the request with ``exclude_none``):
    #:
    #: - ``False`` — sends ``think: false``; deliberation OFF. Required for
    #:   thinking models that think by default (qwen3.5:9b, see G0). This is
    #:   the sealed corpus's condition (contexts 1-2).
    #: - ``None``  — omits the parameter entirely, for models without a
    #:   thinking mode where sending it could be rejected (captured
    #:   per-model by the replication mini-gate).
    #: - ``True``  — sends ``think: true``; deliberation ON. The
    #:   thinking-on track (pre-registered 2026-08-11 evening). Reasoning
    #:   must then arrive on the SEPARATE ``message.thinking`` channel and
    #:   must NOT appear inline in ``message.content``; that is the
    #:   INVERTED mini-gate criterion (``mini_gates.think_behavior``).
    #:   Expect 3-5x the tokens and wall clock of the ``False`` arms.
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
    #: Cache-state control (harness v2, pre-registrable per sweep):
    #: - ``"none"``    — current behaviour, byte-identical to harness v1
    #:   (the default; sweeps 1-7 ran with this implicitly);
    #: - ``"prewarm"`` — before each t0-fixed / pert-t0 run, the arm's exact
    #:   opening prompt is sent once and the reply discarded, so the run
    #:   measures warm-KV-state repeatability;
    #: - ``"shuffle"`` — per-repeat case-order randomisation, derived
    #:   deterministically from MASTER_SEED (averages KV-cache/history
    #:   position effects across cases).
    #: The active policy is recorded in the manifest and on every journal
    #: line. WARNING: changing the policy mid-sweep invalidates the sweep's
    #: internal comparability (runs before/after the switch saw different
    #: cache states and, under shuffle, different execution orders) — pick
    #: it before run 1 and keep it for the whole sweep, like every other
    #: locked constant.
    cache_policy: str = "none"
    #: Refresh the per-run environment fingerprint (nvidia-smi snapshot)
    #: every N runs; between refreshes the cached snapshot is journalled.
    env_fingerprint_every: int = 25
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
#: registry KEY -> (results dirname, wire think parameter[, served model tag]).
#: qwen3.5:9b is the headline pre-registered sweep; the other entries
#: replicate the identical design as robustness checks (same conditions,
#: cases, metrics, and the SAME planned seed schedule — planned_runs()
#: derives seeds from MASTER_SEED only, independent of model, so
#: per-(condition, case, repeat) seeds are identical across models for
#: cross-model comparability).
#:
#: Key/tag separation (2026-08-08, owner-approved infra-context-2
#: replications): a 2-tuple value means the key IS the served model tag
#: (all original entries, unchanged). A 3-tuple value adds an explicit
#: served model tag, so one model tag can appear under several keys — one
#: per infra context — each with its own isolated results dir. Convention
#: for context keys: "<model-tag>@<ollama-version>". Runners, manifests
#: and servers always use the TAG (``config_for_model(key).model``); dirs,
#: journals and gate evidence live under the KEY's results dirname.
#:
#: Thinking-on track (2026-08-11, pre-registered before any run): keys
#: suffixed "@think" serve the same TAG with ``think=True`` into a
#: dedicated "results-<slug>-thinking" dir. They are the ONLY entries whose
#: think value may differ from their tag's thinking-off entry — that
#: difference IS the manipulation, so their ``config_hash`` differs from
#: the thinking-off key's by design (``think`` is hashed), which is what
#: keeps the two tracks from ever being mistaken for one another.
REPLICATION_MODELS: dict[str, tuple[str, bool | None] | tuple[str, bool | None, str]] = {
    "qwen3.5:9b": ("results", False),
    "qwen2.5:7b-instruct": ("results-qwen2.5-7b", None),
    "mistral-nemo:latest": ("results-mistral-nemo", None),
    # substituted for gate-failed mistral-nemo (see CHANGELOG 2026-08-06 late)
    "mistral-small3.2:24b": ("results-mistral-small3.2", None),
    # candidate third model after both mistrals gate-failed (Ollama template bug)
    "llama3.1:8b": ("results-llama3.1-8b", None),
    "qwen2.5:14b-instruct": ("results-qwen2.5-14b", None),
    "gemma3:27b": ("results-gemma3-27b", None),
    "gemma4:latest": ("results-gemma4", None),
    "granite4:latest": ("results-granite4", None),
    "gpt-oss:20b": ("results-gpt-oss-20b", None),
    # infra context 2 (Ollama 0.32.6) qwen replications — see CHANGELOG
    # 2026-08-08. Same model blobs (digest-pinned), same seed schedule,
    # distinct results dirs; the 0.31.1 sweeps stay the pre-registered results.
    # gate battery 2026-08-11 (candidates for a future sweep; strict policy)
    "granite4.1:8b": ("results-granite4.1-8b", None),
    "lfm2.5:8b": ("results-lfm2.5-8b", None),
    # pulled 2026-08-11 under Ollama 0.32.9 (412'd on 0.32.6 as "requires
    # newer Ollama"). /api/show reports capability "thinking", so its
    # thinking-off entry sends think=false explicitly (like qwen3.5:9b),
    # never None — omitting it would let the model think by default.
    "muse-glimmer:30b": ("results-muse-glimmer-30b", False),
    "qwen2.5:7b-instruct@0.32.6": (
        "results-qwen2.5-7b-ollama0326", None, "qwen2.5:7b-instruct"),
    "qwen3.5:9b@0.32.6": (
        "results-qwen3.5-9b-ollama0326", False, "qwen3.5:9b"),
    "qwen2.5:14b-instruct@0.32.6": (
        "results-qwen2.5-14b-ollama0326", None, "qwen2.5:14b-instruct"),
    # --- thinking-on track (infra context 3, Ollama 0.32.9) --------------
    # Candidate set = every locally stored model whose /api/show
    # capabilities include "thinking" (verified 2026-08-11 against the
    # pinned arm-A server). Own results dirs; none collides with a sealed
    # dir. gemma4:e4b is omitted: it shares gemma4:latest's blob digest.
    "qwen3.5:9b@think": ("results-qwen3.5-9b-thinking", True, "qwen3.5:9b"),
    "lfm2.5:8b@think": ("results-lfm2.5-8b-thinking", True, "lfm2.5:8b"),
    "gemma4:latest@think": ("results-gemma4-thinking", True, "gemma4:latest"),
    "gpt-oss:20b@think": ("results-gpt-oss-20b-thinking", True, "gpt-oss:20b"),
    "deepseek-r1:14b@think": (
        "results-deepseek-r1-14b-thinking", True, "deepseek-r1:14b"),
    "muse-glimmer:30b@think": (
        "results-muse-glimmer-30b-thinking", True, "muse-glimmer:30b"),
}

#: Registry-key suffix marking the thinking-on track (see REPLICATION_MODELS).
THINKING_KEY_SUFFIX = "@think"


def thinking_keys() -> tuple[str, ...]:
    """Registry keys belonging to the thinking-on track, in registry order."""
    return tuple(k for k in REPLICATION_MODELS if k.endswith(THINKING_KEY_SUFFIX))


def replication_entry(key: str) -> tuple[str, str, bool | None]:
    """Resolve a registry key to ``(model_tag, dirname, think)``.

    For 2-tuple entries the key doubles as the served model tag (original
    scheme, byte-compatible); 3-tuple entries carry the tag explicitly.
    """
    if key not in REPLICATION_MODELS:
        raise KeyError(
            f"unknown replication model {key!r}; add it to REPLICATION_MODELS"
        )
    entry = REPLICATION_MODELS[key]
    if len(entry) == 2:
        dirname, think = entry
        return key, dirname, think
    dirname, think, model_tag = entry
    return model_tag, dirname, think


def config_for_model(model: str) -> ExperimentConfig:
    """The full experiment configuration for one replication registry key.

    Each key gets its own sibling results dir (own manifest, journals,
    progress, gates evidence) so sweeps can never contaminate each other.
    The returned config's ``.model`` is the served model TAG — the value
    runners, manifests and Ollama servers use — which equals the key except
    for explicit key/tag entries (e.g. ``"…@0.32.6"`` infra-context keys).
    """
    import dataclasses

    model_tag, dirname, think = replication_entry(model)
    return dataclasses.replace(
        DEFAULT_CONFIG,
        model=model_tag,
        think=think,
        results_dir=EXPERIMENTS_DIR / dirname,
    )

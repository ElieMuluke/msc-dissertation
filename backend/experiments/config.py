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
DFAH_REPO = Path("/home/eliem/Projects/dfah-repo")
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

# --- Budget-sensitivity track (v2b, pre-registered; "@b32" registry keys) ----
#: Per-role LLM-turn budgets for the MAS pipeline. These are the existing
#: ``max_iterations`` semantics (model calls per tool loop), applied per
#: node — NOT tool-call counts. They pool to 32, matching the single arm,
#: so the pooled turn budget is EQUAL across arms and each agent is TOLD
#: its budget (see the *_B32 prompt variants). Sized to demand: the data
#: node is the only multi-tool node (16); policy_risk has one tool (8);
#: orchestrator and reporting call no tools (4 each, headroom only).
MAS_ITERATION_BUDGETS: dict[str, int] = {
    "orchestrator": 4,
    "data": 16,
    "policy_risk": 8,
    "reporting": 4,
}
#: The single arm's LLM-turn budget under the budget track — the pooled MAS
#: total, disclosed in its prompt exactly as each MAS role's budget is.
SINGLE_ITERATION_BUDGET: int = 32
#: Registry-key marker for the budget-sensitivity track: a key contains
#: "@b32" either terminally ("<tag>@b32") or hyphen-qualified
#: ("<tag>@b32-think", "<tag>@b32-think-budget").
B32_KEY_MARKER = "@b32"


def is_budget_track_key(key: str) -> bool:
    """True for budget-sensitivity ("@b32") registry keys."""
    return key.endswith(B32_KEY_MARKER) or f"{B32_KEY_MARKER}-" in key


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
    #: v2-UNIFORM LEGACY: the pre-registered v2 sweeps ran this single scalar
    #: for every agent in both arms (8 per agent — pooled 32 for the 4-node
    #: MAS pipeline vs 8 for the monolith, the asymmetry the budget track
    #: removes). It stays readable so old manifests keep verifying; the
    #: budget-sensitivity track ignores it in favour of the per-role fields
    #: below (selected by ``budget_track``).
    max_iterations: int = 8
    #: Budget-sensitivity track (v2b, "@b32" registry keys) — per-role
    #: LLM-turn budgets for the MAS pipeline (the existing ``max_iterations``
    #: semantics, applied per node; NOT tool-call counts). Pooled: 32.
    mas_iteration_budgets: dict[str, int] = field(
        default_factory=lambda: dict(MAS_ITERATION_BUDGETS)
    )
    #: Budget-sensitivity track — the single arm's LLM-turn budget, equal to
    #: the MAS pipeline's pooled total so neither arm is budget-bound first.
    single_iteration_budget: int = SINGLE_ITERATION_BUDGET
    #: True only for "@b32" registry keys: selects the per-role budgets above
    #: AND the budget-disclosing prompt variants (SYSTEM_PROMPT_B32 /
    #: MAS_PROMPTS_B32). False = byte-identical v2 construction.
    budget_track: bool = False
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
    # --- budget-raised thinking-on condition (2026-08-12, pre-registered) ---
    # qwen3.5:9b@think FAILED its gate 6/8 because the MAS `reporting` node
    # spends the locked num_predict=2048 on deliberation and emits empty
    # content. This key re-runs the identical design with the generation
    # budget raised (see THINKING_BUDGET_OVERRIDES) so the qwen family is
    # represented in the thinking track at all. TWO factors therefore differ
    # from the sealed thinking-off qwen3.5:9b sweep (think AND num_predict):
    # that comparison is CONFOUNDED by construction and must be reported as
    # such — see CHANGELOG 2026-08-12.
    "qwen3.5:9b@think-budget": (
        "results-qwen3.5-9b-thinking-budget", True, "qwen3.5:9b"),
    # --- budget-sensitivity track (v2b, pre-registered; owner-approved) ------
    # "@b32" keys re-run the identical design with the iteration budget
    # EQUALISED across arms (single 32; MAS 4/16/8/4 per role, pooled 32)
    # and DISCLOSED to every agent in its prompt (SYSTEM_PROMPT_B32 /
    # MAS_PROMPTS_B32). Everything else is the locked v2 design — cases,
    # conditions, seeds, num_predict 2048, num_ctx 16384, cache_policy
    # "none", strict v2 parsing, run_timeout_s 900. ``think`` per key
    # mirrors the tag's sealed counterpart exactly. The "@b32-think-budget"
    # key additionally carries its sealed counterpart's pre-approved
    # num_predict=8192 override (see THINKING_BUDGET_OVERRIDES) — that
    # sweep is confounded vs 2048 sweeps by construction, as before.
    "qwen2.5:7b-instruct@b32": (
        "results-budget-qwen2.5-7b", None, "qwen2.5:7b-instruct"),
    "granite4.1:8b@b32": ("results-budget-granite4.1-8b", None, "granite4.1:8b"),
    "qwen3.5:9b@b32": ("results-budget-qwen3.5-9b", False, "qwen3.5:9b"),
    "lfm2.5:8b@b32-think": (
        "results-budget-lfm2.5-8b-thinking", True, "lfm2.5:8b"),
    "qwen3.5:9b@b32-think-budget": (
        "results-budget-qwen3.5-9b-thinking", True, "qwen3.5:9b"),
    "gemma4:latest@b32": ("results-budget-gemma4", None, "gemma4:latest"),
}

#: Registry-key marker for the thinking-on track (see REPLICATION_MODELS).
#: A key either ends with it ("<tag>@think") or qualifies it with a
#: hyphenated variant ("<tag>@think-budget"); both send ``think=True``.
THINKING_KEY_SUFFIX = "@think"

#: Per-registry-key override of the locked ``num_predict`` constant.
#:
#: ``num_predict`` is a LOCKED design constant (2048 everywhere else, hashed
#: into every manifest's config record). This dict is the single, explicit
#: place where a pre-registered condition may raise it, keyed by registry KEY
#: so one served tag can appear both overridden and not. The value flows
#: through :func:`config_for_model` into ``ExperimentConfig.num_predict`` and
#: therefore into the manifest's hashed ``config`` record and every journal
#: line — a budget-raised sweep can never be confused with a standard one.
#:
#: Raising it BREAKS comparability with every sweep run at 2048: any
#: cross-condition claim involving an overridden key is confounded by the
#: budget as well as by whatever else differs. Add an entry only with a dated
#: CHANGELOG pre-registration that states the confound.
THINKING_BUDGET_OVERRIDES: dict[str, int] = {
    # 8192: the failing qwen3.5:9b@think gate showed the MAS `reporting` node
    # consuming 6,108 completion tokens without emitting an answer, so 2048
    # (and 4096) cannot fit deliberation + answer on a 4-node pipeline. 8192
    # is the smallest power-of-two headroom above the observed deliberation
    # cost. num_ctx stays 16384, so prompt + generation still fit the context.
    "qwen3.5:9b@think-budget": 8192,
    # Budget track: the qwen3.5:9b thinking-on sweep carries its sealed
    # counterpart's raised generation budget (same rationale, same confound
    # disclosure — see CHANGELOG-budget-track-DRAFT.md).
    "qwen3.5:9b@b32-think-budget": 8192,
}


def thinking_keys() -> tuple[str, ...]:
    """Registry keys belonging to the thinking-on track, in registry order.

    Covers both the plain ``"@think"`` keys and hyphenated variants of the
    marker (``"@think-budget"``) — every key here runs ``think=True``.
    """
    return tuple(
        k for k in REPLICATION_MODELS
        if k.endswith(THINKING_KEY_SUFFIX) or f"{THINKING_KEY_SUFFIX}-" in k
    )


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

    ``num_predict`` is the locked 2048 unless the KEY appears in
    :data:`THINKING_BUDGET_OVERRIDES`, in which case that condition's
    pre-registered raised budget is used (and is hashed into its manifest).

    ``budget_track`` is True only for "@b32" keys (see
    :func:`is_budget_track_key`); every other key constructs byte-identically
    to the pre-b32 code path.
    """
    import dataclasses

    model_tag, dirname, think = replication_entry(model)
    return dataclasses.replace(
        DEFAULT_CONFIG,
        model=model_tag,
        think=think,
        num_predict=THINKING_BUDGET_OVERRIDES.get(model, DEFAULT_CONFIG.num_predict),
        results_dir=EXPERIMENTS_DIR / dirname,
        budget_track=is_budget_track_key(model),
    )

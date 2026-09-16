"""
⚠ NON-AUTHORITATIVE / PROVISIONAL — NOT THE IMPLEMENTATION BASELINE ⚠

This module is an implementation candidate only. It is NOT a realization of
`docs/architecture/WORKSPACE_ARCHITECTURE.md`, which is the sole authoritative
Workspace architecture document. Do not import this module assuming it conforms
to that document, and do not treat its presence on `main` as architectural
approval.

Known non-conformance (see WORKSPACE_ARCHITECTURE.md §B.6 for the full audit):
  - VerificationStatus collapses three independent verification dimensions
    (§K.1) into one flat enum.
  - File has no state field — QUARANTINED is unrepresentable (§I.3).
  - File has no version field — optimistic concurrency is unimplementable (§I.7).
  - Every "Architecture:" docstring below cites the predecessor UX/UI report,
    which is itself marked SUPERSEDED — DO NOT USE FOR IMPLEMENTATION.

Disposition (rework to conform / documented exception / remove) is Open
Decision #19 in WORKSPACE_ARCHITECTURE.md §V, pending an explicit decision from
the project's decision-makers. This banner should be removed only when that
decision is made and recorded, not independently of it.
---

core/workspace/domain.py — Workspace Domain Model

Defines the core domain primitives for OCBrain's workspace architecture:
Project, Session, Discussion, Task, File, Artifact, ComputationalLevel,
and ResourcePolicy.

Architecture:
    OCBrain UX/UI & Workspace Architecture Report §J — Domain Model.
    Extends the existing Kernel domain (Goal, ExecutionPlan,
    WorkflowDefinition, ExecutionContext) with workspace-level
    primitives that provide persistent, user-facing structure above
    execution-level concepts.

Design:
    - Pure data classes — no execution logic, no I/O.
    - Fields are additive-only across versions.
    - Every primitive has a UUID identity and timestamps.
    - Follows the same dataclass + field(default_factory=...) convention
      established by ExecutionContext, WorkflowDefinition, and Goal.
    - ComputationalLevel is a user-facing intent, not a model tier.
    - ResourcePolicy is the system's translation of that intent.

Explicitly NOT in scope:
    - Persistence (see workspace/repository.py — separate concern)
    - API serialization (see interface/workspace_api.py)
    - Business logic (see workspace/service.py)
    - C-MoE expert selection (future, post-kernel-freeze)

Governance:
    Domain objects themselves are inert. All mutations flow through
    the workspace service layer, which must respect GovernanceKernel
    constraints. No domain object may bypass Governance.

Relationship to existing primitives:
    - Task.goal → core.cognitive.intent.Goal (existing)
    - Task.plan → core.cognitive.planner.ExecutionPlan (existing)
    - Execution wraps existing ExecutionContext/ExecutionOutcome
    - File and Artifact are NEW — no predecessor exists
    - ComputationalLevel and ResourcePolicy are NEW
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


# ── Enums ─────────────────────────────────────────────────────────────────


class ProjectState(Enum):
    """Lifecycle state of a Project."""
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


class SessionState(Enum):
    """Lifecycle state of a Session."""
    ACTIVE = "active"
    PAUSED = "paused"
    CLOSED = "closed"
    ARCHIVED = "archived"


class DiscussionState(Enum):
    """Lifecycle state of a Discussion."""
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"


class TaskState(Enum):
    """Lifecycle state of a Task.

    Mirrors the conceptual flow:
    PLANNED → APPROVED → EXECUTING → COMPLETED | FAILED | CANCELLED
    """
    PLANNED = "planned"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ComputationalLevel(Enum):
    """User-facing computational intensity intent.

    Architecture:
        UX Architecture Report §L — Computational Control.

    This is a user preference expressing desired computational intensity.
    It is NOT a model tier, NOT a fixed resource allocation, and NOT
    a direct API parameter to any provider.

    The system translates this intent into an adaptive ResourcePolicy
    based on task complexity, available resources, governance constraints,
    and project/session defaults.

    Semantics:
        LOW    — Minimize latency and resource use.
        MEDIUM — Balanced quality / cost / latency.
        HIGH   — Prioritize quality and reliability.
        MAX    — Maximum justified computation within hard caps.
                 MAX never means unlimited.
    """
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    MAX = "max"


class FileSource(Enum):
    """How a File entered the workspace."""
    UPLOADED = "uploaded"       # User uploaded
    GENERATED = "generated"    # OCBrain created during execution
    IMPORTED = "imported"      # Imported from external source


class ArtifactType(Enum):
    """Category of an Artifact."""
    TEXT = "text"
    CODE = "code"
    DATA = "data"
    REPORT = "report"
    IMAGE = "image"
    BINARY = "binary"
    OTHER = "other"


class VerificationStatus(Enum):
    """Verification state of an Artifact or claim.

    Architecture:
        UX Architecture Report §N — Verification UX.
        Verification is distinct from critique, confidence, or model opinion.
    """
    UNVERIFIED = "unverified"
    VERIFIED = "verified"
    CONTRADICTED = "contradicted"
    SUPERSEDED = "superseded"


# ── Domain Primitives ─────────────────────────────────────────────────────


@dataclass
class Project:
    """A persistent workspace container.

    Architecture:
        UX Architecture Report §J.1 — Project.

    Projects are long-lived, user-managed containers that hold sessions,
    files, artifacts, memory, and policies. They persist across sessions
    and provide the top-level organizational unit.

    Attributes:
        project_id: Globally unique identifier.
        name: User-assigned project name.
        description: Optional project description.
        state: Lifecycle state.
        default_computational_level: Default for new sessions/tasks.
        created_at: Unix epoch creation time.
        updated_at: Unix epoch last modification time.
        metadata: Extensible project data.
    """
    project_id:                 str                  = field(default_factory=lambda: str(uuid.uuid4()))
    name:                       str                  = ""
    description:                str                  = ""
    state:                      ProjectState         = ProjectState.ACTIVE
    default_computational_level: ComputationalLevel  = ComputationalLevel.MEDIUM
    created_at:                 float                = field(default_factory=time.time)
    updated_at:                 float                = field(default_factory=time.time)
    metadata:                   Dict[str, Any]       = field(default_factory=dict)


@dataclass
class Session:
    """An active working period within a Project.

    Architecture:
        UX Architecture Report §J.1 — Session.

    Sessions are medium-lived, closeable and resumable. They hold
    discussions, tasks, and session-scoped context. A session inherits
    its project's defaults but can override them.

    Attributes:
        session_id: Globally unique identifier.
        project_id: Parent project.
        name: Auto-generated or user-assigned.
        state: Lifecycle state.
        default_computational_level: Overrides project default if set.
        created_at: Unix epoch creation time.
        closed_at: Unix epoch close time (None if still active).
        metadata: Extensible session data.
    """
    session_id:                 str                           = field(default_factory=lambda: str(uuid.uuid4()))
    project_id:                 str                           = ""
    name:                       str                           = ""
    state:                      SessionState                  = SessionState.ACTIVE
    default_computational_level: Optional[ComputationalLevel] = None  # None = inherit from project
    created_at:                 float                         = field(default_factory=time.time)
    closed_at:                  Optional[float]               = None
    metadata:                   Dict[str, Any]                = field(default_factory=dict)

    def effective_computational_level(self, project: Project) -> ComputationalLevel:
        """Resolve the effective computational level, inheriting from project if unset."""
        return self.default_computational_level or project.default_computational_level


@dataclass
class Discussion:
    """A focused conversation thread within a Session.

    Architecture:
        UX Architecture Report §J.1 — Discussion.

    Discussions are branchable conversation threads that can hold messages,
    attached files, decisions, and tasks. Multiple discussions can coexist
    within a session, each with its own context scope.

    Context inheritance: Discussion context inherits from Session context
    but adds discussion-specific state. Sibling discussions are isolated.

    Attributes:
        discussion_id: Globally unique identifier.
        session_id: Parent session.
        title: Auto-generated or user-assigned.
        state: Lifecycle state.
        branched_from: If branched, the source discussion ID.
        branch_point_message_index: Message index where branching occurred.
        created_at: Unix epoch creation time.
        metadata: Extensible discussion data.
    """
    discussion_id:              str                  = field(default_factory=lambda: str(uuid.uuid4()))
    session_id:                 str                  = ""
    title:                      str                  = ""
    state:                      DiscussionState      = DiscussionState.ACTIVE
    branched_from:              Optional[str]        = None
    branch_point_message_index: Optional[int]        = None
    created_at:                 float                = field(default_factory=time.time)
    metadata:                   Dict[str, Any]       = field(default_factory=dict)


@dataclass
class Message:
    """A single message within a Discussion.

    Attributes:
        message_id: Globally unique identifier.
        discussion_id: Parent discussion.
        role: Message author role (user, assistant, system).
        content: Message text content.
        attached_file_ids: Files referenced or attached to this message.
        execution_id: If this message triggered an execution, its ID.
        computational_level: The level requested for this message's task.
        timestamp: Unix epoch creation time.
        metadata: Extensible message data (e.g., token counts, model used).
    """
    message_id:           str                           = field(default_factory=lambda: str(uuid.uuid4()))
    discussion_id:        str                           = ""
    role:                 str                           = "user"  # user | assistant | system
    content:              str                           = ""
    attached_file_ids:    List[str]                     = field(default_factory=list)
    execution_id:         Optional[str]                 = None
    computational_level:  Optional[ComputationalLevel]  = None
    timestamp:            float                         = field(default_factory=time.time)
    metadata:             Dict[str, Any]                = field(default_factory=dict)


@dataclass
class Task:
    """A goal-directed unit of work.

    Architecture:
        UX Architecture Report §J.1 — Task.

    Tasks bridge the workspace domain (user intent) and the kernel domain
    (Goal, ExecutionPlan, WorkflowDefinition). A Task wraps the cognitive
    pipeline's output and tracks its execution lifecycle.

    Attributes:
        task_id: Globally unique identifier.
        discussion_id: The discussion that initiated this task (optional).
        session_id: The session this task belongs to.
        project_id: The project this task belongs to.
        state: Lifecycle state.
        computational_level: Requested computational intensity.
        goal_summary: Human-readable summary of the goal.
        goal_id: Reference to the cognitive Goal object (root_operation_id).
        execution_ids: Execution attempts for this task.
        artifact_ids: Artifacts produced by this task.
        created_at: Unix epoch creation time.
        completed_at: Unix epoch completion time.
        metadata: Extensible task data.
    """
    task_id:              str                           = field(default_factory=lambda: str(uuid.uuid4()))
    discussion_id:        Optional[str]                 = None
    session_id:           str                           = ""
    project_id:           str                           = ""
    state:                TaskState                     = TaskState.PLANNED
    computational_level:  ComputationalLevel            = ComputationalLevel.MEDIUM
    goal_summary:         str                           = ""
    goal_id:              Optional[str]                 = None  # → Goal.root_operation_id
    execution_ids:        List[str]                     = field(default_factory=list)
    artifact_ids:         List[str]                     = field(default_factory=list)
    created_at:           float                         = field(default_factory=time.time)
    completed_at:         Optional[float]               = None
    metadata:             Dict[str, Any]                = field(default_factory=dict)


@dataclass
class FileMetadata:
    """Metadata about a file's content and processing state.

    Attributes:
        mime_type: MIME type if detected.
        encoding: Character encoding if text.
        line_count: Number of lines if text.
        language: Programming language if source code.
        parsed: Whether the file has been parsed/indexed.
        preview_available: Whether a preview can be generated.
        hash_sha256: Content hash for deduplication/integrity.
    """
    mime_type:          Optional[str]  = None
    encoding:           Optional[str]  = None
    line_count:         Optional[int]  = None
    language:           Optional[str]  = None
    parsed:             bool           = False
    preview_available:  bool           = False
    hash_sha256:        Optional[str]  = None


@dataclass
class File:
    """A file within the workspace.

    Architecture:
        UX Architecture Report §J.1 — File.
        Files are first-class workspace objects, not chat attachments.

    Files support the full lifecycle: upload → validate → discover →
    inspect → read/preview → select as context → analyze/transform →
    create/modify → version/compare → verify → save → download/export →
    archive/delete/restore.

    Attributes:
        file_id: Globally unique identifier.
        project_id: Owning project.
        name: Display name (basename).
        path: Logical path within the project file space.
        size_bytes: File size.
        source: How the file entered the workspace.
        metadata: Content metadata.
        storage_ref: Internal storage location reference.
        uploaded_by: Who uploaded (user ID or "system").
        created_at: Unix epoch creation time.
        modified_at: Unix epoch last modification time.
        deleted: Soft-delete flag.
        extra: Extensible file data.
    """
    file_id:      str                  = field(default_factory=lambda: str(uuid.uuid4()))
    project_id:   str                  = ""
    name:         str                  = ""
    path:         str                  = ""
    size_bytes:   int                  = 0
    source:       FileSource           = FileSource.UPLOADED
    metadata:     FileMetadata         = field(default_factory=FileMetadata)
    storage_ref:  str                  = ""  # internal path to stored content
    uploaded_by:  str                  = "user"
    created_at:   float                = field(default_factory=time.time)
    modified_at:  float                = field(default_factory=time.time)
    deleted:      bool                 = False
    extra:        Dict[str, Any]       = field(default_factory=dict)


@dataclass
class ArtifactLineage:
    """Provenance tracking for an Artifact.

    Architecture:
        UX Architecture Report §43 — Provenance UX.

    Attributes:
        source_task_id: The task that produced this artifact.
        source_execution_id: The specific execution that produced it.
        input_file_ids: Files used as inputs.
        input_artifact_ids: Other artifacts used as inputs.
        capability_types: Capabilities invoked during production.
        model_used: Model identifier if an LLM was involved.
        computational_level: The level active during production.
    """
    source_task_id:       Optional[str]  = None
    source_execution_id:  Optional[str]  = None
    input_file_ids:       List[str]      = field(default_factory=list)
    input_artifact_ids:   List[str]      = field(default_factory=list)
    capability_types:     List[str]      = field(default_factory=list)
    model_used:           Optional[str]  = None
    computational_level:  Optional[str]  = None


@dataclass
class Artifact:
    """A versioned, traceable output produced by OCBrain.

    Architecture:
        UX Architecture Report §J.1 — Artifact.
        Artifacts are distinct from Files: files are inputs, artifacts
        are outputs. Both are first-class.

    Attributes:
        artifact_id: Globally unique identifier.
        project_id: Owning project.
        name: Display name.
        artifact_type: Category (text, code, data, etc.).
        content: The artifact content (text-based) or reference.
        file_id: If the artifact is file-based, reference to the File.
        version: Version number (monotonically increasing).
        verification: Current verification status.
        lineage: Provenance tracking.
        created_at: Unix epoch creation time.
        modified_at: Unix epoch last modification time.
        metadata: Extensible artifact data.
    """
    artifact_id:    str                  = field(default_factory=lambda: str(uuid.uuid4()))
    project_id:     str                  = ""
    name:           str                  = ""
    artifact_type:  ArtifactType         = ArtifactType.TEXT
    content:        str                  = ""
    file_id:        Optional[str]        = None
    version:        int                  = 1
    verification:   VerificationStatus   = VerificationStatus.UNVERIFIED
    lineage:        ArtifactLineage      = field(default_factory=ArtifactLineage)
    created_at:     float                = field(default_factory=time.time)
    modified_at:    float                = field(default_factory=time.time)
    metadata:       Dict[str, Any]       = field(default_factory=dict)


# ── Resource Policy ───────────────────────────────────────────────────────


@dataclass
class ResourceBudget:
    """Hard budget ceilings for a single task or execution.

    Architecture:
        UX Architecture Report §M.4, §20 — MAX is bounded,
        Resource Budgets and Hard Caps.

    These are hard ceilings, never overridable by ComputationalLevel.
    The system enforces: soft target → hard ceiling → emergency cutoff.

    Attributes:
        max_tokens: Maximum total tokens (input + output).
        max_cost_usd: Maximum cost in USD.
        max_tool_calls: Maximum number of tool/capability invocations.
        max_retries: Maximum retry attempts.
        max_duration_seconds: Maximum wall-clock time.
        max_llm_calls: Maximum number of LLM API calls.
        max_parallel: Maximum parallel operations.
    """
    max_tokens:             Optional[int]   = None
    max_cost_usd:           Optional[float] = None
    max_tool_calls:         Optional[int]   = None
    max_retries:            int             = 3
    max_duration_seconds:   float           = 300.0
    max_llm_calls:          Optional[int]   = None
    max_parallel:           int             = 1


@dataclass
class ResourcePolicy:
    """The system's adaptive translation of a ComputationalLevel.

    Architecture:
        UX Architecture Report §L.1, §M — Computational Control.

    A ResourcePolicy is derived from:
        User's ComputationalLevel +
        Task complexity +
        Available resources +
        Governance constraints +
        Project/Session defaults

    It specifies the concrete resource allocation for a task.
    The user never sets ResourcePolicy directly — they set
    ComputationalLevel and the system derives this.

    Attributes:
        requested_level: What the user asked for.
        effective_level: What the system determined after policy evaluation.
        model_preference: Preferred model tier (e.g., "strong", "fast").
        reasoning_effort: Provider-agnostic reasoning effort (low/medium/high/max).
        expert_count: Maximum number of C-MoE experts to engage.
        retrieval_breadth: Retrieval expansion factor (1.0 = normal).
        verification_depth: Verification effort (minimal/standard/strong/strongest).
        budget: Hard resource ceilings.
        rationale: Why the effective level differs from requested (if it does).
        metadata: Extensible policy data.
    """
    requested_level:    ComputationalLevel  = ComputationalLevel.MEDIUM
    effective_level:    ComputationalLevel  = ComputationalLevel.MEDIUM
    model_preference:   str                 = "standard"  # fast | standard | strong | best
    reasoning_effort:   str                 = "medium"    # low | medium | high | max
    expert_count:       int                 = 1
    retrieval_breadth:  float               = 1.0
    verification_depth: str                 = "standard"  # minimal | standard | strong | strongest
    budget:             ResourceBudget      = field(default_factory=ResourceBudget)
    rationale:          str                 = ""
    metadata:           Dict[str, Any]      = field(default_factory=dict)


@dataclass
class ResourceAllocation:
    """Actual resources consumed during an execution.

    Architecture:
        UX Architecture Report §M.6, §26 — Allocation must be observable.
        Requested ≠ Effective ≠ Actual.

    This is recorded after execution, not set before. It captures what
    actually happened, for observability and billing.

    Attributes:
        policy: The policy that governed this execution.
        tokens_used: Actual tokens consumed.
        cost_usd: Actual cost incurred.
        tool_calls_made: Actual tool/capability invocations.
        llm_calls_made: Actual LLM API calls.
        models_used: Models actually invoked.
        experts_used: C-MoE experts actually engaged.
        duration_seconds: Actual wall-clock time.
        escalations: Number of escalation events.
        de_escalations: Number of de-escalation events.
        budget_utilization: Fraction of budget consumed (0.0–1.0).
    """
    policy:               ResourcePolicy     = field(default_factory=ResourcePolicy)
    tokens_used:          int                = 0
    cost_usd:             float              = 0.0
    tool_calls_made:      int                = 0
    llm_calls_made:       int                = 0
    models_used:          List[str]          = field(default_factory=list)
    experts_used:         List[str]          = field(default_factory=list)
    duration_seconds:     float              = 0.0
    escalations:          int                = 0
    de_escalations:       int                = 0
    budget_utilization:   float              = 0.0

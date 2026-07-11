"""
core/workflow/definition.py — Workflow Data Model (K2.2)

Declarative workflow definitions: nodes, edges, retry policies.

Architecture:
    KERNEL_ARCHITECTURE_v1.0.md §8 — Workflow Model.
    WorkflowDefinition is a static DAG describing execution order.
    WorkflowRuntime interprets it at execution time.

Design:
    - Pure data classes — no execution logic.
    - WorkflowNode specifies worker_type + config.
    - WorkflowEdge connects nodes (optional condition).
    - RetryPolicy controls per-node retry behavior.
    - WorkflowDefinition is the complete DAG.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class NodeStatus(Enum):
    """Lifecycle status of a workflow node during execution."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


@dataclass
class RetryPolicy:
    """Per-node retry configuration.

    Architecture:
        KERNEL_ARCHITECTURE_v1.0.md §8.3 — Retry Policy.

    Attributes:
        max_retries: Maximum retry attempts (0 = no retries).
        backoff_seconds: Initial backoff delay.
        backoff_multiplier: Exponential backoff factor.
        max_backoff_seconds: Maximum backoff delay.
        retryable_errors: Error substrings that trigger retries.
                          Empty list = retry on any error.
    """
    max_retries: int = 0
    backoff_seconds: float = 1.0
    backoff_multiplier: float = 2.0
    max_backoff_seconds: float = 30.0
    retryable_errors: List[str] = field(default_factory=list)


@dataclass
class WorkflowNode:
    """A single step in a workflow.

    Architecture:
        KERNEL_ARCHITECTURE_v1.0.md §8.1 — WorkflowNode.

    Attributes:
        node_id: Unique identifier within the workflow.
        worker_type: The worker type to invoke (must be in WorkerRegistry).
        config: Configuration passed to the worker via ExecutionContext.metadata.
        retry_policy: Optional retry behavior for this node.
        error_branch: Node ID to execute on failure (optional).
    """
    node_id: str = ""
    worker_type: str = ""
    config: Dict[str, Any] = field(default_factory=dict)
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    error_branch: str = ""


@dataclass
class WorkflowEdge:
    """A directed edge connecting two workflow nodes.

    Architecture:
        KERNEL_ARCHITECTURE_v1.0.md §8.2 — WorkflowEdge.

    Attributes:
        from_node: Source node ID.
        to_node: Target node ID.
        condition: Optional condition key checked against previous result metadata.
    """
    from_node: str = ""
    to_node: str = ""
    condition: str = ""


@dataclass
class WorkflowDefinition:
    """A complete workflow DAG.

    Architecture:
        KERNEL_ARCHITECTURE_v1.0.md §8 — Workflow Model.

    Attributes:
        workflow_id: Unique identifier for this workflow definition.
        name: Human-readable workflow name.
        nodes: All nodes in the workflow.
        edges: Directed edges defining execution order.
        entry_node: The first node to execute. Must exist in nodes.
        metadata: Additional workflow-level configuration.
    """
    workflow_id: str = ""
    name: str = ""
    nodes: List[WorkflowNode] = field(default_factory=list)
    edges: List[WorkflowEdge] = field(default_factory=list)
    entry_node: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_node(self, node_id: str) -> Optional[WorkflowNode]:
        """Look up a node by ID."""
        for node in self.nodes:
            if node.node_id == node_id:
                return node
        return None

    def get_successors(self, node_id: str) -> List[str]:
        """Return node IDs of all successors of the given node."""
        return [e.to_node for e in self.edges if e.from_node == node_id]

    def validate(self) -> List[str]:
        """Validate the workflow definition. Returns list of errors (empty = valid)."""
        errors = []
        node_ids = {n.node_id for n in self.nodes}

        if not self.entry_node:
            errors.append("No entry_node specified")
        elif self.entry_node not in node_ids:
            errors.append(f"entry_node '{self.entry_node}' not in nodes")

        for edge in self.edges:
            if edge.from_node not in node_ids:
                errors.append(f"Edge from unknown node: '{edge.from_node}'")
            if edge.to_node not in node_ids:
                errors.append(f"Edge to unknown node: '{edge.to_node}'")

        for node in self.nodes:
            if node.error_branch and node.error_branch not in node_ids:
                errors.append(f"Node '{node.node_id}' error_branch "
                              f"'{node.error_branch}' not in nodes")
        return errors


# ── Canonical Definitions (K2.2) ────────────────────────────────────────────

PLANNER_NODE_ID = "planner"


def build_planner_workflow(
    workflow_id: str = "planner-default",
) -> WorkflowDefinition:
    """The canonical single-node workflow used by the Orchestrator bridge.

    Architecture:
        KERNEL_ARCHITECTURE_v1.0.md §8 — Workflow Model.
        K2.2 — Production Runtime Migration.

    Design:
        Orchestrator.handle() does not itself know how to build a DAG — it
        wraps every incoming query in this trivial one-node workflow so
        that query handling participates in the same WorkflowRuntime
        lifecycle (events, retry policy, error containment) as any future
        multi-node workflow, without a bespoke non-workflow code path.

        The single node invokes worker_type="PlannerWorker", which itself
        performs the classify -> dispatch -> merge pipeline. Retries are
        deliberately disabled by default (RetryPolicy(max_retries=0)):
        PlannerWorker's own internal dispatch already fans out to multiple
        modules and contains their individual failures; retrying the whole
        pipeline on any partial failure would silently re-run modules that
        already succeeded. A future node-level RetryPolicy can be attached
        here once retry semantics for partial-success pipelines are
        explicitly designed -- not assumed as part of this cutover.

    Returns:
        A WorkflowDefinition with a single entry node, worker_type
        "PlannerWorker", node_id PLANNER_NODE_ID.
    """
    return WorkflowDefinition(
        workflow_id=workflow_id,
        name="default_planner_workflow",
        nodes=[
            WorkflowNode(
                node_id=PLANNER_NODE_ID,
                worker_type="PlannerWorker",
                retry_policy=RetryPolicy(max_retries=0),
            ),
        ],
        edges=[],
        entry_node=PLANNER_NODE_ID,
    )

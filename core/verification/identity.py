"""
Identity types for the Verification / Critic / Evidence System.

Convention match: core.workers.evaluator.EvaluationRecord uses a plain
`resource_id: str = field(default_factory=lambda: str(uuid.uuid4()))`
pattern -- no wrapper class, no Pydantic. This module follows the same
runtime representation (plain str) and adds typing.NewType wrappers
for call-site type safety, which costs nothing at runtime and is easy
to drop if a live-repo pull shows a different convention is preferred.
"""
from __future__ import annotations

import uuid
from typing import NewType


def new_id() -> str:
    """Matches the exact generation pattern used by EvaluationRecord."""
    return str(uuid.uuid4())


RequestId = NewType("RequestId", str)
VerificationId = NewType("VerificationId", str)
RunId = NewType("RunId", str)
StepId = NewType("StepId", str)
TaskId = NewType("TaskId", str)
ExecutionId = NewType("ExecutionId", str)
AttemptId = NewType("AttemptId", str)
WorkerId = NewType("WorkerId", str)
ArtifactId = NewType("ArtifactId", str)
EnvironmentId = NewType("EnvironmentId", str)
RubricId = NewType("RubricId", str)
CriterionId = NewType("CriterionId", str)
ClaimId = NewType("ClaimId", str)
EvidenceId = NewType("EvidenceId", str)
ObservationId = NewType("ObservationId", str)
ReceiptId = NewType("ReceiptId", str)
EscalationId = NewType("EscalationId", str)

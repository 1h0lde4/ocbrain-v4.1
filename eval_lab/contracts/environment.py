"""eval_lab/contracts/environment.py — environment definition and instance.

Implements §13 of this Slice. Kept small and deliberately thin on
"available tools"/"tool behavior" specifics -- Slice 2 does not execute
environments (§2's scope boundary explicitly excludes "environment
runner"), so those fields are descriptive metadata a future environment
runner will interpret, not something this contract layer validates the
semantics of.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from eval_lab.contracts.identifiers import (
    CURRENT_SCHEMA_VERSION,
    EnvironmentId,
    EnvironmentInstanceId,
    EnvironmentVersion,
    SchemaVersion,
)
from eval_lab.contracts.serialization import ContractValidationError


@dataclass(frozen=True)
class EnvironmentDefinition:
    """Describes available tools, initial-state specification, rules,
    oracle bindings, and authorization model (§13). `oracle_ids` is a
    plain tuple of references rather than embedded OracleDefinitions
    (oracle.py) -- per §26 of this Slice, references should not require
    the referenced object to be loaded in memory to validate."""

    environment_id: EnvironmentId
    version: EnvironmentVersion
    description: str
    available_tools: frozenset[str]
    initial_state_specification: str
    rules: tuple[str, ...] = ()
    oracle_ids: tuple[str, ...] = ()
    authorization_model_description: str = ""
    schema_version: SchemaVersion = CURRENT_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "environment_id": self.environment_id,
            "version": self.version,
            "description": self.description,
            "available_tools": sorted(self.available_tools),
            "initial_state_specification": self.initial_state_specification,
            "rules": list(self.rules),
            "oracle_ids": list(self.oracle_ids),
            "authorization_model_description": self.authorization_model_description,
            "schema_version": str(self.schema_version),
        }


@dataclass(frozen=True)
class EnvironmentInstance:
    """One concrete instantiated environment (§13: "repeated evaluation
    runs may each receive independent environment instances"). Isolation
    itself (per ADR-LAB-01/§22's execution-instance-isolation requirement)
    is a Slice 3+ runtime concern; this contract only records that an
    instance exists and which definition/version it was created from --
    it does not implement or enforce isolation."""

    environment_instance_id: EnvironmentInstanceId
    environment_id: EnvironmentId
    environment_version: EnvironmentVersion
    created_at: datetime
    seed: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "environment_instance_id": self.environment_instance_id,
            "environment_id": self.environment_id,
            "environment_version": self.environment_version,
            "created_at": self.created_at.isoformat(),
            "seed": self.seed,
        }

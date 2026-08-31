"""eval_lab — Agent Evaluation & Reliability Lab.

Reserved top-level package, sibling to `core/` (ADR-LAB-02). Nothing under
`core/` may import from here; this package must be deletable without
breaking normal OCBrain execution.

Slice 1 (research + architecture, six ADRs, all PROPOSED) is complete.
Slice 2 (this package's `contracts` subpackage) implements the domain
contract layer only: value objects, identifiers, enums, validation, and
serialization. No trace adapter, no evaluator execution, no persistence,
no CLI. See eval_lab/README.md and docs/reports/
AGENT_EVALUATION_RELIABILITY_LAB_RESEARCH_AND_ARCHITECTURE_REPORT.md for
the full research and architecture this package implements.
"""

from __future__ import annotations

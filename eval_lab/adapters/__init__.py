"""eval_lab/adapters — Slice 3: the trace ingestion/normalization boundary.

Consumes core.events.event_stream.StreamEvent (the pure dataclass, not the
stateful EventStream/EventStore service classes) and produces Slice 2's
Trajectory/TrajectoryEvent contracts. Deterministic, Lab-side, no runtime
orchestration, no evaluation. See trace_normalizer.py, event_mapping.py,
outcomes.py, and docs/reports/EVAL_LAB_SLICE3_TRACE_ADAPTER_DISCOVERY_AND_DESIGN.md.
"""

from __future__ import annotations

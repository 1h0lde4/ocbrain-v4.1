"""
Reusable capability conformance check (ADR-CAP-02 §Conformance).

``check_conformance(contract, adapter, samples)`` returns a list of violations;
an implementation conforms iff the list is empty. It exercises an implementation
*only through the public surface a caller has* -- the CapabilityRegistry and
AdapterRuntime -- so it cannot pass by reaching into internals.

To conform-test a future implementation of a capability:
    1. build its contract (or import the foundation one),
    2. write a ``ConformanceSamples`` (valid request per operation, one request
       that is invalid at the request level, optionally an empty-result request),
    3. ``assert await check_conformance(contract, adapter, samples) == []``.

What it verifies: identity, metadata validity, contract-version compatibility,
operation validity, input contract (required keys, unknown operation), output
contract (schema id, produced keys), status vocabulary (success <-> status),
failure and empty-result semantics, runtime-stamped provenance, availability,
and the negative boundary that an output never carries a verification /
governance / planning verdict.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from core.capabilities.adapter_runtime import AdapterRuntime
from core.capabilities.capability import CapabilityContract, CapabilityRequest
from core.capabilities.descriptors import (
    ALL_STATUSES, REQUEST_LEVEL_STATUSES, SUCCESS_STATUSES, CapabilityStatus as S,
)
from core.capabilities.foundation.schemas import schema_compatible
from core.capabilities.registry import CapabilityRegistrationError, CapabilityRegistry
from core.capabilities.resource import ResourceManager

FORBIDDEN_OUTPUT_KEYS = frozenset({
    "verified", "verdict", "receipt", "execution_plan", "plan", "clarification",
    "intent_sufficiency", "selected_capability", "governance", "approved",
    "route", "routing_decision"})


@dataclass
class ConformanceSamples:
    # operation name -> a request payload that MUST succeed
    valid: Dict[str, Dict[str, Any]]
    # one payload that is invalid at the request level for the default operation
    invalid: Dict[str, Any] = field(default_factory=dict)
    # optional: (operation, payload) that legitimately yields nothing (EMPTY)
    empty: Optional[tuple] = None


def _keys(obj: Any):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from _keys(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _keys(v)


async def check_conformance(contract: CapabilityContract, adapter: Any,
                            samples: ConformanceSamples) -> List[str]:
    bad: List[str] = []
    cap = contract.capability_type

    # identity + metadata validity ------------------------------------------
    if getattr(adapter, "capability_type", cap) != cap:
        bad.append("adapter.capability_type differs from the contract's identity")
    if not getattr(adapter, "adapter_name", ""):
        bad.append("adapter has no adapter_name")
    bad += contract.structural_problems()
    if not contract.operations:
        bad.append("contract declares no operations")
    for op in contract.operations:
        if not op.description or not op.inputs or not op.outputs or not op.produces:
            bad.append(f"operation {op.name}: incomplete descriptor")
    try:
        json.dumps({"ops": [o.to_dict() for o in contract.operations]})
    except (TypeError, ValueError):
        bad.append("operation descriptors are not JSON-serializable")

    # registration under the contract (version compatibility, operations) ----
    registry = CapabilityRegistry()
    try:
        registry.register_capability(contract)
        registry.register_adapter(cap, adapter)
    except CapabilityRegistrationError as e:
        return bad + [f"registration refused: {e}"]
    runtime = AdapterRuntime(registry, ResourceManager())
    if not adapter.is_available():
        bad.append("adapter is not available after registration")

    # operation validity -------------------------------------------------------
    declared = set(contract.operation_names())
    for op in samples.valid:
        if op not in declared:
            bad.append(f"sample operation {op!r} is not declared by the contract")
    r = await runtime.invoke(cap, request=CapabilityRequest(cap, {}, operation="__nope__"))
    if r.status != S.INVALID_REQUEST:
        bad.append("unknown operation was not refused as invalid_request")

    for op in contract.operations:
        # input contract: each required key is enforced before the adapter runs
        for key in op.requires:
            payload = {k: v for k, v in samples.valid.get(op.name, {}).items() if k != key}
            r = await runtime.invoke(cap, request=CapabilityRequest(cap, payload, operation=op.name))
            if r.status != S.INVALID_REQUEST:
                bad.append(f"{op.name}: missing required key {key!r} -> {r.status}, "
                           f"expected invalid_request")

    # output contract + provenance + negative boundary ---------------------------
    for op_name, payload in samples.valid.items():
        op = contract.get_operation(op_name)
        r = await runtime.invoke(cap, request=CapabilityRequest(cap, payload, operation=op_name))
        if r.status not in ALL_STATUSES:
            bad.append(f"{op_name}: status {r.status!r} outside the vocabulary")
        if r.success != (r.status in SUCCESS_STATUSES):
            bad.append(f"{op_name}: success/status disagree ({r.success}/{r.status})")
        if r.status not in SUCCESS_STATUSES:
            bad.append(f"{op_name}: valid sample did not succeed: {r.status} {r.error}")
            continue
        out = r.output
        if not isinstance(out, dict):
            bad.append(f"{op_name}: output is not an object")
            continue
        missing = [k for k in op.produces if k not in out]
        if missing:
            bad.append(f"{op_name}: output lacks declared keys {missing}")
        if not any(schema_compatible(out.get("schema"), t.schema_id)
                   for t in op.outputs if t.schema_id):
            bad.append(f"{op_name}: output schema {out.get('schema')!r} matches no declared output type")
        if out.get("status") not in (None, r.status):
            bad.append(f"{op_name}: output.status disagrees with result.status")
        for key in ("capability_type", "operation", "contract_version", "trace_id"):
            if not r.provenance.get(key):
                bad.append(f"{op_name}: runtime did not stamp provenance.{key}")
        if not (r.provenance.get("adapter") or {}).get("name"):
            bad.append(f"{op_name}: runtime did not stamp provenance.adapter.name")
        leaked = FORBIDDEN_OUTPUT_KEYS & set(_keys(out))
        if leaked:
            bad.append(f"{op_name}: output carries authority-shaped key(s) {sorted(leaked)}")
        try:
            json.dumps(out)
        except (TypeError, ValueError):
            bad.append(f"{op_name}: output is not JSON-serializable")

    # failure semantics: request-level problems are request-level statuses -----
    if samples.invalid:
        default_op = contract.get_operation("").name
        r = await runtime.invoke(cap, request=CapabilityRequest(cap, samples.invalid, operation=default_op))
        if r.success or not r.error:
            bad.append("invalid sample did not fail with an error message")
        elif r.status not in REQUEST_LEVEL_STATUSES:
            bad.append(f"invalid sample reported {r.status!r}; a bad request is "
                       f"request-level, not an adapter fault")

    # empty-result semantics ---------------------------------------------------
    if samples.empty:
        op_name, payload = samples.empty
        r = await runtime.invoke(cap, request=CapabilityRequest(cap, payload, operation=op_name))
        if r.status != S.EMPTY or not r.success:
            bad.append(f"empty sample returned {r.status!r}; a legitimate empty result "
                       f"is a success with status 'empty', never a failure")
    return bad

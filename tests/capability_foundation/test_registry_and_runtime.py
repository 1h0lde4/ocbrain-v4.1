"""
Registry, descriptors and AdapterRuntime semantics (ADR-CAP-01/02).

Covers: registration/uniqueness/metadata integrity, structured discovery
(input/output compatibility, negative matches), implementation replacement
without identity change, contract-version compatibility, lifecycle, operation
validation, status-aware fallback that never poisons adapter health, and
runtime-stamped provenance.
"""
import json

import pytest

from core.capabilities.adapter_runtime import AdapterRuntime
from core.capabilities.capability import (
    BaseAdapter, CapabilityContract, CapabilityRequest, CapabilityResult,
    CapabilityType,
)
from core.capabilities.descriptors import (
    ALL_STATUSES, CapabilityLifecycle, CapabilityStatus as S,
    FALLTHROUGH_STATUSES, OperationSpec, REQUEST_LEVEL_STATUSES, SemanticType,
    SUCCESS_STATUSES, SideEffect, TypeSpec, operations_composable,
)
from core.capabilities.foundation.contracts import (
    file_reading_contract, foundation_contracts, structured_reasoning_contract,
    text_generation_contract,
)
from core.capabilities.registry import CapabilityRegistrationError, CapabilityRegistry
from core.capabilities.resource import ResourceManager
from tests.capability_foundation.fixtures import ScriptedModel, build_registry


class Recorder:
    """Minimal async event stream double."""
    def __init__(self):
        self.events = []

    async def append(self, event_type, source, payload):
        self.events.append((event_type, payload))


class Stub(BaseAdapter):
    def __init__(self, name, cap, results, *, version="", implements="", ops=()):
        super().__init__()
        self.adapter_name, self.capability_type = name, cap
        self.adapter_version, self.implements_contract = version, implements
        self.supported_operations = tuple(ops)
        self._results, self.calls = list(results), []

    async def execute(self, request, resources):
        self.calls.append(request)
        r = self._results.pop(0) if len(self._results) > 1 else self._results[0]
        if isinstance(r, BaseException):
            raise r
        return r


def _cap(ops=(), default="", version="1.0.0", **kw):
    return CapabilityContract(capability_type="demo", description="demo capability",
                              version=version, operations=tuple(ops),
                              default_operation=default, **kw)


def _op(name, **kw):
    return OperationSpec(name, name, **kw)


# ── vocabulary ──────────────────────────────────────────────────────────────

class TestVocabulary:
    def test_status_sets_are_consistent(self):
        assert SUCCESS_STATUSES.isdisjoint(REQUEST_LEVEL_STATUSES)
        assert FALLTHROUGH_STATUSES <= REQUEST_LEVEL_STATUSES
        assert SUCCESS_STATUSES <= ALL_STATUSES and REQUEST_LEVEL_STATUSES <= ALL_STATUSES
        # the distinctions the task requires are all representable
        for needed in ("ok", "partial", "degraded", "empty", "unsupported", "malformed",
                       "unreadable", "dependency_unavailable", "failed", "timeout",
                       "cancelled", "unavailable"):
            assert needed in ALL_STATUSES

    def test_result_status_derived_and_consistent(self):
        assert CapabilityResult(success=True).status == S.OK
        assert CapabilityResult(success=False).status == S.FAILED
        assert CapabilityResult.of(S.EMPTY).success is True
        assert CapabilityResult.of(S.MALFORMED).success is False
        with pytest.raises(ValueError):
            CapabilityResult(success=True, status=S.FAILED)
        with pytest.raises(ValueError):
            CapabilityResult(success=False, status="mostly-fine")

    def test_empty_is_not_failure_and_not_ok_by_accident(self):
        empty, failed = CapabilityResult.of(S.EMPTY), CapabilityResult.of(S.FAILED)
        assert empty.success and not failed.success and empty.status != failed.status

    def test_typespec_compatibility(self):
        doc = TypeSpec(SemanticType.DOCUMENT, ("application/json",), "ocbrain.document_set/1")
        assert TypeSpec(SemanticType.DOCUMENT).accepts(doc)                 # unconstrained consumer
        assert not TypeSpec(SemanticType.TEXT).accepts(doc)                 # semantic mismatch
        assert not TypeSpec(SemanticType.DOCUMENT, (), "ocbrain.document_set/2").accepts(doc)
        assert TypeSpec(SemanticType.TEXT, ("text/*",)).accepts(
            TypeSpec(SemanticType.TEXT, ("text/markdown",)))
        assert not TypeSpec(SemanticType.TEXT, ("text/plain",)).accepts(
            TypeSpec(SemanticType.TEXT, ("application/pdf",)))

    def test_operation_and_type_validation(self):
        with pytest.raises(ValueError):
            OperationSpec("Bad Name", "x")
        with pytest.raises(ValueError):
            OperationSpec("ok", "x", side_effects="teleport")
        with pytest.raises(ValueError):
            TypeSpec(SemanticType.TEXT, schema_id="no-major")

    def test_isolated_entry_constants_cannot_drift(self):
        from core.capabilities.foundation.readers import isolated_entry as e
        from core.capabilities.foundation.readers.defaults import ISOLATED_READER_VERSION
        assert (e.MALFORMED, e.UNSUPPORTED, e.LIMIT_EXCEEDED,
                e.DEPENDENCY_UNAVAILABLE, e.INVALID_REQUEST) == (
            S.MALFORMED, S.UNSUPPORTED, S.LIMIT_EXCEEDED,
            S.DEPENDENCY_UNAVAILABLE, S.INVALID_REQUEST)
        assert e.READER_VERSION == ISOLATED_READER_VERSION


# ── registry ────────────────────────────────────────────────────────────────

class TestRegistry:
    def test_foundation_registration_and_uniqueness(self):
        registry, _ = build_registry()
        assert registry.list_capabilities() == ["file_reading", "structured_reasoning",
                                                "text_generation"]
        with pytest.raises(CapabilityRegistrationError):
            registry.register_capability(text_generation_contract())   # identity is unique
        assert registry.validate() == []                               # every contract has an adapter

    def test_metadata_integrity(self):
        for c in foundation_contracts():
            assert c.structural_problems() == []
            assert c.default_operation in c.operation_names()
            assert c.side_effects in (SideEffect.NONE, SideEffect.READ_ONLY)
            assert not c.is_general_purpose            # none is a fallback; LLM_COMPLETION stays the fallback
            for op in c.operations:
                assert op.inputs and op.outputs and op.produces
        assert file_reading_contract().side_effects == SideEffect.READ_ONLY
        assert text_generation_contract().side_effects == SideEffect.NONE
        assert structured_reasoning_contract().side_effects == SideEffect.NONE

    def test_invalid_contract_rejected(self):
        r = CapabilityRegistry()
        with pytest.raises(CapabilityRegistrationError):
            r.register_capability(_cap([_op("a"), _op("a")]))              # duplicate op
        with pytest.raises(CapabilityRegistrationError):
            r.register_capability(_cap([_op("a")], default="zzz"))         # default not declared
        with pytest.raises(CapabilityRegistrationError):
            r.register_capability(_cap(side_effects="explodes"))

    def test_legacy_contract_still_registers_and_needs_no_operations(self):
        r = CapabilityRegistry()
        r.register_capability(_cap())                                       # no operations at all
        assert r.get_contract("demo").get_operation("") is None
        assert r.describe("demo")["operations"] == []

    def test_contract_version_compatibility_fails_closed(self):
        r = CapabilityRegistry()
        r.register_capability(_cap(version="2.1.0"))
        with pytest.raises(CapabilityRegistrationError):
            r.register_adapter("demo", Stub("old", "demo", [CapabilityResult(success=True)],
                                            implements="1"))               # implements major 1, contract is 2
        r.register_adapter("demo", Stub("new", "demo", [CapabilityResult(success=True)],
                                        implements="2.0"))
        r.register_adapter("demo", Stub("legacy", "demo", [CapabilityResult(success=True)]))  # undeclared: accepted

    def test_adapter_operations_must_be_declared_by_contract(self):
        r = CapabilityRegistry()
        r.register_capability(_cap([_op("a")]))
        with pytest.raises(CapabilityRegistrationError):
            r.register_adapter("demo", Stub("x", "demo", [CapabilityResult(success=True)],
                                            ops=("a", "ghost")))

    def test_descriptor_is_machine_readable_and_json_safe(self):
        registry, _ = build_registry()
        d = registry.describe("file_reading")
        json.dumps(d)                                                       # JSON-serializable
        assert d["capability_type"] == "file_reading" and d["contract_version"] == "1.0.0"
        assert d["default_operation"] == "read_document"
        assert {o["name"] for o in d["operations"]} == {"read_document", "extract_structure"}
        assert d["operations"][0]["inputs"][0]["semantic_type"] == SemanticType.ARTIFACTS
        assert "application/pdf" in d["operations"][0]["inputs"][0]["media_types"]
        impl = d["implementations"][0]
        assert impl["adapter_version"] and impl["implements_contract"] == "1" and impl["available"]
        assert len(registry.describe_all()) == 3

    def test_implementation_replacement_keeps_identity_and_contract(self):
        registry, _ = build_registry()
        contract_before = registry.get_contract("text_generation")
        old = registry.get_adapters("text_generation")[0]
        new = Stub("alt-text", "text_generation", [CapabilityResult(success=True)],
                   version="9.9.9", implements="1")
        registry.register_adapter("text_generation", new)
        assert registry.deregister_adapter("text_generation", old.adapter_name) is True
        assert registry.deregister_adapter("text_generation", "nope") is False
        assert registry.get_contract("text_generation") is contract_before      # identity untouched
        assert [a.adapter_name for a in registry.get_adapters("text_generation")] == ["alt-text"]
        assert registry.describe("text_generation")["implementations"][0]["adapter_version"] == "9.9.9"

    def test_lifecycle_states(self):
        registry, _ = build_registry()
        registry.set_lifecycle("text_generation", CapabilityLifecycle.DEPRECATED,
                               reason="superseded", replaced_by="text_generation_v2")
        assert registry.is_discoverable("text_generation")                       # deprecated: still visible
        registry.set_lifecycle("text_generation", CapabilityLifecycle.DISABLED)
        assert not registry.is_discoverable("text_generation")
        registry.set_lifecycle("text_generation", CapabilityLifecycle.ACTIVE)    # reversible
        registry.set_lifecycle("text_generation", CapabilityLifecycle.RETIRED)
        with pytest.raises(CapabilityRegistrationError):
            registry.set_lifecycle("text_generation", CapabilityLifecycle.ACTIVE)  # terminal
        with pytest.raises(CapabilityRegistrationError):
            registry.set_lifecycle("ghost", CapabilityLifecycle.DISABLED)
        assert registry.describe("text_generation")["lifecycle"]["state"] == "retired"


# ── structured matching: input/output compatibility, negatives ──────────────

def _refs(found):
    return {(o.capability_type, o.operation) for o in found}


class TestStructuredMatching:
    def test_artifact_media_type_compatibility(self):
        registry, _ = build_registry()
        for media in ("application/pdf", "text/csv", "text/markdown",
                      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"):
            got = _refs(registry.find_consumers(TypeSpec(SemanticType.ARTIFACTS, (media,))))
            assert ("file_reading", "read_document") in got, media

    def test_negative_and_unsupported_combinations(self):
        registry, _ = build_registry()
        assert registry.find_consumers(TypeSpec(SemanticType.ARTIFACTS, ("image/png",))) == []
        assert registry.find_consumers(TypeSpec(SemanticType.ARTIFACTS, ("video/mp4",))) == []
        # a document set cannot be *read* again by FILE_READING
        assert all(o.capability_type != "file_reading" for o in registry.find_consumers(
            TypeSpec(SemanticType.DOCUMENT, ("application/json",), "ocbrain.document_set/1")))
        # schema major mismatch is not compatible
        assert registry.find_consumers(
            TypeSpec(SemanticType.DOCUMENT, ("application/json",), "ocbrain.document_set/2")) == []

    def test_output_compatibility(self):
        registry, _ = build_registry()
        assert _refs(registry.find_producers(TypeSpec(SemanticType.DOCUMENT))) == {
            ("file_reading", "read_document"), ("file_reading", "extract_structure")}
        assert _refs(registry.find_producers(TypeSpec(SemanticType.ANALYSIS))) == {
            ("structured_reasoning", "analyze"), ("structured_reasoning", "compare")}
        assert {c for c, _ in _refs(registry.find_producers(TypeSpec(SemanticType.TEXT)))} == {
            "text_generation"}

    def test_composition_compatibility_matrix(self):
        fr, sr, tg = (file_reading_contract(), structured_reasoning_contract(),
                      text_generation_contract())
        read, analyze = fr.get_operation("read_document"), sr.get_operation("analyze")
        assert operations_composable(read, analyze)                                   # FILE_READING -> STRUCTURED_REASONING
        assert operations_composable(analyze, tg.get_operation("summarize"))          # -> TEXT_GENERATION
        assert operations_composable(read, tg.get_operation("summarize"))             # doc set can be summarized directly
        assert not operations_composable(analyze, read)                               # analysis is not an artifact
        assert not operations_composable(tg.get_operation("generate"), read)

    def test_lifecycle_and_availability_filter_structured_queries(self):
        registry, _ = build_registry()
        registry.set_lifecycle("file_reading", CapabilityLifecycle.DISABLED)
        assert registry.find_consumers(TypeSpec(SemanticType.ARTIFACTS, ("application/pdf",))) == []
        bare = CapabilityRegistry()                                                   # declared but unfulfilled
        bare.register_capability(file_reading_contract())
        assert bare.find_consumers(TypeSpec(SemanticType.ARTIFACTS, ("application/pdf",))) == []


# ── AdapterRuntime ──────────────────────────────────────────────────────────

def _runtime(contract, *adapters, events=None):
    registry = CapabilityRegistry()
    registry.register_capability(contract)
    for a in adapters:
        registry.register_adapter(contract.capability_type, a)
    return registry, AdapterRuntime(registry, ResourceManager(), event_stream=events)


class TestAdapterRuntimeOperations:
    @pytest.mark.asyncio
    async def test_unknown_operation_fails_closed_without_calling_adapters(self):
        a = Stub("a", "demo", [CapabilityResult(success=True)])
        _, rt = _runtime(_cap([_op("go")], default="go"), a)
        r = await rt.invoke("demo", request=CapabilityRequest("demo", {}, operation="nope"))
        assert r.status == S.INVALID_REQUEST and "go" in r.error and a.calls == []

    @pytest.mark.asyncio
    async def test_required_payload_keys_enforced(self):
        a = Stub("a", "demo", [CapabilityResult(success=True)])
        _, rt = _runtime(_cap([_op("go", requires=("x",))], default="go"), a)
        for payload in ({}, {"x": None}, {"x": ""}, {"x": []}):
            r = await rt.invoke("demo", request=CapabilityRequest("demo", payload))
            assert r.status == S.INVALID_REQUEST, payload
        ok = await rt.invoke("demo", request=CapabilityRequest("demo", {"x": 0}))   # 0 is a real value
        assert ok.success and len(a.calls) == 1

    @pytest.mark.asyncio
    async def test_default_operation_resolved_for_the_adapter(self):
        a = Stub("a", "demo", [CapabilityResult(success=True)])
        _, rt = _runtime(_cap([_op("first"), _op("second")], default="second"), a)
        await rt.invoke("demo", request=CapabilityRequest("demo", {}))
        assert a.calls[0].operation == "second"

    @pytest.mark.asyncio
    async def test_legacy_contract_unchanged(self):
        a = Stub("a", "demo", [CapabilityResult(success=True, output="hi")])
        _, rt = _runtime(_cap(), a)
        r = await rt.invoke("demo", foo=1)                                          # payload= kwargs convenience path
        assert r.success and r.output == "hi" and a.calls[0].operation == ""

    @pytest.mark.asyncio
    async def test_adapters_only_offered_operations_they_implement(self):
        gen_only = Stub("gen-only", "demo", [CapabilityResult(success=True, output="G")],
                        ops=("gen",))
        both = Stub("both", "demo", [CapabilityResult(success=True, output="B")])
        _, rt = _runtime(_cap([_op("gen"), _op("sum")], default="gen"), gen_only, both)
        r = await rt.invoke("demo", request=CapabilityRequest("demo", {}, operation="sum"))
        assert r.output == "B" and gen_only.calls == []
        _, rt2 = _runtime(_cap([_op("gen"), _op("sum")], default="gen"), gen_only)
        r2 = await rt2.invoke("demo", request=CapabilityRequest("demo", {}, operation="sum"))
        assert r2.status == S.UNAVAILABLE

    @pytest.mark.asyncio
    async def test_disabled_capability_is_not_invocable(self):
        a = Stub("a", "demo", [CapabilityResult(success=True)])
        registry, rt = _runtime(_cap(), a)
        registry.set_lifecycle("demo", CapabilityLifecycle.DISABLED, reason="maintenance")
        r = await rt.invoke("demo")
        assert r.status == S.UNAVAILABLE and "disabled" in r.error and a.calls == []
        registry.set_lifecycle("demo", CapabilityLifecycle.DEPRECATED, replaced_by="demo2")
        assert (await rt.invoke("demo")).success                                     # deprecated still runs


class TestStatusAwareFailureHandling:
    @pytest.mark.asyncio
    async def test_request_level_status_never_poisons_adapter_health(self):
        bad_input = Stub("a", "demo", [CapabilityResult.of(S.MALFORMED, error="garbage in")])
        second = Stub("b", "demo", [CapabilityResult(success=True)])
        _, rt = _runtime(_cap(), bad_input, second)
        r = await rt.invoke("demo")
        assert r.status == S.MALFORMED                          # returned immediately, not masked
        assert bad_input.health_score == 100 and bad_input.cooldown_until == 0
        assert second.calls == []                               # malformed input is not shopped around

    @pytest.mark.asyncio
    async def test_hostile_inputs_cannot_put_the_capability_into_cooldown(self):
        a = Stub("a", "demo", [CapabilityResult.of(S.LIMIT_EXCEEDED, error="bomb")])
        _, rt = _runtime(_cap(), a)
        for _ in range(10):
            assert (await rt.invoke("demo")).status == S.LIMIT_EXCEEDED
        assert a.is_available() and a.health_score == 100

    @pytest.mark.asyncio
    async def test_unsupported_falls_through_without_penalty(self):
        a = Stub("a", "demo", [CapabilityResult.of(S.UNSUPPORTED, error="no")])
        b = Stub("b", "demo", [CapabilityResult(success=True, output="from b")])
        _, rt = _runtime(_cap(), a, b)
        r = await rt.invoke("demo")
        assert r.success and r.output == "from b" and r.adapter_used == "b"
        assert a.health_score == 100 and a.cooldown_until == 0

    @pytest.mark.asyncio
    async def test_all_declined_reports_the_decline_not_a_generic_failure(self):
        a = Stub("a", "demo", [CapabilityResult.of(S.UNSUPPORTED, error="not for me")])
        b = Stub("b", "demo", [CapabilityResult.of(S.DEPENDENCY_UNAVAILABLE, error="no lib")])
        _, rt = _runtime(_cap(), a, b)
        r = await rt.invoke("demo")
        assert r.status in (S.UNSUPPORTED, S.DEPENDENCY_UNAVAILABLE)
        assert len(r.metadata["adapters_declined"]) == 2
        assert a.health_score == 100 and b.health_score == 100

    @pytest.mark.asyncio
    async def test_real_failures_and_exceptions_keep_existing_penalty_semantics(self):
        failing = Stub("bad", "demo", [CapabilityResult.of(S.FAILED, error="provider down")])
        boom = Stub("boom", "demo", [RuntimeError("kaput")])
        good = Stub("good", "demo", [CapabilityResult(success=True, output="ok")])
        _, rt = _runtime(_cap(), failing, boom, good)
        r = await rt.invoke("demo")
        assert r.success and r.adapter_used == "good"
        assert failing.health_score < 100 and boom.health_score < 100

    @pytest.mark.asyncio
    async def test_empty_success_is_not_treated_as_failure(self):
        a = Stub("a", "demo", [CapabilityResult.of(S.EMPTY, output={"x": 1})])
        b = Stub("b", "demo", [CapabilityResult(success=True)])
        _, rt = _runtime(_cap(), a, b)
        r = await rt.invoke("demo")
        assert r.status == S.EMPTY and r.success and b.calls == []


class TestProvenanceAndObservability:
    @pytest.mark.asyncio
    async def test_runtime_stamps_identity_and_adapter_cannot_forge_it(self):
        forged = CapabilityResult(success=True, provenance={
            "capability_type": "forged", "adapter": {"name": "forged"}, "custom": "kept"})
        a = Stub("real-adapter", "demo", [forged], version="3.1.4")
        _, rt = _runtime(_cap([_op("go")], default="go", version="1.2.3"), a)
        r = await rt.invoke("demo", request=CapabilityRequest("demo", {}, trace_id="t-1"))
        p = r.provenance
        assert p["capability_type"] == "demo" and p["operation"] == "go"
        assert p["contract_version"] == "1.2.3" and p["trace_id"] == "t-1"
        assert p["adapter"] == {"name": "real-adapter", "version": "3.1.4"}
        assert p["custom"] == "kept"

    @pytest.mark.asyncio
    async def test_events_carry_operation_version_and_status(self):
        ev = Recorder()
        a = Stub("a", "demo", [CapabilityResult.of(S.UNSUPPORTED, error="x")])
        b = Stub("b", "demo", [CapabilityResult.of(S.PARTIAL, output={})], version="2.0")
        _, rt = _runtime(_cap([_op("go")], default="go", version="1.0.0"), a, b, events=ev)
        await rt.invoke("demo")
        kinds = {k: p for k, p in ev.events}
        assert kinds["adapter.declined"]["status"] == S.UNSUPPORTED
        assert kinds["adapter.declined"]["operation"] == "go"
        inv = kinds["adapter.invoked"]
        assert inv["status"] == S.PARTIAL and inv["contract_version"] == "1.0.0"
        assert inv["adapter_version"] == "2.0" and inv["operation"] == "go"

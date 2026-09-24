"""
Negative boundaries: what the capability layer must NOT be.

Capability != Planner / Compiler / Governance / Verification / C-MoE / Intent
Sufficiency / arbitrary filesystem access / a place that stores memory or
learns. Enforced structurally (import graph, result shape, descriptor shape,
source scan) so the boundary cannot erode by accident.
"""
import ast
import dataclasses
import json
import pathlib

import pytest

from core.capabilities.capability import CapabilityType
from core.capabilities.descriptors import CapabilityLifecycle, OperationRef, SideEffect
from core.capabilities.foundation.contracts import foundation_contracts
from core.capabilities.foundation.wiring import register_foundation_capabilities
from core.capabilities.registry import CapabilityRegistry
from core.runtime.worker_registry import WorkerRegistry
from core.workers.base import AbstractCognitiveWorker
from core.workers.capability_steps import FOUNDATION_STEP_WORKERS
from tests.capability_foundation.conformance import FORBIDDEN_OUTPUT_KEYS
from tests.capability_foundation.fixtures import ScriptedModel, build_registry

ROOT = pathlib.Path(__file__).resolve().parents[2]
CODE = sorted((ROOT / "core/capabilities/foundation").rglob("*.py")) + [
    ROOT / "core/capabilities/descriptors.py", ROOT / "core/workers/capability_steps.py"]

# The capability layer supplies an ability. It must not reach into the systems
# that decide, plan, govern, verify, remember or learn.
FORBIDDEN_IMPORTS = ("core.cognitive", "core.governance", "core.workflow",
                     "core.verification", "core.memory", "core.orchestrator",
                     "core.model_router", "core.learning", "core.meta",
                     "core.knowledge", "core.evolution")


def _imports(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                yield a.name
        elif isinstance(node, ast.ImportFrom) and node.module:
            yield node.module


class TestImportGraph:
    @pytest.mark.parametrize("path", CODE, ids=lambda p: str(p.relative_to(ROOT)))
    def test_foundation_never_imports_deciding_systems(self, path):
        bad = [m for m in _imports(path) if m.startswith(FORBIDDEN_IMPORTS)]
        assert bad == [], f"{path.name} imports {bad}"

    def test_isolated_parser_process_imports_nothing_from_the_project(self):
        path = ROOT / "core/capabilities/foundation/readers/isolated_entry.py"
        assert [m for m in _imports(path) if m.split(".")[0] == "core"] == []

    def test_file_reading_source_has_no_filesystem_access_at_all(self):
        """FILE_READING never opens a path or lists a directory. (The isolation
        runner legitimately makes a temp dir for a subprocess cwd; it never
        touches an artifact path and is excluded from this scan.)"""
        names = ["file_reading.py", "handoff.py", "schemas.py",
                 "readers/base.py", "readers/text_readers.py", "readers/defaults.py"]
        for name in names:
            src = (ROOT / "core/capabilities/foundation" / name).read_text(encoding="utf-8")
            tree = ast.parse(src)
            calls = {ast.unparse(n.func) for n in ast.walk(tree) if isinstance(n, ast.Call)}
            mods = set(_imports(ROOT / "core/capabilities/foundation" / name))
            assert not ({"open", "io.open", "os.listdir", "os.walk", "os.scandir", "glob.glob",
                         "shutil.copy", "Path", "pathlib.Path"} & calls), (name, calls)
            assert not ({"os", "os.path", "pathlib", "glob", "shutil", "tempfile"} & mods), (name, mods)


class TestResultAndDescriptorShape:
    @pytest.mark.asyncio
    async def test_no_output_carries_a_plan_verdict_route_or_approval(self):
        from tests.capability_foundation.test_conformance import (
            CASES, FILE_SAMPLES, REASON_SAMPLES, TEXT_SAMPLES,
        )
        from core.capabilities.adapter_runtime import AdapterRuntime
        from core.capabilities.capability import CapabilityRequest
        from core.capabilities.resource import ResourceManager
        for _, contract, factory, samples in CASES:
            registry = CapabilityRegistry()
            c = contract()
            registry.register_capability(c)
            registry.register_adapter(c.capability_type, factory())
            rt = AdapterRuntime(registry, ResourceManager())
            for op, payload in samples.valid.items():
                r = await rt.invoke(c.capability_type, request=CapabilityRequest(
                    c.capability_type, payload, operation=op))
                blob = json.dumps({"o": r.output, "p": r.provenance})
                keys = set()
                def walk(x):
                    if isinstance(x, dict):
                        for k, v in x.items():
                            keys.add(k)
                            walk(v)
                    elif isinstance(x, list):
                        [walk(v) for v in x]
                walk(json.loads(blob))
                assert not (FORBIDDEN_OUTPUT_KEYS & keys), (c.capability_type, op)

    def test_descriptors_and_structured_queries_rank_and_select_nothing(self):
        registry, _ = build_registry()
        words = ("score", "rank", "best", "selected", "recommended", "confidence", "preferred")
        blob = json.dumps(registry.describe_all()).lower()
        # description prose may say "conclusions"; assert on KEYS, not prose
        keys = set()
        def walk(x):
            if isinstance(x, dict):
                for k, v in x.items():
                    keys.add(k.lower())
                    walk(v)
            elif isinstance(x, list):
                [walk(v) for v in x]
        walk(json.loads(blob))
        assert not [k for k in keys if any(w in k for w in words)], keys
        assert [f.name for f in dataclasses.fields(OperationRef)] == ["capability_type", "operation"]

    def test_metadata_is_descriptive_not_enforcement(self):
        """side_effects/repeatability describe an operation; nothing in the
        capability layer enforces them (GovernanceKernel / sandbox do). Recorded
        as a test so nobody mistakes the field for a permission."""
        import asyncio
        from core.capabilities.adapter_runtime import AdapterRuntime
        from core.capabilities.capability import BaseAdapter, CapabilityContract, CapabilityResult
        from core.capabilities.resource import ResourceManager

        ran = []

        class Liar(BaseAdapter):
            adapter_name, capability_type = "liar", "x_pure"
            async def execute(self, request, resources):
                ran.append("performed a side effect")
                return CapabilityResult(success=True)

        reg = CapabilityRegistry()
        reg.register_capability(CapabilityContract("x_pure", "claims purity",
                                                   side_effects=SideEffect.NONE))
        reg.register_adapter("x_pure", Liar())
        asyncio.run(AdapterRuntime(reg, ResourceManager()).invoke("x_pure"))
        assert ran == ["performed a side effect"]      # the declaration did not stop it


class TestIdentityAndScope:
    def test_only_llm_completion_is_general_purpose(self):
        registry, _ = build_registry()
        assert [c for c in registry.list_capabilities()
                if registry.get_contract(c).is_general_purpose] == []
        assert all(not c.is_general_purpose for c in foundation_contracts())

    def test_file_access_stays_declared_and_unactivated(self):
        registry, _ = build_registry()
        assert CapabilityType.FILE_ACCESS == "file_access"
        assert "file_access" not in registry.list_capabilities()
        assert CapabilityType.FILE_READING != CapabilityType.FILE_ACCESS

    def test_foundation_contracts_declare_only_read_only_or_no_side_effects(self):
        assert {c.capability_type: c.side_effects for c in foundation_contracts()} == {
            "file_reading": SideEffect.READ_ONLY,
            "structured_reasoning": SideEffect.NONE,
            "text_generation": SideEffect.NONE}

    def test_step_workers_go_through_the_governed_template_method(self):
        for cls in FOUNDATION_STEP_WORKERS:
            assert issubclass(cls, AbstractCognitiveWorker)
            assert cls.execute is AbstractCognitiveWorker.execute      # governance path not overridden
            assert cls.worker_type == cls.capability_type              # the compile() bridge

    def test_registering_the_foundation_registers_nothing_else(self):
        registry = CapabilityRegistry()
        register_foundation_capabilities(registry, text_model=ScriptedModel())
        assert registry.list_capabilities() == ["file_reading", "structured_reasoning",
                                                "text_generation"]
        workers = WorkerRegistry()
        assert workers.list_types() == []

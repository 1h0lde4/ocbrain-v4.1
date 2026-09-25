"""
core/capabilities/foundation/wiring.py — explicit registration (composition root only).

Importing anything in this package registers nothing. main.py calls these two
functions when ``[capabilities] foundation_enabled`` is true; tests call them to
build isolated stacks. No auto-discovery, no import side effects.
"""
from __future__ import annotations

from typing import Optional

from core.capabilities.foundation.contracts import foundation_contracts
from core.capabilities.foundation.file_reading import (
    ArtifactResolver, FileReadingAdapter,
)
from core.capabilities.foundation.models import ProviderMeshTextModel, TextModel
from core.capabilities.foundation.readers.base import ReadLimits, ReaderRegistry
from core.capabilities.foundation.readers.isolation import IsolatedRunner
from core.capabilities.foundation.structured_reasoning import (
    StructuredReasoningAdapter,
)
from core.capabilities.foundation.text_generation import TextGenerationAdapter
from core.capabilities.registry import CapabilityRegistry


def register_foundation_capabilities(
        registry: CapabilityRegistry, *,
        text_model: Optional[TextModel] = None,
        readers: Optional[ReaderRegistry] = None,
        runner: Optional[IsolatedRunner] = None,
        limits: Optional[ReadLimits] = None,
        resolver: Optional[ArtifactResolver] = None) -> None:
    """Register the three contracts and one default implementation each.

    Replacing an implementation later is register_adapter(new) +
    deregister_adapter(old) under the unchanged capability identity.
    """
    model = text_model or ProviderMeshTextModel()
    for contract in foundation_contracts():
        registry.register_capability(contract)
    registry.register_adapter(
        "file_reading",
        FileReadingAdapter(readers=readers, runner=runner, limits=limits,
                           resolver=resolver))
    registry.register_adapter("structured_reasoning",
                              StructuredReasoningAdapter(model=model))
    registry.register_adapter("text_generation",
                              TextGenerationAdapter(model=model))


def register_foundation_workers(worker_registry, adapter_runtime) -> None:
    """Register the three explicit step workers (worker_type == capability_type)."""
    from core.workers.capability_steps import FOUNDATION_STEP_WORKERS
    for worker_class in FOUNDATION_STEP_WORKERS:
        worker_registry.register(
            worker_class, constructor_kwargs={"adapter_runtime": adapter_runtime})

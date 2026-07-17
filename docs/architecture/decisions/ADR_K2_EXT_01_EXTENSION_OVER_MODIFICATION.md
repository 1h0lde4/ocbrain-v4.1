# ADR-K2-EXT-01: Extension over Modification

**Status:** Accepted
**Date:** July 2026
**Context:** K2.3 Capability Runtime implementation

---

## Context

During K2.3, the Capability Runtime needed to integrate with the existing `ModelRouter` inference system. Two approaches were available:

1. **Modify** `ModelRouter` to implement the new `Adapter` Protocol directly.
2. **Extend** by wrapping `ModelRouter` in a new `ModelRouterAdapter` that satisfies the `Adapter` Protocol without changing `ModelRouter`.

The same decision pattern applied to the `Provider` health-tracking system and its relationship to the new `Adapter` Protocol.

## Decision

**Extension over modification.** New capabilities are added by creating new wrappers/adapters that delegate to existing, proven components rather than modifying those components to satisfy new interfaces.

Specifically:
- `ModelRouterAdapter` wraps `ModelRouter` unmodified (`core/capabilities/adapters/model_router_adapter.py`)
- `Adapter` is defined as a Protocol (structural typing), so existing `Provider` subclasses satisfy it by shape without inheritance changes
- `OllamaAdapter` and `OpenAICompatAdapter` were built as pure `Adapter` implementations alongside `ModelRouterAdapter`, providing the "at least one alternative" required by the Constitution's Law of Replaceability

## Rationale

1. **Contract Stability** — `ModelRouter` has live production consumers. Modifying its class declaration risks breaking existing code paths.
2. **Evidence over Assumption** — `ModelRouter`'s internal routing logic (provider mesh, health tracking, fallback) is proven and tested. Wrapping preserves this validated behavior exactly.
3. **Replaceability** — Three adapters for `LLM_COMPLETION` means the system can switch inference providers without any kernel change.
4. **Separation of Concerns** — The wrapping adapter translates between the capability model's `CapabilityRequest`/`CapabilityResult` and `ModelRouter`'s own `RouteRequest`/`RouteResult`. Neither needs to know the other's types.

## Consequences

- `ModelRouter` remains unmodified — all existing tests and behavior preserved.
- A thin translation layer (`ModelRouterAdapter`) exists, adding one level of indirection for LLM inference calls.
- Future capability types can follow the same pattern: wrap existing proven code, don't rewrite it.
- This pattern is now considered standard practice for K3+ work.

## Evidence

- `core/capabilities/adapters/model_router_adapter.py` — wraps ModelRouter
- `core/capabilities/adapters/ollama_adapter.py` — pure Adapter implementation
- `core/capabilities/adapters/openai_compat_adapter.py` — pure Adapter implementation
- `main.py` — all three registered in composition root for `LLM_COMPLETION`
- `core/capabilities/capability.py` — `Adapter` as Protocol, `BaseAdapter` as optional convenience base

## References

- Constitution Law 7 (Replaceability)
- Constitution Law 8 (Evidence over Assumption)
- `KERNEL_ARCHITECTURE_v1.0.md` §10 (Capability Model)

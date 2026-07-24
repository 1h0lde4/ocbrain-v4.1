# OCBrain Implementation Governance Directive v1.0

**Date:** July 24, 2026
**Status:** APPROVED
**Authority:** Architecture Governance
**Scope:** Implementation governance only. This document introduces **no architecture**. It defines the mandatory operational rules for implementing the frozen OCBrain architecture.

---

# 1. Purpose

Following the completion of the architecture hardening process, the OCBrain architecture is considered **frozen**.

From this point forward, all development shall follow the implementation governance defined in this document.

This document defines:

* implementation workflow
* packet acceptance rules
* implementation constraints
* repository workflow
* review process
* testing requirements
* parallel development rules
* amendment boundaries

It does **not** define architecture.

---

# 2. Authority

Implementation shall follow the following order of authority.

1. OCBRAIN_KERNEL_CONSTITUTION.md
2. KERNEL_ARCHITECTURE_v1.0.md
3. K4 Architecture
4. K4.1 Architecture
5. K4.2 Architecture
6. K5 Architecture
7. Architecture Evolution Directive
8. Architecture-to-Implementation Transition
9. This document

If any conflict exists, the higher authority prevails.

Implementation is **never** permitted to reinterpret architecture.

---

# 3. Architecture Freeze

The architecture is frozen.

Implementation SHALL NOT:

* redesign completed architecture
* introduce new architectural concepts
* introduce new resource types
* introduce new protocols
* introduce new lifecycle states
* create new architectural boundaries
* rename architectural concepts
* alter public contracts
* redefine ownership boundaries
* reinterpret architectural intent

Architectural evolution is permitted only through the Constitution amendment process after implementation evidence demonstrates a genuine deficiency.

---

# 4. Definition of Done

A packet is considered COMPLETE only when all of the following conditions are satisfied.

## Architecture Compliance

* Every implemented feature traces directly to an authoritative architecture section.
* No architectural interpretation was required.
* No architectural concepts were introduced.

## Functional Completion

* All packet scope implemented.
* All packet completion criteria satisfied.
* Forbidden work remains absent.

## Testing

* Existing repository tests pass.
* New packet tests pass.
* Integration tests pass where applicable.
* Static analysis passes.
* Type checking passes.
* Lint passes.

## Documentation

* Required documentation updated.
* Public interfaces documented when applicable.

## Repository

* No TODO placeholders.
* No FIXME placeholders.
* No temporary code.
* No commented-out implementation.

## Review

* Architecture compliance verified.
* Regression review completed.
* Code review completed.

## Version Control

Implementation committed immediately after completion.

A packet is not complete until committed.

---

# 5. Forbidden Implementation Decisions

Implementation SHALL NOT:

* change public interfaces
* rename architecture resources
* rename architecture events
* rename lifecycle states
* modify ownership boundaries
* invent new abstractions that alter architecture
* bypass Governance
* bypass EventStream
* bypass UnifiedMemory
* bypass Resource Protocol
* bypass lifecycle management
* replace architectural mechanisms with alternatives
* silently simplify architecture

When architecture appears difficult to implement, implementation SHALL stop rather than redesign.

---

# 6. Traceability Requirements

Every implementation packet SHALL begin with an Architecture Sources section.

Example:

Architecture Sources

* K4.2 §5
* K4.2 §12
* K4.2 §15

Only these sections authorize implementation.

If implementation requires additional architecture references, they shall be cited explicitly.

No uncited architectural interpretation is permitted.

---

# 7. Refactoring Rules

Refactoring is permitted only when all conditions hold.

* required by the packet
* preserves behavior
* preserves public interfaces
* preserves architecture
* preserves tests

The following are forbidden:

* opportunistic cleanup
* cosmetic redesign
* architectural simplification
* unrelated restructuring
* broad file reorganization

Implementation sessions are not cleanup sessions.

---

# 8. Git Workflow

Every packet shall produce exactly one logical commit.

Commit shall include:

* implementation
* tests
* documentation

Multiple packets SHALL NOT be combined into one commit.

Every commit message shall identify:

* packet number
* milestone
* architecture reference

Example

Packet 02 — K4.2.4 Capability Discovery

---

# 9. Packet Ownership

Each implementation packet owns only the files assigned to it.

Implementation SHALL NOT modify files owned by another unfinished packet unless explicitly required by the implementation plan.

If modification outside ownership becomes necessary:

* document justification
* minimize change
* preserve interfaces
* preserve compatibility

This rule exists to support parallel implementation.

---

# 10. Parallel Development Rules

Independent implementation sessions SHALL remain isolated.

Each session:

* receives only its assigned packet
* follows only cited architecture
* never redesigns neighboring packets
* never assumes unfinished functionality
* never edits unrelated modules

Integration occurs only after packet acceptance.

---

# 11. Testing Requirements

Each packet SHALL include:

## Existing Tests

All existing repository tests pass.

## New Tests

Packet-specific functionality verified.

## Regression Tests

No existing functionality regresses.

## Integration Tests

Executed when packet dependencies require them.

No implementation may weaken existing coverage.

---

# 12. Implementation Review

Every completed packet undergoes four reviews.

## Architecture Review

Matches authoritative architecture.

## Code Review

Implementation quality.

## Regression Review

No unintended behavior introduced.

## Dependency Review

No downstream packet affected.

Only after all four reviews is the packet accepted.

---

# 13. Implementation Packet Template

Every implementation packet SHALL contain:

* Architecture Sources
* Dependencies
* Scope
* Explicitly Forbidden Work
* Target Files
* Required Tests
* Completion Criteria
* Commit Requirements

Packets shall be executable independently.

No packet may depend upon previous conversation history.

---

# 14. Architecture Amendments

Implementation SHALL NOT modify architecture.

If implementation discovers an architectural deficiency, work stops.

Any amendment requires:

1. failing implementation evidence
2. affected architecture citation
3. demonstration that no existing mechanism solves the issue
4. minimal proposed change
5. downstream impact analysis

Only after approval may architecture change.

---

# 15. Operational Sequence

Implementation proceeds as follows.

1. Read authoritative architecture.
2. Read Architecture-to-Implementation Transition.
3. Read this document.
4. Implement assigned packet only.
5. Write tests.
6. Execute test suite.
7. Execute review checklist.
8. Commit.
9. Stop.

Implementation SHALL NOT continue into the next packet automatically.

---

# 16. Status

Once approved, this document becomes frozen.

It is the operational authority for all OCBrain implementation work.

Architecture evolves only through the Architecture Evolution Directive.

Implementation evolves only through this document.

The separation between architecture and implementation shall remain permanent.

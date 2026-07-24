# OCBrain Implementation Packet Template

**Version:** 1.0
**Status:** FROZEN — operational template
**Authority:** Implementation Governance Directive v1.0
**Purpose:** Canonical template for all OCBrain implementation packets

---

# Packet [XX] — [Packet Name]

**Milestone:** [K4.2.X / K4.X]
**Status:** [NOT STARTED / IN PROGRESS / COMPLETE]
**Dependencies:** [List completed prerequisite packets]
**Assigned Module(s):** [List target modules]
**Estimated Scope:** [Brief size estimate]

---

## 1. Objective

[Short description of what this packet accomplishes. Implementation only. No architecture redefinition.]

---

## 2. Architecture Sources

Implementation is authorized exclusively by the following architecture sections.

Implementation outside these citations is forbidden.

* [K4.2 §X]
* [K4.2 §Y]
* [K4 §Z]

---

## 3. Existing Interfaces

The following public interfaces SHALL remain unchanged.

* [interface_1]
* [interface_2]

Implementation SHALL NOT modify, rename, or redefine any interface listed above.

---

## 4. Target Files

### Existing Files to Modify

* [path/to/file.py]

### New Files to Create

* [path/to/new_file.py]

No other files may be modified unless explicitly justified in this section.

---

## 5. Dependencies

### Required Completed Packets

* [Packet XX — Name]

### Existing Runtime Dependencies

* [module/class/interface]

### Existing Interfaces Relied Upon

* [interface_name — source]

---

## 6. Scope

The following SHALL be implemented.

* [Deliverable 1]
* [Deliverable 2]
* [Deliverable 3]

Everything outside this list is outside packet scope.

---

## 7. Explicitly Forbidden Work

This packet SHALL NOT:

* introduce new architectural concepts
* create new public interfaces beyond those specified in Scope
* modify architecture
* perform capability execution
* redesign governance
* perform unrelated cleanup or refactoring
* modify files owned by other packets
* [packet-specific prohibitions]

---

## 8. Architecture Constraints

The following constraints apply directly to this packet.

* [Constraint 1 — source citation]
* [Constraint 2 — source citation]

These constraints are restated from authoritative sources. They are not new architecture.

---

## 9. Resource Contracts

The following existing resource contracts are referenced by this packet.

* [Resource — source citation]

These contracts SHALL NOT be redefined. Implementation SHALL conform to them exactly.

---

## 10. Events

### Events Consumed

* [event_name — source]

### Events Produced

* [event_name — source]

All event names are existing. No event redesign is permitted.

---

## 11. State Machines

The following existing lifecycle states are referenced by this packet.

* [Artifact — lifecycle — source]

These state machines SHALL NOT be redefined. Implementation SHALL conform to them exactly.

---

## 12. Required Tests

### Existing Tests

All existing repository tests SHALL pass.

### New Unit Tests

* [test_description]

### Integration Tests

* [test_description — if applicable]

### Regression Tests

No existing functionality shall regress.

### Architecture Compliance Tests

* [compliance_check]

### Replay Verification Tests

* [replay_check — if applicable]

---

## 13. Completion Criteria

The packet is complete when all of the following are satisfied.

* [Criterion 1 — objectively verifiable]
* [Criterion 2 — objectively verifiable]
* [Criterion 3 — objectively verifiable]
* All existing tests pass
* All new tests pass

---

## 14. Architecture Compliance Checklist

Before submission, verify:

- [ ] No architecture added
- [ ] No public interfaces changed beyond scope
- [ ] No lifecycle states changed
- [ ] No resource contracts changed
- [ ] No protocols changed
- [ ] Governance preserved
- [ ] Deterministic replay preserved
- [ ] Provenance preserved
- [ ] Ownership boundaries preserved
- [ ] EventStream integration preserved
- [ ] UnifiedMemory integration preserved
- [ ] Constitution compliance verified

---

## 15. Definition of Done

Per Implementation Governance Directive v1.0 §4:

- [ ] Architecture compliance verified
- [ ] Functional completion verified
- [ ] Testing complete
- [ ] Documentation updated
- [ ] No TODO/FIXME placeholders
- [ ] No temporary code
- [ ] No commented-out implementation
- [ ] Architecture review completed
- [ ] Code review completed
- [ ] Regression review completed
- [ ] Dependency review completed

---

## 16. Commit Requirements

Exactly one logical commit.

Commit SHALL include:

* implementation
* tests
* documentation

Commit message format:

```
Packet XX — [Packet Name]
```

---

## 17. Final Validation

- [ ] Architecture compliant
- [ ] All tests passing
- [ ] Documentation updated
- [ ] Commit completed
- [ ] Packet complete

---

## 18. Stop Condition

After successful completion of this packet:

* **STOP.**
* Do NOT begin another packet.
* Do NOT implement future milestones.
* Do NOT redesign architecture.
* Await review and approval.

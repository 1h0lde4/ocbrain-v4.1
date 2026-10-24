# Addendum — evidence labels, REVISION 2 (PROPOSED, pending maintainer ratification)

**Status: PROPOSED.** A separate, additive addendum. Preserved unedited: the revision-1 addendum (sha256 `14184571a12694f443c53d5c8b83107a117125be814d527d0aa2e45f7d173ffd`), the delivered report `batch1_review_response_1d813bd.md` (sha256 `1699456359e9ad4c3bb28a97e0ead8452d5808362ff90d555bfa29d1dec33b20`), and the PROPOSED spec (`abe17d13-…spec_PROPOSED.md`, sha256 `0bf4148775ae6e20456327cb6009b42b9e6e8fc8b350a0acb4115a0ec653fa44`). G4 OPEN · High · freeze-blocking; G5–G8 HELD; freeze readiness NOT DECLARED. No requirement, status or severity changes; nothing is closed, ratified or accepted here.

## 1. The three product-state labels — the only labels

| Label | Meaning | Where it can come from |
|---|---|---|
| **HISTORICAL BASELINE** | What the actual, unchanged product does or contains at `1d813bd` | **OBSERVED** (it was run) or **STATIC** (it was read in source) |
| **NEGATIVE CONTROL** | A test or measurement is shown to detect a deliberately disabled, incomplete or permissive implementation | Diagnostic variants or test adapters on throw-away data; never product code |
| **FIXED PRODUCT** | The actual implementation, at an immutable commit, run against the same tests | Does not exist yet for any row: UNEXERCISED |

They are never merged into one "passes-after" column.

## 2. What is not a label

A result about a **PROPOSED protocol applied to a probe artefact**, or about a **diagnostic variant**, carries **no** product-state label; write it as *n/a — probe artefact* and say what it was for.

| Descriptor | Axis | Examples |
|---|---|---|
| purpose: baseline characterisation, negative control, **test-satisfiability**, **protocol feasibility**, static grounding, measurement validation | what the experiment was for | V1/V2/V3 (can the RC tests be satisfied by a trigger fix?); TR/A/RT; fault injection; races; the state classifier |
| evidence kind: OBSERVED, STATIC, SIMULATED, SYNTHETIC-PRECONDITION, EXTRAPOLATED, UNTESTED, UNKNOWN, UNVERIFIED, PROPOSED, BLOCKED, OPEN | how the statement is known | a torn WAL made by truncation is SIMULATED; a prepared legacy fixture is SYNTHETIC-PRECONDITION |

"Protocol-feasibility evidence" describes purpose. It is **not** a fourth label.

## 3. Corrections to revision-1 wording

1. **Revision-1 addendum §3** said: *"Its probe-protocol results (variants TR/A/RT, fault injection, race) are negative-control-style or feasibility evidence; none is fixed-product evidence."* That sentence mixes purpose and label. Correct reading: TR/A/RT, fault injection and the race are **protocol-feasibility results on probe artefacts and carry no product-state label**. The **negative controls** are trigger-only (T), rebuild-only (R), the non-atomic variant and detect-before-lock. "None is fixed-product evidence" remains true.
2. **Revision-1 addendum §2 item 2** called V1/V2 *"negative-control-style"* evidence. A negative control must **fail**; V1/V2 **pass** the RC tests. They are **test-satisfiability diagnostics** (no product-state label). V3 (FTS5 secure-delete on) is the same kind and also exposes the unexplained RC-09 anomaly. Retiring "negative-control-style" for V1/V2 does not weaken the delivered report's own caveat that the only "passes-after" evidence is on throw-away diagnostic variants. (If the maintainer prefers to keep V1/V2 under "negative control", that is D-6; this addendum proposes the stricter reading because it matches the definition in §1.)
3. **"fails-before / passes-after"** is retired. Use one result column per label. A single "fails-before" is the HISTORICAL BASELINE result (OBSERVED or STATIC); "passes-after" can only be a FIXED PRODUCT result at an immutable commit, so it is empty for every row.
4. **"verified"** is reserved for checks that were executed. "Verified at 1d813bd" in the revision-1 packet §2 meant *read at source*; write STATIC.
5. **FTS-A2 provenance.** A *prepared fixture* (raw SQL, a synthetic history) establishes an **initial state**, not product behaviour. Record separately (a) how the initial state was produced (SYNTHETIC-PRECONDITION, or produced by the unchanged product through its API on a fresh database = HISTORICAL BASELINE — OBSERVED) and (b) what the unchanged historical implementation then did to it (OBSERVED). Packet rev 2 §4.2 does this.
6. **Permissive reference adapter** (report §6.4): a negative control only, as revision 1 already said; its use still needs maintainer approval.

## 4. Consequences for the FTS decision packet
`g4_fts_correctness_batch_decision_packet_1d813bd_REV2_PROPOSED.md` §2 and §7 use this model. FTS-A1…A7 stay **packet-local**; passing them would not close any G4 isolation requirement.

## 5. Not changed
No requirement, status or severity changes. No row is closed, ratified or accepted by this addendum; ratification is ledger item D-6.

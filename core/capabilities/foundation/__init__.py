"""
core/capabilities/foundation — the capability foundation (ADR-CAP-01/02/03;
Status: DRAFT on this branch — see docs/architecture/decisions/).

Three semantic capabilities, deliberately small and replaceable:

    TEXT_GENERATION       produce / transform prose
    STRUCTURED_REASONING  structured analysis of supplied material
    FILE_READING          semantic reading of an already-authorized artifact

plus the typed contracts they hand to each other. Nothing here plans, selects,
verifies, governs or decides what the user meant; each capability supplies an
*ability* and reports what happened (status, provenance, evidence-shaped source
references). See docs/architecture/CAPABILITY_FOUNDATION.md.

Nothing in this package is registered by import. Registration is explicit and
lives in ``wiring.register_foundation()``, called from main.py only when
``[capabilities] foundation_enabled`` is true (default false).
"""

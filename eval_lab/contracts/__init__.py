"""eval_lab/contracts — Slice 2 domain contract layer.

Deliberately no wildcard re-exports here: each module below is imported
explicitly by callers and by the test suite, so it's always visible which
contract file a given type actually comes from. See eval_lab/README.md
for the module map and ADR-LAB-01..06 for the decisions these contracts
implement.
"""

from __future__ import annotations

# OCBrain v4.3.4 — Bug Fixes Applied

## Summary
3 bugs fixed from reference codebase analysis (zip + GitHub v4.1).

---

## BUG 1: AdaptiveSemaphore — Release Before Acquire Check
**File:** `core/runtime/resilience.py`
**Severity:** HIGH — Can cause semaphore corruption under concurrent load

**Root Cause:**
`__aexit__` unconditionally called `self._semaphore.release()` with no
guard checking whether `__aenter__` had actually acquired the semaphore.
Under certain exception paths, this would release a semaphore that was
never acquired, corrupting the concurrency counter.

**Fix:**
Added `self._acquired = False` flag to `__init__`. Set to `True` ONLY
after `await self._semaphore.acquire()` succeeds. In `__aexit__`, check
`if not self._acquired: return` before calling release.

---

## BUG 2: MemoryVault — Fake BM25 (Substring Search)
**File:** `core/memory/mem_vault.py`
**Severity:** MEDIUM — Silent correctness bug, poor search quality

**Root Cause:**
`bm25_search_placeholder()` was implemented as simple token overlap /
keyword matching while being labeled as BM25. This produced random
rankings with no regard for term frequency or document frequency.

**Fix:**
Replaced with genuine Okapi BM25 scoring (k1=1.5, b=0.75).
`bm25_search_placeholder()` now delegates to new `bm25_search()` method
for backward compatibility. IDF uses standard log-smoothed formula.

---

## BUG 3: ContextMemory — set_long_term_memories Defined Twice  
**File:** `core/context.py` (ZIP version)
**Severity:** MEDIUM — Silent overwrite, first definition unreachable

**Root Cause (in original ZIP):**
```python
# Line 52 — accepts list of strings
def set_long_term_memories(self, memories: list): ...

# Line 141 — overwrites above, accepts list[dict]
def set_long_term_memories(self, memories: list[dict]): ...
```
The second definition silently overwrote the first. Callers passing plain
strings instead of dicts would break at runtime.

**Status:** Already fixed in GitHub v4.1 by renaming line 141 to
`set_long_term_memories_string()`. Confirmed clean in current codebase.

---

## Verification
All 114 tests pass after fixes:
```
pytest tests/ -q -p no:warnings
114 passed in 14.78s
```

# CodeQL Findings — Sept 2026: Working Notes

Register checked first: none of the three categories below were previously tracked in `KNOWN_ISSUES.md`. Genuinely new, surfaced by CodeQL's scan (confirmed running as part of Packet G's PR #26 checks).

**Note on this file's history:** the first version of this investigation (Category 1 below) was completed, committed locally, but not yet pushed when the underlying compute environment was reset, losing all uncommitted/unpushed local state. Nothing merged or pushed was affected — `main`'s Packet G merge (`b1e4184`) survived intact. Category 1's analysis is reconstructed here after re-verifying its key facts fresh against the re-cloned repository, not reproduced from memory alone. Lesson applied going forward: push each finding immediately rather than batching commits locally.

---

## Category 1: "Incomplete URL substring sanitization" — confirmed false positive, all 3 locations

**Flagged:** `tests/test_parser.py:18`, `tests/test_module_factory.py:120`, `tests/test_context.py:64`.

**The actual vulnerability this CodeQL query detects:** code that checks whether a trusted substring appears *anywhere within* a single URL string (e.g. `if "trusted-domain.com" in redirect_url:`) — bypassable by an attacker via a crafted URL like `evil.com/trusted-domain.com` or `trusted-domain.com.evil.com`, since substring containment says nothing about the URL's actual host.

**What's actually at each location, verified by checking the real return type, not assumed from the code's shape:**

| Location | Expression | Right-hand side type | Confirmed via |
|---|---|---|---|
| `test_parser.py:18` | `"https://example.com" in result.entities["urls"]` | `list[str]` | `core/parser.py:41`: `urls = _URL_RE.findall(text)` — `re.findall()` always returns a list |
| `test_module_factory.py:120` | `"https://example.com" in sources` | `list[str]` | `core/config.py:169`: `def get_sources(...) -> list[str]`, returns `list(dict.fromkeys(...))` |
| `test_context.py:64` | `"https://example.com" in urls` | `list[str]` | `core/context.py:178`: `def get_entity(...) -> list[str]`, returns `[r[0] for r in cur.fetchall()]` |

All three are `value in list_of_strings` — Python's `in` on a list is exact-equality membership against each element, not substring search within one string. There is no bypass here analogous to the real vulnerability class: an attacker cannot make `"https://example.com" in ["https://evil.com/https://example.com"]` evaluate `True`, because list membership doesn't do substring matching at all. This is CodeQL's heuristic pattern-matcher — which looks for the textual shape `"url-like-literal" in <expr>` — unable to distinguish string-substring containment from list-membership containment, both spelled with the same `in` keyword in Python.

**Classification: false positive, confirmed by checking the actual data flow, not asserted from confidence in the pattern alone.** All three are also test code exercising extraction/storage correctness, not a security decision gating any real request — even if the semantics *were* substring containment, there'd be no exploitable consequence here.

**Disposition:** no code change. Recommend dismissing these three specific CodeQL alerts with reason "false positive" (or GitHub's "used in tests" category, which also applies) so they stop appearing in future scans as unresolved findings requiring attention.

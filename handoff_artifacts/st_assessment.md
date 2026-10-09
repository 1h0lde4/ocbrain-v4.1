## Exposure assessment: evidence, proposed verdict, options (owner decision pending)

**Method and limits.** Source reading of the published wheels (`sentence-transformers` 3.0.0 … 3.4.1, 5.5.0, 5.6.0, 6.0.0, 6.1.0; `chromadb` 0.5.3) and of the repo at `main` @ `8c0ea03`. **No exploit code was executed and torch was not installed.** The Hugging Face host is unreachable from the sandbox, so no hub file was read.

### Q4: is the flaw present in what the declared range can install?
The advisory names `import_module_class`; that function only exists from 5.x. The **same gate exists in 3.x** as `SentenceTransformer._load_module_class_from_ref`:
| Version | Gate for non-`sentence_transformers.*` class refs |
|---|---|
| 3.0.0, 3.0.1 | no custom-module loading at all |
| 3.1.0 - 3.3.1 | `if trust_remote_code:` only: **no local-path short-circuit** |
| **3.4.0, 3.4.1** | `if trust_remote_code or os.path.exists(model_name_or_path):` **present** |
| 5.5.0 / 5.6.0 | short-circuit present; **5.6.0 only adds a `FutureWarning`** |
| 6.0.0+ | short-circuit removed; local dirs require `trust_remote_code=True` (`versionchanged:: 6.0`) |

The declared range `>=3.0.0,<4.0` allows 10 releases; a resolver picks **3.4.1** (released 2025-01-29), which is in the affected set. Note for the remediation decision: "first patched 5.6.0" removes nothing by itself; the behavior changes in 6.0.0.

### Q1: what does the gate actually test?
In 3.4.1, `__init__` rebinds a short name to `sentence-transformers/<name>` when no local path of that name exists, and **nothing rebinds it to the cache snapshot path** before `_load_module_class_from_ref(class_ref, model_name_or_path, ...)` (`SentenceTransformer.py:1672`). So `os.path.exists` tests the **identifier string relative to the process working directory**, not the hub cache. It is evaluated only for class refs outside `sentence_transformers.*` (early return at the top of the function). Identifiers used here: `all-MiniLM-L6-v2` (`core/learning/similarity.py:20`; `memory_vector.py` default via `InMemoryVectorBackend()` at `unified_memory.py:289`) and `sentence-transformers/all-MiniLM-L6-v2` / `sentence-transformers/all-mpnet-base-v2` (`modules/embedding_fn.py` `_MODEL_MAP`; Chroma 0.5.3 forwards `model_name` and `**kwargs` to `SentenceTransformer`, and the repo passes none).

### Q2 / Q3: who can write the relevant paths; download behavior
- No model directories are tracked; nothing at the repo root is named like those identifiers; the app never sets or reads the working directory (only unrelated: `core/sandbox/backends/_ns_init.py:83` `os.chdir("/")` in a sandbox child; `modules/system_ctrl/module.py:27` roots at `CWD/workspace`). Module/data sinks write under `modules/` and `data/` (contained by #46/#56).
- No cache/offline configuration anywhere (no `HF_HOME`, `*_OFFLINE`, `cache_folder`, `local_files_only`): library defaults apply, i.e. models are fetched from the Hub at first use into the default cache and loaded as hub ids, not local paths.
- Android: the Termux bundle ships `requirements.txt` (the 3.x range); the p4a `--requirements` list names `sentence-transformers` unpinned and the step ends `|| true`, so what it resolves, or whether it builds, is **not established**.

### Reasoning (analysis, not proof)
To use this gate here, an attacker would have to create, at the process working directory, a directory whose relative path equals one of the three identifiers, containing a `modules.json` with a custom class ref and its Python file, **before** the model loads. That needs write access to the working directory; no OCBrain input path found creates anything there. Someone who can write the working directory (normally the project root) can already modify the application's own code, so the gate adds little. This assumes the operator controls the working directory.

### Unverified premises (explicit)
1. The two models' hub `modules.json` being stock `sentence_transformers.*` types (hub host blocked from the sandbox).
2. The launch working directory, and who can write it, in each deployment mode.
3. What the p4a build resolves.
4. `system_ctrl`'s confinement was not re-audited here.
5. Nothing was executed.

### Proposed verdict (the owner decides)
**Conditionally exposed in principle** (flaw pattern present in 3.4.0/3.4.1, which a resolver picks); **not reachable through any OCBrain input path found**; practical exposure requires **local write access to the process working directory**. Low in practice, contingent on deployment permissions.

### Options (nothing done)
1. **Record a boundary decision**, as for `chromadb`: state the preconditions and reopen triggers (model identifiers become configurable or user-supplied; models loaded from local directories; any feature that creates directories at the process working directory; a working directory writable by untrusted parties; `trust_remote_code` introduced).
2. **Avoid the pattern without a major jump** by bounding the range below 3.4.0 (3.1.0-3.3.1 gate only on `trust_remote_code`): a dependency-policy change that needs compatibility testing; not recommended without it.
3. **Upgrade**: behavior changes only in **6.0.0+** (5.6.0 would clear the alert without removing the behavior). 6.x requires Python >=3.10 (repo floor is 3.11) but is a 3-to-6 major jump with its own compatibility work, including the Chroma 0.5.3 wrapper's construction call.
4. **Alert disposition**: #4 stays open until the owner decides; dismissal policy is the owner's.

No dependency was changed, no alert dismissed, no register text touched. #70 stays open for the decision.

# OCBrain External Resource → Skill → Governed Capability Research Study

**Status:** Research Only — NO implementation performed or proposed for immediate execution.
**Scope:** 7 named repositories inspected at source-code level (not README-only) + a dedicated sweep for GitHub-repo-to-capability systems + cross-check against the live OCBrain repository (`1h0lde4/ocbrain-v4.1`, fresh clone this session).
**Companion documents already in the repo (not superseded by this one):** `OCBRAIN_FUTURE_ARCHITECTURE.md` (root, 200+ repos, memory/runtime focus), `docs/architecture/FUTURE_RESEARCH_VAULT.md` (living FRI index — this study's recommendations belong there once triaged), the unread-in-full "RS" (Reliability Study) and "CMS" (C-MoE Study) referenced throughout `docs/Bugs Hunt & fix reports/KERNEL_V1_0_PRE_FREEZE_DEBT_RECONCILIATION_AUDIT.md`. **This report does not replace CMS.** Anything here touching C-MoE should be reconciled against CMS before becoming an ADR — see §I.
**Evidence tags:** `[FACT]` = verified directly against source/config in this session. `[DOC]` = stated in the project's own docs but not independently verified in code this session. `[INFER]` = my synthesis/judgment. `[REC]` = a recommendation, not a finding.

---

## A. Executive Assessment

OCBrain does not need a new capability-acquisition subsystem invented from first principles. It needs a **Resource Analyzer + gated promotion pipeline that feeds the existing `CapabilityRegistry` through its existing, unchanged API**, and — this is the single most important finding of this study — **it already has the right promotion mechanism running in production for a narrower case**. `core/model_router.py` `[FACT]` implements a `bootstrap → shadow → native` maturity state machine with objective, similarity-scored promotion (`_maybe_promote`) and quality-gated rollback (`_maybe_rollback`), persisted state, and zero reliance on self-reported success. This is structurally the same mechanism every serious external system in this study converges on independently (Composio's session-scoped tool exposure, Resource2Skill's shell→candidate→active gates, `ai-capability-registry`'s trust lattice, and — outside the named list — the academic "SkillOpt" pattern of bounded edits accepted only by a held-out gate). Per OCBrain's own stated principle, *extension over specialization*, the correct move is to generalize `model_router`'s state machine into the shared Capability lifecycle primitive, not invent a parallel one.

Five findings recur across independent sources strongly enough to treat as load-bearing:

1. **Trust must be earned by externally-computed evidence, never self-report.** `model_router.py`'s cosine-similarity gate, the `darwincode.md` agent (from the prior `codegraff2` study in this same session) explicitly telling itself "you cannot inflate your own score here," Resource2Skill's `exec_ok`/`judge_score` fields, and the academic SkillOpt paper's "held-out gate accepts only edits that improve validation performance" are four independent implementations of the same rule.
2. **Auto-generated capability granularity defaults to wrong.** The mature OpenAPI→MCP tooling ecosystem (FastMCP, Speakeasy, `cnoe-io/openapi-mcp-codegen`) can mechanically turn any spec into tool definitions in minutes — and every one of those projects' own documentation warns that naive 1:1 endpoint-to-tool mapping produces bad agent behavior, recommending codegen as a *starting point* for aggressive pruning, not a final product. Composio solves this differently — session-scoped dynamic tool discovery instead of static bulk registration — which is itself informative.
3. **Trust granularity should track acquisition method, not be uniform.** Resource2Skill tiers per-artifact (`T1`–`T5`) because its content is auto-distilled and variable; `ai-capability-registry` trusts per-source (pinned commits of nine curated providers) because its content is human-curated upstream. OCBrain's pipeline will have both kinds of input and needs both mechanisms, not one.
4. **A capability/skill library needs a maintenance loop separate from the execution loop.** The academic "SkillOps" framing (task-time loop vs. library-time loop) maps directly onto extending `MemoryCuratorWorker` rather than inventing a new canonical worker type — OCBrain already has the right architectural slot.
5. **Outcome-only success is not sufficient promotion evidence.** Recent research (`SkillCoach`, arXiv 2607.01874) shows verifier-passing trajectories can still exhibit non-reusable, brittle skill use. Promotion evidence needs to check *process* (did it follow the declared procedure/checks), not just *outcome*.

The one component in the brief's hypothesis I'd flag for outright rejection as a default is a **cloud-only CEE** (E2B, as used by `disler/agent-sandbox-skill`) — it is a well-built, concrete CEE precedent worth studying structurally, but as a *default* dependency it conflicts directly with LAW 5 (Local-First By Default). See §H.

---

## B. Repository-by-Repository Analysis

### 1. `microsoft/Resource2Skill` [FACT — cloned, `core/extraction`, `core/skill_wiki/schemas`, one full skill entry inspected]

**What it is:** Official Microsoft release accompanying the paper *"RESOURCE2SKILL: Distilling Executable Agent Skills from Human-Created Multimodal Resources"* (arXiv 2606.29538). Turns tutorials (mostly YouTube), articles, and code into executable skills across five domains (Web, PowerPoint, Excel, Blender, REAPER-style audio), each with its own MCP-server backend.

**Architecture:** `core/sources` (resource ingestion) → `core/extraction` (`shell_loader.py`, `distiller_shell.py`, `quality_gate.py`, `schemas.py`) → `skills_wiki/<domain>/<skill_id>/` (browsable metadata + text/visual/code) and `skills_library/<domain>/` (the actual executable assets the MCP servers load) → `core/retrieval`.

**Important components:**
- A formal JSON Schema (`core/skill_wiki/schemas/meta.schema.json`) `[FACT]` with **required** fields `skill_id, skill_name, tier, category_path, schema_version, wash_version, license, exec_ok, source`, an explicit **5-level trust tier enum** (`T1`–`T5`), and `source.type` enum `[youtube, github, article, docs, manual, distilled, static_artifact]` — note `distilled` is a valid source type, i.e., skills can be derived from other skills with the lineage recorded.
- `quality_gate.py` `[FACT]`: three hard gates before a shell can be promoted to `status="active"` — `exec_ok` (executes without exception against synthetic sample inputs generated by `make_sample_slots()`), a domain-specific render/output-quality check, and an optional CLIP-based visual-similarity check against the *original source frame*. **A shell failing any gate is stored as `status="candidate"` and hidden from default retrieval** — this is a working, in-production instance of exactly the DISCOVERED→CANDIDATE→ACTIVE lifecycle the brief hypothesizes.
- Per-skill folders are genuinely multimodal (`text/`, `visual/`, `code/`), not just markdown.
- `license` is a first-class, required field, tracked per skill (e.g., `"youtube_review_pending"` in the example inspected) — IP provenance is treated as a governance dimension, not an afterthought.

**Weaknesses / limits:** Domain-coupled (each domain has a bespoke MCP backend and bespoke quality gate logic — `quality_gate.py`'s specific checks are PowerPoint-specific in the file inspected, e.g. LibreOffice rendering). Not itself an agent-runtime or governance kernel — it's a skill-distillation pipeline plus retrieval, with no analog to OCBrain's `GovernanceKernel`, `WorkflowRuntime`, or event sourcing. `core/retrieval` and `core/sources` were not independently inspected this session `[INFER — directory names only]`.

**Adopt:** the meta-schema's field shape (tier enum, `source.type` enum including `distilled`, required `exec_ok`/`license`), the multi-gate-before-active pattern, `make_sample_slots()`-style synthetic-input validation.
**Reject:** nothing structurally — the domain-specific rendering/CLIP checks don't generalize to OCBrain's non-multimedia domains, but that's expected, not a flaw.

### 2. `ComposioHQ/composio` [FACT — README, `docs/tool-router.md`, `skills/composio/SKILL.md` read in full; core session/toolkit Python/TS source not independently read]

**What it is:** A hosted platform (not primarily an open architecture to copy wholesale) giving agents 1000+ pre-authenticated toolkits via per-user sessions, with an MCP endpoint per session.

**Important components:**
- **Session-scoped, runtime tool discovery, not static bulk registration.** `composio.create(user_id)` / `composio.tool_router.create(user_id, toolkits=[...])` returns a session whose default behavior is "meta tools that discover, authenticate, and execute app tools at runtime, so you don't load hundreds of tool definitions into context" `[FACT — README]`. This is a different, complementary answer to the granularity problem than static curation: instead of deciding the *right* grain at registration time, defer exposure decisions to session-scoped runtime discovery.
- **Composio ships itself as a SKILL.md**, and it's a genuinely sophisticated example of a skill-as-router: it doesn't front-load task instructions, it front-loads a *decision tree* (product? job?) and only then loads one of `references/for-you.md` / `references/platform.md` / `references/errors.md` `[FACT]`. It also bakes explicit anti-fabrication rules directly into the skill body: *"Never invent toolkit or tool slugs. Discover them at runtime,"* *"Do not invent repository facts... state the unknown and ask."* This is a directly reusable pattern for how OCBrain-authored skills should be written, independent of anything about Composio's own product.
- Per-user session scoping (multi-tenant credential isolation) is a dimension the brief didn't ask about but is relevant if OCBrain ever needs to separate credential contexts.

**Weaknesses:** Fundamentally a hosted SaaS with an API key model; the "sandbox"/"workbench" language in its marketing was not verified against source this session `[INFER]` — treat any OCBrain conclusion about Composio's actual execution isolation as unverified. Its registry is toolkit-centric (SaaS integrations: Gmail, Slack, GitHub, Notion) — a different problem shape than "arbitrary GitHub repo," closer to what OCBrain would need for *external service* adapters than for *repository-derived* capabilities.

**Adopt:** session-scoped/runtime-discovered tool exposure as a second granularity strategy alongside static curation; the anti-fabrication-rules-baked-into-the-skill-body pattern for OCBrain's own skill authoring.
**Reject:** nothing to reject; mostly orthogonal (external-service integration, not repo-to-capability).

### 3. `datalayer/agent-skills` [FACT — README in full, module list; `manager.py`/`codegen.py`/`server.py` contents not read]

**What it is:** A different, code-first take on "skill." Skills are literally **Python files with async functions** (not primarily prose instructions), auto-discovered from directories containing a `SKILL.md` (so it still uses the SKILL.md convention for *discovery metadata*, but the *body* of the skill is executable code the agent imports and calls, composing MCP tools and other skills together) `[FACT]`.
- `AgentSkillsToolset` supports path-based loading (scan a directory tree for `SKILL.md`) and module-based loading (`AgentSkill.from_module()`, for skills shipped inside an installed pip package) `[FACT]`.
- Execution goes through a pluggable `SandboxExecutor` (backends include generic code-sandboxes and Kaggle GPU sandboxes) `[FACT]`.
- `manager.py`, `codegen.py`, `types.py`, `server.py` exist as core modules; `codegen.py` strongly suggests skill-code generation from tool schemas but its contents were **not read this session** `[INFER — filename only, flagged as unverified]`.

**Adopt:** the explicit **Skill ≠ prose-only** distinction. This directly answers one of the brief's own required questions (`Skill ≠ Tool ≠ Capability`): datalayer's model shows a skill can *be* composed executable code rather than instructions describing how to act, which is a materially different thing from an Anthropic-style SKILL.md, and OCBrain's Skill layer should explicitly support both shapes rather than assuming skills are always prose.
**Reject:** nothing — under-verified rather than rejected; flagged for a follow-up pass before any adoption decision (`codegen.py`, `server.py` unread).

### 4. `Open-Dot-Agents/SKILL.md` [FACT — full specification (`docs/specification.mdx`) and `skills-ref` structure read]

**What it is:** The canonical, formal specification for the Agent Skills format. Per its own README: *"originally developed by Anthropic, released as an open standard"* `[FACT — README]`, and it is the same convention OCBrain (via this very Claude session) already consumes operationally every session — I read `/mnt/skills/public/*/SKILL.md` files before document/code-generation tasks as a matter of course, so this is a first-party, already-battle-tested reference, not a theoretical one.

**Formal spec, in full [FACT]:**
- Directory: `SKILL.md` (required) + optional `scripts/`, `references/`, `assets/`.
- Frontmatter fields: `name` (required, ≤64 chars, `a-z0-9-`, must match directory name), `description` (required, ≤1024 chars), `license` (optional), `compatibility` (optional, ≤500 chars, environment requirements), `metadata` (optional, free string map), `allowed-tools` (optional, experimental, space-separated tool allowlist).
- **Three-stage progressive disclosure with explicit token budgets**: Metadata (~100 tokens, name+description, loaded for *all* skills at startup) → Instructions (<5000 tokens recommended, full body, loaded on activation) → Resources (loaded only as needed).
- A reference validator exists (`skills-ref validate ./my-skill`) checking frontmatter and naming conventions.
- Adoption is broad: the docs list 40+ client logos (Claude, Cursor, VS Code, Gemini CLI, Amp, Cline/Roo Code, opencode, goose, Letta, and more) `[FACT]`.

**Gap relative to what OCBrain needs:** versioning is a free-text convention inside the optional `metadata` map, not a formal, enforced field — there is no mandatory semver, no immutability guarantee, no formal deprecation state. This is intentional (it's a consumer-facing portability format for many different clients, not a governed registry format) but it means **OCBrain cannot adopt SKILL.md as its Capability Contract wholesale** — it's the right format for the *Skill* layer's portable, human/agent-authored procedure, not for the *Capability* layer's governed, versioned, trust-tiered record. See §D.

**Adopt:** the format verbatim for OCBrain's Skill layer (directory + frontmatter + progressive disclosure token budgets); the anti-fabrication and "keep it under 500 lines, split to references/" discipline.
**Reject:** using it as-is for the Capability Contract (insufficient versioning/immutability guarantees for a governed registry).

### 5. `SWE-agent/SWE-agent` [FACT — `tools/` structure inspected; one `config.yaml` sampled (near-empty/inherited, not representative of a populated bundle)]

**What it is:** The README's own top banner is important and easy to miss: *"Most of our current development effort is on mini-swe-agent, which has superseded SWE-agent... Our general recommendation is to use mini-SWE-agent instead of SWE-agent going forward"* `[FACT]`. The outer agent loop is semi-deprecated by its own maintainers; the part relevant to this brief — its Agent-Computer Interface (ACI) tool-bundle design — is unaffected by that and still the clearest available example of "expose external software as tools without modifying the software."

**Important components:** `tools/` contains named, self-contained bundles (`search`, `submit`, `filemap`, `edit_anthropic`, `windowed`, `web_browser`, `registry`, etc.), each a directory of `bin/` (executables) plus optional `lib/` (shared code) plus a `config.yaml` declaring registration `[FACT — structure]`. This is a **tool-bundle-as-directory-plus-manifest** pattern, structurally similar to SKILL.md's `scripts/`+`references/`+`assets/` but oriented toward CLI-executable interfaces rather than agent-readable procedure text — i.e., SWE-agent is the Tool exemplar where SKILL.md is the Skill(procedure) exemplar, a useful contrast for §D.

**Weaknesses:** Semi-deprecated in favor of a simpler successor (worth a follow-up look — see §L). The one `config.yaml` sampled this session was empty/inherited, so the actual populated-bundle schema was **not independently confirmed** `[INFER — pattern from directory structure, not a verified schema]`.

**Adopt:** the bundle = `{bin/ + optional lib/ + manifest}` directory pattern as the Tool-layer analog to SKILL.md's Skill-layer pattern; "expose the software unmodified, adapt at the boundary" as the concrete answer to the brief's stated goal for this repo.
**Reject:** nothing; under-verified on schema specifics.

### 6. `disler/agent-sandbox-skill` [FACT — full `SKILL.md` for the `agent-sandboxes` skill read]

**What it is:** A SKILL.md-format skill (consumed by Claude Code, Gemini CLI, Codex CLI — confirmed by `AGENTS.md`/`CLAUDE.md`/`GEMINI.md` at the repo root) that operates E2B cloud sandboxes through a CLI wrapper.

**Important components — a genuinely complete CEE lifecycle precedent [FACT, all from the SKILL.md body]:**
- **Provision:** `sbx init` with named, resource-tiered templates (vCPU/RAM/cost/best-for table, e.g. `fullstack-vue-fastapi-node22-lite`: 2 vCPU/4GB/$0.15/hr, "best for browser tests").
- **Execute:** `sbx exec` as the unified interface, with escalation flags **opt-in only, not default** (`--root` for privileged execution, `--shell` for shell features) and a mandatory timeout.
- **Lifecycle bounds:** default 12-hour auto-timeout, explicit `extend-lifetime`/`kill`/`pause`, "never delete unless explicitly asked."
- **Verify/collect:** `sbx browser` provides Playwright-based result validation — screenshot, DOM extraction, accessibility-tree extraction — i.e., a concrete mechanism for verifying what a sandboxed capability actually *did*, not just capturing stdout.
- **Concurrency safety:** each agent tracks its own sandbox ID independently; browser automation supports per-agent ports for parallel use.

**Weaknesses:** Cloud-only (E2B-as-a-service) — no local execution fallback described in the skill itself. This is the repo's core design choice, not a flaw in context, but it is a direct tension with OCBrain's LAW 5.

**Adopt:** the *lifecycle shape* (tiered provisioning → bounded/opt-in-escalation execution → auto-timeout → explicit verify-by-inspection step), independent of the specific cloud vendor.
**Reject:** E2B (or any single cloud vendor) as OCBrain's *default* CEE backend. See §H.

### 7. `Friz-zy/ai-capability-registry` [FACT — README, `registry/` structure, `skill-catalog.d/` structure, `registry/policies.yaml` read in full]

**What it is:** A personal/community meta-registry aggregating skills, MCP servers, workflows, and role prompts from **nine curated upstream sources pinned as git submodules by commit** (Anthropic Skills, Anthropic Knowledge Work Plugins, OpenAI Skills, Vercel Agent Skills, the Agent Skills spec itself, Kilo Marketplace, Superpowers, and two Trail of Bits security sources), plus 169 enabled MCP servers across three catalogs and 34 workflow definitions `[FACT]`. It does not itself execute capabilities — it generates routing catalogs and CLI-specific agent configs for consuming tools (Claude Code, Codex, Kilo, opencode, Amazon Kiro).

**The single most directly reusable artifact found in this entire study is `registry/policies.yaml` [FACT, verbatim structure]:**
```yaml
security_policy:
  allow:  [docker, hosted_https, hosted_https_oauth]
  deny:   [curl_pipe_sh, npm_global_exec, python_remote_exec, arbitrary_shell_mcp,
           unrestricted_filesystem_mcp, unrestricted_browser_exec, local_database_mcp]
  require: [pinned_versions, license_check, manual_review, read_only_default]

trust_levels:
  trusted:              {allowed_actions: [index, install, enable_by_default]}
  reviewed:              {allowed_actions: [index, install, enable_manually]}
  candidate:              {allowed_actions: [index_only]}
  denied:                 {allowed_actions: []}
  trusted_runtime_layer:  {allowed_actions: [index, install, route_allowlisted_only]}

promotion_policy:
  default_state: index_only
  promote_to_reviewed_requires: [maintainer_check, license_check, source_review, scripts_review, pinned_commit]
  promote_to_trusted_requires:  [official_vendor_or_security_vendor, stable_execution_model,
                                  documented_permissions, reproducible_install]
```
This models trust as a **state-plus-permitted-actions lattice**, not a strict linear pipeline — `candidate` and `denied` are valid, stable, indefinitely-persisted resting states, not just transit points — and it separates trust in *capability content* from trust in the *runtime layer that isolates it* (`trusted_runtime_layer`). It also gives itemized, checkable promotion criteria rather than "human review" as an opaque black box.

**Weaknesses / caveat:** this session verified the **policy declaration**, not its **enforcement code** — I did not find or inspect a script that actually reads `policies.yaml` and enforces it at install/generation time `[INFER — the `scripts/` directory was listed but not opened]`. Treat this as a well-designed *policy schema* worth adopting verbatim in shape, with the caveat that its own enforcement rigor is unverified. Trust here is source-level (nine curated, human-vetted, commit-pinned providers), which only works because the inputs are already human-curated — this is the "per-source vs. per-artifact" contrast noted in §A/§C.

**Adopt:** the entire policy schema shape (allow/deny/require mechanism lists; five-level trust lattice including the runtime-layer distinction; itemized promotion criteria) almost verbatim for §E/§H below.
**Reject:** nothing; caveat on unverified enforcement.

---

## C. Cross-Project Synthesis

| Pattern | Where it appears (≥2 independent sources) | OCBrain implication |
|---|---|---|
| Progressive disclosure (metadata → full detail → resources, on demand) | SKILL.md spec (formal token budgets), Composio (session-scoped meta-tools), Resource2Skill (wiki vs. library split), `ai-capability-registry` (`index_only` default) | Any Resource Analyzer output must default to metadata-only visibility; full detail loads only on candidate activation. |
| Trust as a lattice of states-with-permitted-actions, not a strict pipeline | `ai-capability-registry`'s explicit model; Resource2Skill's persistent `candidate` (not transient); `model_router`'s persisted `stage` | Reject a strict linear FSM for the Capability lifecycle (§F) in favor of a lattice with legitimate resting states and an explicit rollback edge. |
| Promotion gated on externally-computed evidence; self-report explicitly distrusted | `model_router.py` (cosine similarity vs. shadow answer), `darwincode.md` (external fitness scoring, explicit "cannot inflate your own score" language), Resource2Skill (`exec_ok`/`judge_score`), academic SkillOpt (held-out gate) | Any promotion signal computed by the capability/skill itself, or by the LLM that authored it, is disqualified as promotion evidence by construction. |
| Auto-generated capability granularity defaults to wrong (too fine, 1:1) | Universal caveat across the entire OpenAPI→MCP tooling ecosystem (FastMCP's own docs, Neon's engineering blog, `cnoe-io/openapi-mcp-codegen`'s LLM-overlay step) | The Resource Analyzer needs a mandatory curation/grouping step before registration; raw mechanical extraction is a draft, never a final capability set. |
| Trust granularity should track acquisition method | Resource2Skill (per-artifact tiers, because auto-distilled) vs. `ai-capability-registry` (per-source trust, because human-curated) | OCBrain needs both a per-artifact gate path (for anything LLM-distilled from an arbitrary repo) and a per-source trust path (for anything ingested from an already-curated provider). |
| Skill/capability libraries need a maintenance loop distinct from the execution loop | Academic "SkillOps" (explicit task-time vs. library-time loops); `MemoryCuratorWorker` already exists in OCBrain for exactly this role in the memory layer | Extend `MemoryCuratorWorker`'s remit (or add a peer worker built the same way) rather than inventing a new canonical worker type. |
| Security posture is a mechanism allow/deny/require list, not a single boolean | `ai-capability-registry`'s `security_policy`; agent-sandbox-skill's opt-in-only escalation flags | §H should mirror an allow/deny/require structure, not a single "sandboxed: true/false" flag. |
| Portable interop is achieved via a shared *file format*, not a shared runtime | SKILL.md's 40+ client adoption; Composio shipping itself as a SKILL.md; datalayer reusing the SKILL.md frontmatter for discovery even though its body semantics differ | If OCBrain ever wants ecosystem interop (explicitly a later concern per this study's own scope rules), the portable unit should be a file format, not a protocol only OCBrain's runtime speaks. |
| Outcome-only verification is insufficient promotion evidence | Academic SkillCoach (process vs. outcome distinction); Resource2Skill's multi-gate design (exec + render + similarity, not just "did it run") | Verification procedure in the Capability Contract (§E) needs a process-adherence check, not just a pass/fail outcome flag. |

**Revisiting the brief's hypothesized target architecture:** the linear pipeline (`External Resource → Resource Analyzer → Capability/Skill Extraction → Governance Gate → CEE/Sandbox → Execute → Verify → Score → Reject/Promote → Registry → Planner → Work Graph`) survives this research largely intact as a *sequence of required steps*, but the research says two things should change: (1) draw it as a **state lattice with a standing `candidate`/`denied` layer and an explicit rollback edge**, not a one-way pipe (per the trust-lattice pattern above); and (2) insert an explicit **curation/grouping step** between "Extraction" and "Governance Gate" — without it, mechanical extraction (especially from OpenAPI/MCP-manifest-bearing repos) will over-produce fine-grained, low-quality candidates by default, per the universal caveat in the row above.

---

## Required OCBrain Conceptual Distinctions

| Term | Brief's definition | Assessment | Refinement |
|---|---|---|---|
| **Tool** | Primitive executable operation | Sufficient. | No change — confirmed as the right grain by SWE-agent's `bin/`-level bundles. |
| **Adapter** | Integration mechanism connecting OCBrain to an external execution mechanism | Sufficient, and this already matches OCBrain's *live* code — `core/capabilities/adapter_runtime.py`'s `AdapterRuntime.invoke(capability_type, ...)` `[FACT]` is exactly this. | No change. |
| **Skill** | Reusable procedural knowledge describing how to accomplish something | **Incomplete.** The research shows two materially different shapes both calling themselves "Skill": *prose-instruction* skills (SKILL.md body: tells an agent how to think about a task) and *code-composition* skills (datalayer: literally importable, callable functions). Conflating them is a modeling error — they have different execution models, different trust requirements, and different consumers (a PlannerWorker-adjacent process reads prose; a CoderWorker-adjacent process imports code). | **Split into two subtypes under one Skill concept**: `Skill.procedural` (prose, SKILL.md-shaped, progressive disclosure) and `Skill.executable` (code-composition, datalayer-shaped, imported and called). Both still sit below Capability in the hierarchy. |
| **Capability** | A governed, validated, executable unit that OCBrain can reliably invoke | Sufficient, and it already matches live code — `CapabilityContract` + one or more registered `Adapter`s via `CapabilityRegistry.register_capability()`/`register_adapter()` `[FACT]` is exactly this pair today. This research changes *how contracts get populated*, not what a Capability is. | No change to the definition; §E extends the contract fields. |
| **Repository** | External software/resource from which one or more capabilities and/or skills may be extracted | Sufficient, with one addition. | **Add:** a Repository is untrusted by default and is never itself registered as a Capability — it is always mediated by at least one Adapter or one extracted Skill, and popularity/stars/fame confer no default trust (this is implicit in every named repo's own security posture and explicit in `ai-capability-registry`'s `security_policy`). |

---

## D. Proposed OCBrain Capability Model

```text
Repository (untrusted, external, never directly registered)
      │
      ▼
Resource Analyzer  ──produces──►  candidate Skill.procedural  and/or  candidate Skill.executable
      │                                          │
      │                          (curation / grouping step — mandatory, not optional)
      ▼                                          ▼
candidate CapabilityContract  ◄──wraps──  curated Skill(s) + required Tool(s) + chosen Adapter shape
      │
      ▼
Governance Gate (policy lattice, §H)  ──►  CEE / Sandbox validation (§F, §G)
      │
      ▼
CapabilityRegistry.register_capability() + register_adapter()   [EXISTING API, UNCHANGED — FACT]
      │
      ▼
C-MoE (future; selection among already-registered adapters — CMS-1 scope, UNCHANGED by this research)
      │
      ▼
Planner / Plan Compilation / Work Graph / Execution Runtime   [EXISTING, K4.2, UNCHANGED]
```

The load-bearing claim here, worth restating: **everything above the `CapabilityRegistry.register_capability()` line is new or extended by this research; everything below it is existing, complete K4.2 machinery that requires zero changes.** `[FACT, verified against `core/capabilities/registry.py` this session — the registry's own module docstring states "The registry owns metadata. It does NOT execute," and has no `execute()`/`invoke()` method anywhere in the file.]` This research is entirely upstream of the registry boundary that already exists.

---

## E. Proposed Capability Contract

| Field | Mandatory? | Source pattern | Immutable after registration? |
|---|---|---|---|
| `capability_type` (identity) | Yes | Existing OCBrain field, unchanged | Yes |
| `version` | Yes | SKILL.md's `metadata.version` convention, made formal instead of free-text | No (new versions supersede, old ones retained per §F) |
| `description` | Yes | SKILL.md `description` field shape (what + when to use) | No |
| `source` (`{type, url, commit, captured_at}`) | Yes | Resource2Skill's `source` object, `type` enum extended with OCBrain's own acquisition methods | Yes |
| `trust_state` | Yes | §F lattice | No (this is the field the lattice mutates) |
| `derived_from` | No (Yes if distilled) | Resource2Skill's `source.type: "distilled"` lineage concept, implemented using OCBrain's **existing** dual-provenance convention already used for `Intent`/`Goal`/`ExecutionPlan`/`LearningRecord` `[DOC — per project conventions in memory/prior sessions, not re-verified this session]` | Yes |
| `inputs` / `outputs` (schema) | Yes | Existing `CapabilityContract` shape, unchanged | No (new version required to change) |
| `security_requirements` | Yes | `ai-capability-registry`'s allow/deny/require shape (§H) | Yes — **never self-declared by the source repository itself**; always independently derived by the Resource Analyzer / Governance Gate, since a malicious or careless repo can misrepresent its own permission needs |
| `verification_evidence` (`{exec_ok, judge_score, wash_errors[], process_adherence}`) | Generated automatically | Resource2Skill's `exec_ok`/`judge_score`/`wash_errors`; `process_adherence` new, per SkillCoach's outcome-vs-process finding | No (append-only log per attempt) |
| `license` | No, but required before `trusted` | Resource2Skill | Yes |
| `compatibility` | No | SKILL.md spec | No |
| `retry_policy` | No | Existing OCBrain `RetryPolicy` convention | No |

**Fields verified independently vs. self-declared** is the single most important row-level distinction: `security_requirements` and `exec_ok`-equivalent verification must **never** be taken from the source repository's own claims (its README, its own manifest) — every serious system in this study (the entire security posture of `ai-capability-registry`, Resource2Skill's independent gates, `model_router`'s independent similarity check) computes trust evidence externally, never accepts self-report.

---

## F. Capability Lifecycle

Reconciling the brief's 8-state hypothesis, `ai-capability-registry`'s 5-level lattice, and `model_router.py`'s proven 3-stage mechanism:

```text
        ┌─────────────────────────────────────────────────────────┐
        │                                                           │
DISCOVERED → ANALYZED → CANDIDATE → SANDBOX_VALIDATED → SHADOW → REVIEWED → ACTIVE
   │            │            │              │              │         │        │
   │            │            │              │              │         │        ▼
   │            │            │              │              │         │   (rollback edge,
   │            │            │              │              │         │    any state ≥
   ▼            ▼            ▼              ▼              ▼         ▼    SANDBOX_VALIDATED,
                                          DENIED  ◄──────────────────────  back to SANDBOX_VALIDATED
                                     (terminal, retained          or to DENIED — model_router's
                                      in the ledger, not          `_maybe_rollback` pattern)
                                      deleted — darwincode/
                                      Resource2Skill pattern)
```

- **DISCOVERED / ANALYZED / CANDIDATE**: index-only, hidden from default retrieval — matches both `ai-capability-registry`'s `default_state: index_only` and Resource2Skill's "failing gate → status=candidate, hidden from default retrieval." No execution has happened yet.
- **SANDBOX_VALIDATED**: passed the CEE's hard gates (§G) — the Resource2Skill three-gate pattern (executes cleanly against synthetic inputs / produces valid output / meets a fidelity bar) generalized beyond multimedia domains.
- **SHADOW** *(new, not in the brief's original hypothesis — added because `model_router.py` already proves this stage's value in OCBrain specifically)*: the capability is invoked for real requests but its output is only scored against a trusted baseline or human review, never actually acted on by the system — this is `model_router`'s `shadow` stage, generalized. Promotion out of `SHADOW` requires the same kind of objective, non-self-reported evidence `model_router` already uses (§C).
- **REVIEWED**: matches `ai-capability-registry`'s `promote_to_reviewed_requires` checklist almost directly — maintainer/source check, license check, script review, pinned commit.
- **ACTIVE**: matches `model_router`'s `native` — fully live, still monitored, **rollback remains available at any time**, not just during a probation window.
- **DENIED**: a first-class terminal state, retained (not deleted) for audit — matches darwincode's lineage-ledger ethos and Resource2Skill's status-tracking, not a silent rejection.

This is deliberately **not drawn as a strict pipeline**: `CANDIDATE` and `DENIED` are legitimate, potentially-permanent resting states (per `ai-capability-registry`'s lattice model), and the rollback edge is a first-class part of the design, not an exception path — because every production system studied here treats rollback as routine, not rare.

---

## G. GitHub Repository Acquisition Architecture

```text
GitHub URL
   │
   ▼
Sandboxed shallow clone (existing bash_tool network-allowlist precedent already
established in this session's own tooling is a reasonable model: explicit domain
allowlist, no arbitrary egress)
   │
   ▼
Repository Analyzer — branches by what's actually present, not a single strategy:
   ├── has OpenAPI spec / MCP manifest  → mechanical generation (FastMCP / openapi-mcp-codegen-
   │                                       style), OUTPUT IS ALWAYS "candidate," never auto-trusted,
   │                                       because mechanical 1:1 extraction is a known-bad default
   │                                       granularity (§C) until curated
   ├── has an existing test suite / CI  → R2E-style equivalence-harness reuse: program-analysis +
   │                                       LLM-constructed test harnesses become the verification
   │                                       procedure for SANDBOX_VALIDATED (§F), reusing work the
   │                                       repo's own maintainers already did rather than re-deriving it
   └── neither                          → Resource2Skill-style LLM-assisted distillation into a
                                            Skill.procedural or Skill.executable (§D); starts at the
                                            lowest trust tier by construction, since nothing has
                                            verified it yet
   │
   ▼
Curation / grouping step (mandatory — §C's universal caveat) — collapses raw extraction into
capability-shaped candidates at the right grain, not one candidate per detected entry point
   │
   ▼
CEE sandbox validation (§F: SANDBOX_VALIDATED) — provisioned isolated env, resource-tiered,
timeout-bounded, escalation flags opt-in only (agent-sandbox-skill pattern, vendor-neutral)
   │
   ▼
Governance Gate (§H policy lattice) — security_requirements independently derived, never
self-declared by the source repo; license check; provenance completeness check
   │
   ▼
CapabilityRegistry.register_capability() / register_adapter()   [EXISTING, UNCHANGED]
```

---

## H. Security Model

Adapting `ai-capability-registry`'s `security_policy` shape (§B.7) to OCBrain's own LAWs:

```yaml
allow:
  - subprocess_isolated_execution      # LAW 3
  - docker_isolated_execution          # LAW 3
  - pinned_commit_clone
  - read_only_filesystem_default
deny:
  - curl_pipe_sh
  - unrestricted_network_egress
  - unrestricted_filesystem_access
  - privileged_execution_by_default    # opt-in only, matches agent-sandbox-skill's --root pattern
  - self_declared_permissions          # security_requirements is NEVER taken from the source repo
require:
  - pinned_versions
  - license_check
  - manual_review_above_permission_floor
  - provenance_completeness            # source.{type,url,commit} all present, no exceptions
```

**Explicit rejection, flagged per the brief's own required categorization:** a cloud-only CEE (E2B or equivalent) as OCBrain's *primary* execution backend for validating externally-acquired capabilities directly conflicts with LAW 5 ("cloud services are optional accelerators, not core dependencies"). `disler/agent-sandbox-skill`'s *lifecycle shape* (tiered provisioning, bounded execution, opt-in escalation, verify-by-inspection) is worth adopting; the specific cloud dependency is not. Any CEE implementation needs a local (subprocess- or Docker-based, running inside OCBrain's existing Task Runner process per the mandatory 4-process runtime model) path as the default, with a cloud sandbox as an optional accelerator only.

---

## I. Integration Assessment

| Existing OCBrain component | Status found this session | What this research requires of it |
|---|---|---|
| `CapabilityRegistry` (`core/capabilities/registry.py`) | `[FACT]` Complete, registry-only (no execute path), composition-root-only registration | **Unchanged.** Gains new upstream input sources only. |
| `AdapterRuntime` (`core/capabilities/adapter_runtime.py`) | `[FACT, per KERNEL_V1_0_PRE_FREEZE_DEBT_RECONCILIATION_AUDIT.md's CMS-4 citation]` `invoke(capability_type, ...)` only selects among adapters for an *already-given* type | **Unchanged.** |
| Planner / Constraint Extraction / Plan Compilation / Work Graph | `[FACT, CURRENT_STATE.md]` K4.2 complete, all 9 packets done, live-wired behind `use_k42_frontend` (default `false`) | **Unchanged.** Capability *selection* is explicitly out of scope for this research — that's C-MoE's job. |
| `model_router.py` | `[FACT]` Working `bootstrap/shadow/native` state machine with similarity-gated promotion and rollback, for a narrower case (routing to a fine-tuned local model vs. an external one) | **Generalize, don't replace.** This is the headline recommendation of §F. |
| C-MoE | `[FACT, per KERNEL_V1_0_PRE_FREEZE_DEBT_RECONCILIATION_AUDIT.md CMS-1]` Zero code exists; explicitly scoped as "a thin, bounded resolution function" at v1.0, not the full adaptive-scaling system | **Untouched by this research.** This pipeline produces registry *contents* C-MoE will eventually choose among; it does not touch C-MoE's own selection logic. Any apparent overlap should be reconciled against the full CMS document, which this session did not read in full — flagged explicitly, not silently assumed compatible. |
| `RecursionGovernor` | `[FACT, confirmed by live grep this session AND KERNEL_V1_0_PRE_FREEZE_DEBT_RECONCILIATION_AUDIT.md]` `recursion_depth` is set to literal `0` at every call site; the evaluator is correct but never receives a real number | Not required for *this research* to proceed, but flagged by the existing audit as becoming urgent the moment any C-MoE-adjacent implementation packet starts, which any future implementation of this research eventually would be adjacent to. Exact current `DEBT-XXX` numbering was inconsistent between `CURRENT_STATE.md` and the reconciliation audit in this session's reading — **do not cite a specific debt ID without re-checking `KNOWN_ISSUES.md` at implementation time**, since the most recent commit message ("D10 Post-Merge Confirmation") itself references correcting a DEBT ID collision. |
| Memory architecture (L0–L4) | `[DOC, per prior-session memory, not re-verified this session]` 5-layer hierarchy | `Skill.procedural`/`Skill.executable` content is procedural knowledge by definition and belongs conceptually in L3, consistent with the existing model — not independently re-verified against source this session. |
| `MemoryCuratorWorker` | `[DOC, canonical worker type per project instructions]` | Natural home for the "library-time loop" (§C) — extend rather than add a new canonical worker type, pending confirmation of its current implementation status, which this session did not check. |
| CEE (Capability Execution Environment) | Does not exist yet | This research is the first concrete specification attempt — §F/§G/§H. |

**Explicit gap in this session's coverage, stated rather than silently glossed over:** the full "RS" (Reliability Study) and "CMS" (C-MoE Study) documents are referenced extensively by `KERNEL_V1_0_PRE_FREEZE_DEBT_RECONCILIATION_AUDIT.md` but were **not read in full this session** — only quoted fragments surfaced via that audit document. Before any recommendation here becomes an ADR, it should be reconciled against CMS in particular, since C-MoE is the component this pipeline feeds most directly.

---

## J. Scope Classification

| Recommendation | Classification |
|---|---|
| Adopt SKILL.md format verbatim for `Skill.procedural` | Post-Kernel v1.0 |
| Split `Skill` into `.procedural` / `.executable` subtypes | Post-Kernel v1.0 |
| Extend `CapabilityContract` per §E | Post-Kernel v1.0 |
| Generalize `model_router.py`'s state machine into the shared lifecycle (§F) | Post-Kernel v1.0 — and should be **the first concrete design spike**, since the mechanism already exists and is proven |
| First CEE implementation (local subprocess/Docker-backed, per §H) | Post-Kernel v1.0 |
| Full GitHub Repository Acquisition pipeline (§G), Resource Analyzer, automatic distillation | Future |
| R2E-style automatic equivalence-test-harness generation for OCBrain's own extraction pipeline | Research only — genuinely open, not yet a design |
| Alem-based testing of capability selection / skill composition / recovery (§ below) | Future — depends on both this pipeline and C-MoE existing first |
| Wiring `RecursionGovernor`'s real depth counter | **Not this research's scope** — pre-existing, independently tracked debt; noted here only because C-MoE-adjacent work is what the existing audit flags as the trigger that makes it urgent |
| Cloud-only (E2B) CEE as the default | **Reject** |
| Naive 1:1 mechanical endpoint-to-capability registration without a curation gate | **Reject** |
| Self-reported / capability-computes-its-own-fitness promotion evidence | **Reject** |
| Reconciling this document against the full CMS/RS studies | **Required before ADR**, not yet done |

This research deliberately proposes **zero changes to K4.2, the Planner, Plan Compilation, the Work Graph, or C-MoE's scope** — consistent with the brief's own instruction not to create scope drift in the current milestone.

---

## K. Prioritized Recommendations

**Must adopt**
- Generalize `model_router.py`'s `bootstrap/shadow/native` + `_maybe_promote`/`_maybe_rollback` mechanism into the Capability lifecycle state machine (§F). Already proven in this codebase; extension-over-specialization applies directly.
- Adopt the `ai-capability-registry` `security_policy` allow/deny/require shape for §H, with `self_declared_permissions` added to `deny` explicitly.
- Adopt the SKILL.md format verbatim for `Skill.procedural`, including its token-budget progressive-disclosure numbers.

**Strongly consider**
- Split `Skill` into `.procedural`/`.executable` subtypes (§ Conceptual Distinctions) before any Skill-layer implementation begins — retrofitting this split later would be more disruptive than designing for it now.
- Per-artifact tiering (Resource2Skill-style) for anything LLM-distilled; per-source trust (ai-capability-registry-style, commit-pinned) for anything ingested from an already-curated provider — build both paths, not one.
- Extend `MemoryCuratorWorker` for the library-time maintenance loop rather than introducing a new canonical worker type.

**Research further**
- R2E/R2E-Gym-style automatic equivalence-test-harness generation as OCBrain's own verification-procedure generator for repos that lack existing tests.
- The `codegen.py`/`server.py` internals of `datalayer/agent-skills` (unread this session) before committing to the `.executable` skill subtype's exact runtime shape.
- Whether `ai-capability-registry`'s `policies.yaml` has real enforcement code behind it (unverified this session) before treating it as more than a schema reference.

**Unnecessary**
- A new bespoke lifecycle state machine designed from scratch — `model_router.py` already solves the hard part.
- Adopting Composio or `ai-capability-registry` as running dependencies — both are architecturally instructive, neither is a drop-in fit for OCBrain's local-first, governed posture.

**Reject**
- Cloud-only CEE as the default execution backend.
- Auto-promoting mechanically-generated (OpenAPI/MCP-manifest) capabilities without a curation step.
- Any promotion path where the evidence originates from the capability/skill itself or from the LLM that authored it.

---

## L. Candidate Next Research Repositories

Beyond the seven named targets, this sweep surfaced a cluster clearly worth a dedicated follow-up study, roughly in priority order:

1. **`r2e-project/r2e`** and its successor **R2E-Gym** (arXiv 2504.07164) `[FACT — confirmed real, ICML'24, actively maintained per GitHub org activity]` — program-analysis + LLM-constructed "equivalence test harnesses" for arbitrary GitHub functions; the strongest lead for OCBrain's own automatic verification-procedure generation (§K, "research further").
2. **`SWE-agent/mini-swe-agent`** — SWE-agent's own maintainers now recommend this successor over SWE-agent itself; worth checking whether its simplified ACI changes the Tool-bundle pattern noted in §B.5.
3. The 2026 academic "self-evolving skill library" cluster: **SkillOps** ("Managing LLM Agent Skill Libraries as Self-Maintaining Software Ecosystems" — task-time/library-time loop split, direct citation for the `MemoryCuratorWorker` extension recommendation), **SkillOpt** (bounded add/delete/replace edits behind a held-out gate — direct citation for §C's "never self-report" pattern), **SkillCoach** (arXiv 2607.01874 — process-vs-outcome verification), **SkillWeaver**, **SkillRL**, **Skill1** (arXiv 2605.06130 — formalizes the select/utilize/distill three-stage lifecycle cited in §F).
4. **"What keeps agent skills from being reusable? Evidence from 138k SKILL.md files"** (Agent Skills '26 workshop) — an empirical, at-scale study of real-world SKILL.md reusability failure modes; directly relevant to whatever authoring guidance OCBrain eventually publishes for its own skill authors, but its specific findings were not read this session and should not be assumed.
5. **`cnoe-io/openapi-mcp-codegen`** — the most currently-maintained, concrete example found of "mechanical generation plus an LLM-assisted overlay layer for descriptions/prompts, with a rule-based fallback if no LLM is configured" — a good template for OCBrain's own curation step (§C, §G) if the mechanical-extraction branch is implemented.

---

## Alem Connection

```text
External Repository → Skill/Capability (this study) → CapabilityRegistry (existing, unchanged)
      → Planner → Work Graph → Execution (existing K4.2, unchanged) → Alem
```

This is explicitly **future scope** — it depends on both this pipeline and a working C-MoE existing first, neither of which this study implements. What's worth recording now, since it was directly verified earlier in this same session studying `alem-world/alem-env`: Alem's structured `<action>/<communication>/<scratchpad>` output contract, its progressive information disclosure by game-level, and its tiered fuzzy action-parsing fallback (`alem/llm/action_parser.py`) are the same *shape* of problem a newly-registered, LLM-authored `Skill.procedural` needs validated against for multi-worker use — Alem is a plausible test harness for:
- **Capability selection** (once C-MoE exists): scenarios requiring a choice among 2+ registered capabilities of genuinely ambiguous applicability.
- **Skill composition**: tasks solvable only by chaining 2+ newly-registered skills together.
- **Watchdog/recovery**: deliberately injecting a capability that times out or returns malformed output mid-task, and checking that Supervisor-layer recovery handles it the same way Alem already exercises multi-agent coordination failure generally.
- **Long-horizon multi-worker synchronization**: reusing Alem's existing coordination-benchmark machinery rather than building a parallel one, consistent with this study's overall bias toward extending proven mechanisms.

None of this should be implemented now; it is recorded here so it isn't rediscovered from scratch once both prerequisites exist.

---

## Research Standard — Coverage and Uncertainty Notes

Per the brief's own required rigor, an explicit account of what was and wasn't independently verified in source this session, consolidated in one place:

- **Read at source-code/spec level, not just README:** Resource2Skill (`core/extraction`, `core/skill_wiki/schemas`, one full skill artifact), the Agent Skills specification (`docs/specification.mdx` in full), `ai-capability-registry` (`registry/policies.yaml` in full), `agent-sandbox-skill` (its `SKILL.md` in full), OCBrain's own `core/capabilities/registry.py` and `core/model_router.py`.
- **Read at README/docs level, structure sampled, core execution logic not independently read:** Composio (session/auth/sandbox internals in `python/`/`ts/` not opened), `datalayer/agent-skills` (`manager.py`/`codegen.py`/`server.py` not opened), SWE-agent (only one, likely-unrepresentative `config.yaml` sampled).
- **Confirmed to exist via `git ls-remote` and cloned, but given proportionally less depth given the volume of higher-yield material found elsewhere:** none excluded outright — all seven named repos received at least structural + README-level treatment plus one deeper artifact each.
- **Referenced but not independently opened this session, flagged rather than assumed:** the full "RS" and "CMS" prior-research documents in the OCBrain repo (only quoted fragments seen via a third document that cites them); `ai-capability-registry`'s policy-enforcement code (only the policy declaration was read).
- **Web-search-sourced findings** (R2E/R2E-Gym, the OpenAPI→MCP tooling ecosystem, the 2026 self-evolving-skill-library academic cluster) are current as of this session's searches (Aug 26, 2026) and were cross-checked against at least one primary source (project GitHub page, OpenReview/arXiv listing, or vendor documentation) rather than taken from a single secondary mention.

No OCBrain code was modified during this study.

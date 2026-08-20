"""
tests/test_capability_discrimination.py — K4.2-H2-D3

Capability Discrimination Acceptance Suite.

Objective (docs/architecture/h2_packets/D3_CAPABILITY_DISCRIMINATION.md):
prove, with a genuinely distinct second capability class, that
Capability Discovery (core/cognitive/planner.py::discover_capabilities())
actually discriminates between capability types -- not merely that it
returns without crashing.

H1 already built two of the six required behaviors against real
production wording (TestGeneralPurposeFallback in
tests/core/cognitive/test_planner.py: test_general_purpose_bypasses_min_score
for Case A, test_specificity_dominance_ranks_specific_above_general for
Case B). This suite extends that established pattern with test-only
capabilities instead of production ones (so this suite's correctness
never depends on production capability wording), and adds the four
behaviors H1's freeze review explicitly left uncovered: C (unsupported
request), D (registration-order independence), E (dynamic registration),
F (evidence), plus the required registry-isolation boundary test.

Frozen contracts this suite exercises but never weakens or redefines:
    - min_score=0.01, passed explicitly on every discover_capabilities()
      call below -- never omitted, never changed.
    - CapabilityMatch's existing evidence fields (lexical_score,
      specificity_tier, general_fallback) -- read, not altered.
    - is_general_purpose's fallback-not-override semantics (K4.2-H1 D2,
      ADR-K4.2-H-02): a general-purpose capability is only ever a
      rescue candidate when nothing specific clears min_score; it never
      outranks a genuine specific match.

Every capability contract here is registered into a CapabilityRegistry()
instance created locally inside each test -- never a shared module-level
registry, never the production registry main.py's composition root
builds (see TestRegistryIsolationBoundary for the explicit proof).
CapabilityRegistry itself has no class-level or module-level mutable
state (core/capabilities/registry.py: each instance owns its own
_contracts/_adapters dicts from __init__) -- this suite's isolation
follows from that, and TestRegistryIsolationBoundary demonstrates it
behaviorally rather than asserting it only by source inspection.

Every test-only capability_type string used below (calendar_scheduling,
document_translation, general_purpose_assistant,
torque_calibration_procedure, sequence_verification_procedure) was
confirmed, by a repository-wide search performed while writing this
suite, to appear nowhere else in this codebase -- production or test.
The two domains (calendar scheduling, document translation) are
unrelated to each other and to the sole registered production
capability (llm_completion), so specificity results here cannot be an
artifact of accidentally reusing production wording.

All six behaviors run against the real, unmocked discover_capabilities().
No part of the discovery mechanism itself is mocked or monkeypatched
anywhere in this file.

Case D / "Open question" resolution (see docs/architecture/decisions/
ADR_K4_2_H_03_CAPABILITY_DISCRIMINATION.md for the full writeup): the
non-tied case (TestRegistrationOrderIndependence's first test) passed
unmodified -- discover_capabilities()'s specificity-dominance sort is
already keyed on (is_general_purpose, -relevance_score), which fully
determines order whenever scores differ. Writing the exact-score-tie
edge case (that class's second test) surfaced a genuine, if currently
dormant, gap: Python's stable sort has no third key, so an exact tie
within the same is_general_purpose group silently falls back to
insertion order -- i.e. registration order. That is a trivial,
clearly-deterministic tie-break gap (no CapabilityMatch field, no
scoring formula, no public signature, no architectural boundary
changes), so per the packet's own decision tree it was corrected
directly rather than escalated: discover_capabilities()'s sort key
gained a third, deterministic component (capability_type, alphabetical)
purely to break exact ties. See that test class's docstring and the ADR
for the full before/after evidence.
"""
import pytest

from core.capabilities.capability import BaseAdapter, CapabilityContract
from core.capabilities.registry import CapabilityRegistry
from core.cognitive.planner import (
    CapabilityDiscoveryRequest,
    CapabilityDiscoveryResult,
    discover_capabilities,
)


# ─────────────────────────────────────────────────────────────────────────
# Helpers — local to this file only. Deliberately not imported from
# tests/core/cognitive/test_planner.py (this packet's ownership scope is
# this file alone; a cross-test-file import would blur that boundary for
# no real benefit, since both helpers are a handful of lines).
# ─────────────────────────────────────────────────────────────────────────

def _register(registry: CapabilityRegistry, capability_type: str, description: str,
               *, is_general_purpose: bool = False) -> None:
    """Registers one CapabilityContract, plus a fulfilling BaseAdapter, into
    `registry`. Mirrors test_planner.py's _make_registry() construction
    idiom exactly (same BaseAdapter() + attribute-assignment pattern) so
    these fixtures read as an extension of the established style. Every
    capability here gets an adapter -- discover_capabilities() excludes
    any capability with zero registered adapters regardless of score, and
    that exclusion path is not what this suite is testing.
    """
    registry.register_capability(CapabilityContract(
        capability_type=capability_type,
        description=description,
        is_general_purpose=is_general_purpose,
    ))
    adapter = BaseAdapter()
    adapter.adapter_name = f"fake-{capability_type}"
    adapter.capability_type = capability_type
    registry.register_adapter(capability_type, adapter)


def _planner_source_text() -> str:
    """Raw source text of core/cognitive/planner.py, for a literal
    substring check (see TestDynamicCapabilityRegistration). A plain
    substring search is the right tool here, unlike test_planner.py's
    AST-based _real_code_identifiers(): that helper exists to avoid
    false positives from *common* forbidden names appearing in
    explanatory docstrings/comments, which does not apply to the
    synthetic, never-elsewhere-used capability_type strings this file
    invents -- they cannot appear in planner.py's prose by accident, so
    a literal match here is unambiguous evidence of hard-coding.
    """
    import core.cognitive.planner as planner_module
    with open(planner_module.__file__) as f:
        return f.read()


# ─────────────────────────────────────────────────────────────────────────
# Test-only capability descriptions. Two genuinely distinct domains
# (calendar scheduling, document translation) plus one test-only
# general-purpose fallback -- none reusing production (llm_completion)
# wording, per the packet's explicit instruction to keep this suite
# independent of production capability text.
# ─────────────────────────────────────────────────────────────────────────

GENERAL_PURPOSE_DESC = (
    "Provide a general conversational or informational response using "
    "a language model when no specialized capability applies."
)
CALENDAR_DESC = (
    "Schedule a meeting or appointment on a calendar and check for "
    "time conflicts."
)
TRANSLATION_DESC = (
    "Translate a written document from one language into another."
)


# ─────────────────────────────────────────────────────────────────────────
# Case A — General-purpose fallback
# ─────────────────────────────────────────────────────────────────────────

class TestGeneralPurposeFallbackDiscrimination:
    """A broad request with no specific match is rescued by the
    general-purpose capability. H1's test_general_purpose_bypasses_min_score
    already covers this against the real llm_completion capability; this
    is the same behavior against a test-only general-purpose capability,
    so the suite as a whole no longer depends on production wording for
    any of its six cases.
    """

    @pytest.mark.asyncio
    async def test_broad_unrelated_request_is_rescued_by_general_purpose_capability(self):
        registry = CapabilityRegistry()
        _register(registry, "calendar_scheduling", CALENDAR_DESC)
        _register(registry, "document_translation", TRANSLATION_DESC)
        _register(registry, "general_purpose_assistant", GENERAL_PURPOSE_DESC,
                   is_general_purpose=True)

        request = CapabilityDiscoveryRequest(
            subgoal_ref="case-a",
            description="Write a short poem about autumn leaves for a greeting card.",
        )
        result = await discover_capabilities(request, registry, min_score=0.01)

        assert result.top_match is not None, (
            "a general-purpose capability must rescue a request with no "
            "specific match -- an empty result here would be the exact "
            "K42-002 regression class, just against test-only capabilities"
        )
        assert result.top_match.capability_type == "general_purpose_assistant"
        assert result.top_match.is_general_purpose is True
        # Neither specific capability has any real lexical overlap with a
        # poem-about-autumn-leaves request -- both must be filtered out by
        # min_score, leaving the fallback as the only candidate.
        assert [m.capability_type for m in result.matches] == ["general_purpose_assistant"]


# ─────────────────────────────────────────────────────────────────────────
# Case B — Specificity dominance
# ─────────────────────────────────────────────────────────────────────────

class TestSpecificityDominanceDiscrimination:
    """A genuinely distinct specific capability outranks the
    general-purpose fallback when the evidence supports it. H1's
    test_specificity_dominance_ranks_specific_above_general already
    proves this with a test-only flight_booking contract; this is the
    same invariant against this suite's own calendar/general-purpose
    pair, so Case B doesn't depend on H1's fixtures either.
    """

    @pytest.mark.asyncio
    async def test_genuinely_specific_capability_outranks_general_purpose_fallback(self):
        registry = CapabilityRegistry()
        _register(registry, "calendar_scheduling", CALENDAR_DESC)
        _register(registry, "document_translation", TRANSLATION_DESC)
        _register(registry, "general_purpose_assistant", GENERAL_PURPOSE_DESC,
                   is_general_purpose=True)

        request = CapabilityDiscoveryRequest(
            subgoal_ref="case-b",
            description=(
                "Please schedule a meeting with the finance team and check "
                "for calendar conflicts next Tuesday."
            ),
        )
        result = await discover_capabilities(request, registry, min_score=0.01)

        assert [m.capability_type for m in result.matches][0] == "calendar_scheduling", (
            "a real lexical match (calendar_scheduling) must outrank a "
            "general-purpose-only fallback, exactly as H1 Decision 2 requires"
        )
        specific = next(m for m in result.matches if m.capability_type == "calendar_scheduling")
        general = next(m for m in result.matches if m.capability_type == "general_purpose_assistant")
        assert specific.is_general_purpose is False
        assert specific.relevance_score > general.relevance_score
        assert general.is_general_purpose is True
        # document_translation has zero lexical overlap with a scheduling
        # request and is not general-purpose -- it must be filtered out
        # entirely, not merely ranked last.
        assert "document_translation" not in [m.capability_type for m in result.matches]


# ─────────────────────────────────────────────────────────────────────────
# Case C — Unsupported request
# ─────────────────────────────────────────────────────────────────────────

class TestUnsupportedRequestDiscrimination:
    """Neither capability is falsely selected when a request is outside
    both capabilities' semantics. Not covered by any existing H1 test
    (H1's freeze review named this the one behavior H1 didn't build).

    Uses a registry with only the two specific (non-general-purpose)
    capabilities -- no general-purpose fallback registered at all. A
    general-purpose capability bypasses min_score by construction (that
    is its entire purpose, proven by Case A above), so it would always
    appear regardless of request; the only registry shape that can
    actually prove "unsupported requests remain unsupported" is one
    where nothing is positioned to rescue a bad match.
    """

    @pytest.mark.asyncio
    async def test_request_outside_both_capabilities_semantics_yields_no_match(self):
        registry = CapabilityRegistry()
        _register(registry, "calendar_scheduling", CALENDAR_DESC)
        _register(registry, "document_translation", TRANSLATION_DESC)

        request = CapabilityDiscoveryRequest(
            subgoal_ref="case-c",
            description="Recommend a good recipe for baking sourdough bread this weekend.",
        )
        result = await discover_capabilities(request, registry, min_score=0.01)

        assert result.matches == [], (
            "a request genuinely outside both registered capabilities' "
            "semantics must yield zero candidates, not a forced match -- "
            "existence of a capability is not itself evidence of relevance"
        )
        assert result.top_match is None
        assert isinstance(result, CapabilityDiscoveryResult)


# ─────────────────────────────────────────────────────────────────────────
# Case D — Registration-order independence
# ─────────────────────────────────────────────────────────────────────────

class TestRegistrationOrderIndependence:
    """Registering the two test capabilities in the opposite order does
    not change which one wins. Not covered by any existing H1 test, and
    treated here as a genuinely open question rather than an assumption
    (per the packet's explicit instruction) -- both tests below were run
    against the unmodified implementation first; only the second one
    (the exact-tie edge case) failed. See this class's second test and
    ADR_K4_2_H_03_CAPABILITY_DISCRIMINATION.md for the full before/after.
    """

    @pytest.mark.asyncio
    async def test_two_distinct_capabilities_rank_identically_regardless_of_registration_order(self):
        """The realistic case: two specific capabilities with genuinely
        different relevance to the request (0.2 vs. ~0.06 lexical
        overlap -- confirmed while designing this test, not asserted as
        literal floats here to avoid brittleness). Passed against the
        unmodified implementation: discover_capabilities()'s sort key is
        (is_general_purpose, -relevance_score), which is a total order
        whenever scores differ, independent of insertion order.
        """
        request = CapabilityDiscoveryRequest(
            subgoal_ref="case-d-distinct",
            description=(
                "Translate the quarterly planning document into German "
                "before the meeting, checking the translation for errors."
            ),
        )

        registry_forward = CapabilityRegistry()
        _register(registry_forward, "calendar_scheduling", CALENDAR_DESC)
        _register(registry_forward, "document_translation", TRANSLATION_DESC)
        result_forward = await discover_capabilities(request, registry_forward, min_score=0.01)

        registry_reversed = CapabilityRegistry()
        _register(registry_reversed, "document_translation", TRANSLATION_DESC)
        _register(registry_reversed, "calendar_scheduling", CALENDAR_DESC)
        result_reversed = await discover_capabilities(request, registry_reversed, min_score=0.01)

        forward_order = [m.capability_type for m in result_forward.matches]
        reversed_order = [m.capability_type for m in result_reversed.matches]
        assert forward_order == reversed_order == ["document_translation", "calendar_scheduling"], (
            "the more relevant capability (document_translation) must win "
            "regardless of which order the two were registered in"
        )
        assert result_forward.top_match.capability_type == result_reversed.top_match.capability_type
        # Scores themselves (not just the winner) must be identical across
        # both runs -- registration order must not perturb scoring either.
        assert result_forward.matches[0].relevance_score == result_reversed.matches[0].relevance_score
        assert result_forward.matches[1].relevance_score == result_reversed.matches[1].relevance_score

    @pytest.mark.asyncio
    async def test_exact_score_tie_does_not_depend_on_registration_order(self):
        """The open question's actual edge case: what happens when two
        specific capabilities score *exactly* the same? This is where an
        implicit "first-registered-at-max-score wins" tie-break could
        hide, because a score-only sort key cannot distinguish two equal
        scores -- only insertion order can, if nothing else is asked to.

        torque_calibration_procedure and sequence_verification_procedure
        are constructed so their relevance_score against the probe
        request is float-identical (verified while designing this test:
        both descriptions share the same number of overlap and non-overlap
        tokens with the request, by symmetric construction -- this is a
        deliberate boundary probe of the sort's tie-break behavior, not a
        naturalistic request, unlike every other case in this file).

        Before ADR_K4_2_H_03_CAPABILITY_DISCRIMINATION.md's fix, this
        test failed: registering torque_calibration_procedure first made
        it win; registering sequence_verification_procedure first made
        IT win -- the same registry contents, same scores, produced a
        different winner purely from insertion order. That is exactly
        the K4.2-H2 "registration order does not affect semantics"
        invariant being violated, confirmed empirically rather than
        assumed. The fix added a third, deterministic sort key
        (capability_type, alphabetical) purely to break exact ties;
        it changes no CapabilityMatch field, no scoring formula, and no
        public signature, so per the packet's decision tree this was a
        trivial, clearly-deterministic tie-break correction, made
        directly rather than escalated. This test now pins down the
        specific deterministic winner (alphabetically-first
        capability_type) as a regression guard.
        """
        request = CapabilityDiscoveryRequest(
            subgoal_ref="case-d-tie",
            description=(
                "Run the widget assembly calibration covering torque and "
                "sequence checks before shipment."
            ),
        )
        torque_desc = "Calibrate widget assembly torque to the fixture alignment."
        sequence_desc = "Verify widget assembly sequence to the checklist alignment."

        registry_forward = CapabilityRegistry()
        _register(registry_forward, "torque_calibration_procedure", torque_desc)
        _register(registry_forward, "sequence_verification_procedure", sequence_desc)
        result_forward = await discover_capabilities(request, registry_forward, min_score=0.01)

        registry_reversed = CapabilityRegistry()
        _register(registry_reversed, "sequence_verification_procedure", sequence_desc)
        _register(registry_reversed, "torque_calibration_procedure", torque_desc)
        result_reversed = await discover_capabilities(request, registry_reversed, min_score=0.01)

        # Confirm this genuinely is an exact tie (not a near-tie that
        # would pass for an uninteresting reason) before asserting
        # anything about order-independence.
        scores_forward = {m.capability_type: m.relevance_score for m in result_forward.matches}
        assert scores_forward["torque_calibration_procedure"] == scores_forward["sequence_verification_procedure"]
        assert scores_forward["torque_calibration_procedure"] >= 0.01

        assert result_forward.top_match.capability_type == result_reversed.top_match.capability_type, (
            "an exact relevance_score tie must resolve identically "
            "regardless of registration order"
        )
        assert result_forward.top_match.capability_type == "sequence_verification_procedure", (
            "deterministic tie-break is alphabetical by capability_type "
            "('sequence_...' < 'torque_...'); pins down the specific rule, "
            "not just that some rule exists"
        )


# ─────────────────────────────────────────────────────────────────────────
# Case E — Dynamic registration
# ─────────────────────────────────────────────────────────────────────────

class TestDynamicCapabilityRegistration:
    """Adding a capability requires zero changes to planner.py. Proven
    behaviorally (register a new capability mid-test, into a registry
    that already produced one discovery result, and show the very next
    discovery call picks it up correctly) rather than assumed from
    DRIFT-06's prior confirmation that no hard-coded type strings exist
    in routing -- this is what "write the test as a genuine proof" means
    for this case. This test file makes zero edits to planner.py outside
    the single, separately-documented Case D tie-break correction above;
    that in itself is part of the proof this case asserts.
    """

    @pytest.mark.asyncio
    async def test_newly_registered_capability_is_discovered_without_planner_changes(self):
        registry = CapabilityRegistry()
        _register(registry, "calendar_scheduling", CALENDAR_DESC)
        _register(registry, "general_purpose_assistant", GENERAL_PURPOSE_DESC,
                   is_general_purpose=True)

        request = CapabilityDiscoveryRequest(
            subgoal_ref="case-e",
            description=(
                "Translate the quarterly planning document into German "
                "before the meeting, checking the translation for errors."
            ),
        )

        result_before = await discover_capabilities(request, registry, min_score=0.01)
        assert "document_translation" not in [m.capability_type for m in result_before.matches], (
            "document_translation is not registered yet -- it cannot appear"
        )
        # calendar_scheduling has weak (but nonzero) overlap with this
        # request and clears min_score, so it is the best available
        # candidate until a genuinely relevant capability exists.
        assert result_before.top_match.capability_type == "calendar_scheduling"

        # The capability set changes. No planner.py code runs here or
        # anywhere else in this test -- only registry state changes.
        _register(registry, "document_translation", TRANSLATION_DESC)

        result_after = await discover_capabilities(request, registry, min_score=0.01)
        assert result_after.top_match.capability_type == "document_translation", (
            "once a genuinely relevant capability is registered, discovery "
            "must surface it as the new top match on the very next call -- "
            "no planner.py change, no restart, no re-registration of "
            "anything else"
        )
        assert result_after.top_match.relevance_score > result_before.top_match.relevance_score

    def test_test_only_capability_types_are_not_hard_coded_in_planner_source(self):
        """Belt-and-suspenders companion to the behavioral proof above:
        confirms discover_capabilities() cannot special-case these
        specific capability_type strings even in principle, since they
        do not appear anywhere in planner.py's source text at all."""
        source = _planner_source_text()
        for synthetic_type in (
            "calendar_scheduling",
            "document_translation",
            "general_purpose_assistant",
            "torque_calibration_procedure",
            "sequence_verification_procedure",
        ):
            assert synthetic_type not in source


# ─────────────────────────────────────────────────────────────────────────
# Case F — Evidence
# ─────────────────────────────────────────────────────────────────────────

class TestCapabilityMatchEvidence:
    """The winning CapabilityMatch exposes why it won. H1 already asserts
    on evidence["specificity_tier"]/evidence["general_fallback"] inline
    within other tests (e.g. test_general_purpose_bypasses_min_score);
    this gives that same evidence contract its own explicitly named,
    dedicated test, covering both a specific winner and a general-purpose
    fallback in the same result so the contrast is visible in one place.
    """

    @pytest.mark.asyncio
    async def test_winning_and_fallback_matches_carry_explanatory_evidence(self):
        registry = CapabilityRegistry()
        _register(registry, "calendar_scheduling", CALENDAR_DESC)
        _register(registry, "general_purpose_assistant", GENERAL_PURPOSE_DESC,
                   is_general_purpose=True)

        request = CapabilityDiscoveryRequest(
            subgoal_ref="case-f",
            description=(
                "Please schedule a meeting with the finance team and check "
                "for calendar conflicts next Tuesday."
            ),
        )
        result = await discover_capabilities(request, registry, min_score=0.01)
        assert len(result.matches) == 2

        specific = next(m for m in result.matches if m.capability_type == "calendar_scheduling")
        assert specific.evidence["general_fallback"] is False
        assert specific.evidence["specificity_tier"] in ("strong_specific", "weak_specific")
        # lexical_score is evidence's record of the same relevance_score
        # the ranking itself used -- evidence must not silently diverge
        # from the value that actually drove the decision.
        assert specific.evidence["lexical_score"] == round(specific.relevance_score, 4)

        fallback = next(m for m in result.matches if m.capability_type == "general_purpose_assistant")
        assert fallback.evidence["general_fallback"] is True
        assert fallback.evidence["specificity_tier"] == "general_fallback"
        assert fallback.evidence["lexical_score"] == round(fallback.relevance_score, 4)

        # The two matches' evidence must actually differ -- evidence that
        # was identical regardless of which capability won would explain
        # nothing.
        assert specific.evidence["general_fallback"] != fallback.evidence["general_fallback"]
        assert specific.evidence["specificity_tier"] != fallback.evidence["specificity_tier"]


# ─────────────────────────────────────────────────────────────────────────
# Required boundary test — test-only capabilities never touch a
# separately-instantiated (production-representative) registry.
# ─────────────────────────────────────────────────────────────────────────

class TestRegistryIsolationBoundary:
    """CapabilityRegistry has no class-level or module-level shared state
    (core/capabilities/registry.py __init__ owns fresh _contracts/
    _adapters dicts per instance; confirmed by reading that file while
    designing this suite, and by the discover_capabilities() docstring's
    own confirmation that no get_capability_registry() singleton accessor
    exists anywhere in this codebase). This test demonstrates that
    isolation behaviorally rather than only asserting it from source
    reading: registering this suite's synthetic capabilities into one
    registry instance must leave a second, independently-constructed
    instance completely untouched.
    """

    def test_test_only_capabilities_never_touch_a_separate_registry_instance(self):
        this_suite_registry = CapabilityRegistry()
        _register(this_suite_registry, "calendar_scheduling", CALENDAR_DESC)
        _register(this_suite_registry, "document_translation", TRANSLATION_DESC)
        _register(this_suite_registry, "general_purpose_assistant", GENERAL_PURPOSE_DESC,
                   is_general_purpose=True)
        assert len(this_suite_registry.list_capabilities()) == 3

        production_representative_registry = CapabilityRegistry()
        assert production_representative_registry.list_capabilities() == [], (
            "a freshly constructed CapabilityRegistry must start empty "
            "regardless of what any other registry instance has "
            "registered -- no shared/global/singleton state anywhere"
        )
        for synthetic_type in (
            "calendar_scheduling", "document_translation", "general_purpose_assistant",
        ):
            assert synthetic_type not in production_representative_registry.list_capabilities()
            assert production_representative_registry.get_contract(synthetic_type) is None

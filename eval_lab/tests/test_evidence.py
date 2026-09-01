"""Evidence/provenance/annotation tests — §79 'Evidence' category."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from eval_lab.contracts.enums import ConfidenceLevel, EvidenceCapturePolicy, EvidenceOrigin, TrustClassification
from eval_lab.contracts.evidence import (
    Annotation,
    AnnotationConfidence,
    AnnotationVerdict,
    Annotator,
    AnnotatorAgreement,
    ArtifactReference,
    Evidence,
    EvidenceFreshness,
)
from eval_lab.contracts.serialization import ContractValidationError

NOW = datetime(2026, 8, 30, tzinfo=timezone.utc)


def test_evidence_requires_at_least_one_reference():
    with pytest.raises(ContractValidationError, match="evidence_requires_at_least_one_reference"):
        Evidence(
            evidence_id="ev1", origin=EvidenceOrigin.ENVIRONMENT_GENERATED,
            trust_classification=TrustClassification.VALIDATED, capture_policy=EvidenceCapturePolicy.FULL,
            freshness=EvidenceFreshness(captured_at=NOW),
        )


def test_evidence_with_state_predicate_is_valid():
    ev = Evidence(
        evidence_id="ev1", origin=EvidenceOrigin.ENVIRONMENT_GENERATED,
        trust_classification=TrustClassification.VALIDATED, capture_policy=EvidenceCapturePolicy.FULL,
        freshness=EvidenceFreshness(captured_at=NOW), state_predicate_description="file exists",
    )
    assert ev.to_dict()["state_predicate_description"] == "file exists"


def test_evidence_composite_reference_allowed():
    """More than one reference field set is allowed (composite evidence)."""
    ev = Evidence(
        evidence_id="ev1", origin=EvidenceOrigin.ORACLE_GENERATED,
        trust_classification=TrustClassification.VALIDATED, capture_policy=EvidenceCapturePolicy.FULL,
        freshness=EvidenceFreshness(captured_at=NOW),
        state_predicate_description="exit code 0", oracle_output_description="verifier: pass",
    )
    d = ev.to_dict()
    assert d["state_predicate_description"] and d["oracle_output_description"]


def test_unavailable_capture_policy_rejects_content():
    with pytest.raises(ContractValidationError, match="unavailable_capture_policy_with_content"):
        Evidence(
            evidence_id="ev1", origin=EvidenceOrigin.AGENT_GENERATED,
            trust_classification=TrustClassification.UNKNOWN, capture_policy=EvidenceCapturePolicy.UNAVAILABLE,
            freshness=EvidenceFreshness(captured_at=NOW), state_predicate_description="should not be set",
        )


def test_evidence_freshness_none_vs_false_distinction():
    """produced_before_task_mutation=None (not applicable) must round-trip
    distinctly from False (definitely produced after)."""
    f_none = EvidenceFreshness(captured_at=NOW)
    f_false = EvidenceFreshness(captured_at=NOW, produced_before_task_mutation=False)
    assert f_none.to_dict()["produced_before_task_mutation"] is None
    assert f_false.to_dict()["produced_before_task_mutation"] is False


def test_artifact_reference_does_not_embed_content():
    art = ArtifactReference(artifact_id="art1", artifact_type="file", storage_location="s3://bucket/key", content_hash="abc123")
    d = art.to_dict()
    assert "content" not in d and "data" not in d, "ArtifactReference must reference, never embed, artifact content"


def test_annotation_verdict_is_a_closed_enum():
    """Correction pass: verdict was a raw str with manual membership
    checking; now AnnotationVerdict. Valid construction with the enum:"""
    annot = Annotator(annotator_id="a1", display_name="reviewer")
    a = Annotation(
        annotation_id="an1", annotator=annot, task_description="does it pass?",
        verdict=AnnotationVerdict.PASS, confidence=AnnotationConfidence(level=ConfidenceLevel.HIGH), created_at=NOW,
    )
    assert a.verdict == AnnotationVerdict.PASS
    assert a.to_dict()["verdict"] == "pass"


def test_annotation_rejects_non_enum_verdict():
    """A raw string (even a previously-"valid" one like "pass") is no
    longer accepted -- the type discipline is now enforced by isinstance,
    not by a membership set, per the correction pass's strengthening of
    this invariant (a caller must use AnnotationVerdict.PASS, not the
    bare string "pass")."""
    annot = Annotator(annotator_id="a1", display_name="reviewer")
    with pytest.raises(ContractValidationError, match="verdict_not_enum_member"):
        Annotation(
            annotation_id="an1", annotator=annot, task_description="does it pass?",
            verdict="pass", confidence=AnnotationConfidence(level=ConfidenceLevel.HIGH), created_at=NOW,
        )


def test_annotation_confidence_level_is_a_closed_enum():
    """Correction pass: AnnotationConfidence.level was deliberately left
    as a free string with a documented (but, on review, unjustified)
    exemption from the enum discipline applied elsewhere. Now shares
    ConfidenceLevel with EvaluationResult.confidence."""
    ac = AnnotationConfidence(level=ConfidenceLevel.MEDIUM)
    assert ac.to_dict()["level"] == "medium"
    with pytest.raises(ContractValidationError, match="level_not_enum_member"):
        AnnotationConfidence(level="medium")


def test_annotator_agreement_rate_bounds():
    with pytest.raises(ContractValidationError, match="agreement_rate_out_of_range"):
        AnnotatorAgreement(source_a_description="human1", source_b_description="human2", n_compared=10, agreement_rate=1.5)


def test_annotator_agreement_negative_n_rejected():
    with pytest.raises(ContractValidationError, match="negative_n_compared"):
        AnnotatorAgreement(source_a_description="a", source_b_description="b", n_compared=-1, agreement_rate=0.5)


def test_annotator_agreement_valid():
    a = AnnotatorAgreement(source_a_description="human1", source_b_description="judge1", n_compared=50, agreement_rate=0.82)
    assert a.to_dict()["agreement_rate"] == 0.82

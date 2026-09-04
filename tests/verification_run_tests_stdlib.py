import os
import sys
import unittest
from datetime import datetime, timezone

# Portable repo-root insertion, matching tests/conftest.py's own technique —
# needed here because running this file directly (not via pytest) skips
# conftest.py entirely.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.verification.identity import new_id
from core.verification.epistemic import (
    BasisComponent, VerificationBasis, ObservationAuthority,
    InspectionAuthorization, VerificationAssurance,
)
from core.verification.evidence import (
    EvidenceSource, EvidenceItem, EvidenceDirectness, EvidenceStatus,
    CircularEvidenceError, check_not_circular,
)
from core.verification.verdict import (
    VerificationVerdict, VerificationExecutionFailure, VerificationResult,
)
from core.verification.receipt import VerificationReceipt, Replayability


def basis(*components):
    return VerificationBasis(frozenset(components))


def assurance(**overrides):
    defaults = dict(
        basis=basis(BasisComponent.DETERMINISTIC),
        observation_authority=ObservationAuthority.FILESYSTEM,
        inspection_authorization=InspectionAuthorization(surface="fs:/tmp", authorized=True),
        assurance_scope="artifact_existence", coverage=1.0,
        independence_level="single_verifier", integrity_verified=True,
    )
    defaults.update(overrides)
    return VerificationAssurance(**defaults)


class TestVerificationBasisIsCompositional(unittest.TestCase):
    def test_single_component_allowed(self):
        self.assertTrue(basis(BasisComponent.DETERMINISTIC).is_deterministic_only)

    def test_multiple_components_allowed(self):
        b = basis(BasisComponent.DETERMINISTIC, BasisComponent.RUNTIME_OBSERVATION)
        self.assertTrue(b.has(BasisComponent.DETERMINISTIC))
        self.assertTrue(b.has(BasisComponent.RUNTIME_OBSERVATION))
        self.assertFalse(b.is_deterministic_only)

    def test_empty_basis_rejected(self):
        with self.assertRaises(ValueError):
            VerificationBasis(frozenset())


class TestAssuranceMustBeScoped(unittest.TestCase):
    def test_missing_scope_rejected(self):
        with self.assertRaises(ValueError):
            assurance(assurance_scope="")

    def test_coverage_out_of_range_rejected(self):
        with self.assertRaises(ValueError):
            assurance(coverage=1.5)

    def test_unauthorized_surface_rejected(self):
        with self.assertRaises(ValueError):
            assurance(inspection_authorization=InspectionAuthorization(surface="fs:/etc/shadow", authorized=False))


class TestCircularEvidenceRejected(unittest.TestCase):
    def test_restatement_of_claim_rejected(self):
        claim_id = new_id()
        ev = EvidenceItem(
            evidence_id=new_id(),
            source=EvidenceSource(source_type="agent_assertion", source_id="agent-1", producer="agent"),
            locator="chat:turn-4", directness=EvidenceDirectness.MODEL_INTERPRETATION,
            status=EvidenceStatus.SUFFICIENT, observed_at=datetime.now(timezone.utc),
            retrieved_at=datetime.now(timezone.utc), content_summary='agent says "X is true"',
            supports_claim_ids=(claim_id,), is_restatement_of_claim=True,
        )
        with self.assertRaises(CircularEvidenceError):
            check_not_circular(claim_id, ev)

    def test_genuine_evidence_accepted(self):
        claim_id = new_id()
        ev = EvidenceItem(
            evidence_id=new_id(),
            source=EvidenceSource(source_type="filesystem", source_id="fs", producer="runtime"),
            locator="/repo/output.txt", directness=EvidenceDirectness.DIRECT,
            status=EvidenceStatus.SUFFICIENT, observed_at=datetime.now(timezone.utc),
            retrieved_at=datetime.now(timezone.utc), content_summary="file exists, 1024 bytes",
            supports_claim_ids=(claim_id,), is_restatement_of_claim=False,
        )
        check_not_circular(claim_id, ev)  # must not raise


class TestVerifierCrashCannotBecomePass(unittest.TestCase):
    def test_execution_failure_with_positive_verdict_rejected(self):
        with self.assertRaises(ValueError):
            VerificationResult(
                verification_id=new_id(), task_id=new_id(), execution_id=new_id(),
                attempt_id=new_id(), verdict=VerificationVerdict.VERIFIED,
                assurance=assurance(), confidence=0.9,
                execution_failure=VerificationExecutionFailure.VERIFIER_CRASH,
            )

    def test_execution_failure_with_unverifiable_accepted(self):
        r = VerificationResult(
            verification_id=new_id(), task_id=new_id(), execution_id=new_id(),
            attempt_id=new_id(), verdict=VerificationVerdict.UNVERIFIABLE,
            assurance=assurance(), confidence=0.0,
            execution_failure=VerificationExecutionFailure.VERIFIER_CRASH,
        )
        self.assertEqual(r.verdict, VerificationVerdict.UNVERIFIABLE)


class TestReceiptImmutability(unittest.TestCase):
    def _make_result(self):
        return VerificationResult(
            verification_id=new_id(), task_id=new_id(), execution_id=new_id(),
            attempt_id=new_id(), verdict=VerificationVerdict.VERIFIED,
            assurance=assurance(), confidence=0.95,
        )

    def test_supersession_returns_new_object_original_untouched(self):
        result = self._make_result()
        r1 = VerificationReceipt(
            receipt_id=new_id(), verification_id=result.verification_id, result=result,
            issued_at=datetime.now(timezone.utc), replayability=Replayability.FULLY_REPLAYABLE,
        )
        new_receipt_id = new_id()
        r2 = r1.superseded_by(new_receipt_id)
        self.assertIsNone(r1.superseded_by_receipt_id)
        self.assertEqual(r2.superseded_by_receipt_id, new_receipt_id)
        self.assertIsNot(r1, r2)

    def test_receipt_fields_cannot_be_reassigned(self):
        result = self._make_result()
        r = VerificationReceipt(
            receipt_id=new_id(), verification_id=result.verification_id, result=result,
            issued_at=datetime.now(timezone.utc), replayability=Replayability.FULLY_REPLAYABLE,
        )
        with self.assertRaises(Exception):
            r.receipt_id = "tampered"


if __name__ == "__main__":
    unittest.main(verbosity=2)

"""MEM-02 lifecycle checks; all storage below is a test-local MEM-01 double."""
from dataclasses import FrozenInstanceError, replace
import json
import unittest

from runtime.context.contracts import digest
from runtime.memory import ClaimStatus, EvidenceState, MemoryContractError
from runtime.memory.lifecycle import (
    DecisionEvidence, Disposition, MemoryLink, MemoryReference, NormalizationEvidence,
    decode_candidate, deduplicate_candidates, normalize_claim, prepare_candidate,
    store_candidate,
)
from runtime.tests.test_memory_foundation import (
    InMemoryMemoryDouble, annotated_record, record, source, verified_record,
)


class RecordingMemory(InMemoryMemoryDouble):
    def __init__(self):
        super().__init__()
        self.reads = []
        self.writes = []

    def get(self, project_id, record_id):
        self.reads.append((project_id, record_id))
        return super().get(project_id, record_id)

    def put_candidate(self, project_id, item):
        self.writes.append((project_id, item.record_id))
        return super().put_candidate(project_id, item)


def candidate(record_id="candidate-1", original=None, **changes):
    return prepare_candidate("alpha", record() if original is None else original,
                             record_id=record_id, **changes)


class MemoryLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.memory = RecordingMemory()

    def test_normalization_preserves_original_and_transformation_digests(self):
        original = record(claim="first  \r\n  second\t\rthird\n")
        item = candidate(original=original)
        self.assertEqual(item.normalized_claim, "first\n  second\nthird\n")
        self.assertEqual(item.original, original)
        self.assertEqual(item.transformation.input_digest, digest(original.claim))
        self.assertEqual(item.transformation.output_digest, digest(item.normalized_claim))
        self.assertEqual(normalize_claim(item.normalized_claim), item.normalized_claim)

    def test_interior_spacing_unicode_and_case_are_not_semantically_rewritten(self):
        text = "  A  B\nCafé is NOT accepted.\t"
        self.assertEqual(candidate(original=record(claim=text)).normalized_claim,
                         "  A  B\nCafé is NOT accepted.")

    def test_verified_original_round_trips_without_verifying_derived_envelope(self):
        original = annotated_record()
        item = candidate(original=original)
        stored = store_candidate("alpha", item, self.memory)
        restored = decode_candidate("alpha", stored, record_id="candidate-1")
        self.assertEqual(restored.original, original)
        self.assertEqual(restored.original.status, ClaimStatus.EVIDENCE_VERIFIED)
        self.assertEqual(stored.status, ClaimStatus.REPORTED)
        self.assertIsNone(stored.verification)
        self.assertIsNone(stored.capture)
        self.assertIsNone(stored.review)
        self.assertEqual((stored.trust, stored.authority), ("untrusted", "none"))

    def test_all_dispositions_and_rationale_are_stored_as_evidence(self):
        for disposition in Disposition:
            with self.subTest(disposition=disposition):
                decision = DecisionEvidence(disposition=disposition,
                                            rationale="Rejected warning remains relevant.")
                item = candidate(record_id=disposition.value, decision=decision)
                stored = store_candidate("alpha", item, self.memory)
                self.assertEqual(decode_candidate("alpha", stored,
                    record_id=disposition.value).decision, decision)
                self.assertEqual(stored.authority, "none")

    def test_identical_store_is_idempotent_and_does_not_rewrite(self):
        first = candidate()
        stored = store_candidate("alpha", first, self.memory)
        self.assertEqual(store_candidate("alpha", candidate(), self.memory), stored)
        self.assertEqual(len(self.memory.writes), 1)

    def test_changed_claim_at_same_key_is_rejected_without_write(self):
        store_candidate("alpha", candidate(), self.memory)
        before = dict(self.memory.records)
        with self.assertRaises(MemoryContractError):
            store_candidate("alpha", candidate(original=record(claim="Opposing claim")), self.memory)
        self.assertEqual(self.memory.records, before)
        self.assertEqual(len(self.memory.writes), 1)

    def test_changed_rationale_source_version_and_metadata_collide(self):
        store_candidate("alpha", candidate(), self.memory)
        for changed in (
            candidate(decision=DecisionEvidence(disposition=Disposition.DEFERRED, rationale="Wait")),
            candidate(original=record(sources=(source(source_version="revision-2"),))),
            candidate(original=annotated_record()),
        ):
            with self.subTest(changed=changed), self.assertRaises(MemoryContractError):
                store_candidate("alpha", changed, self.memory)
        self.assertEqual(len(self.memory.writes), 1)

    def test_conflicting_claims_and_source_versions_remain_distinct(self):
        items = (candidate("old", original=record(claim="Do not use this method")),
                 candidate("new", original=record(claim="Use this method",
                     sources=(source(source_version="revision-2"),))))
        unique = deduplicate_candidates("alpha", items + (items[0],))
        self.assertEqual(len(unique), 2)
        restored = [decode_candidate("alpha", store_candidate("alpha", item, self.memory),
                    record_id=item.reference.record_id) for item in unique]
        self.assertEqual({c.original.claim for c in restored},
                         {"Do not use this method", "Use this method"})
        self.assertEqual({c.original.sources[0].source_version for c in restored},
                         {"revision-1", "revision-2"})

    def test_normalized_match_does_not_merge_raw_source_histories(self):
        a = candidate("a", original=record(claim="Same \r\n"))
        b = candidate("b", original=record(claim="Same\n"))
        self.assertEqual(a.normalized_claim, b.normalized_claim)
        self.assertEqual(len(deduplicate_candidates("alpha", (a, b))), 2)

    def test_deduplication_is_deterministic_and_key_collisions_fail(self):
        a, b = candidate("a"), candidate("b")
        self.assertEqual(deduplicate_candidates("alpha", (b, a, b)), (a, b))
        with self.assertRaises(MemoryContractError):
            deduplicate_candidates("alpha", (a, candidate("a", original=record(claim="Changed"))))

    def test_explicit_links_are_sorted_deduplicated_and_round_trip(self):
        file_link = MemoryLink(project_id="alpha", kind="file", target="src/code.py#L2", version="v1")
        memory_link = MemoryLink(project_id="alpha", kind="memory",
                                target=MemoryReference(project_id="alpha", record_id="warning").identity)
        a = candidate(links=(memory_link, file_link, file_link))
        self.assertEqual(a, candidate(links=(file_link, memory_link)))
        self.assertEqual(len(a.links), 2)
        self.assertEqual(decode_candidate("alpha", a.to_memory_record(), record_id="candidate-1"), a)

    def test_foreign_links_and_ambiguous_memory_references_are_rejected(self):
        with self.assertRaises(MemoryContractError):
            candidate(links=(MemoryLink(project_id="beta", kind="file", target="a.py"),))
        for target in ("warning", "memory:beta:warning", "memory:alpha:../warning"):
            with self.subTest(target=target), self.assertRaises(MemoryContractError):
                MemoryLink(project_id="alpha", kind="memory", target=target)

    def test_cross_project_inputs_fail_before_memory_operations(self):
        with self.assertRaises(MemoryContractError):
            prepare_candidate("alpha", record("beta"), record_id="candidate-1")
        with self.assertRaises(MemoryContractError):
            store_candidate("beta", candidate(), self.memory)
        with self.assertRaises(MemoryContractError):
            deduplicate_candidates("beta", (candidate(),))
        self.assertEqual((self.memory.reads, self.memory.writes), ([], []))

    def test_same_candidate_id_isolated_across_projects(self):
        for project in ("alpha", "beta"):
            item = prepare_candidate(project, record(project), record_id="same")
            store_candidate(project, item, self.memory)
        self.assertEqual(set(self.memory.records), {("alpha", "same"), ("beta", "same")})

    def test_unknown_stale_missing_and_absent_metadata_are_preserved(self):
        for state in EvidenceState:
            with self.subTest(state=state):
                item = candidate(original=record(sources=(source(state=state),)))
                restored = decode_candidate("alpha", item.to_memory_record(), record_id="candidate-1")
                self.assertEqual(restored.original.sources[0].state, state)
                self.assertIsNone(restored.original.capture)
                self.assertIsNone(restored.original.sources[0].review)

    def test_missing_and_malformed_inputs_are_rejected(self):
        for project, original, identity in ((None, record(), "a"), ("alpha", None, "a"),
                                           ("alpha", record(), "../a")):
            with self.subTest(project=project, original=original), self.assertRaises(MemoryContractError):
                prepare_candidate(project, original, record_id=identity)
        for links in ([], (None,), tuple(MemoryLink(project_id="alpha", kind="file", target="a")
                                         for _ in range(33))):
            with self.subTest(links=links), self.assertRaises(MemoryContractError):
                candidate(links=links)
        with self.assertRaises(MemoryContractError):
            store_candidate("alpha", candidate(), None)

    def test_invalid_rationale_and_transformation_are_rejected(self):
        for disposition, rationale in (("accepted", "reason"), (Disposition.ACCEPTED, ""),
                                       (Disposition.DEFERRED, [])):
            with self.subTest(disposition=disposition), self.assertRaises(MemoryContractError):
                DecisionEvidence(disposition=disposition, rationale=rationale)
        with self.assertRaises(MemoryContractError):
            replace(candidate(), transformation=NormalizationEvidence(
                algorithm="newline-trailing-space-v1", input_digest=digest("other"),
                output_digest=digest("other")))

    def test_serialized_envelope_bound_is_enforced_before_writes(self):
        with self.assertRaises(MemoryContractError):
            candidate(original=record(claim="x" * (128 * 1024)))
        self.assertEqual(self.memory.writes, [])

    def test_immutable_candidate_and_nested_metadata(self):
        item = candidate()
        for owner, field, value in ((item, "normalized_claim", "x"),
                                   (item.reference, "project_id", "beta"),
                                   (item.transformation, "algorithm", "other")):
            with self.subTest(field=field), self.assertRaises(FrozenInstanceError):
                setattr(owner, field, value)

    def test_illicit_record_mutation_and_authority_are_revalidated(self):
        for field, value in (("claim", []), ("trust", "canonical"), ("authority", "approved")):
            item = candidate()
            object.__setattr__(item.original, field, value)
            with self.subTest(field=field), self.assertRaises(MemoryContractError):
                store_candidate("alpha", item, self.memory)
        self.assertEqual(self.memory.reads, [])

    def test_forged_normalization_and_nested_authority_fail_decode(self):
        stored = candidate().to_memory_record()
        for mutate in (
            lambda p: p["candidate"].update(normalized_claim="fabricated"),
            lambda p: p["candidate"]["original"].update(authority="approved"),
            lambda p: p["candidate"]["reference"].update(project_id="beta"),
            lambda p: p.update(version=True),
            lambda p: p["candidate"].update(extra="unrecognized"),
        ):
            payload = json.loads(stored.claim)
            mutate(payload)
            with self.subTest(mutate=mutate), self.assertRaises(MemoryContractError):
                decode_candidate("alpha", replace(stored, claim=json.dumps(payload)), record_id="candidate-1")

    def test_duplicate_json_noncanonical_body_and_missing_fields_fail_decode(self):
        stored = candidate().to_memory_record()
        for body in (stored.claim.replace('"version":1', '"version":1,"version":1', 1),
                     json.dumps(json.loads(stored.claim), indent=2), "{}", "not json", "[]"):
            with self.subTest(body=body[:40]), self.assertRaises(MemoryContractError):
                decode_candidate("alpha", replace(stored, claim=body), record_id="candidate-1")

    def test_corrupted_original_verification_is_not_accepted_on_decode(self):
        stored = candidate(original=verified_record()).to_memory_record()
        payload = json.loads(stored.claim)
        payload["candidate"]["original"]["verification"]["claim_digest"] = digest("different")
        with self.assertRaises(MemoryContractError):
            decode_candidate("alpha", replace(stored, claim=json.dumps(payload)), record_id="candidate-1")

    def test_storage_return_and_read_back_must_match_exact_evidence(self):
        class BadReturn(RecordingMemory):
            def put_candidate(self, project_id, item):
                super().put_candidate(project_id, item)
                return replace(item, record_id="other")
        class MissingReadBack(RecordingMemory):
            def get(self, project_id, record_id):
                return None
        for memory in (BadReturn(), MissingReadBack()):
            with self.subTest(memory=memory), self.assertRaises(MemoryContractError):
                store_candidate("alpha", candidate(), memory)

    def test_foreign_existing_provider_record_is_rejected(self):
        self.memory.records[("alpha", "candidate-1")] = prepare_candidate(
            "beta", record("beta"), record_id="candidate-1").to_memory_record()
        with self.assertRaises(MemoryContractError):
            store_candidate("alpha", candidate(), self.memory)
        self.assertEqual(self.memory.writes, [])


if __name__ == "__main__":
    unittest.main()

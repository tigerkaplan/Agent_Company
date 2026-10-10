"""Focused tests for the standalone reporter; no runtime suite is imported."""

import ast
from contextlib import ExitStack, redirect_stderr, redirect_stdout
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock


MODULE = Path(__file__).with_name("run_validation_diagnostics.py")
SPEC = importlib.util.spec_from_file_location("validation_diagnostics", MODULE)
diagnostics = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(diagnostics)

TEST_ID = "runtime.tests.example.Case.test_one"
LINE = "test_one (" + TEST_ID + ") ... "


class DiagnosticTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def log(self, text, name="tests.log", encoding="utf-8"):
        path = self.root / name
        path.write_bytes(text.encode(encoding))
        return path

    def result(self, value, name="result.json"):
        return self.log(json.dumps(value), name)

    def source(self, text):
        return diagnostics.build_report([self.log(text)])["sources"][0]

    def cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = diagnostics.main(list(map(str, args)))
        self.assertEqual("", err.getvalue())
        self.assertEqual(1, len(out.getvalue().splitlines()))
        return code, json.loads(out.getvalue()), out.getvalue()

    def test_completed_log_keeps_observations_hash_and_logged_timing(self):
        text = LINE + "ok\nRan 1 test in 1.250s\nOK\n"
        path = self.log(text)
        report = diagnostics.build_report([path])
        source = report["sources"][0]
        self.assertEqual(str(path), source["path"])
        self.assertEqual(hashlib.sha256(text.encode()).hexdigest(), source["sha256"])
        self.assertEqual(1.25, source["summaries"][0]["seconds"])
        self.assertEqual("OK", source["tests"][0]["status"])
        self.assertEqual("OBSERVED", report["status"])
        self.assertEqual({"UNKNOWN"}, set(report["conclusions"].values()))

    def test_duplicates_are_not_collapsed_or_counted_as_unique_tests(self):
        source = self.source(LINE + "ok\n" + LINE + "ok\nRan 2 tests in 0s\nOK\n")
        self.assertEqual(2, len(source["records"]))
        self.assertEqual(2, source["tests"][0]["logged_occurrences"])
        self.assertEqual(1, len(source["tests"]))

    def test_conflicting_duplicates_preserve_each_terminal_status(self):
        source = self.source(LINE + "ok\n" + LINE + "FAIL\n")
        self.assertEqual(["OK", "FAIL"], [r["status"] for r in source["records"]])
        self.assertEqual("UNKNOWN", source["tests"][0]["status"])

    def test_skipped_failed_error_expected_failure_and_unexpected_success(self):
        for raw, expected in [("skipped 'reason'", "SKIPPED"), ("FAIL", "FAIL"),
                              ("ERROR", "ERROR"), ("expected failure", "EXPECTED_FAILURE"),
                              ("unexpected success", "UNEXPECTED_SUCCESS")]:
            with self.subTest(raw=raw):
                source = self.source(LINE + raw + "\n")
                self.assertEqual(expected, source["records"][0]["status"])
                self.assertEqual(raw, source["records"][0]["raw_status"])

    def test_truncated_test_remains_unfinished_even_with_prior_success(self):
        source = self.source(LINE + "ok\n" + LINE)
        self.assertEqual("UNFINISHED", source["records"][-1]["status"])
        self.assertEqual("UNKNOWN", source["tests"][0]["status"])
        self.assertTrue(any("truncation" in s for s in source["limitations"]))

    def test_wrapped_powershell_output_and_split_identity(self):
        source = self.source("python : " + LINE.rstrip() + "\n... ok\n" +
                             "test_one\n(" + TEST_ID + ") ... ERROR\n")
        self.assertEqual([TEST_ID, TEST_ID], [r["test_id"] for r in source["records"]])
        self.assertEqual(["OK", "ERROR"], [r["status"] for r in source["records"]])
        self.assertEqual([2, 4], [r["end_line"] for r in source["records"]])

    def test_nonadjacent_status_is_not_attached_to_unfinished_test(self):
        source = self.source(LINE + "\nnoise\n... ok\n")
        self.assertEqual("UNFINISHED", source["records"][0]["status"])
        self.assertEqual(2, source["unparsed_nonempty_lines"])

    def test_bare_wrapped_status_requires_an_adjacent_ellipsis_marker(self):
        source = self.source(LINE + "\nFAIL\n" + LINE + "\nok\n")
        self.assertEqual(["FAIL", "OK"], [r["status"] for r in source["records"]])
        source = self.source("test_one (" + TEST_ID + ")\nok\n")
        self.assertEqual("UNFINISHED", source["records"][0]["status"])

    def test_display_name_conflict_preserves_id_and_marks_status_unknown(self):
        source = self.source(LINE.replace("test_one (", "test_other (") + "ok\n")
        self.assertEqual(TEST_ID, source["tests"][0]["test_id"])
        self.assertEqual("OK", source["records"][0]["status"])
        self.assertEqual("UNKNOWN", source["tests"][0]["status"])
        self.assertIn("display name conflicts with exact test ID", source["tests"][0]["limitations"])

    def test_unknown_status_is_not_success(self):
        source = self.source(LINE + "ok; invoke-command\n")
        self.assertEqual("UNKNOWN", source["records"][0]["status"])

    def test_parameterized_subtests_and_malformed_ids_are_not_normalized(self):
        source = self.source("  " + LINE + "(x=1) ... ERROR\n" +
                             "test_one (not-an-id) ... ok\n")
        self.assertEqual([], source["tests"])
        self.assertEqual(2, source["unparsed_nonempty_lines"])

    def test_missing_id_fragment_is_retained(self):
        source = self.source("test_one\n")
        self.assertIsNone(source["records"][0]["test_id"])
        self.assertEqual("UNFINISHED", source["records"][0]["status"])

    def test_failure_header_does_not_create_a_second_occurrence(self):
        source = self.source(LINE + "FAIL\nFAIL: test_one (" + TEST_ID + ")\n")
        self.assertEqual(1, source["tests"][0]["logged_occurrences"])
        self.assertEqual(1, len(source["diagnostics"]))

    def test_failure_header_conflicting_with_ok_is_unknown(self):
        source = self.source(LINE + "ok\nFAIL: test_one (" + TEST_ID + ")\nOK\n")
        self.assertEqual("UNKNOWN", source["tests"][0]["status"])
        self.assertTrue(any("contradictory" in s for s in source["limitations"]))

    def test_header_without_occurrence_does_not_invent_execution(self):
        source = self.source("ERROR: test_one (" + TEST_ID + ")\n")
        self.assertEqual(0, source["tests"][0]["logged_occurrences"])
        self.assertEqual("UNKNOWN", source["tests"][0]["status"])

    def test_summary_count_mismatch_and_multiple_summaries_are_explicit(self):
        source = self.source(LINE + "ok\nRan 2 tests in 0s\nRan 1 test in 1s\n")
        self.assertEqual(2, len(source["summaries"]))
        self.assertIn("summary count differs from parsed occurrences", source["limitations"])
        self.assertIn("multiple summaries; run boundaries are UNKNOWN", source["limitations"])

    def test_invalid_summary_timings_remain_unknown(self):
        for value in ("-1", "nan", "inf", "1e999", "broken"):
            with self.subTest(value=value):
                source = self.source("Ran 1 test in " + value + "s\n")
                self.assertIsNone(source["summaries"][0]["seconds"])
                json.dumps(source, allow_nan=False)

    def test_no_summary_or_outcome_does_not_imply_completion(self):
        source = self.source(LINE + "ok\n")
        self.assertEqual([], source["summaries"])
        self.assertIn("no parsed run summary; completion is UNKNOWN", source["limitations"])

    def test_result_claims_and_declared_occurrences_are_separate(self):
        path = self.result({"status": "PASS", "passed": True, "elapsed_seconds": 2.5,
                            "tests": [{"id": TEST_ID, "occurrences": 7}]})
        source = diagnostics.build_report(result_paths=[path])["sources"][0]
        self.assertEqual(7, source["records"][0]["declared_occurrences"])
        self.assertEqual(0, source["tests"][0]["logged_occurrences"])
        self.assertEqual("UNKNOWN", source["tests"][0]["status"])
        self.assertEqual(2.5, source["timings"][0]["seconds"])
        self.assertEqual("CLAIMED", source["timings"][0]["basis"])

    def test_result_test_statuses_and_conflicting_ids(self):
        path = self.result({"tests": [{"test_id": TEST_ID, "status": "skipped"},
                                     {"id": TEST_ID, "test_id": "other.C.test_one", "status": "passed"}]})
        source = diagnostics.build_report(result_paths=[path])["sources"][0]
        self.assertEqual("SKIPPED", source["records"][0]["status"])
        self.assertIsNone(source["records"][1]["test_id"])

    def test_occurrence_count_boundaries_reject_bool_zero_and_large_claims(self):
        for count in (True, False, 0, -1, "2", 1.5, 10**400, 1_000_001):
            with self.subTest(count=str(count)[:20]):
                path = self.result({"tests": [{"id": TEST_ID, "occurrences": count}]})
                source = diagnostics.build_report(result_paths=[path])["sources"][0]
                self.assertIsNone(source["records"][0]["declared_occurrences"])
                self.assertTrue(any("invalid occurrence" in s for s in source["limitations"]))
        for count in (1, 1_000_000):
            path = self.result({"tests": [{"id": TEST_ID, "occurrences": count}]})
            self.assertEqual(count, diagnostics.build_report(result_paths=[path])["sources"][0]
                             ["records"][0]["declared_occurrences"])

    def test_invalid_result_timings_do_not_coerce_or_invent_zero(self):
        for value in (True, -1, "1", None, [], {}, 10**400, float("inf")):
            with self.subTest(value=str(value)[:20]):
                path = self.result({"elapsed_seconds": value})
                source = diagnostics.build_report(result_paths=[path])["sources"][0]
                if source["timings"]:
                    self.assertIsNone(source["timings"][0]["seconds"])
                else:
                    self.assertEqual("UNKNOWN", source["parse_state"])

    def test_contradictory_result_claims_are_kept(self):
        path = self.result({"status": "PASS", "passed": False, "exit_code": 1})
        source = diagnostics.build_report(result_paths=[path])["sources"][0]
        self.assertEqual(3, len(source["aggregate_claims"]))
        self.assertTrue(any("contradictory" in s for s in source["limitations"]))

    def test_recorded_command_and_hash_remain_inert_claims(self):
        command = ["python", "payload.py", "$(do-not-run)"]
        declared = "a" * 64
        source = diagnostics.build_report(result_paths=[self.result({
            "command": command, "log_sha256": declared})])["sources"][0]
        self.assertEqual(command, source["inert_claims"][0]["value"])
        self.assertEqual(declared, source["log_hash"]["declared"])
        self.assertEqual("VALID", source["log_hash"]["validity"])
        self.assertEqual("UNKNOWN", source["log_hash"]["association"])
        self.assertTrue(any("unverifiable" in s for s in source["limitations"]))

    def test_original_invalid_timing_claims_are_preserved_separately(self):
        for value in (True, -1, -2.5, "1", None, [], {}, 10**400):
            with self.subTest(value=str(value)[:20]):
                source = diagnostics.build_report(result_paths=[self.result({
                    "elapsed_seconds": value})])["sources"][0]
                timing = source["timings"][0]
                self.assertEqual(value, timing["raw_value"])
                self.assertIsNone(timing["seconds"])
                self.assertEqual("INVALID", timing["validity"])
                json.dumps(source, allow_nan=False)

    def test_overflowed_json_timing_preserves_original_numeric_token(self):
        path = self.log('{"elapsed_seconds":1e999}', "result.json")
        code, report, _ = self.cli("--result", path)
        self.assertEqual(0, code)
        self.assertEqual("1e999", report["sources"][0]["timings"][0]["raw_value"])
        self.assertIsNone(report["sources"][0]["timings"][0]["seconds"])

    def test_timing_validity_boundaries(self):
        for value in (0, 0.0, -0.0, 1.25):
            source = diagnostics.build_report(result_paths=[self.result({
                "elapsed_seconds": value})])["sources"][0]
            self.assertEqual(value, source["timings"][0]["raw_value"])
            self.assertEqual(value, source["timings"][0]["seconds"])
            self.assertEqual("VALID", source["timings"][0]["validity"])

    def test_command_claim_validity_never_discards_original_values(self):
        for command in (None, False, 7, "", [], ["python", 1], {"execute": "payload"}):
            with self.subTest(command=command):
                source = diagnostics.build_report(result_paths=[self.result({
                    "command": command})])["sources"][0]
                self.assertEqual(command, source["inert_claims"][0]["value"])
                self.assertEqual("INVALID", source["inert_claims"][0]["validity"])
        source = diagnostics.build_report(result_paths=[self.result({
            "command": "python payload.py", "runner_command": ["python", "runner.py"]})])["sources"][0]
        self.assertEqual(["VALID", "VALID"], [c["validity"] for c in source["inert_claims"]])

    def test_fail_and_incomplete_are_compatible_claims(self):
        for claims in ({"status": "FAIL", "complete": False},
                       {"passed": False, "stopped": True},
                       {"status": "INCOMPLETE", "passed": False, "exit_code": 1}):
            with self.subTest(claims=claims):
                source = diagnostics.build_report(result_paths=[self.result(claims)])["sources"][0]
                self.assertFalse(any("contradictory" in s for s in source["limitations"]))

    def test_observed_failure_exit_codes_and_error_status_conflict_with_success(self):
        for claims in ({"status": "PASS", "exit_code": 2},
                       {"status": "PASS", "exit_code": -15},
                       {"status": "ERROR", "passed": True}):
            source = diagnostics.build_report(result_paths=[self.result(claims)])["sources"][0]
            self.assertTrue(any("contradictory" in s for s in source["limitations"]))

    def test_unknown_occurrence_is_uncertainty_not_a_failure_claim(self):
        source = self.source(LINE + "unrecognized\nRan 1 test in 0s\nOK\n")
        self.assertFalse(any("contradictory" in s for s in source["limitations"]))
        self.assertEqual("UNKNOWN", source["tests"][0]["status"])

    def test_complete_and_incomplete_claims_conflict_independently_of_failure(self):
        for claims in ({"complete": True, "stopped": True, "passed": False},
                       {"complete": True, "status": "INCOMPLETE"}):
            source = diagnostics.build_report(result_paths=[self.result(claims)])["sources"][0]
            self.assertTrue(any("contradictory" in s for s in source["limitations"]))

    def test_bool_and_string_exit_codes_do_not_invent_failure(self):
        for code in (True, False, "2", 2.0, None):
            source = diagnostics.build_report(result_paths=[self.result({
                "passed": True, "exit_code": code})])["sources"][0]
            self.assertFalse(any("contradictory" in s for s in source["limitations"]))

    def test_declared_test_counts_disagree_without_inventing_execution(self):
        source = diagnostics.build_report(result_paths=[self.result({
            "test_count": 2, "tests_run": 1})])["sources"][0]
        self.assertIn("test_count differs from tests_run; count association is UNKNOWN", source["limitations"])
        self.assertEqual([], source["tests"])

    def test_invalid_counts_are_not_coerced_into_disagreement(self):
        for count in (True, False, -1, 1.0, "1", None, []):
            source = diagnostics.build_report(result_paths=[self.result({
                "test_count": count, "tests_run": 1})])["sources"][0]
            self.assertIn("invalid count claim: test_count", source["limitations"])
            self.assertFalse(any("differs from tests_run" in s for s in source["limitations"]))
        for count in (0, 1, 10**400):
            source = diagnostics.build_report(result_paths=[self.result({
                "test_count": count, "tests_run": count})])["sources"][0]
            self.assertFalse(any("count claim" in s or "differs from tests_run" in s for s in source["limitations"]))

    def test_hash_missing_invalid_and_unverifiable_are_explicit(self):
        source = diagnostics.build_report(result_paths=[self.result({})])["sources"][0]
        self.assertEqual("MISSING", source["log_hash"]["validity"])
        for declared in (None, True, 1, [], {}, "", "a" * 63, "g" * 64):
            with self.subTest(declared=declared):
                source = diagnostics.build_report(result_paths=[self.result({
                    "log_sha256": declared})])["sources"][0]
                self.assertEqual(declared, source["log_hash"]["declared"])
                self.assertEqual("INVALID", source["log_hash"]["validity"])

    def test_hash_comparisons_do_not_invent_result_log_associations(self):
        a = self.log(LINE + "ok\n", "a.log")
        b = self.log(LINE + "FAIL\n", "b.log")
        missing = self.root / "missing.log"
        result = self.result({"log_sha256": hashlib.sha256(a.read_bytes()).hexdigest().upper(),
                              "log": "do-not-open.log"})
        report = diagnostics.build_report([a, b, missing], [result])
        claimed = report["sources"][-1]
        self.assertEqual(["MATCH", "MISMATCH", "UNVERIFIABLE"],
                         [c["relation"] for c in claimed["log_hash"]["comparisons"]])
        self.assertEqual("UNKNOWN", claimed["log_hash"]["association"])
        self.assertEqual({"UNKNOWN"}, set(report["conclusions"].values()))

    def test_hash_comparisons_and_claims_are_deterministic(self):
        log = self.log(LINE + "ok\n", "a.log")
        result = self.result({"command": ["python", "payload"], "elapsed_seconds": -2.5,
                              "log_sha256": "f" * 64})
        before = {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in self.root.iterdir()}
        a = self.cli("--result", result, "--log", log)[2]
        b = self.cli("--log", log, "--result", result)[2]
        self.assertEqual(a, b)
        self.assertEqual(before, {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in self.root.iterdir()})

    def test_unreadable_and_malformed_hash_evidence_never_becomes_verified(self):
        result = self.result({"log_sha256": "a" * 64})
        with mock.patch.object(diagnostics, "MAX_SOURCE_BYTES", 128):
            oversized = self.log("x" * 129)
            source = diagnostics.build_report([oversized], [result])["sources"][-1]
        self.assertEqual("UNVERIFIABLE", source["log_hash"]["comparisons"][0]["relation"])
        malformed = self.log('{"log_sha256":', "malformed.json")
        source = diagnostics.build_report(result_paths=[malformed])["sources"][0]
        self.assertTrue(any("unverifiable" in s for s in source["limitations"]))
        self.assertEqual("UNKNOWN", source["parse_state"])

    def test_trailing_subprocess_output_and_interruption_are_source_specific(self):
        clean = self.log(LINE + "ok\nRan 1 test in 0s\nOK\n", "clean.log")
        tail = self.log(LINE + "ok\nRan 1 test in 0s\nOK\nSubprocess exited with code 1\nKeyboardInterrupt\n", "tail.log")
        report = diagnostics.build_report([tail, clean])
        self.assertEqual([], report["sources"][0]["uncertainties"])
        source = report["sources"][1]
        self.assertEqual([4, 5], [u["line"] for u in source["uncertainties"] if u["kind"] == "TRAILING_OUTPUT"])
        self.assertTrue(any(u["kind"] == "INTERRUPTION" for u in source["uncertainties"]))
        self.assertEqual("KeyboardInterrupt", source["uncertainties"][-1]["value"])
        self.assertEqual(2, source["unparsed_nonempty_lines"])
        self.assertEqual("OK", source["tests"][0]["status"])
        self.assertEqual("UNKNOWN", report["conclusions"]["accepted_result"])

    def test_interruption_before_summary_is_not_lost(self):
        source = self.source(LINE + "\nKeyboardInterrupt\n")
        self.assertTrue(any(u["kind"] == "INTERRUPTION" and u["line"] == 2 for u in source["uncertainties"]))
        self.assertEqual("UNKNOWN", source["tests"][0]["status"])

    def test_trailing_parsed_test_and_signal_markers_are_uncertain(self):
        for marker in ("SIGINT", "SIGTERM", "InterruptedError"):
            source = self.source(LINE + "ok\nRan 1 test in 0s\nOK\n" + LINE + "FAIL\n" + marker + "\n")
            self.assertEqual([4, 5], [u["line"] for u in source["uncertainties"] if u["kind"] == "TRAILING_OUTPUT"])
            self.assertTrue(any(u["kind"] == "INTERRUPTION" for u in source["uncertainties"]))
        source = self.source(LINE + "ok\nRan 1 test in 0s\nOK\n  \n\n")
        self.assertEqual([], source["uncertainties"])

    def test_grouped_summary_preserves_previous_per_id_semantics(self):
        records, headers = [], []
        statuses = ("OK", "FAIL", "ERROR", "SKIPPED", "UNFINISHED", "UNKNOWN",
                    "EXPECTED_FAILURE", "UNEXPECTED_SUCCESS")
        for i in range(80):
            test_id = "m.C.test_" + str(i)
            records.append({"test_id": test_id, "status": statuses[i % len(statuses)],
                            "basis": "LOGGED" if i % 3 else "CLAIMED"})
            if i % 2 == 0:
                records.append({"test_id": test_id, "status": statuses[(i + 1) % len(statuses)],
                                "basis": "LOGGED", "display_name": "wrong" if i % 4 else "test_" + str(i)})
            if i % 5 == 0:
                headers.append({"test_id": test_id, "status": "ERROR"})
        records.append({"test_id": None, "status": "UNFINISHED", "basis": "LOGGED"})
        headers.append({"test_id": "m.C.test_header_only", "status": "FAIL"})
        # Reference is the original scan-per-ID semantics, retained for this repair.
        expected = []
        for test_id in sorted({r["test_id"] for r in records if r["test_id"] is not None} |
                              {r["test_id"] for r in headers}):
            rows = [r for r in records if r["test_id"] == test_id]
            matched_headers = [r for r in headers if r["test_id"] == test_id]
            observed = sorted({r["status"] for r in rows + matched_headers})
            reasons = []
            if len(observed) > 1:
                reasons.append("conflicting or differing observations")
            if any(s in ("UNKNOWN", "UNFINISHED") for s in observed) or not rows:
                reasons.append("missing, unknown or unfinished occurrence evidence")
            if any(r.get("display_name", test_id.rsplit(".", 1)[-1]) != test_id.rsplit(".", 1)[-1] for r in rows):
                reasons.append("display name conflicts with exact test ID")
            expected.append({"test_id": test_id, "observed_records": len(rows),
                             "logged_occurrences": sum(r["basis"] == "LOGGED" for r in rows),
                             "statuses": observed, "status": "UNKNOWN" if reasons else observed[0],
                             "limitations": reasons})
        for ordered in (records, list(reversed(records))):
            source = {"records": ordered, "diagnostics": headers, "aggregate_claims": [], "limitations": []}
            diagnostics._summarize(source)
            self.assertEqual(expected, source["tests"])

    def test_summarize_groups_records_in_bounded_passes(self):
        class CountedList(list):
            iterations = 0

            def __iter__(self):
                self.iterations += 1
                return super().__iter__()

        rows = CountedList({"test_id": "m.C.test_" + str(i), "status": "OK", "basis": "LOGGED"}
                           for i in range(100))
        headers = CountedList()
        source = {"records": rows, "diagnostics": headers, "aggregate_claims": [], "limitations": []}
        diagnostics._summarize(source)
        self.assertEqual(100, len(source["tests"]))
        self.assertLessEqual(rows.iterations, 3)
        self.assertLessEqual(headers.iterations, 3)

    def test_success_and_incomplete_or_stopped_claims_conflict(self):
        for claim in ({"complete": False}, {"stopped": True}):
            path = self.result({"passed": True, **claim})
            source = diagnostics.build_report(result_paths=[path])["sources"][0]
            self.assertTrue(any("contradictory" in s for s in source["limitations"]))

    def test_malformed_duplicate_key_truncated_and_nonobject_json(self):
        for text in ('{"tests": [', '{"status":"PASS","status":"FAIL"}', '[]',
                     '{"seconds":NaN}', '{"seconds":Infinity}', '{"x":' + '[' * 1200):
            with self.subTest(text=text[:50]):
                path = self.log(text, "result.json")
                code, report, _ = self.cli("--result", path)
                self.assertEqual(2, code)
                self.assertEqual("UNKNOWN", report["sources"][0]["parse_state"])
                self.assertEqual([], report["sources"][0]["records"])

    def test_invalid_tests_collection_and_entries_are_limited(self):
        for tests in ({}, None, [1, None, {"id": "not-an-id"}]):
            path = self.result({"tests": tests})
            source = diagnostics.build_report(result_paths=[path])["sources"][0]
            self.assertEqual([], source["tests"])
            self.assertTrue(source["limitations"])

    def test_overlap_is_exact_mentions_including_failures_and_unfinished(self):
        left = self.log(LINE + "FAIL\n", "a.log")
        right = self.log(LINE, "b.log")
        declared = self.result({"tests": [{"id": TEST_ID, "occurrences": 3}]})
        report = diagnostics.build_report([right, left], [declared])
        self.assertEqual(3, len(report["overlap"]))
        for overlap in report["overlap"]:
            self.assertEqual("OBSERVED", overlap["status"])
            self.assertEqual([TEST_ID], overlap["exact_ids"])
            self.assertEqual("UNKNOWN", overlap["uncertain_observations"][0]["status"])
        self.assertEqual("UNKNOWN", report["conclusions"]["coverage"])

    def test_prefix_differences_are_preserved_without_alias_matching(self):
        left = self.log(LINE + "ok\n", "a.log")
        right = self.log(LINE.replace("runtime.tests", "tests") + "ok\n", "b.log")
        report = diagnostics.build_report([left, right])
        self.assertEqual([], report["overlap"][0]["exact_ids"])
        self.assertEqual("tests.example.Case.test_one", report["sources"][1]["tests"][0]["test_id"])

    def test_deterministic_output_ignores_input_order_and_duplicates(self):
        a, b = self.log(LINE + "ok\n", "a.log"), self.log(LINE + "FAIL\n", "b.log")
        self.assertEqual(self.cli("--log", a, "--log", b)[2], self.cli("--log", b, "--log", a)[2])
        report = diagnostics.build_report([a, a])
        self.assertEqual(1, len(report["sources"]))
        self.assertEqual(1, report["sources"][0]["tests"][0]["logged_occurrences"])

    def test_missing_empty_directory_and_invalid_encoding_evidence(self):
        missing = self.root / "missing.log"
        empty = self.log("", "empty.log")
        invalid = self.root / "invalid.log"
        invalid.write_bytes(b"\xffbad")
        for path in (missing, self.root, invalid):
            with self.subTest(path=path.name):
                code, report, _ = self.cli("--log", path)
                self.assertEqual(2, code)
                self.assertEqual("UNKNOWN", report["sources"][0]["parse_state"])
        source = diagnostics.build_report([empty])["sources"][0]
        self.assertEqual(hashlib.sha256(b"").hexdigest(), source["sha256"])
        self.assertEqual([], source["tests"])
        self.assertEqual(hashlib.sha256(b"\xffbad").hexdigest(),
                         diagnostics.build_report([invalid])["sources"][0]["sha256"])

    def test_utf8_bom_utf16_bom_and_crlf_are_supported(self):
        text = LINE + "ok\r\nRan 1 test in 0s\r\nOK\r\n"
        for encoding in ("utf-8-sig", "utf-16"):
            path = self.log(text, encoding=encoding)
            source = diagnostics.build_report([path])["sources"][0]
            self.assertEqual("OK", source["tests"][0]["status"])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), source["sha256"])

    def test_size_boundary_has_no_partial_hash_or_partial_success(self):
        with mock.patch.object(diagnostics, "MAX_SOURCE_BYTES", 8):
            eight = self.log("abcdefgh")
            self.assertIsNotNone(diagnostics.build_report([eight])["sources"][0]["sha256"])
            nine = self.log("abcdefghi")
            source = diagnostics.build_report([nine])["sources"][0]
            self.assertEqual("UNKNOWN", source["parse_state"])
            self.assertIsNone(source["sha256"])
            self.assertEqual([], source["records"])

    def test_changed_read_metadata_is_explicit(self):
        path = self.log(LINE + "ok\n")
        actual = os.stat(path)
        changed = mock.Mock(st_dev=actual.st_dev, st_ino=actual.st_ino,
                            st_size=actual.st_size + 1, st_mtime_ns=actual.st_mtime_ns)
        with mock.patch.object(diagnostics.os, "fstat", side_effect=[actual, changed]):
            source = diagnostics.build_report([path])["sources"][0]
        self.assertTrue(any("changed while reading" in s for s in source["limitations"]))

    def test_usage_errors_and_help_are_json_stdout_only(self):
        for args in ((), ("--log",), ("--output", "report.json"), ("--lo", "x"),
                     ("--discover",), ("tests.log",)):
            with self.subTest(args=args):
                code, report, _ = self.cli(*args)
                self.assertEqual(2, code)
                self.assertTrue(report["errors"])
        self.assertEqual(0, self.cli("--help")[0])

    def test_failed_log_exit_is_reporting_success_only(self):
        path = self.log(LINE + "FAIL\nRan 1 test in 0s\nFAILED (failures=1)\n")
        code, report, _ = self.cli("--log", path)
        self.assertEqual(0, code)
        self.assertEqual("UNKNOWN", report["conclusions"]["accepted_result"])

    def test_untrusted_content_and_references_cannot_write_execute_or_import(self):
        sentinel = self.root / "untouched-report.json"
        sentinel.write_text("existing report")
        malicious = self.log("import os; os.remove('untouched-report.json')\n" + LINE + "ok\n")
        result = self.result({"command": ["python", "payload.py"], "log": str(sentinel),
                              "manifest": str(sentinel), "compatibility": {"status": "AVAILABLE"},
                              "status": "PASS", "tests": [{"id": TEST_ID, "status": "ok"}]})
        before = {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in self.root.iterdir()}
        real_open = os.open
        opened = []

        def readonly(path, flags, *args, **kwargs):
            self.assertFalse(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))
            opened.append(os.fspath(path))
            return real_open(path, flags, *args, **kwargs)

        with ExitStack() as stack:
            stack.enter_context(mock.patch.object(diagnostics.os, "open", side_effect=readonly))
            for name in ("system", "popen", "remove", "unlink", "rename", "replace", "mkdir"):
                stack.enter_context(mock.patch.object(os, name, side_effect=AssertionError(name)))
            for name in ("run", "Popen", "call", "check_call", "check_output"):
                stack.enter_context(mock.patch.object(subprocess, name, side_effect=AssertionError(name)))
            stack.enter_context(mock.patch.object(importlib.util, "spec_from_file_location", side_effect=AssertionError("import")))
            stack.enter_context(mock.patch.object(unittest.TestLoader, "discover", side_effect=AssertionError("discover")))
            stack.enter_context(mock.patch.object(unittest.TextTestRunner, "run", side_effect=AssertionError("execute")))
            stack.enter_context(mock.patch("builtins.open", side_effect=AssertionError("unexpected open")))
            code, report, _ = self.cli("--log", malicious, "--result", result)
        self.assertEqual(0, code)
        self.assertEqual(sorted(map(str, (malicious, result))), sorted(opened))
        self.assertEqual(before, {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in self.root.iterdir()})
        self.assertEqual({"UNKNOWN"}, set(report["conclusions"].values()))

    def test_static_reporter_has_only_allowlisted_imports_and_no_runner_references(self):
        tree = ast.parse(MODULE.read_text(encoding="utf-8"))
        imports = {name.name for node in ast.walk(tree) if isinstance(node, ast.Import) for name in node.names}
        self.assertEqual({"argparse", "hashlib", "json", "math", "os", "re", "stat", "sys"}, imports)
        self.assertFalse(any(isinstance(node, ast.ImportFrom) for node in ast.walk(tree)))
        calls = {node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
        self.assertFalse({"eval", "exec", "compile", "__import__"} & calls)


if __name__ == "__main__":
    unittest.main()

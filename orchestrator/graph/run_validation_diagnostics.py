"""Read explicitly named evidence; emit observations, never validation decisions.

Usage: python -B run_validation_diagnostics.py --log tests.log --result result.json
Only standard-library modules are imported. Evidence references are never opened,
and neither tests nor the validation runner are loaded. Exit 0 means reporting
completed, even for logged failures; exit 2 means an input/usage error. Neither
exit code says anything about acceptance. JSON is the sole output, including
usage errors and --help. Input ordering does not affect the output.
"""

import argparse
import hashlib
import json
import math
import os
import re
import stat
import sys


MAX_SOURCE_BYTES = 16 * 1024 * 1024
MAX_JSON_OCCURRENCES = 1_000_000
ID = r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+"
START = re.compile(r"^(?:python(?:\.exe)? : )?(test\w*)"
                   r"(?: \((" + ID + r")\))?(?: \.\.\.(?: (.*))?)?$")
CONTINUATION = re.compile(r"^\((" + ID + r")\)(?: \.\.\.(?: (.*))?)?$")
SUMMARY = re.compile(r"^Ran (\d+) tests? in (\S+)s$")
DIAGNOSTIC = re.compile(r"^(FAIL|ERROR): test\w* \((" + ID + r")\)$")
TIMING_FIELDS = ("seconds", "duration_seconds", "elapsed_seconds", "execution_seconds",
                 "discovery_seconds", "manifest_generation_seconds",
                 "manifest_reporting_seconds", "worker_reporting_seconds", "reporting_seconds")
LIMITATIONS = [
    "All evidence is untrusted text or JSON; provenance and truth are unverified.",
    "Exact IDs are retained; prefixes, aliases and parameterized IDs are not normalized.",
    "Only simple verbose unittest lines, adjacent wrapped lines, summaries and failure headers are parsed.",
    "Descriptions, subtests, compact progress output and other formats may remain unparsed.",
    "JSON supports top-level result claims and a tests list of objects with id or test_id; declarations are not execution.",
    "Timing is reported as logged or claimed; no per-test timing is inferred.",
    "Declared log hashes are compared only with explicit inputs; byte equality never establishes a run association.",
    "No discovery, evidence-reference traversal, compatibility validation or acceptance is performed.",
]


def _status(value):
    if not isinstance(value, str):
        return "UNKNOWN"
    return {"ok": "OK", "pass": "OK", "passed": "OK", "fail": "FAIL",
            "failed": "FAIL", "failure": "FAIL", "error": "ERROR", "skip": "SKIPPED",
            "skipped": "SKIPPED", "expected failure": "EXPECTED_FAILURE",
            "unexpected success": "UNEXPECTED_SUCCESS", "unfinished": "UNFINISHED",
            "incomplete": "UNFINISHED"}.get(value.lower(), "UNKNOWN")


def _log_status(value):
    if value is None or value == "":
        return "UNFINISHED"
    if re.fullmatch(r"skipped (?:'[^\r\n]*'|\"[^\r\n]*\")", value):
        return "SKIPPED"
    # Deliberately narrower than result claims: arbitrary suffixes are unknown.
    if value in ("ok", "FAIL", "ERROR", "expected failure", "unexpected success"):
        return _status(value)
    return "UNKNOWN"


def _timing(value):
    if type(value) not in (int, float):
        return None
    try:
        return value if value >= 0 and math.isfinite(value) else None
    except OverflowError:
        return None


def _parse_log(text, source):
    records, summaries, diagnostics = [], [], []
    pending = None
    pending_marker = False
    ignored = 0
    lines = text.splitlines()
    last_run_marker = None
    for number, line in enumerate(lines, 1):
        # Whitespace inside IDs or nonadjacent fragments is never reconstructed.
        line = line.rstrip()
        start = START.fullmatch(line)
        continuation = CONTINUATION.fullmatch(line) if pending is not None else None
        terminal = line.startswith("... ") or line == "..."
        if pending is not None and continuation and pending["test_id"] is None:
            pending["test_id"] = continuation[1]
            pending["end_line"] = number
            pending["raw_status"] = continuation[2]
            pending["status"] = _log_status(continuation[2])
            pending_marker = "..." in line
            if continuation[2] is not None:
                pending = None
            continue
        bare_status = pending_marker and _log_status(line) not in ("UNKNOWN", "UNFINISHED")
        if pending is not None and (terminal or bare_status):
            pending["end_line"] = number
            pending["raw_status"] = line[4:] if line.startswith("... ") else None if line == "..." else line
            pending["status"] = _log_status(pending["raw_status"])
            pending = None
            continue
        pending = None
        pending_marker = False
        if start:
            record = {"test_id": start[2], "display_name": start[1], "line": number,
                      "end_line": number, "status": _log_status(start[3]),
                      "raw_status": start[3], "basis": "LOGGED", "declared_occurrences": None}
            records.append(record)
            if start[3] is None:
                pending = record
                pending_marker = "..." in line
            if start[2] is None:
                source["limitations"].append("test ID fragment at line " + str(number))
            continue
        summary = SUMMARY.fullmatch(line)
        diagnostic = DIAGNOSTIC.fullmatch(line)
        if summary:
            last_run_marker = number
            try:
                seconds = _timing(float(summary[2]))
                count = int(summary[1])
            except (ValueError, OverflowError):
                seconds, count = None, None
            summaries.append({"line": number, "test_count": count,
                              "seconds": seconds, "raw_seconds": summary[2],
                              "validity": "VALID" if seconds is not None and count is not None else "INVALID"})
            if seconds is None or count is None:
                source["limitations"].append("invalid summary at line " + str(number))
        elif diagnostic:
            diagnostics.append({"line": number, "status": diagnostic[1], "test_id": diagnostic[2]})
        elif line == "OK" or line.startswith("OK (") or line.startswith("FAILED"):
            last_run_marker = number
            source["aggregate_claims"].append({"line": number, "value": line})
        elif line:
            ignored += 1
    for number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        if last_run_marker is not None and number > last_run_marker:
            source["uncertainties"].append({"kind": "TRAILING_OUTPUT", "line": number, "value": line})
        if re.search(r"\b(?:KeyboardInterrupt|InterruptedError|SIGINT|SIGTERM)\b", line):
            source["uncertainties"].append({"kind": "INTERRUPTION", "line": number, "value": line})
    if any(item["kind"] == "TRAILING_OUTPUT" for item in source["uncertainties"]):
        source["limitations"].append("trailing subprocess output after final summary/outcome; completion is UNKNOWN")
    if any(item["kind"] == "INTERRUPTION" for item in source["uncertainties"]):
        source["limitations"].append("interruption marker observed in this source; completion is UNKNOWN")
    source.update(records=records, summaries=summaries, diagnostics=diagnostics,
                  unparsed_nonempty_lines=ignored)
    if not summaries:
        source["limitations"].append("no parsed run summary; completion is UNKNOWN")
    if not source["aggregate_claims"]:
        source["limitations"].append("no aggregate outcome claim; outcome is UNKNOWN")
    if len(summaries) > 1:
        source["limitations"].append("multiple summaries; run boundaries are UNKNOWN")
    if any(item["test_count"] != len(records) for item in summaries):
        source["limitations"].append("summary count differs from parsed occurrences")
    if not text.endswith(("\n", "\r")) and text:
        source["limitations"].append("no final newline; truncation is possible")


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError("nonfinite JSON number")


def _json_float(token):
    # Preserve overflowing JSON numbers as inert spelling, never emit Infinity.
    value = float(token)
    return value if math.isfinite(value) else token


def _parse_result(text, source):
    try:
        value = json.loads(text, object_pairs_hook=_unique_object, parse_constant=_reject_constant,
                           parse_float=_json_float)
    except (ValueError, RecursionError):
        source["limitations"].append("malformed, truncated, duplicate-key or nonfinite JSON")
        source["parse_state"] = "UNKNOWN"
        return
    if not isinstance(value, dict):
        source["limitations"].append("result must be a JSON object")
        source["parse_state"] = "UNKNOWN"
        return
    # Preserve recorded commands verbatim, without importing or executing them.
    for key in ("command", "runner_command"):
        if key in value:
            command = value[key]
            valid = ((isinstance(command, str) and bool(command)) or
                     (isinstance(command, list) and bool(command) and
                      all(isinstance(item, str) and bool(item) for item in command)))
            source["inert_claims"].append({"field": key, "value": command, "basis": "CLAIMED",
                                         "validity": "VALID" if valid else "INVALID"})
            if not valid:
                source["limitations"].append("invalid command claim: " + key)
    declared = value.get("log_sha256")
    validity = ("MISSING" if "log_sha256" not in value else "VALID" if
                isinstance(declared, str) and re.fullmatch(r"[0-9a-fA-F]{64}", declared) else "INVALID")
    source["log_hash"] = {"declared": declared, "basis": "CLAIMED", "validity": validity,
                          "association": "UNKNOWN", "comparisons": []}
    if validity != "VALID":
        source["limitations"].append("declared log SHA-256 is " + validity.lower())
    # Other aggregate claims retain the existing scalar-only format.
    for key in ("status", "passed", "complete", "stopped", "exit_code", "test_count", "tests_run"):
        if key in value:
            item = value[key]
            scalar = item is None or type(item) in (str, bool, int, float)
            finite = type(item) is not float or math.isfinite(item)
            source["aggregate_claims"].append({"field": key, "value": item if scalar and finite else None})
            if not scalar or not finite:
                source["limitations"].append("invalid aggregate claim: " + key)
    counts = {}
    for key in ("test_count", "tests_run"):
        if key in value:
            if type(value[key]) is int and value[key] >= 0:
                counts[key] = value[key]
            else:
                source["limitations"].append("invalid count claim: " + key)
    if len(counts) == 2 and counts["test_count"] != counts["tests_run"]:
        source["limitations"].append("test_count differs from tests_run; count association is UNKNOWN")
    for key in TIMING_FIELDS:
        if key in value:
            seconds = _timing(value[key])
            source["timings"].append({"field": key, "seconds": seconds, "raw_value": value[key],
                                      "validity": "VALID" if seconds is not None else "INVALID", "basis": "CLAIMED"})
            if seconds is None:
                source["limitations"].append("invalid timing: " + key)
    tests = value.get("tests", [])
    if not isinstance(tests, list):
        source["limitations"].append("tests is not a list")
        return
    for index, entry in enumerate(tests):
        if not isinstance(entry, dict):
            source["limitations"].append("invalid test entry at index " + str(index))
            continue
        test_id = entry.get("id", entry.get("test_id"))
        if (not isinstance(test_id, str) or re.fullmatch(ID, test_id) is None or
                ("id" in entry and "test_id" in entry and entry["id"] != entry["test_id"])):
            test_id = None
            source["limitations"].append("invalid or conflicting test ID at index " + str(index))
        count = entry.get("occurrences")
        if count is not None and (type(count) is not int or not 1 <= count <= MAX_JSON_OCCURRENCES):
            count = None
            source["limitations"].append("invalid occurrence claim at index " + str(index))
        raw = entry.get("status")
        source["records"].append({"test_id": test_id, "index": index, "basis": "CLAIMED",
                                  "status": _status(raw), "raw_status": raw if isinstance(raw, str) else None,
                                  "declared_occurrences": count})
    source["limitations"].append("result claims are unverified; declared counts are not logged occurrences")


def _summarize(source):
    tests = []
    rows_by_id, headers_by_id = {}, {}
    for record in source["records"]:
        if record["test_id"] is not None:
            rows_by_id.setdefault(record["test_id"], []).append(record)
    for header in source["diagnostics"]:
        headers_by_id.setdefault(header["test_id"], []).append(header)
    ids = sorted(rows_by_id.keys() | headers_by_id.keys())
    for test_id in ids:
        rows = rows_by_id.get(test_id, [])
        headers = headers_by_id.get(test_id, [])
        statuses = sorted({r["status"] for r in rows + headers})
        reasons = []
        if len(statuses) > 1:
            reasons.append("conflicting or differing observations")
        if any(status in ("UNKNOWN", "UNFINISHED") for status in statuses) or not rows:
            reasons.append("missing, unknown or unfinished occurrence evidence")
        if any(r.get("display_name", test_id.rsplit(".", 1)[-1]) != test_id.rsplit(".", 1)[-1] for r in rows):
            reasons.append("display name conflicts with exact test ID")
        tests.append({"test_id": test_id, "observed_records": len(rows),
                      "logged_occurrences": sum(r["basis"] == "LOGGED" for r in rows),
                      "statuses": statuses, "status": "UNKNOWN" if reasons else statuses[0],
                      "limitations": reasons})
    source["tests"] = tests
    if not ids:
        source["limitations"].append("no exact test IDs parsed")
    # Outcomes remain claims; expose contradictions instead of selecting a winner.
    claims = source["aggregate_claims"]
    outcomes = set()
    completion = set()
    for claim in claims:
        value, field = claim.get("value"), claim.get("field")
        if field == "passed" and type(value) is bool:
            outcomes.add("OK" if value else "FAIL")
        elif field == "exit_code" and type(value) is int:
            outcomes.add("OK" if value == 0 else "FAIL")
        elif field == "complete" and type(value) is bool:
            completion.add("COMPLETE" if value else "UNFINISHED")
        elif field == "stopped" and value is True:
            completion.add("UNFINISHED")
        elif field in (None, "status") and isinstance(value, str):
            status = "OK" if value.startswith("OK") else "FAIL" if value.startswith("FAILED") else _status(value)
            if status in ("OK", "FAIL", "ERROR", "UNEXPECTED_SUCCESS"):
                outcomes.add("OK" if status == "OK" else "FAIL")
            elif status == "UNFINISHED":
                completion.add("UNFINISHED")
    if (len(outcomes) > 1 or len(completion) > 1 or
            ("OK" in outcomes and ("UNFINISHED" in completion or any(
                r["status"] in ("FAIL", "ERROR", "UNEXPECTED_SUCCESS", "UNFINISHED")
                for r in source["records"] + source["diagnostics"])))):
        source["limitations"].append("contradictory aggregate and/or occurrence evidence; outcome is UNKNOWN")
    if "OK" in outcomes and any(r["status"] == "UNKNOWN" for r in source["records"]):
        source["limitations"].append("aggregate success with unknown occurrence evidence; outcome is UNKNOWN")
    source["limitations"] = sorted(set(source["limitations"]))


def _read_source(kind, path):
    source = {"kind": kind, "path": path, "sha256": None, "byte_count": None,
              "parse_state": "OBSERVED", "encoding": None, "limitations": [],
              "records": [], "summaries": [], "diagnostics": [], "timings": [],
              "aggregate_claims": [], "inert_claims": [], "uncertainties": [], "unparsed_nonempty_lines": 0}
    try:
        before = os.stat(path, follow_symlinks=False)
        if not stat.S_ISREG(before.st_mode):
            raise ValueError("only regular files are supported (no links or special files)")
        # Nonblocking avoids a substituted FIFO; fstat checks the opened object too.
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NONBLOCK", 0)
        descriptor = os.open(path, flags)
        with os.fdopen(descriptor, "rb") as stream:
            opened = os.fstat(stream.fileno())
            if not stat.S_ISREG(opened.st_mode):
                raise ValueError("opened source is not a regular file")
            data = stream.read(MAX_SOURCE_BYTES + 1)
            after = os.fstat(stream.fileno())
        if len(data) > MAX_SOURCE_BYTES:
            raise ValueError("source exceeds 16 MiB; full source hash is UNKNOWN")
        source["byte_count"] = len(data)
        source["sha256"] = hashlib.sha256(data).hexdigest()
        identity = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns)
        if identity(before) != identity(opened) or identity(opened) != identity(after):
            source["limitations"].append("source changed while reading; hash identifies read bytes only")
        encoding = "utf-16" if data.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig"
        source["encoding"] = encoding
        text = data.decode(encoding, errors="strict")
        if kind == "log":
            _parse_log(text, source)
        else:
            _parse_result(text, source)
    except (OSError, ValueError) as exc:
        source["parse_state"] = "UNKNOWN"
        # Stable category, without host-specific exception prose or source content.
        source["limitations"].append("source read/decode error: " + type(exc).__name__)
        if isinstance(exc, ValueError) and not isinstance(exc, UnicodeError):
            source["limitations"].append(str(exc))
    _summarize(source)
    return source


def _compare_log_hashes(sources):
    # Compare bytes of every explicit log, never select an associated run/log.
    logs = [(index, source) for index, source in enumerate(sources) if source["kind"] == "log"]
    for source in sources:
        if source["kind"] != "result":
            continue
        claim = source.get("log_hash")
        if claim is None:
            source["limitations"].append("declared log SHA-256 is unverifiable; result claims could not be parsed")
        else:
            for index, log in logs:
                relation = "UNVERIFIABLE"
                if claim["validity"] == "VALID" and log["sha256"] is not None:
                    relation = "MATCH" if claim["declared"].lower() == log["sha256"] else "MISMATCH"
                claim["comparisons"].append({"log_source": index, "observed_sha256": log["sha256"],
                                              "relation": relation, "association": "UNKNOWN"})
            if not logs or any(item["relation"] == "UNVERIFIABLE" for item in claim["comparisons"]):
                source["limitations"].append("declared log SHA-256 is unverifiable against one or more explicit inputs")
            if any(item["relation"] == "MISMATCH" for item in claim["comparisons"]):
                source["limitations"].append("declared log SHA-256 mismatches explicit input bytes; association is UNKNOWN")
        source["limitations"] = sorted(set(source["limitations"]))


def build_report(log_paths=(), result_paths=()):
    """Read these paths only; return a deterministic, non-authoritative report."""
    inputs = [("log", os.fspath(p)) for p in log_paths] + [("result", os.fspath(p)) for p in result_paths]
    report = {"schema_version": 1, "status": "OBSERVED", "sources": [], "overlap": [],
              "limitations": list(LIMITATIONS),
              "conclusions": {key: "UNKNOWN" for key in
                              ("accepted_result", "compatible_availability", "coverage",
                               "execution_reuse", "test_skipping", "measured_speedup")}}
    if not inputs:
        report["errors"] = ["at least one explicit --log or --result path is required"]
    if len(set(inputs)) != len(inputs):
        report["limitations"].append("duplicate identical input arguments are read once")
    report["sources"] = [_read_source(kind, path) for kind, path in sorted(set(inputs))]
    sources = report["sources"]
    _compare_log_hashes(sources)
    for left in range(len(sources)):
        for right in range(left + 1, len(sources)):
            common = sorted({r["test_id"] for r in sources[left]["tests"]} &
                            {r["test_id"] for r in sources[right]["tests"]})
            conflicts = []
            for test_id in common:
                a = next(r for r in sources[left]["tests"] if r["test_id"] == test_id)
                b = next(r for r in sources[right]["tests"] if r["test_id"] == test_id)
                if a["statuses"] != b["statuses"] or "UNKNOWN" in (a["status"], b["status"]):
                    conflicts.append({"test_id": test_id, "status": "UNKNOWN",
                                      "left_statuses": a["statuses"], "right_statuses": b["statuses"],
                                      "reason": "differing or incomplete evidence; run association is unverified"})
            report["overlap"].append({"left_source": left, "right_source": right,
                                      "status": "OBSERVED", "exact_ids": common,
                                      "uncertain_observations": conflicts,
                                      "meaning": "exact ID mentions only; coverage is UNKNOWN"})
    return report


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError(message)


def main(argv=None):
    parser = _Parser(add_help=False, allow_abbrev=False)
    parser.add_argument("--log", action="append", default=[])
    parser.add_argument("--result", action="append", default=[])
    parser.add_argument("--help", action="store_true")
    try:
        args = parser.parse_args(argv)
        if args.help:
            report = {"usage": "--log PATH [--log PATH ...] --result PATH [--result PATH ...]",
                      "minimum": "one explicit path", "limitations": LIMITATIONS}
        else:
            report = build_report(args.log, args.result)
        code = 2 if report.get("errors") or any(s["parse_state"] == "UNKNOWN" for s in report.get("sources", [])) else 0
    except ValueError as exc:
        report, code = {"schema_version": 1, "status": "UNKNOWN", "errors": [str(exc)]}, 2
    print(json.dumps(report, sort_keys=True, ensure_ascii=True, allow_nan=False, separators=(",", ":")))
    return code


if __name__ == "__main__":
    sys.exit(main())

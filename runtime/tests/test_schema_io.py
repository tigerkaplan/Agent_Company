import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from runtime.core.validation import (
    D_MAX,
    SCHEMA_MAX_BYTES,
    W_MAX,
    JobValidationError,
    JobValidator,
    SchemaIntegrityError,
)


class SchemaIOTests(unittest.TestCase):
    def _write(self, root: Path, name: str, raw: bytes) -> Path:
        path = root / name
        path.write_bytes(raw)
        return path

    class _RecordingReader(io.BytesIO):
        def __init__(self, raw: bytes, maximum_chunk: int | None = None):
            super().__init__(raw)
            self.maximum_chunk = maximum_chunk
            self.requests: list[int] = []

        def fileno(self) -> int:
            return 101

        def read(self, size: int = -1) -> bytes:
            self.requests.append(size)
            if self.maximum_chunk is not None:
                size = min(size, self.maximum_chunk)
            return super().read(size)

    def test_initial_schema_boundary_and_raw_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prefix = b'{"type":"object","padding":"'
            suffix = b'"}'
            raw = prefix + (b"x" * (SCHEMA_MAX_BYTES - len(prefix) - len(suffix))) + suffix
            path = self._write(root, "schema.json", raw)
            reader = self._RecordingReader(raw)
            with patch.object(Path, "open", return_value=reader):
                with patch(
                    "runtime.core.validation.os.fstat",
                    return_value=SimpleNamespace(st_size=SCHEMA_MAX_BYTES),
                ):
                    validator = JobValidator(path)

            self.assertEqual(reader.requests, [SCHEMA_MAX_BYTES])
            self.assertEqual(validator.schema_raw_bytes, raw)
            self.assertEqual(validator.schema_sha256, hashlib.sha256(raw).hexdigest())
            validator.validate({})

    def test_initial_schema_over_boundary_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self._write(
                Path(directory), "schema.json", b" " * (SCHEMA_MAX_BYTES + 1)
            )
            reader = self._RecordingReader(b" " * (SCHEMA_MAX_BYTES + 1))
            with patch.object(Path, "open", return_value=reader):
                with patch(
                    "runtime.core.validation.os.fstat",
                    return_value=SimpleNamespace(st_size=SCHEMA_MAX_BYTES + 1),
                ):
                    with self.assertRaisesRegex(SchemaIntegrityError, "exceeds 131072"):
                        JobValidator(path)
            self.assertEqual(reader.requests, [])

    def test_short_reads_never_request_more_than_remaining_extent(self):
        with tempfile.TemporaryDirectory() as directory:
            raw = b'{"type":"object"}'
            path = self._write(Path(directory), "schema.json", raw)
            reader = self._RecordingReader(raw, maximum_chunk=3)
            with patch.object(Path, "open", return_value=reader):
                with patch(
                    "runtime.core.validation.os.fstat",
                    return_value=SimpleNamespace(st_size=len(raw)),
                ):
                    validator = JobValidator(path)

            self.assertEqual(reader.requests, [17, 14, 11, 8, 5, 2])
            self.assertTrue(all(0 < size <= SCHEMA_MAX_BYTES for size in reader.requests))
            self.assertEqual(validator.schema_raw_bytes, raw)

    def test_growth_during_acquisition_fails_closed_without_eof_probe(self):
        with tempfile.TemporaryDirectory() as directory:
            raw = b'{"type":"object"}'
            path = self._write(Path(directory), "schema.json", raw)
            reader = self._RecordingReader(raw)
            extents = [
                SimpleNamespace(st_size=len(raw)),
                SimpleNamespace(st_size=len(raw) + 1),
            ]
            with patch.object(Path, "open", return_value=reader):
                with patch("runtime.core.validation.os.fstat", side_effect=extents):
                    with self.assertRaisesRegex(SchemaIntegrityError, "changed"):
                        JobValidator(path)

            self.assertEqual(reader.requests, [len(raw)])

    def test_external_schema_is_bounded_and_cached_per_operation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            main = self._write(
                root,
                "main.json",
                json.dumps(
                    {
                        "allOf": [
                            {"$ref": "external.json"},
                            {"$ref": "external.json"},
                        ]
                    }
                ).encode(),
            )
            external = self._write(root, "external.json", b'{"type":"object"}')
            validator = JobValidator(main)
            original = Path.open
            reads = 0

            def counted_open(path, *args, **kwargs):
                nonlocal reads
                if Path(path) == external and args and args[0] == "rb":
                    reads += 1
                return original(path, *args, **kwargs)

            with patch.object(Path, "open", counted_open):
                validator.validate({})
            self.assertEqual(reads, 1)

            external.write_bytes(b" " * (SCHEMA_MAX_BYTES + 1))
            with self.assertRaisesRegex(SchemaIntegrityError, "exceeds 131072"):
                validator.validate({})

    def test_legitimate_recursive_schema_advances_through_instance(self):
        with tempfile.TemporaryDirectory() as directory:
            schema = {
                "type": "object",
                "properties": {"child": {"$ref": "#"}},
                "additionalProperties": False,
            }
            path = self._write(Path(directory), "schema.json", json.dumps(schema).encode())
            JobValidator(path).validate({"child": {"child": {}}})

    def test_non_progressing_recursive_schema_is_sticky(self):
        with tempfile.TemporaryDirectory() as directory:
            schema = {"anyOf": [{"allOf": [{"$ref": "#"}]}, {"type": "object"}]}
            path = self._write(Path(directory), "schema.json", json.dumps(schema).encode())
            with self.assertRaisesRegex(SchemaIntegrityError, "non-progressing"):
                JobValidator(path).validate({})

    def test_direct_self_reference_is_non_progressing(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self._write(Path(directory), "schema.json", b'{"$ref":"#"}')
            with self.assertRaisesRegex(SchemaIntegrityError, "non-progressing"):
                JobValidator(path).validate({})

    def test_depth_limit_is_enforced_before_descending(self):
        with tempfile.TemporaryDirectory() as directory:
            schema = {
                "type": "object",
                "properties": {"child": {"$ref": "#"}},
            }
            path = self._write(Path(directory), "schema.json", json.dumps(schema).encode())
            with patch("runtime.core.validation.D_MAX", 3):
                with self.assertRaisesRegex(SchemaIntegrityError, "D_MAX=3"):
                    JobValidator(path).validate({"child": {"child": {"child": {}}}})

    def test_work_limit_is_sticky_across_branches(self):
        with tempfile.TemporaryDirectory() as directory:
            schema = {"anyOf": [{"type": "string"}, {"type": "object"}]}
            path = self._write(Path(directory), "schema.json", json.dumps(schema).encode())
            with patch("runtime.core.validation.W_MAX", 3):
                with self.assertRaisesRegex(SchemaIntegrityError, "W_MAX=3"):
                    JobValidator(path).validate({})

    def test_published_limits_match_contract(self):
        self.assertEqual(W_MAX, 16_777_216)
        self.assertEqual(D_MAX, 128)

    def test_malformed_utf8_remains_a_validation_error(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self._write(Path(directory), "schema.json", b"\xff")
            with self.assertRaises(JobValidationError):
                JobValidator(path)


if __name__ == "__main__":
    unittest.main()

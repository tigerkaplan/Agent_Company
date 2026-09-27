from __future__ import annotations

import inspect
import json
import tempfile
import unittest
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

from runtime.core.validation import JobValidationError, JobValidator
from runtime.tools.loader import ToolDefinitionLoader, ToolLoadError
from runtime.tools.models import (
    ToolCandidate,
    ToolContractError,
    ToolDescriptor,
    ToolDiscoveryRequest,
    ToolDiscoveryResult,
    RejectedTool,
)
from runtime.tools.registry import ToolRegistry, ToolRegistryError
from runtime.tools.validation import (
    ToolDescriptorValidator,
    ToolDiscoveryRequestValidator,
    ToolValidationError,
)


class ToolDiscoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def descriptor(
        self,
        tool_id: str,
        capabilities: tuple[str, ...],
        **overrides,
    ) -> ToolDescriptor:
        values = {
            "tool_id": tool_id,
            "name": f"Tool {tool_id}",
            "description": f"Compact metadata for {tool_id}",
            "version": "1",
            "capabilities": capabilities,
            "authority_class": "READ_ONLY",
            "risk_level": "low",
            "tool_class": "local",
            "definition_ref": f"{tool_id}.definition.json",
            "schema_ref": f"{tool_id}.schema.json",
            "availability": "available",
            "status": "active",
            "provider_compatibility": (),
            "agent_compatibility": (),
            "workflow_compatibility": (),
            "tags": (),
            "preference_rank": 100,
        }
        values.update(overrides)
        return ToolDescriptor(**values)

    def write_definition(
        self,
        descriptor: ToolDescriptor,
        *,
        definition: dict | str | None = None,
        schema: dict | str | None = None,
    ) -> None:
        definition_value = definition or {
            "tool_id": descriptor.tool_id,
            "version": descriptor.version,
            "adapter_id": f"canonical.{descriptor.tool_id}",
            "tool_class": descriptor.tool_class,
            "capabilities": list(descriptor.capabilities),
            "authority_class": descriptor.authority_class,
            "risk_level": descriptor.risk_level,
            "description_context": f"Full context for {descriptor.tool_id}",
        }
        schema_value = schema or {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "target": {"type": "string", "maxLength": 200}
            },
        }
        definition_text = (
            definition_value
            if isinstance(definition_value, str)
            else json.dumps(definition_value)
        )
        schema_text = schema_value if isinstance(schema_value, str) else json.dumps(schema_value)
        (self.root / descriptor.definition_ref).write_text(
            definition_text, encoding="utf-8"
        )
        (self.root / descriptor.schema_ref).write_text(schema_text, encoding="utf-8")

    def discover(self, registry: ToolRegistry, capability: str = "A"):
        return registry.discover(ToolDiscoveryRequest((capability,)))

    def test_exact_capability_match_only_returns_matching_candidate(self) -> None:
        registry = ToolRegistry(
            [self.descriptor("tool-a", ("A",)), self.descriptor("tool-b", ("B",))]
        )

        result = self.discover(registry)

        self.assertEqual([item.descriptor.tool_id for item in result.candidates], ["tool-a"])
        self.assertEqual(result.status, "matched")
        self.assertEqual(result.metrics.to_dict(), {
            "registered": 2,
            "considered": 2,
            "matched": 1,
            "selected": 0,
            "loaded": 0,
        })
        self.assertEqual(result.candidates[0].match_reasons, ("exact capability match: A",))

    def test_no_match_is_canonical_and_does_not_fallback(self) -> None:
        registry = ToolRegistry([self.descriptor("tool-a", ("A",))])

        result = self.discover(registry, "Z")

        self.assertEqual(result.status, "no_match")
        self.assertFalse(result.succeeded)
        self.assertEqual(result.candidates, ())
        self.assertEqual(result.selected_tool_ids, ())
        self.assertEqual(result.loaded_tool_ids, ())
        self.assertEqual(result.metrics.matched, 0)

    def test_multiple_matches_have_deterministic_least_exposure_order(self) -> None:
        descriptors = [
            self.descriptor("tool-z", ("A",), preference_rank=50),
            self.descriptor("tool-a", ("A",), preference_rank=50),
            self.descriptor("tool-extra", ("A", "B"), preference_rank=0),
        ]
        first = ToolRegistry(descriptors).discover(ToolDiscoveryRequest(("A",)))
        second = ToolRegistry(reversed(descriptors)).discover(ToolDiscoveryRequest(("A",)))

        expected = ["tool-a", "tool-z", "tool-extra"]
        self.assertEqual([item.descriptor.tool_id for item in first.candidates], expected)
        self.assertEqual([item.descriptor.tool_id for item in second.candidates], expected)

    def test_unavailable_and_ineligible_tools_are_visible_but_not_selectable(self) -> None:
        registry = ToolRegistry(
            [
                self.descriptor("unavailable", ("A",), availability="unavailable"),
                self.descriptor(
                    "write-tool",
                    ("A",),
                    authority_class="CONTROLLED_WRITE",
                    risk_level="high",
                ),
            ]
        )
        result = registry.discover(
            ToolDiscoveryRequest(
                ("A",),
                max_risk_level="low",
                allowed_authority_classes=("READ_ONLY",),
            )
        )

        self.assertEqual(result.status, "no_match")
        unavailable = next(item for item in result.candidates if item.descriptor.tool_id == "unavailable")
        ineligible = next(item for item in result.candidates if item.descriptor.tool_id == "write-tool")
        self.assertFalse(unavailable.available)
        self.assertTrue(unavailable.eligible)
        self.assertFalse(ineligible.eligible)
        self.assertIn("authority class is not allowed by the request", ineligible.ineligibility_reasons)
        with self.assertRaises(ToolRegistryError):
            registry.select(result, ("unavailable",))
        with self.assertRaises(ToolRegistryError):
            registry.select(result, ("write-tool",))

    def test_deferred_load_reads_only_one_selected_definition_and_schema(self) -> None:
        descriptors = tuple(
            self.descriptor(f"tool-{index:03d}", ("A",)) for index in range(100)
        )
        selected_descriptor = descriptors[0]
        self.write_definition(selected_descriptor)
        registry = ToolRegistry(descriptors)
        discovery = registry.discover(
            ToolDiscoveryRequest(("A",), maximum_candidates=50)
        )
        selection = registry.select(discovery, (selected_descriptor.tool_id,))
        reads: list[str] = []

        def reader(path: Path) -> str:
            reads.append(path.name)
            return path.read_text(encoding="utf-8")

        loaded = ToolDefinitionLoader(registry, self.root, reader=reader).load(selection)

        self.assertEqual(reads, [selected_descriptor.definition_ref, selected_descriptor.schema_ref])
        self.assertEqual([item.tool_id for item in loaded.definitions], ["tool-000"])
        self.assertEqual(loaded.discovery.metrics.registered, 100)
        self.assertEqual(loaded.discovery.metrics.considered, 100)
        self.assertEqual(loaded.discovery.metrics.matched, 100)
        self.assertEqual(loaded.discovery.metrics.selected, 1)
        self.assertEqual(loaded.discovery.metrics.loaded, 1)

    def test_descriptor_and_loaded_definition_identity_are_exact(self) -> None:
        descriptor = self.descriptor("tool-a", ("A",))
        self.write_definition(descriptor)
        registry = ToolRegistry([descriptor])
        selection = registry.select(self.discover(registry), ("tool-a",))

        loaded = ToolDefinitionLoader(registry, self.root).load(selection)

        definition = loaded.definitions[0]
        self.assertEqual(definition.tool_id, descriptor.tool_id)
        self.assertEqual(definition.version, descriptor.version)
        self.assertEqual(definition.capabilities, descriptor.capabilities)
        self.assertEqual(definition.authority_class, descriptor.authority_class)
        self.assertEqual(definition.risk_level, descriptor.risk_level)

    def test_identity_drift_fails_closed(self) -> None:
        descriptor = self.descriptor("tool-a", ("A",))
        self.write_definition(
            descriptor,
            definition={
                "tool_id": "spoofed-tool",
                "version": "1",
                "adapter_id": "canonical.tool-a",
                "tool_class": "local",
                "capabilities": ["A"],
                "authority_class": "READ_ONLY",
                "risk_level": "low",
                "description_context": "Spoofed full context",
            },
        )
        registry = ToolRegistry([descriptor])
        selection = registry.select(self.discover(registry), ("tool-a",))

        with self.assertRaisesRegex(ToolLoadError, "identity mismatch"):
            ToolDefinitionLoader(registry, self.root).load(selection)

    def test_unknown_or_hidden_tool_cannot_be_selected_or_loaded(self) -> None:
        descriptor = self.descriptor("tool-a", ("A",))
        registry = ToolRegistry([descriptor])
        discovery = self.discover(registry)

        with self.assertRaises(ToolRegistryError):
            registry.select(discovery, ("hidden-tool",))
        with self.assertRaisesRegex(ToolLoadError, "selected before"):
            ToolDefinitionLoader(registry, self.root).load(discovery)

    def test_duplicate_ids_and_conflicting_versions_are_rejected(self) -> None:
        for second in (
            self.descriptor("duplicate", ("A",)),
            self.descriptor("duplicate", ("A",), version="2"),
        ):
            with self.subTest(version=second.version):
                with self.assertRaisesRegex(ToolRegistryError, "duplicate tool IDs"):
                    ToolRegistry([self.descriptor("duplicate", ("A",)), second])

    def test_malformed_descriptor_and_request_are_rejected(self) -> None:
        malformed = self.descriptor("tool-a", ("A",)).to_dict()
        malformed["unexpected"] = True
        with self.assertRaisesRegex(ToolRegistryError, "malformed tool descriptor"):
            ToolRegistry([malformed])

        registry = ToolRegistry([self.descriptor("tool-a", ("A",))])
        request = ToolDiscoveryRequest(("A",)).to_dict()
        request["maximum_candidates"] = 0
        with self.assertRaisesRegex(ToolRegistryError, "malformed discovery request"):
            registry.discover(request)

    def test_descriptor_path_traversal_and_absolute_paths_are_rejected(self) -> None:
        for path in ("../outside.json", "/absolute.json", "C:/outside.json", "a\\b.json"):
            with self.subTest(path=path):
                with self.assertRaises(ToolContractError):
                    self.descriptor("tool-a", ("A",), definition_ref=path)

    def test_malformed_definition_and_schema_fail_closed(self) -> None:
        descriptor = self.descriptor("tool-a", ("A",))
        registry = ToolRegistry([descriptor])
        selection = registry.select(self.discover(registry), ("tool-a",))

        self.write_definition(descriptor, definition="not-json")
        with self.assertRaisesRegex(ToolLoadError, "not valid JSON"):
            ToolDefinitionLoader(registry, self.root).load(selection)

        self.write_definition(
            descriptor,
            schema={"type": "object", "$ref": "../outside.schema.json"},
        )
        with self.assertRaisesRegex(ToolLoadError, "prohibited external or traversing"):
            ToolDefinitionLoader(registry, self.root).load(selection)

    def test_schema_keyword_and_required_property_validation_fail_closed(self) -> None:
        descriptor = self.descriptor("tool-a", ("A",))
        registry = ToolRegistry([descriptor])
        selection = registry.select(self.discover(registry), ("tool-a",))
        cases = (
            {"type": "object", "x-provider-command": "run"},
            {
                "type": "object",
                "properties": {"known": {"type": "string"}},
                "required": ["missing"],
            },
            {"type": "string"},
        )
        for index, schema in enumerate(cases):
            with self.subTest(index=index):
                self.write_definition(descriptor, schema=schema)
                with self.assertRaises(ToolLoadError):
                    ToolDefinitionLoader(registry, self.root).load(selection)

    def test_source_mutation_cannot_change_registry_snapshot(self) -> None:
        source = [self.descriptor("tool-a", ("A",))]
        registry = ToolRegistry(source)
        before = registry.snapshot.digest
        source.append(self.descriptor("tool-b", ("A",)))

        result = self.discover(registry)

        self.assertEqual(registry.snapshot.digest, before)
        self.assertEqual(result.metrics.registered, 1)
        self.assertEqual([item.descriptor.tool_id for item in result.candidates], ["tool-a"])
        with self.assertRaises(FrozenInstanceError):
            registry.snapshot.descriptors[0].name = "mutated"
        with self.assertRaises(TypeError):
            registry._snapshot = ToolRegistry([]).snapshot

    def test_snapshot_and_retained_descriptors_are_detached_from_trusted_state(self) -> None:
        source = self.descriptor(
            "tool-a",
            ("A",),
            availability="unavailable",
            provider_compatibility=("provider-a",),
            tags=("safe",),
        )
        registry = ToolRegistry([source])
        digest = registry.snapshot.digest
        baseline = self.discover(registry)
        self.assertFalse(baseline.candidates[0].selectable)

        with self.assertRaises(AttributeError):
            source.__dict__["availability"] = "available"
        with self.assertRaises(TypeError):
            source.capabilities[0] = "B"
        for name, value in (
            ("availability", "available"),
            ("capabilities", ("B",)),
            ("authority_class", "CONTROLLED_WRITE"),
            ("risk_level", "high"),
            ("status", "disabled"),
            ("provider_compatibility", ("provider-b",)),
            ("tags", ("mutated",)),
            ("definition_ref", "mutated.definition.json"),
            ("schema_ref", "mutated.schema.json"),
        ):
            object.__setattr__(source, name, value)

        snapshot_view = registry.snapshot
        self.assertFalse(hasattr(snapshot_view, "__dict__"))
        with self.assertRaises(AttributeError):
            object.__setattr__(snapshot_view, "digest", "0" * 64)
        with self.assertRaises(AttributeError):
            object.__setattr__(
                registry,
                "_ToolRegistry__snapshot",
                ToolRegistry([]).snapshot,
            )
        snapshot_descriptor = snapshot_view.descriptors[0]
        with self.assertRaises(AttributeError):
            snapshot_descriptor.__dict__["availability"] = "available"
        with self.assertRaises(AttributeError):
            object.__setattr__(snapshot_descriptor, "available", True)
        for name, value in (
            ("availability", "available"),
            ("capabilities", ("B",)),
            ("authority_class", "CONTROLLED_WRITE"),
            ("risk_level", "high"),
            ("status", "disabled"),
            ("agent_compatibility", ("other-agent",)),
            ("workflow_compatibility", ("other-workflow",)),
            ("provider_compatibility", ("provider-b",)),
            ("tags", ("mutated",)),
            ("definition_ref", "mutated.definition.json"),
            ("schema_ref", "mutated.schema.json"),
        ):
            object.__setattr__(snapshot_descriptor, name, value)

        detached_lookup = registry.descriptor("tool-a")
        self.assertIsNotNone(detached_lookup)
        object.__setattr__(detached_lookup, "availability", "available")

        after = self.discover(registry)
        trusted = registry.snapshot.descriptors[0]
        self.assertEqual(registry.snapshot.digest, digest)
        self.assertEqual(trusted.capabilities, ("A",))
        self.assertEqual(trusted.availability, "unavailable")
        self.assertEqual(trusted.authority_class, "READ_ONLY")
        self.assertEqual(trusted.risk_level, "low")
        self.assertEqual(trusted.status, "active")
        self.assertEqual(trusted.provider_compatibility, ("provider-a",))
        self.assertEqual(trusted.tags, ("safe",))
        self.assertEqual(trusted.definition_ref, "tool-a.definition.json")
        self.assertEqual(trusted.schema_ref, "tool-a.schema.json")
        self.assertEqual(after.to_dict(), baseline.to_dict())
        with self.assertRaises(ToolRegistryError):
            registry.select(after, ("tool-a",))

    def test_registry_digest_is_deterministic_and_binds_every_policy_field(self) -> None:
        first = self.descriptor("tool-a", ("A",))
        second = self.descriptor("tool-b", ("B",))
        expected = ToolRegistry([first, second]).snapshot.digest
        self.assertEqual(ToolRegistry([second, first]).snapshot.digest, expected)
        self.assertEqual(
            ToolRegistry(
                [
                    ToolDescriptor.from_dict(first.to_dict()),
                    ToolDescriptor.from_dict(second.to_dict()),
                ]
            ).snapshot.digest,
            expected,
        )

        changes = (
            {"availability": "unavailable"},
            {"capabilities": ("A", "C")},
            {"authority_class": "CONTROLLED_WRITE"},
            {"risk_level": "high"},
            {"tool_class": "connector"},
            {"version": "2"},
            {"provider_compatibility": ("provider-a",)},
            {"agent_compatibility": ("agent-a",)},
            {"workflow_compatibility": ("workflow-a",)},
            {"status": "deprecated"},
            {"tags": ("tag-a",)},
            {"definition_ref": "other.definition.json"},
            {"schema_ref": "other.schema.json"},
        )
        for override in changes:
            with self.subTest(override=override):
                values = first.to_dict()
                values.update(override)
                changed = ToolRegistry(
                    [ToolDescriptor.from_dict(values), second]
                ).snapshot.digest
                self.assertNotEqual(changed, expected)

    def test_registry_content_and_digest_are_structurally_inseparable(self) -> None:
        descriptor = self.descriptor(
            "tool-a",
            ("A",),
            availability="unavailable",
        )
        registry = ToolRegistry([descriptor])
        before = self.discover(registry)
        digest = registry.snapshot.digest
        forged = descriptor.to_dict()
        forged["availability"] = "available"
        forged_payload = json.dumps(
            forged,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )

        attempts = (
            ("_ToolRegistry__descriptor_payloads", (forged_payload,)),
            ("_ToolRegistry__digest", "0" * 64),
            ("_ToolRegistry__snapshot", ToolRegistry([ToolDescriptor.from_dict(forged)]).snapshot),
            ("_ToolRegistry__canonical_payloads", (forged_payload,)),
            ("_ToolRegistry__canonical_digest", "0" * 64),
        )
        for name, value in attempts:
            with self.subTest(name=name):
                with self.assertRaises((AttributeError, TypeError)):
                    object.__setattr__(registry, name, value)

        snapshot = registry.snapshot
        for name, value in (
            ("_ToolRegistrySnapshot__descriptor_payloads", (forged_payload,)),
            ("_ToolRegistrySnapshot__digest", "0" * 64),
        ):
            with self.subTest(snapshot_name=name):
                with self.assertRaises((AttributeError, TypeError)):
                    object.__setattr__(snapshot, name, value)

        after = self.discover(registry)
        self.assertEqual(after.to_dict(), before.to_dict())
        self.assertEqual(registry.snapshot.digest, digest)
        self.assertFalse(after.candidates[0].selectable)
        with self.assertRaises(ToolRegistryError):
            registry.select(after, ("tool-a",))

        stale = replace(after, registry_digest="0" * 64)
        with self.assertRaisesRegex(ToolRegistryError, "different registry"):
            registry.verify_discovery(stale)

        malformed_registry = tuple.__new__(ToolRegistry, (("not canonical json",),))
        with self.assertRaisesRegex(ToolRegistryError, "malformed"):
            malformed_registry.discover(ToolDiscoveryRequest(("A",)))

    def test_shared_secret_detection_covers_serializable_tool_strings(self) -> None:
        secret_cases = (
            {"name": "API_KEY=synthetic-secret"},
            {"description": "PASSWORD=synthetic-secret"},
            {"tool_id": "sk-abcdefghijklmnop"},
            {"version": "sk-abcdefghijklmnop"},
            {"capabilities": ("sk-abcdefghijklmnop",)},
            {"provider_compatibility": ("sk-abcdefghijklmnop",)},
            {"agent_compatibility": ("sk-abcdefghijklmnop",)},
            {"workflow_compatibility": ("sk-abcdefghijklmnop",)},
            {"tags": ("sk-abcdefghijklmnop",)},
            {"definition_ref": "TOKEN=synthetic-secret.json"},
            {"schema_ref": "secret/PASSWORD=synthetic-secret.json"},
        )
        for override in secret_cases:
            with self.subTest(override=override):
                values = self.descriptor("tool-a", ("A",)).to_dict()
                values.update(override)
                with self.assertRaisesRegex(ToolContractError, "credential-like"):
                    ToolDescriptor.from_dict(values)

        for request in (
            ToolDiscoveryRequest(("A",)).to_dict() | {"agent": "sk-abcdefghijklmnop"},
            ToolDiscoveryRequest(("A",)).to_dict()
            | {"allowed_provider_ids": ["sk-abcdefghijklmnop"]},
            ToolDiscoveryRequest(("A",)).to_dict()
            | {"required_capabilities": ["sk-abcdefghijklmnop"]},
        ):
            with self.assertRaisesRegex(ToolValidationError, "credential-like"):
                ToolDiscoveryRequestValidator().validate(request)

        mutated_descriptor = self.descriptor("mutated-tool", ("A",))
        object.__setattr__(
            mutated_descriptor,
            "description",
            "TOKEN=synthetic-secret",
        )
        with self.assertRaisesRegex(ToolContractError, "credential-like"):
            mutated_descriptor.to_dict()
        with self.assertRaisesRegex(ToolContractError, "credential-like"):
            ToolCandidate(
                descriptor=self.descriptor("tool-b", ("A",)),
                match_reasons=("Bearer synthetic-provider-token",),
                available=True,
                eligible=True,
            )
        with self.assertRaisesRegex(ToolContractError, "credential-like"):
            RejectedTool(
                tool_id="tool-b",
                version="1",
                reasons=("PASSWORD=synthetic-secret",),
            )

        descriptor = self.descriptor("tool-a", ("A",))
        registry = ToolRegistry([descriptor])
        selection = registry.select(self.discover(registry), ("tool-a",))
        self.write_definition(
            descriptor,
            definition={
                "tool_id": "tool-a",
                "version": "1",
                "adapter_id": "canonical.tool-a",
                "tool_class": "local",
                "capabilities": ["A"],
                "authority_class": "READ_ONLY",
                "risk_level": "low",
                "description_context": "Bearer synthetic-provider-token",
            },
        )
        with self.assertRaisesRegex(ToolLoadError, "credential-like"):
            ToolDefinitionLoader(registry, self.root).load(selection)

        self.write_definition(
            descriptor,
            schema={
                "type": "object",
                "description": "TOKEN=synthetic-secret",
            },
        )
        with self.assertRaisesRegex(ToolLoadError, "credential-like"):
            ToolDefinitionLoader(registry, self.root).load(selection)

    def test_required_capability_bound_matches_schema_and_runtime(self) -> None:
        schema = JobValidator(
            Path(__file__).resolve().parents[2]
            / "schemas"
            / "tool-discovery-request.schema.json"
        )
        validator = ToolDiscoveryRequestValidator()
        base = ToolDiscoveryRequest(("A",)).to_dict()
        maximum = [f"CAP_{index:02d}" for index in range(20)]
        schema.validate(base | {"required_capabilities": maximum})
        validated = validator.validate(base | {"required_capabilities": maximum})
        self.assertEqual(
            len(validated.required_capabilities),
            20,
        )
        for capabilities in (
            [],
            ["A", "A"],
            [f"CAP_{index:02d}" for index in range(21)],
        ):
            with self.subTest(count=len(capabilities)):
                with self.assertRaises(JobValidationError):
                    schema.validate(base | {"required_capabilities": capabilities})
                with self.assertRaises(ToolValidationError):
                    validator.validate(base | {"required_capabilities": capabilities})

    def test_descriptor_reference_schema_and_runtime_rules_match(self) -> None:
        schema = JobValidator(
            Path(__file__).resolve().parents[2]
            / "schemas"
            / "tool-descriptor.schema.json"
        )
        validator = ToolDescriptorValidator()
        base = self.descriptor(
            "tool-a",
            ("A",),
            definition_ref="definitions/tool-a.json",
            schema_ref="schemas/tool-a.json",
        ).to_dict()

        for reference in (
            "definitions/tool-a.json",
            "nested/definitions/tool-a.v1.json",
            "nested_1/dir-2/tool_03.v1.json",
        ):
            with self.subTest(valid=reference):
                payload = base | {
                    "definition_ref": reference,
                    "schema_ref": reference,
                }
                schema.validate(payload)
                validator.validate(payload)
                ToolDescriptor.from_dict(payload)

        invalid = (
            "../outside.json",
            "dir/../../outside.json",
            "C:/outside.json",
            "/outside.json",
            "file://outside.json",
            "http://example.invalid/tool.json",
            "https://example.invalid/tool.json",
            "custom:tool.json",
            "dir\\..\\outside.json",
            "",
            "x" * 501,
            "dir//tool.json",
            "dir/./tool.json",
            "dir/",
        )
        for reference in invalid:
            for field_name in ("definition_ref", "schema_ref"):
                with self.subTest(reference=reference, field=field_name):
                    payload = base | {field_name: reference}
                    with self.assertRaises(JobValidationError):
                        schema.validate(payload)
                    with self.assertRaises(ToolValidationError):
                        validator.validate(payload)
                    with self.assertRaises(ToolContractError):
                        ToolDescriptor.from_dict(payload)

    def test_descriptor_reference_control_characters_match_runtime(self) -> None:
        schema = JobValidator(
            Path(__file__).resolve().parents[2]
            / "schemas"
            / "tool-descriptor.schema.json"
        )
        base = self.descriptor(
            "tool-a",
            ("A",),
            definition_ref="definitions/tool-a.json",
            schema_ref="schemas/tool-a.json",
        ).to_dict()
        prohibited = (
            *range(0x00, 0x09),
            0x0B,
            0x0C,
            *range(0x0E, 0x20),
        )
        self.assertEqual(len(prohibited), 29)

        for codepoint in prohibited:
            for reference in (
                f"definitions/x{chr(codepoint)}y.json",
                f"definitions/line\nx{chr(codepoint)}y.json",
            ):
                for field_name in ("definition_ref", "schema_ref"):
                    with self.subTest(
                        codepoint=f"U+{codepoint:04X}",
                        reference=reference,
                        field=field_name,
                    ):
                        payload = base | {field_name: reference}
                        with self.assertRaises(JobValidationError):
                            schema.validate(payload)
                        with self.assertRaises(ToolContractError):
                            ToolDescriptor.from_dict(payload)

        for reference in (
            "definitions/tool\tname.json",
            "definitions/tool\nname.json",
            "definitions/tool\rname.json",
        ):
            for field_name in ("definition_ref", "schema_ref"):
                with self.subTest(valid_control=repr(reference), field=field_name):
                    payload = base | {field_name: reference}
                    schema.validate(payload)
                    ToolDescriptor.from_dict(payload)

    def test_descriptor_reference_lf_boundaries_match_runtime(self) -> None:
        schema = JobValidator(
            Path(__file__).resolve().parents[2]
            / "schemas"
            / "tool-descriptor.schema.json"
        )
        base = self.descriptor(
            "tool-a",
            ("A",),
            definition_ref="definitions/tool-a.json",
            schema_ref="schemas/tool-a.json",
        ).to_dict()
        cases = (
            ("defs/tool.json", True),
            ("defs/nested/tool_01-v2.json", True),
            ("C:/outside.json", False),
            ("safe\nC:/outside.json", False),
            ("segment\\outside.json", False),
            ("safe\nsegment\\outside.json", False),
            ("../outside.json", False),
            ("safe\n../outside.json", True),
            ("safe\n/../outside.json", False),
            ("nested/safe\n/dir/../../outside.json", False),
            ("custom:tool.json", False),
            ("safe\ncustom:tool.json", False),
            ("http://x", False),
            ("safe\nhttp://x", False),
            (".", False),
            ("..", False),
            ("defs/.", False),
            ("defs/..", False),
            ("defs/.\n", True),
            ("defs/..\n", True),
            ("defs/\n.", True),
            ("defs/\n..", True),
            ("defs/.\n/tool.json", True),
            ("defs/..\n/tool.json", True),
            ("defs/a\tb.json", True),
            ("defs/a\nb.json", True),
            ("defs/a\rb.json", True),
            ("", False),
            ("   ", True),
            ("x" * 501, False),
            ("dir//tool.json", False),
            ("dir/", False),
        )

        for reference, expected in cases:
            for field_name in ("definition_ref", "schema_ref"):
                with self.subTest(reference=repr(reference), field=field_name):
                    payload = base | {field_name: reference}
                    schema_accepted = True
                    try:
                        schema.validate(payload)
                    except JobValidationError:
                        schema_accepted = False
                    runtime_accepted = True
                    try:
                        ToolDescriptor.from_dict(payload)
                    except ToolContractError:
                        runtime_accepted = False
                    self.assertEqual(schema_accepted, runtime_accepted)
                    self.assertEqual(runtime_accepted, expected)

    def test_selection_enforces_bound_during_iterable_consumption(self) -> None:
        registry = ToolRegistry(
            self.descriptor(f"tool-{index}", ("A",)) for index in range(3)
        )
        discovery = registry.discover(
            ToolDiscoveryRequest(("A",), maximum_candidates=3)
        )

        def measured(values):
            consumed = [0]

            def iterator():
                for value in values:
                    consumed[0] += 1
                    yield value

            return iterator(), consumed

        valid, valid_count = measured(("tool-0", "tool-1", "tool-2"))
        selected = registry.select(discovery, valid)
        self.assertEqual(valid_count[0], 3)
        self.assertEqual(len(selected.selected_tool_ids), 3)

        overflow, overflow_count = measured(("tool-0", "tool-1", "tool-2", "tool-3"))
        with self.assertRaisesRegex(ToolRegistryError, "candidate bound"):
            registry.select(discovery, overflow)
        self.assertEqual(overflow_count[0], 4)

        large, large_count = measured(f"tool-{index}" for index in range(10000))
        with self.assertRaisesRegex(ToolRegistryError, "candidate bound"):
            registry.select(discovery, large)
        self.assertEqual(large_count[0], 4)

        infinite_count = [0]

        def infinite():
            index = 0
            while True:
                infinite_count[0] += 1
                yield f"tool-{index}"
                index += 1

        with self.assertRaisesRegex(ToolRegistryError, "candidate bound"):
            registry.select(discovery, infinite())
        self.assertEqual(infinite_count[0], 4)

        malformed, malformed_count = measured((None, "tool-0", "tool-1"))
        with self.assertRaisesRegex(ToolRegistryError, "malformed tool ID"):
            registry.select(discovery, malformed)
        self.assertEqual(malformed_count[0], 1)

    def test_selection_rejects_unknown_and_duplicate_ids_during_streaming(self) -> None:
        registry = ToolRegistry(
            self.descriptor(f"tool-{index}", ("A",)) for index in range(3)
        )
        discovery = registry.discover(
            ToolDiscoveryRequest(("A",), maximum_candidates=3)
        )

        def measured(values):
            consumed = [0]

            def iterator():
                for value in values:
                    consumed[0] += 1
                    yield value

            return iterator(), consumed

        first, first_count = measured(
            ("unknown", *(f"tail-{index}" for index in range(10000)))
        )
        with self.assertRaisesRegex(ToolRegistryError, "unknown"):
            registry.select(discovery, first)
        self.assertEqual(first_count[0], 1)

        second, second_count = measured(
            ("tool-0", "unknown", *(f"tail-{index}" for index in range(10000)))
        )
        with self.assertRaisesRegex(ToolRegistryError, "unknown"):
            registry.select(discovery, second)
        self.assertEqual(second_count[0], 2)

        exact, exact_count = measured(("tool-0", "tool-1", "tool-2"))
        selected = registry.select(discovery, exact)
        self.assertEqual(exact_count[0], 3)
        self.assertEqual(len(selected.selected_tool_ids), 3)

        overflow, overflow_count = measured(
            ("tool-0", "tool-1", "tool-2", "tool-0")
        )
        with self.assertRaisesRegex(ToolRegistryError, "candidate bound"):
            registry.select(discovery, overflow)
        self.assertEqual(overflow_count[0], 4)

        infinite_count = [0]

        def infinite_unknown():
            infinite_count[0] += 1
            yield "unknown"
            while True:
                infinite_count[0] += 1
                yield "tool-0"

        with self.assertRaisesRegex(ToolRegistryError, "unknown"):
            registry.select(discovery, infinite_unknown())
        self.assertEqual(infinite_count[0], 1)

        duplicate, duplicate_count = measured(
            ("tool-0", "tool-0", *(f"tail-{index}" for index in range(10000)))
        )
        with self.assertRaisesRegex(ToolRegistryError, "duplicate"):
            registry.select(discovery, duplicate)
        self.assertEqual(duplicate_count[0], 2)

    def test_provider_cannot_promote_unavailable_candidate(self) -> None:
        descriptor = self.descriptor("tool-a", ("A",), availability="unavailable")
        registry = ToolRegistry([descriptor])
        genuine = self.discover(registry)
        promoted = ToolCandidate(
            descriptor=genuine.candidates[0].descriptor,
            match_reasons=genuine.candidates[0].match_reasons,
            available=True,
            eligible=True,
            ineligibility_reasons=(),
        )
        forged = replace(genuine, status="matched", candidates=(promoted,))

        with self.assertRaisesRegex(ToolRegistryError, "mutated"):
            registry.select(forged, ("tool-a",))

    def test_agent_workflow_provider_and_class_constraints_are_deterministic(self) -> None:
        descriptor = self.descriptor(
            "tool-a",
            ("A",),
            tool_class="connector",
            agent_compatibility=("researcher",),
            workflow_compatibility=("research",),
            provider_compatibility=("codex",),
        )
        registry = ToolRegistry([descriptor])
        result = registry.discover(
            ToolDiscoveryRequest(
                ("A",),
                agent="reviewer",
                workflow="software",
                allowed_tool_classes=("local",),
                allowed_provider_ids=("claude",),
            )
        )

        self.assertEqual(result.status, "no_match")
        self.assertEqual(
            result.candidates[0].ineligibility_reasons,
            (
                "tool class is not allowed by the request",
                "no allowed provider is compatible",
                "agent is not compatible",
                "workflow is not compatible",
            ),
        )

    def test_execution_mode_restriction_is_explicit(self) -> None:
        registry = ToolRegistry(
            [
                self.descriptor("read-tool", ("A",)),
                self.descriptor(
                    "write-tool", ("A",), authority_class="CONTROLLED_WRITE"
                ),
            ]
        )

        result = registry.discover(
            ToolDiscoveryRequest(("A",), execution_mode="READ_ONLY")
        )

        read_tool = next(item for item in result.candidates if item.descriptor.tool_id == "read-tool")
        write_tool = next(item for item in result.candidates if item.descriptor.tool_id == "write-tool")
        self.assertTrue(read_tool.selectable)
        self.assertFalse(write_tool.eligible)
        self.assertIn(
            "execution mode does not permit the authority class",
            write_tool.ineligibility_reasons,
        )

    def test_registry_bound_stops_iterable_consumption(self) -> None:
        consumed = 0

        def descriptors():
            nonlocal consumed
            for index in range(1002):
                consumed += 1
                yield self.descriptor(f"tool-{index:04d}", ("A",))

        with self.assertRaisesRegex(ToolRegistryError, "1000-tool bound"):
            ToolRegistry(descriptors())
        self.assertEqual(consumed, 1001)

    def test_duplicate_json_keys_and_unresolved_local_refs_fail_closed(self) -> None:
        descriptor = self.descriptor("tool-a", ("A",))
        registry = ToolRegistry([descriptor])
        selection = registry.select(self.discover(registry), ("tool-a",))

        duplicate = (
            '{"tool_id":"tool-a","tool_id":"spoofed","version":"1",'
            '"adapter_id":"canonical.tool-a","tool_class":"local",'
            '"capabilities":["A"],"authority_class":"READ_ONLY",'
            '"risk_level":"low","description_context":"context"}'
        )
        self.write_definition(descriptor, definition=duplicate)
        with self.assertRaisesRegex(ToolLoadError, "not valid JSON"):
            ToolDefinitionLoader(registry, self.root).load(selection)

        self.write_definition(
            descriptor,
            schema={
                "type": "object",
                "properties": {"value": {"$ref": "#/$defs/missing"}},
            },
        )
        with self.assertRaisesRegex(ToolLoadError, "unresolved local"):
            ToolDefinitionLoader(registry, self.root).load(selection)

    def test_candidate_bound_is_deterministic_and_measured(self) -> None:
        registry = ToolRegistry(
            self.descriptor(f"tool-{index:03d}", ("A",)) for index in range(20)
        )

        result = registry.discover(
            ToolDiscoveryRequest(("A",), maximum_candidates=3)
        )

        self.assertEqual([item.descriptor.tool_id for item in result.candidates], [
            "tool-000", "tool-001", "tool-002"
        ])
        self.assertEqual(result.metrics.matched, 20)
        self.assertEqual(len(result.candidates), 3)
        self.assertEqual(len(result.rejected), 17)

    def test_discovery_and_loaded_results_are_deeply_immutable(self) -> None:
        descriptor = self.descriptor("tool-a", ("A",))
        self.write_definition(descriptor)
        registry = ToolRegistry([descriptor])
        result = self.discover(registry)
        selection = registry.select(result, ("tool-a",))
        loaded = ToolDefinitionLoader(registry, self.root).load(selection)

        with self.assertRaises(FrozenInstanceError):
            result.status = "no_match"
        with self.assertRaises(TypeError):
            loaded.definitions[0].input_schema["type"] = "string"
        with self.assertRaises(TypeError):
            loaded.definitions[0].input_schema["properties"]["target"] = {}

    def test_discovery_does_not_invoke_and_loading_grants_no_authority(self) -> None:
        descriptor = self.descriptor("tool-a", ("A",))
        self.write_definition(descriptor)
        registry = ToolRegistry([descriptor])
        discovery = self.discover(registry)
        self.assertEqual(discovery.selected_tool_ids, ())
        self.assertFalse(hasattr(discovery, "execute"))

        loaded = ToolDefinitionLoader(registry, self.root).load(
            registry.select(discovery, ("tool-a",))
        )
        definition = loaded.definitions[0]
        self.assertFalse(hasattr(definition, "execute"))
        serialized = json.dumps(loaded.to_dict(), sort_keys=True).lower()
        for prohibited in (
            "approval_id",
            "review_decision",
            "continuation_parent_job_id",
            "parent_job_id",
            "recovery_hold_cleared",
            "git_authority",
            "deployment_authority",
        ):
            self.assertNotIn(prohibited, serialized)

    def test_production_tool_layer_has_no_dynamic_import_or_shell_fallback(self) -> None:
        from runtime.tools import loader, models, registry, validation

        source = "\n".join(inspect.getsource(module) for module in (loader, models, registry, validation))
        for prohibited in (
            "importlib",
            "__import__(",
            "subprocess",
            "os.system",
            "shell=True",
            "eval(",
            "exec(",
        ):
            self.assertNotIn(prohibited, source)


if __name__ == "__main__":
    unittest.main()

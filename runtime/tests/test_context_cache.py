"""CORE-09 deterministic cache and provider-builder boundary tests."""
from dataclasses import asdict, replace
import json
from pathlib import Path
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from runtime.cache import CachePolicy, ContextCache
from runtime.context.contracts import ContextPack, DiscoveryError, Material, assemble, digest
from runtime.context.skills import SkillCatalog, SkillMetadata
from runtime.providers.context import ContextBuildError, ExecutionContextBuilder
from runtime.tests.test_providers import request


def pack(text='source'):
    return assemble((Material('files/code', 'a.txt', text, digest(text)),))


class CachePolicyTests(unittest.TestCase):
    def setUp(self):
        self.now = 10.0
        self.cache = ContextCache(clock=lambda: self.now)

    def reuse(self, fresh=None, **kwargs):
        return self.cache.reuse(namespace=kwargs.pop('namespace', 'owner/read'),
                                binding=kwargs.pop('binding', {'job': 'one'}),
                                fresh=fresh or pack(), **kwargs)

    def test_hit_reuses_immutable_pack(self):
        first = self.reuse()
        second = self.reuse()
        self.assertEqual((first.status, second.status), ('MISS', 'HIT'))
        self.assertIs(first.pack, second.pack)
        self.assertEqual(first.key, second.key)

    def test_deterministic_key_across_fresh_caches(self):
        first = self.reuse()
        self.cache = ContextCache()
        second = self.reuse()
        self.assertEqual((second.status, second.key), ('MISS', first.key))

    def test_changed_content_and_forged_source_digest(self):
        self.reuse()
        changed = ContextPack((Material('files/code', 'a.txt', 'changed', digest('source')),))
        result = self.reuse(changed)
        self.assertEqual((result.status, result.reason), ('STALE', 'material_changed'))
        self.assertEqual(result.pack, changed)

    def test_source_version_change_without_text_change(self):
        original = pack()
        self.reuse(original)
        changed = ContextPack((replace(original.materials[0], source_digest=digest('version2')),))
        self.assertEqual(self.reuse(changed).status, 'STALE')

    def test_scope_and_work_isolation(self):
        self.reuse()
        self.assertEqual(self.reuse(namespace='other/read').status, 'MISS')
        self.assertEqual(self.reuse(binding={'job': 'two'}).status, 'MISS')
        self.assertEqual(self.reuse().status, 'HIT')

    def test_expiry_boundary_and_clock_rollback(self):
        self.reuse()
        self.now = 309.999
        self.assertEqual(self.reuse().status, 'HIT')
        self.now = 310
        self.assertEqual(self.reuse().reason, 'expired')
        self.now = 1
        self.assertEqual(self.reuse().reason, 'expired')

    def test_hit_does_not_extend_ttl(self):
        self.reuse()
        self.now = 200
        self.reuse()
        self.now = 310
        self.assertEqual(self.reuse().status, 'STALE')

    def test_malformed_entry_is_rejected(self):
        self.reuse()
        slot = next(iter(self.cache._entries))
        self.cache._entries[slot] = {'valid': True, 'approval_status': 'approved'}
        result = self.reuse()
        self.assertEqual((result.status, result.reason), ('STALE', 'malformed'))
        self.assertEqual(result.pack, pack())

    def test_tampered_pack_is_rejected(self):
        self.reuse()
        slot, entry = next(iter(self.cache._entries.items()))
        self.cache._entries[slot] = replace(entry, pack=pack('injected authority'))
        result = self.reuse()
        self.assertEqual(result.status, 'STALE')
        self.assertEqual(result.pack, pack())

    def test_count_and_byte_bounds(self):
        self.cache = ContextCache(CachePolicy(max_entries=2, max_bytes=2000, entry_bytes=1500))
        for i in range(20):
            self.reuse(binding={'job': str(i)})
            self.assertLessEqual(len(self.cache._entries), 2)
            self.assertLessEqual(sum(e.size for e in self.cache._entries.values()), 2000)
        self.assertEqual(self.reuse(binding={'job': '0'}).status, 'MISS')

    def test_oversized_entry_bypasses_storage(self):
        self.cache = ContextCache(CachePolicy(entry_bytes=100))
        self.assertEqual(self.reuse().status, 'BYPASS')
        self.assertFalse(self.cache._entries)

    def test_invalid_policy_limits(self):
        for values in ({'max_entries': 0}, {'max_entries': True}, {'ttl_seconds': 86401},
                       {'max_bytes': 17 * 1024 * 1024}, {'version': ''}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                CachePolicy(**values)

    def test_invalid_identity_fails_closed(self):
        for binding in ({1: 'ambiguous'}, {'value': float('nan')}, {'value': object()},
                        {'value': 'x' * 65537}, {}):
            with self.subTest(binding=type(binding)), self.assertRaises(DiscoveryError):
                self.reuse(binding=binding)
        with self.assertRaises(DiscoveryError):
            self.reuse(namespace='')

    def test_nonready_and_ambiguous_pack_rejected(self):
        from runtime.context.contracts import MissingInformation
        for value in (ContextPack(pack().materials, (MissingInformation('x', 'supply x'),)),
                      ContextPack(pack().materials * 2), ContextPack(list(pack().materials))):
            with self.assertRaises(DiscoveryError):
                self.reuse(value)

    def test_policy_version_changes_identity(self):
        first = self.reuse()
        self.cache = ContextCache(CachePolicy(version='core09-v2'))
        self.assertNotEqual(first.key, self.reuse().key)

    def test_concurrent_reuse_is_bounded(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: self.reuse(), range(32)))
        self.assertEqual(sum(r.status == 'MISS' for r in results), 1)
        self.assertEqual(len(self.cache._entries), 1)

    def corrupt_material(self, field, value):
        self.reuse()
        slot, entry = next(iter(self.cache._entries.items()))
        material = replace(entry.pack.materials[0])
        object.__setattr__(material, field, value)
        self.cache._entries[slot] = replace(entry, pack=ContextPack((material,)))

    def assert_malformed_rebuilt(self):
        result = self.reuse()
        self.assertEqual((result.status, result.reason), ('STALE', 'malformed'))
        self.assertEqual(result.pack.render(), pack().render())
        self.assertEqual(self.reuse().status, 'HIT')

    def test_cached_integer_to_bool_corruption(self):
        self.corrupt_material('start_line', True)
        self.assert_malformed_rebuilt()

    def test_cached_integer_to_float_corruption(self):
        self.corrupt_material('start_line', 1.0)
        self.assert_malformed_rebuilt()

    def test_cached_malformed_nested_values(self):
        for field, value in (('content', {'nested': ['text']}), ('ref', ['a.txt']),
                             ('source_digest', None), ('source', []),
                             ('retention', 'summary'), ('start_line', 0)):
            with self.subTest(field=field):
                self.cache = ContextCache()
                self.corrupt_material(field, value)
                self.assert_malformed_rebuilt()

    def test_cached_unknown_material_field_rejected(self):
        self.corrupt_material('approval_status', 'approved')
        self.assert_malformed_rebuilt()

    def test_cached_unknown_pack_field_rejected(self):
        self.reuse()
        entry = next(iter(self.cache._entries.values()))
        object.__setattr__(entry.pack, 'valid', True)
        self.assert_malformed_rebuilt()

    def test_cached_missing_field_rejected(self):
        self.reuse()
        material = next(iter(self.cache._entries.values())).pack.materials[0]
        # Deleting a defaulted field otherwise falls back to the class value.
        object.__delattr__(material, 'start_line')
        self.assert_malformed_rebuilt()

    def test_cached_noncanonical_container_rejected(self):
        for field, value in (('materials', [pack().materials[0]]), ('materials', ({},)),
                             ('materials', pack().materials * 2),
                             ('missing', []), ('missing', ({'field': 'x'},))):
            with self.subTest(field=field, value=value):
                self.cache = ContextCache()
                self.reuse()
                entry = next(iter(self.cache._entries.values()))
                object.__setattr__(entry.pack, field, value)
                self.assert_malformed_rebuilt()

    def test_cached_serialization_mismatch_ignores_loose_equality(self):
        self.reuse()
        slot, entry = next(iter(self.cache._entries.items()))
        changed = ContextPack((replace(entry.pack.materials[0], content='SOURCE'),))
        self.cache._entries[slot] = replace(entry, pack=changed)
        with patch.object(Material, '__eq__', return_value=True):
            result = self.reuse()
        self.assertEqual((result.status, result.reason), ('STALE', 'material_changed'))
        self.assertEqual(result.pack.render(), pack().render())

    def test_fresh_and_cached_contract_validation_are_identical(self):
        for field, value in (('start_line', True), ('start_line', 1.0), ('extra', 'unknown')):
            with self.subTest(field=field, value=value):
                fresh = pack()
                object.__setattr__(fresh.materials[0], field, value)
                with self.assertRaises(DiscoveryError):
                    self.reuse(fresh)

    def test_valid_hit_keeps_canonical_serialization_and_object(self):
        first = self.reuse()
        second = self.reuse(pack())
        self.assertEqual(second.status, 'HIT')
        self.assertIs(first.pack, second.pack)
        self.assertEqual(second.pack.render(), pack().render())

    def test_cached_noncanonical_scalar_representation_rejected(self):
        class Text(str):
            pass
        self.corrupt_material('content', Text('source'))
        self.assert_malformed_rebuilt()


class CacheBuilderTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        for ref in ('CONSTITUTION.md', 'AGENTS.md', 'PROJECT_STATE.md', 'input.txt'):
            self.write(ref, 'Current ' + ref)
        self.write('skills/example.md', 'Selected instructions')
        self.meta = SkillMetadata('example', 'example', 'skills/example.md',
                                 digest('Selected instructions'), (), (), (), (), (), ())
        self.catalog()
        self.builder = ExecutionContextBuilder(self.root)
        self.req = request(context_refs=(), input_refs=({'ref_type': 'file', 'ref': 'input.txt'},))

    def write(self, ref, value):
        path = self.root / ref
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value, encoding='utf-8')

    def catalog(self):
        self.write('skills/catalog.json', json.dumps([asdict(self.meta)]))

    def build(self, **changes):
        return self.builder.build(replace(self.req, **changes))

    def test_valid_hit_and_provider_neutrality(self):
        a = self.build(provider='claude')
        b = self.build(provider='codex')
        self.assertEqual(self.builder.last_cache_result.status, 'HIT')
        self.assertEqual(a.render(), b.render())

    def test_source_change_invalidates(self):
        self.build()
        self.write('input.txt', 'new context')
        result = self.build()
        self.assertEqual(self.builder.last_cache_result.status, 'STALE')
        self.assertIn('new context', result.render())

    def test_governance_and_project_state_changes(self):
        for ref in ('CONSTITUTION.md', 'AGENTS.md', 'PROJECT_STATE.md'):
            self.build()
            self.write(ref, 'changed ' + ref)
            self.build()
            self.assertEqual(self.builder.last_cache_result.status, 'STALE')

    def test_missing_source_never_uses_cached_copy(self):
        self.build()
        (self.root / 'input.txt').unlink()
        with self.assertRaises(ContextBuildError):
            self.build()
        self.assertIsNone(self.builder.last_cache_result)

    def test_skill_change_requires_fresh_digest(self):
        self.build(skill='example')
        self.write('skills/example.md', 'new instructions')
        with self.assertRaises(ContextBuildError):
            self.build(skill='example')
        self.meta = replace(self.meta, sha256=digest('new instructions'))
        self.catalog()
        result = self.build(skill='example')
        self.assertNotEqual(self.builder.last_cache_result.status, 'HIT')
        self.assertIn('new instructions', result.render())

    def test_selected_skill_metadata_invalidates(self):
        self.build(skill='example')
        self.meta = replace(self.meta, description='changed metadata')
        self.catalog()
        self.build(skill='example')
        self.assertEqual(self.builder.last_cache_result.status, 'MISS')

    def test_project_task_and_exact_work_isolation(self):
        self.build()
        for changes in ({'project_id': 'different'}, {'job_id': 'different'},
                        {'task': 'different'}, {'execution_id': 'different'},
                        {'agent': 'reviewer'}, {'capability': 'independent_review'}):
            self.build(**changes)
            self.assertEqual(self.builder.last_cache_result.status, 'MISS')

    def test_fresh_authority_fields_never_inherited(self):
        self.build(approval_status='approved', review_required=False)
        result = self.build(approval_status='required', review_required=True)
        self.assertEqual(result.approval_status, 'required')
        self.assertTrue(result.review_required)
        self.assertEqual(result.execution_mode, 'READ_ONLY')
        self.assertIsNone(result.execution_scope)
        result = self.build(approval_status='required', review_required=True)
        self.assertEqual(self.builder.last_cache_result.status, 'HIT')
        self.assertEqual(result.approval_status, 'required')
        self.assertEqual(set(self.builder.last_cache_result.pack.payload()),
                         {'version', 'authority', 'status', 'materials', 'missing'})
        self.assertEqual(result.context_pack.payload()['authority'], 'none')

    def test_irrelevant_file_and_unselected_skill_changes_preserve_hit(self):
        self.build()
        self.write('unrelated.txt', 'not selected')
        self.meta = replace(self.meta, description='irrelevant metadata')
        self.catalog()
        self.build()
        self.assertEqual(self.builder.last_cache_result.status, 'HIT')

    def test_shared_cache_requires_explicit_scope_and_isolates_users(self):
        cache = ContextCache()
        with self.assertRaises(ContextBuildError):
            ExecutionContextBuilder(self.root, cache=cache)
        for scope in ('alice', 'bob'):
            builder = ExecutionContextBuilder(self.root, cache=cache, cache_scope=scope)
            builder.build(self.req)
            self.assertEqual(builder.last_cache_result.status, 'MISS')

    def test_new_builder_has_cold_cache_no_persistence(self):
        self.build()
        second = ExecutionContextBuilder(self.root)
        second.build(self.req)
        self.assertEqual(second.last_cache_result.status, 'MISS')
        self.assertFalse((self.root / 'cache').exists())

    def test_construction_options_change_identity(self):
        self.build()
        self.builder.max_total_bytes -= 1
        self.build()
        self.assertEqual(self.builder.last_cache_result.status, 'MISS')

    def test_selected_skill_removed_between_discovery_and_validation(self):
        from runtime.context.contracts import RepositoryReader
        self.build(skill='example')
        catalog = SkillCatalog.from_file(RepositoryReader(self.root))
        removed = SkillCatalog(RepositoryReader(self.root), ())
        with patch.object(SkillCatalog, 'from_file', side_effect=(catalog, removed)):
            with self.assertRaises(ContextBuildError):
                self.build(skill='example')
        self.assertIsNone(self.builder.last_cache_result)

    def test_availability_change_revalidates_and_unavailability_blocks(self):
        from runtime.context.fallback import CapabilityImplementation, CapabilityRequirement
        requirement = CapabilityRequirement('read', (), (), (), ())
        preferred = CapabilityImplementation('primary', 'preferred', requirement, True)
        alternative = CapabilityImplementation('secondary', 'alternative', requirement, True)
        self.builder.capability_requests = ((requirement, (preferred, alternative)),)
        self.build()
        self.builder.capability_requests = ((requirement, (replace(preferred, available=False), alternative)),)
        result = self.build()
        self.assertEqual(self.builder.last_cache_result.status, 'STALE')
        self.assertIn('secondary', result.render())
        self.builder.capability_requests = ((requirement, (replace(preferred, available=False),)),)
        with self.assertRaises(ContextBuildError):
            self.build()
        self.assertIsNone(self.builder.last_cache_result)

    def test_shared_cache_isolates_repository_roots(self):
        import shutil
        cache = ContextCache()
        first = ExecutionContextBuilder(self.root, cache=cache, cache_scope='owner')
        first.build(self.req)
        with tempfile.TemporaryDirectory() as other:
            root = Path(other) / 'repository'
            shutil.copytree(self.root, root)
            second = ExecutionContextBuilder(root, cache=cache, cache_scope='owner')
            second.build(self.req)
            self.assertEqual(second.last_cache_result.status, 'MISS')

    def test_corrupted_cache_never_enters_provider_package(self):
        for field, value in (('start_line', True), ('start_line', 1.0),
                             ('content', {'nested': 'invalid'}), ('extra', 'unknown')):
            with self.subTest(field=field, value=value):
                self.builder = ExecutionContextBuilder(self.root)
                fresh = self.build()
                cache = self.builder.cache
                slot, entry = next(iter(cache._entries.items()))
                material = replace(entry.pack.materials[0])
                object.__setattr__(material, field, value)
                corrupted = ContextPack((material, *entry.pack.materials[1:]))
                cache._entries[slot] = replace(entry, pack=corrupted)
                result = self.build()
                self.assertEqual(self.builder.last_cache_result.status, 'STALE')
                self.assertEqual(result.render(), fresh.render())
                for item in result.context_pack.materials:
                    item.__post_init__()
                self.build()
                self.assertEqual(self.builder.last_cache_result.status, 'HIT')


if __name__ == '__main__':
    unittest.main()

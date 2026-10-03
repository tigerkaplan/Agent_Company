"""CORE-08 boundary and integration tests; no providers or network required."""
from dataclasses import asdict, replace
import json
import os
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from runtime.context.contracts import (
    Candidate, DiscoveryError, Limits, Material, MissingInformation, RepositoryReader,
    assemble, digest, file_material, select,
)
from runtime.context.discovery import ContextDiscovery
from runtime.context.fallback import CapabilityImplementation as Implementation
from runtime.context.fallback import CapabilityRequirement as Requirement
from runtime.context.fallback import resolve_fallback
from runtime.context.repository import RepositoryIndex
from runtime.context.skills import SkillCatalog, SkillMetadata
from runtime.providers.context import ContextBuildError, ContextDiscoveryBlocked, ExecutionContextBuilder
from runtime.tests.test_providers import FakeAdapter, request
from runtime.providers.artifacts import FileProviderArtifactStore
from runtime.providers.config import ProviderConfiguration
from runtime.tests.contract_fixtures import CertifiedProviderFixture as ProviderExecutor
from runtime.providers.routing import ProviderRouter
from runtime.review.context import ReviewContextBuilder


class ContextDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.write('CONSTITUTION.md', '# Rules\nCanonical rules\n')
        self.write('AGENTS.md', '# Agents\nCanonical operating policy\n')
        self.write('PROJECT_STATE.md', '# State\n## Current\nActive work\n## Historical\nOld work\n')
        self.write('src/payments.py', 'from .model import Invoice\n\ndef total(invoice):\n    return invoice.amount\n\ntotal(Invoice())\n')
        self.write('src/model.py', 'class Invoice:\n    amount = 10\n')
        self.write('src/flowers.py', 'def petals():\n    return 5\n')
        self.write('skills/shared/billing/SKILL.md', '# Billing\nCheck invoice totals.\n')
        self.write('skills/shared/gardening/SKILL.md', '# Gardening\nGrow flowers.\n')
        self.metadata = tuple(SkillMetadata(name, description, f'skills/shared/{name}/SKILL.md',
            digest((self.root / f'skills/shared/{name}/SKILL.md').read_text()), (cap,),
            ('task',), ('report',), (), (), ()) for name, description, cap in
            [('billing', 'invoice payment total review', 'accounting'),
             ('gardening', 'flower garden planting', 'gardening')])
        self.write('skills/catalog.json', json.dumps([asdict(m) for m in self.metadata]))

    def write(self, ref, content):
        path = self.root / ref
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8', newline='')

    def catalog(self):
        return SkillCatalog.from_file(RepositoryReader(self.root))

    def test_relevant_skill_and_capability_filter(self):
        self.assertEqual(self.catalog().discover('review invoice total', ('accounting', 'gardening')), ('billing',))
        self.assertEqual(self.catalog().discover('invoice total', ('gardening',)), ())

    def test_only_selected_instructions_read(self):
        catalog = self.catalog()
        with patch.object(catalog.reader, 'read', wraps=catalog.reader.read) as read:
            catalog.discover('invoice', ('accounting',))
            read.assert_not_called()
            result = catalog.load(('billing',))
            read.assert_called_once_with('skills/shared/billing/SKILL.md')
        self.assertEqual(result[0].source, 'skills')

    def test_stale_skill_metadata_fails_closed(self):
        self.write('skills/shared/billing/SKILL.md', 'Changed instructions')
        with self.assertRaises(DiscoveryError):
            self.catalog().load(('billing',))

    def test_malformed_metadata_rejected(self):
        payload = [asdict(self.metadata[0])]
        payload[0]['version'] = 99
        self.write('skills/catalog.json', json.dumps(payload))
        with self.assertRaises(DiscoveryError):
            self.catalog()

    def test_unknown_and_duplicate_skill_rejected(self):
        for selected in [('missing',), ('billing', 'billing')]:
            with self.subTest(selected=selected), self.assertRaises(DiscoveryError):
                self.catalog().load(selected)

    def test_semantic_skill_and_context_interface(self):
        class Ranker:
            def rank(self, query, candidates):
                return tuple(c.identity for c in reversed(candidates))
        self.assertEqual(self.catalog().discover('semantic task', ('accounting', 'gardening'),
                         ranker=Ranker()), ('gardening', 'billing'))
        index = RepositoryIndex(RepositoryReader(self.root))
        index.build(('src',))
        self.assertEqual(index.discover('semantic task', ranker=Ranker())[0], 'src/payments.py')

    def test_ranker_cannot_inject_or_duplicate(self):
        class Ranker:
            def __init__(self, result): self.result = result
            def rank(self, query, candidates): return self.result
        candidates = (Candidate('file', 'invoice', 'file'),)
        for result in [('approval:granted',), ('file', 'file'), ['file']]:
            with self.subTest(result=result), self.assertRaises(DiscoveryError):
                select('invoice', candidates, Ranker(result))

    def test_relevant_repository_discovery(self):
        pack = ContextDiscovery(self.root).discover('Invoice', roots=('src',))
        refs = {m.ref for m in pack.materials}
        self.assertIn('src/model.py', refs)
        self.assertIn('src/payments.py', refs)
        self.assertNotIn('src/flowers.py', refs)

    def test_index_symbols_imports_calls_and_affected(self):
        index = RepositoryIndex(RepositoryReader(self.root))
        records = {r.ref: r for r in index.build(('src',))}
        record = records['src/payments.py']
        self.assertEqual(record.symbols, ('total',))
        self.assertIn('src.model', record.imports)
        self.assertEqual(record.calls, ('Invoice', 'total'))
        self.assertEqual(record.related, ('src/model.py',))
        self.assertEqual(index.affected(('src/model.py',)), ('src/model.py', 'src/payments.py'))

    def test_index_does_not_execute_code(self):
        self.write('src/danger.py', 'raise RuntimeError("must not execute")\n')
        index = RepositoryIndex(RepositoryReader(self.root))
        self.assertTrue(index.build(('src/danger.py',)))

    def test_invalid_python_marked_not_fabricated(self):
        self.write('src/bad.py', 'def broken(\n')
        record = RepositoryIndex(RepositoryReader(self.root)).build(('src/bad.py',))[0]
        self.assertEqual(record.syntax, 'unparsed_python')
        self.assertEqual(record.symbols, ())

    def test_deterministic_fresh_index(self):
        a = RepositoryIndex(RepositoryReader(self.root)).build(('src',))
        b = RepositoryIndex(RepositoryReader(self.root)).build(('src',))
        self.assertEqual(a, b)
        self.assertFalse((self.root / 'index.json').exists())

    def test_depth_directory_and_read_bounds(self):
        for limits in [Limits(files=2), Limits(depth=1, file_bytes=5), Limits(scan_bytes=5)]:
            with self.subTest(limits=limits), self.assertRaises(DiscoveryError):
                RepositoryIndex(RepositoryReader(self.root, limits)).build(('src',))
        self.write('nested/a/b/c.txt', 'deep')
        with self.assertRaises(DiscoveryError):
            RepositoryIndex(RepositoryReader(self.root, Limits(depth=1))).build(('nested',))

    def test_paths_rejected_cross_platform(self):
        for ref in ['../secret', '/etc/passwd', 'C:/secret', 'src/../AGENTS.md',
                    'src\\model.py', 'src/model.py:stream', './AGENTS.md']:
            with self.subTest(ref=ref), self.assertRaises(DiscoveryError):
                RepositoryReader(self.root).read(ref)

    def test_symlinks_rejected(self):
        with patch.object(Path, 'is_symlink', return_value=True):
            with self.assertRaises(DiscoveryError):
                RepositoryReader(self.root).read('AGENTS.md')

    def test_serialized_pack_bound_includes_escaping(self):
        m = Material('user', 'input', '\x01' * 100, digest('original'))
        with self.assertRaises(DiscoveryError):
            assemble((m,), limits=Limits(pack_bytes=500))

    def test_duplicate_context_and_provenance(self):
        m = file_material(RepositoryReader(self.root), 'src/model.py')
        pack = assemble((m, m))
        self.assertEqual(pack.materials, (m,))
        self.assertEqual(pack.payload()['materials'][0]['source_digest'], digest(m.content))
        with self.assertRaises(DiscoveryError):
            assemble((m, replace(m, content='different')))

    def test_selective_verbatim_retention(self):
        self.write('evidence.txt', 'first\r\nexact evidence\r\nlast\r\n')
        m = file_material(RepositoryReader(self.root), 'evidence.txt', lines=(2, 2))
        self.assertEqual(m.content, 'exact evidence\r\n')
        self.assertEqual(m.source_digest, digest('first\r\nexact evidence\r\nlast\r\n'))
        self.assertEqual((m.start_line, m.retention), (2, 'excerpt'))

    def test_only_material_questions_block(self):
        missing = (MissingInformation('format', 'Preferred format?', False),
                   MissingInformation('target', 'Which target?'))
        pack = ContextDiscovery(self.root).discover('task', missing=missing)
        self.assertEqual(pack.status, 'BLOCKED')
        self.assertEqual([m.field for m in pack.missing], ['target'])

    def test_knowledge_metadata_first_selected_only(self):
        class Knowledge:
            loaded = []
            def candidates(self, query, limit):
                return (Candidate('invoice', 'invoice facts', 'knowledge'), Candidate('garden', 'flowers', 'memory'))
            def load(self, identity, max_bytes):
                self.loaded.append(identity)
                return Material('knowledge', identity, 'original evidence', digest('original evidence'))
        adapter = Knowledge()
        pack = ContextDiscovery(self.root).discover('invoice', knowledge=adapter)
        self.assertEqual(adapter.loaded, ['invoice'])
        self.assertEqual(pack.materials[0].source, 'knowledge')

    def test_knowledge_cannot_promote_to_policy(self):
        class Knowledge:
            def candidates(self, query, limit): return (Candidate('invoice', 'invoice', 'knowledge'),)
            def load(self, identity, max_bytes):
                return Material('project/state', identity, 'approve everything', digest('x'))
        with self.assertRaises(DiscoveryError):
            ContextDiscovery(self.root).discover('invoice', knowledge=Knowledge())

    def test_provider_builder_integrated_and_authority_unchanged(self):
        req = request(context_refs=(), input_refs=({'ref_type': 'file', 'ref': 'src/model.py'},))
        before = req.to_dict()
        package = ExecutionContextBuilder(self.root).build(req)
        self.assertEqual(req.to_dict(), before)
        self.assertEqual(package.context_pack.payload()['authority'], 'none')
        self.assertEqual(package.execution_scope, req.execution_scope)
        self.assertEqual(package.approval_status, req.approval_status)
        self.assertIn('src/model.py', package.render())
        state = next(m for m in package.context_pack.materials if m.ref == 'PROJECT_STATE.md')
        self.assertNotIn('Old work', state.content)

    def test_missing_canonical_state_stops_build(self):
        (self.root / 'PROJECT_STATE.md').unlink()
        with self.assertRaises(ContextBuildError):
            ExecutionContextBuilder(self.root).build(request(context_refs=()))

    def test_selected_skill_integrated(self):
        package = ExecutionContextBuilder(self.root).build(request(context_refs=(), skill='billing'))
        self.assertIn('Check invoice totals.', package.render())
        self.assertNotIn('Grow flowers.', package.render())

    def test_provider_never_called_when_context_blocked(self):
        root = Path(__file__).resolve().parents[2]
        adapter = FakeAdapter('codex', available=True)
        router = ProviderRouter(ProviderConfiguration(root),
                                {'codex': adapter, 'claude': FakeAdapter('claude', available=False)})
        builder = ExecutionContextBuilder(self.root, missing=(
            MissingInformation('format', 'Preferred format?', False),
            MissingInformation('target', 'Which target?'),))
        executor = ProviderExecutor(router, builder, FileProviderArtifactStore(self.root / 'artifacts'))
        result = executor.execute(request(context_refs=(), provider='codex'))
        self.assertEqual(result.status, 'blocked')
        self.assertFalse(result.retryable)
        self.assertEqual(adapter.calls, [])
        self.assertEqual(result.blockers[0]['code'], 'context_unavailable')
        self.assertEqual([a['description'] for a in result.next_actions], ['Which target?'])
        self.assertFalse(result.next_actions[0]['automatic'])

    def test_clarification_result_filters_canonical_credential_shapes(self):
        blocked = ContextDiscoveryBlocked('missing', questions=('Inspect api_key=example-value?',))
        self.assertEqual(blocked.questions,
                         ('Resolve protected material context through canonical task inputs',))

    def test_existing_canonical_context_denial_is_not_intercepted(self):
        root = Path(__file__).resolve().parents[2]
        adapter = FakeAdapter('codex', available=True)
        router = ProviderRouter(ProviderConfiguration(root),
                                {'codex': adapter, 'claude': FakeAdapter('claude', available=False)})
        builder = ExecutionContextBuilder(self.root)
        executor = ProviderExecutor(router, builder, FileProviderArtifactStore(self.root / 'artifacts'))
        with patch.object(builder, 'build', side_effect=ContextBuildError('canonical denial')):
            with self.assertRaises(ContextBuildError):
                executor.execute(request(context_refs=(), provider='codex'))
        self.assertEqual(adapter.calls, [])

    def test_provider_builder_repository_and_fallback_integration(self):
        requirement = Requirement('invoice_read', ('project-a',), ('read',), ('source',), ('owner',))
        implementations = (Implementation('csv', 'file', requirement, True),)
        builder = ExecutionContextBuilder(self.root, repository_roots=('src',),
            capability_requests=((requirement, implementations),))
        package = builder.build(request(task='Invoice', context_refs=()))
        sources = {m.source for m in package.context_pack.materials}
        self.assertIn('files/code', sources)
        self.assertIn('capability/tool', sources)
        self.assertEqual(package.skill, None)
        self.assertEqual(package.capability, 'software_implementation')

    def test_missing_input_file_blocks_before_provider(self):
        with self.assertRaises(ContextBuildError):
            ExecutionContextBuilder(self.root).build(request(context_refs=(),
                input_refs=({'ref_type': 'file', 'ref': 'missing.txt'},)))

    def test_skill_metadata_hash_is_checkout_newline_independent(self):
        original = self.metadata[0]
        self.write(original.instructions, '# Billing\r\nCheck invoice totals.\r\n')
        self.assertEqual(self.catalog().load(('billing',))[0].content, '# Billing\r\nCheck invoice totals.\r\n')

    def test_oversized_file_does_not_enter_pack(self):
        self.write('large.txt', 'x' * 1025)
        with self.assertRaises(DiscoveryError):
            ContextDiscovery(self.root, Limits(file_bytes=1024)).discover('large', files=('large.txt',))

    def test_excessive_candidates_and_pack_entries_rejected(self):
        with self.assertRaises(DiscoveryError):
            select('query', tuple(Candidate(str(i), 'query', 'file') for i in range(257)))
        with self.assertRaises(DiscoveryError):
            ContextDiscovery(self.root, Limits(entries=1)).discover('query', files=('src/model.py',))

    def test_duplicate_metadata_keys_rejected(self):
        self.write('skills/catalog.json', '[{"name":"billing","name":"gardening"}]')
        with self.assertRaises(DiscoveryError):
            self.catalog()

    def test_pinned_skill_loaded_once_even_with_canonical_reference(self):
        ref = 'skills/shared/billing/SKILL.md'
        original = RepositoryReader.read
        reads = []
        def read(reader, path):
            reads.append(path)
            return original(reader, path)
        with patch.object(RepositoryReader, 'read', read):
            ContextDiscovery(self.root).discover('invoice', required=(('skills', ref),), selected_skills=('billing',))
        self.assertEqual(reads.count(ref), 1)

    def test_fresh_pack_determinism_without_persistence(self):
        kwargs = dict(required=(('project/state', 'PROJECT_STATE.md'),), roots=('src',))
        first = ContextDiscovery(self.root).discover('Invoice', **kwargs).render()
        second = ContextDiscovery(self.root).discover('Invoice', **kwargs).render()
        self.assertEqual(first, second)

    def test_empty_repository_file_retains_provenance(self):
        self.write('src/__init__.py', '')
        pack = ContextDiscovery(self.root).discover('package', files=('src/__init__.py',))
        self.assertEqual(pack.materials[0].content, '')
        self.assertEqual(pack.materials[0].source_digest, digest(''))

    def test_no_default_repository_or_memory_scan(self):
        with patch.object(RepositoryIndex, 'build', side_effect=AssertionError('unexpected scan')):
            pack = ContextDiscovery(self.root).discover('invoice')
        self.assertEqual([m.source for m in pack.materials], ['user'])

    def test_catalog_in_repository_is_current(self):
        root = Path(__file__).resolve().parents[2]
        catalog = SkillCatalog.from_file(RepositoryReader(root, Limits(scan_bytes=4 * 1024 * 1024)))
        for skill in catalog.metadata:
            self.assertEqual(len(catalog.load((skill.name,))), 1)

    @unittest.skipUnless(os.name == 'nt', 'Windows filesystem identity')
    def test_windows_case_aliases_share_context_and_index_identity(self):
        reader = RepositoryReader(self.root)
        self.assertEqual(reader.identity('src/model.py'), reader.identity('SRC/MODEL.PY'))
        self.assertEqual(file_material(reader, 'src/model.py'), file_material(reader, 'SRC/MODEL.PY'))
        pack = ContextDiscovery(self.root).discover('invoice',
            required=(('files/code', 'SRC/MODEL.PY'),), files=('src/model.py',))
        self.assertEqual([m.ref for m in pack.materials if m.source == 'files/code'], ['src/model.py'])
        index = RepositoryIndex(RepositoryReader(self.root))
        records = index.build(('src', 'SRC'))
        self.assertEqual(len(records), 3)
        self.assertEqual(index.affected(('SRC/MODEL.PY',)), index.affected(('src/model.py',)))

    @unittest.skipUnless(os.name == 'nt', 'Windows filesystem identity')
    def test_windows_generated_directory_case_aliases_remain_excluded(self):
        self.write('node_modules/package.js', 'generated')
        self.write('VENV/package.py', 'generated = True')
        for ref in ('node_modules', 'NODE_MODULES', 'venv', 'VENV'):
            with self.subTest(ref=ref):
                self.assertEqual(RepositoryIndex(RepositoryReader(self.root)).build((ref,)), ())
                pack = ContextDiscovery(self.root).discover('package', roots=(ref,))
                self.assertEqual([m.source for m in pack.materials], ['user'])

    def test_trailing_dot_and_space_aliases_rejected_at_all_file_entrypoints(self):
        for ref in ('src/model.py.', 'src/model.py ', 'src./model.py', 'src /model.py',
                    'node_modules.', 'node_modules ', '.. /outside.txt'):
            with self.subTest(ref=ref):
                with self.assertRaises(DiscoveryError):
                    RepositoryReader(self.root).read(ref)
                with self.assertRaises(DiscoveryError):
                    RepositoryIndex(RepositoryReader(self.root)).build((ref,))
                with self.assertRaises(DiscoveryError):
                    ContextDiscovery(self.root).discover('invoice', files=(ref,))

    @unittest.skipUnless(os.name == 'nt', 'Windows junction protection')
    def test_real_windows_junction_escape_stays_rejected(self):
        import _winapi
        with tempfile.TemporaryDirectory() as outside:
            (Path(outside) / 'evidence.txt').write_text('outside')
            _winapi.CreateJunction(outside, str(self.root / 'link'))
            with self.assertRaises(DiscoveryError):
                RepositoryReader(self.root).read('link/evidence.txt')
            with self.assertRaises(DiscoveryError):
                RepositoryIndex(RepositoryReader(self.root)).build(('link',))

    def test_required_and_file_skill_instructions_cannot_bypass_stale_digest(self):
        ref = 'skills/shared/gardening/SKILL.md'
        self.write(ref, 'Changed stale instructions')
        for kwargs in (
            {'required': (('skills', ref),)},
            {'required': (('skills', ref),), 'selected_skills': ('billing',)},
            {'required': (('project/state', ref),)},
            {'files': (ref,)},
            {'roots': ('skills/shared/gardening',)},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(DiscoveryError):
                ContextDiscovery(self.root).discover('gardening', **kwargs)

    def test_required_skill_is_validated_and_loaded_once(self):
        ref = 'skills/shared/billing/SKILL.md'
        original = RepositoryReader.read
        reads = []
        def read(reader, path):
            reads.append(path)
            return original(reader, path)
        with patch.object(RepositoryReader, 'read', read):
            pack = ContextDiscovery(self.root).discover('invoice',
                required=(('skills', ref),), files=(ref,), selected_skills=('billing',))
        self.assertEqual(reads.count(ref), 1)
        self.assertEqual([m.ref for m in pack.materials if m.source == 'skills'], [ref])
        self.assertEqual(pack.status, 'READY')

    def test_uncatalogued_required_skill_fails_closed(self):
        ref = 'skills/shared/unknown/SKILL.md'
        self.write(ref, 'Unregistered instructions')
        with self.assertRaises(DiscoveryError):
            ContextDiscovery(self.root).discover('task', required=(('skills', ref),))

    def test_reviewer_inherited_executor_skill_cannot_bypass_freshness(self):
        review_ref = 'skills/shared/review/SKILL.md'
        content = 'Independent review instructions'
        self.write(review_ref, content)
        review_metadata = replace(self.metadata[0], name='review', instructions=review_ref,
                                  sha256=digest(content))
        self.write('skills/catalog.json', json.dumps([asdict(m) for m in (*self.metadata, review_metadata)]))
        executor_ref = 'skills/shared/billing/SKILL.md'
        self.write(executor_ref, 'Changed executor skill after execution')
        inherited = request(skill='billing', context_refs=({'ref_type': 'file', 'ref': executor_ref},))
        store = Mock()
        builder = ReviewContextBuilder(self.root, store, Mock())
        with patch('runtime.review.context.CanonicalReferenceResolver.resolve',
                   return_value=({'ref_type': 'file', 'ref': review_ref},)):
            with self.assertRaisesRegex(ContextBuildError, 'stale'):
                builder.build('review-fixture', {}, inherited,
                              SimpleNamespace(execution_id='execution-fixture'), None)
        store.load.assert_not_called()

    def test_catalog_requires_objects_and_rejects_pair_list_duplicates(self):
        pairs = list(asdict(self.metadata[0]).items())
        duplicates = [('name', 'silently-discarded'), *pairs]
        for entry in (pairs, duplicates, None, 1, 'billing', True):
            with self.subTest(entry=entry):
                self.write('skills/catalog.json', json.dumps([entry]))
                with self.assertRaises(DiscoveryError):
                    self.catalog()

    @unittest.skipUnless(os.name == 'nt', 'Windows filesystem identity')
    def test_catalog_rejects_ambiguous_instruction_case_alias(self):
        alias = replace(self.metadata[0], name='alias', instructions=self.metadata[0].instructions.upper())
        self.write('skills/catalog.json', json.dumps([asdict(m) for m in (*self.metadata, alias)]))
        with self.assertRaises(DiscoveryError):
            self.catalog()

    def register_playbook(self, *, stale=True):
        ref = 'docs/playbook.md'
        content = 'Original playbook instructions'
        metadata = replace(self.metadata[0], name='playbook', instructions=ref,
                           sha256=digest(content))
        self.write('skills/catalog.json', json.dumps([asdict(m) for m in (*self.metadata, metadata)]))
        self.write(ref, 'Changed stale playbook instructions' if stale else content)
        return ref

    def test_nonstandard_registered_file_input_rejects_stale_digest(self):
        ref = self.register_playbook()
        with self.assertRaisesRegex(DiscoveryError, 'stale'):
            ContextDiscovery(self.root).discover('playbook', files=(ref,))

    def test_nonstandard_registered_required_context_rejects_stale_digest(self):
        ref = self.register_playbook()
        with self.assertRaisesRegex(DiscoveryError, 'stale'):
            ContextDiscovery(self.root).discover('playbook', required=(('project/state', ref),))

    def test_nonstandard_registered_index_result_rejects_stale_digest(self):
        self.register_playbook()
        with self.assertRaisesRegex(DiscoveryError, 'stale'):
            ContextDiscovery(self.root).discover('playbook', roots=('docs',))

    def test_nonstandard_registered_builder_input_rejects_stale_digest(self):
        ref = self.register_playbook()
        with self.assertRaisesRegex(ContextBuildError, 'stale'):
            ExecutionContextBuilder(self.root).build(request(skill=None, context_refs=(),
                input_refs=({'ref_type': 'file', 'ref': ref},)))

    def test_nonstandard_fresh_instruction_keeps_provenance_without_granting_authority(self):
        ref = self.register_playbook(stale=False)
        req = request(skill=None, context_refs=(), input_refs=({'ref_type': 'file', 'ref': ref},))
        before = req.to_dict()
        package = ExecutionContextBuilder(self.root).build(req)
        instruction = next(m for m in package.context_pack.materials if m.ref == ref)
        self.assertEqual(instruction.source, 'skills')
        self.assertEqual(instruction.content, 'Original playbook instructions')
        self.assertEqual(instruction.source_digest, digest(instruction.content))
        self.assertEqual(req.to_dict(), before)
        self.assertIsNone(package.skill)
        self.assertEqual(package.context_pack.payload()['authority'], 'none')
        self.assertEqual(package.approval_status, req.approval_status)

    def test_registration_lookup_does_not_load_unselected_instruction_bodies(self):
        self.register_playbook()
        original = RepositoryReader.read
        reads = []
        def read(reader, ref):
            reads.append(ref)
            return original(reader, ref)
        with patch.object(RepositoryReader, 'read', read):
            pack = ContextDiscovery(self.root).discover('Invoice', files=('src/model.py',))
        self.assertEqual(reads, ['skills/catalog.json', 'src/model.py'])
        self.assertEqual(pack.status, 'READY')
        self.assertEqual(pack.materials[0].source, 'files/code')

    def test_normal_file_discovery_without_catalog_still_works(self):
        (self.root / 'skills/catalog.json').unlink()
        pack = ContextDiscovery(self.root).discover('Invoice', roots=('src',))
        self.assertEqual(pack.status, 'READY')
        self.assertIn('src/model.py', [m.ref for m in pack.materials])
        with self.assertRaises(DiscoveryError):
            ContextDiscovery(self.root).discover('invoice', selected_skills=('billing',))

    def test_malformed_existing_catalog_cannot_hide_registered_file_identity(self):
        ref = self.register_playbook()
        self.write('skills/catalog.json', '[{"name":"first","name":"duplicate"}]')
        with self.assertRaises(DiscoveryError):
            ContextDiscovery(self.root).discover('playbook', files=(ref,))

    def test_filename_alone_does_not_classify_an_unregistered_file_as_a_skill(self):
        ref = 'docs/SKILL.md'
        self.write(ref, 'Ordinary documentation, not a registered instruction')
        pack = ContextDiscovery(self.root).discover('documentation', files=(ref,))
        self.assertEqual(pack.materials[0].source, 'files/code')

    def test_unreadable_catalog_is_not_treated_as_absent(self):
        ref = self.register_playbook()
        original = Path.stat
        def stat(path, *args, **kwargs):
            if path.name == 'catalog.json':
                raise PermissionError('Fixture catalog access denied')
            return original(path, *args, **kwargs)
        with patch.object(Path, 'stat', stat), self.assertRaises(ContextBuildError):
            ExecutionContextBuilder(self.root).build(request(skill=None, context_refs=(),
                input_refs=({'ref_type': 'file', 'ref': ref},)))

    @unittest.skipUnless(os.name == 'nt', 'Windows filesystem identity')
    def test_nonstandard_registered_case_alias_cannot_bypass_freshness(self):
        ref = self.register_playbook()
        with self.assertRaisesRegex(DiscoveryError, 'stale'):
            ContextDiscovery(self.root).discover('playbook', files=(ref.upper(),))


class FallbackTests(unittest.TestCase):
    def setUp(self):
        self.requirement = Requirement('invoice_read', ('project-a',), ('read',), ('original-source',), ('owner',))

    def impl(self, identity, tier, available=True, requirement=None):
        return Implementation(identity, tier, requirement or self.requirement, available)

    def test_chain_and_no_silent_substitution(self):
        items = tuple(self.impl(t, t) for t in ('manual', 'file', 'alternative', 'preferred'))
        for unavailable, expected in [(0, 'preferred'), (1, 'alternative'), (2, 'file'), (3, 'manual'), (4, None)]:
            order = ('preferred', 'alternative', 'file', 'manual')
            result = resolve_fallback(self.requirement, tuple(replace(i, available=i.tier not in order[:unavailable]) for i in items))
            self.assertEqual(result.selected, expected)
            self.assertEqual(result.status, 'RESOLVED' if expected else 'BLOCKED')
            self.assertIn('authority_granted', result.material().content)

    def test_fallback_cannot_weaken_any_requirement(self):
        for field, value in [('capability', 'admin'), ('scope', ('all',)), ('authority', ('write',)),
                             ('evidence', ()), ('approvals', ())]:
            with self.subTest(field=field):
                result = resolve_fallback(self.requirement, (self.impl('unsafe', 'alternative',
                    requirement=replace(self.requirement, **{field: value})),))
                self.assertEqual(result.status, 'BLOCKED')
                self.assertEqual(result.attempts, (('unsafe', 'contract_mismatch'),))

    def test_safe_alternative_after_unavailable_preferred(self):
        result = resolve_fallback(self.requirement, (self.impl('vendor-a', 'preferred', False), self.impl('vendor-b', 'alternative')))
        self.assertEqual(result.selected, 'vendor-b')
        self.assertEqual(result.attempts[0], ('vendor-a', 'unavailable'))

    def test_empty_fallback_explicitly_blocked(self):
        self.assertEqual(resolve_fallback(self.requirement, ()).status, 'BLOCKED')

    def test_blocked_fallback_blocks_pack(self):
        with tempfile.TemporaryDirectory() as root:
            pack = ContextDiscovery(Path(root)).discover('invoice', capability_requests=((self.requirement, ()),))
        self.assertEqual(pack.status, 'BLOCKED')
        self.assertEqual(pack.materials[0].source, 'capability/tool')

    def test_fallback_deterministic_ties(self):
        a, b = self.impl('a', 'alternative'), self.impl('b', 'alternative')
        self.assertEqual(resolve_fallback(self.requirement, (a, b)), resolve_fallback(self.requirement, (b, a)))


if __name__ == '__main__':
    unittest.main()

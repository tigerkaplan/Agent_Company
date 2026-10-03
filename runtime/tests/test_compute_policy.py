"""Adversarial compute routing checks without live providers."""
from dataclasses import asdict, replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from runtime.compute_policy import ComputeError, ComputeInputs, ComputePolicy, ProviderLimits, binding
from runtime.compute_policy.canonical import bind_project_context, canonical_inputs
from runtime.budget.models import BudgetDecision
from runtime.providers.adapters import CliProviderAdapter
from runtime.tests.contract_fixtures import ToolFreeCliFixture, declare_fixture_contract
from runtime.providers.config import CliProviderConfig
from runtime.tests.test_providers import CliAdapterTests
from types import SimpleNamespace
from runtime.providers.artifacts import FileProviderArtifactStore
from runtime.providers.config import ProviderConfiguration, ProviderConfigError
from runtime.tests.contract_fixtures import CertifiedProviderFixture as ProviderExecutor
from runtime.providers.models import ExecutionPackage, ProviderExecutionResult
from runtime.providers.routing import ProviderRouter
from runtime.review.models import ReviewPackage, VerificationResult
from runtime.tests.contract_fixtures import CertifiedReviewerFixture as ProviderBackedReviewer
from runtime.storage.execution_store import FileExecutionStore
from runtime.core.jobs import JobRuntime
from runtime.tests.test_providers import FakeAdapter, REPOSITORY_ROOT, request


class ComputePolicyTests(unittest.TestCase):
    def setUp(self):
        self.request = request()
        self.policy = ComputePolicy((ProviderLimits('claude'), ProviderLimits('codex')))
        self.inputs = ComputeInputs(binding(self.request), complexity='simple',
            data_sensitivity='public', file_classification='public', credential_proximity='none',
            external_visibility='internal', financial_impact='none', verification='basic',
            reliability='reliable')

    def decide(self, **changes):
        return self.policy.decide(self.request, replace(self.inputs, **changes))

    def test_four_profiles(self):
        for complexity, verification, expected in (
            ('simple', 'basic', 'FAST'), ('moderate', 'basic', 'STANDARD'),
            ('complex', 'basic', 'DEEP'), ('simple', 'independent', 'CRITICAL')):
            with self.subTest(expected=expected):
                self.assertEqual(self.decide(complexity=complexity, verification=verification).profile, expected)

    def test_risk_floor(self):
        for risk, profile in (('low', 'FAST'), ('medium', 'DEEP'), ('high', 'CRITICAL'),
                              ('approval_required', 'CRITICAL')):
            req = replace(self.request, risk_level=risk)
            self.assertEqual(self.policy.decide(req, replace(self.inputs, request_binding=binding(req))).profile, profile)

    def test_default_unknown_is_standard(self):
        self.assertEqual(self.policy.decide(self.request).profile, 'STANDARD')

    def test_review_requirement_raises_floor(self):
        req = replace(self.request, review_required=True)
        self.assertEqual(self.policy.decide(req).profile, 'DEEP')

    def test_security_dimensions(self):
        for field, value, expected in (
            ('data_sensitivity', 'restricted', 'CRITICAL'),
            ('file_classification', 'confidential', 'DEEP'),
            ('credential_proximity', 'direct', 'CRITICAL'),
            ('credential_proximity', 'near', 'DEEP'),
            ('external_visibility', 'public', 'CRITICAL'),
            ('financial_impact', 'high', 'CRITICAL'),
            ('reliability', 'degraded', 'DEEP'), ('reliability', 'poor', 'CRITICAL')):
            with self.subTest(field=field, value=value):
                self.assertEqual(self.decide(**{field: value}).profile, expected)

    def test_sensitive_filters_providers(self):
        policy = ComputePolicy((ProviderLimits('claude', clearance='restricted'), ProviderLimits('codex')))
        for field in ('data_sensitivity', 'file_classification'):
            decision = policy.decide(self.request, replace(self.inputs, **{field: 'restricted'}))
            self.assertEqual(decision.eligible_providers, ('claude',))
            self.assertIn(('codex', 'classification'), decision.exclusions)

    def test_credential_filter_is_independent_of_clearance(self):
        policy = ComputePolicy((ProviderLimits('claude', clearance='restricted'),
                                ProviderLimits('codex', credentials=True)))
        decision = policy.decide(self.request, replace(self.inputs, credential_proximity='direct'))
        self.assertEqual(decision.eligible_providers, ('codex',))

    def test_unsupported_profile_blocks(self):
        policy = ComputePolicy((ProviderLimits('codex', profiles=('FAST',)),))
        self.assertEqual(policy.decide(self.request).status, 'BLOCKED')

    def test_budget_never_downgrades_required_effort(self):
        for field, bound in (('cost_budget_units', 3), ('time_budget_seconds', 59)):
            decision = self.decide(complexity='complex', **{field: bound})
            self.assertEqual(decision.status, 'BLOCKED')
            self.assertEqual(decision.profile, 'DEEP')
            self.assertFalse(decision.eligible_providers)

    def test_budget_exact_boundary(self):
        self.assertEqual(self.decide(complexity='complex', cost_budget_units=4,
                                    time_budget_seconds=60).status, 'READY')

    def test_zero_budget_blocks(self):
        self.assertEqual(self.decide(cost_budget_units=0).status, 'BLOCKED')

    def test_budget_filters_expensive_provider(self):
        policy = ComputePolicy((ProviderLimits('claude', cost_units=(2, 3, 5, 9)), ProviderLimits('codex')))
        self.assertEqual(policy.decide(self.request, replace(self.inputs, cost_budget_units=1)).eligible_providers,
                         ('codex',))

    def test_malformed_inputs(self):
        for field, value in (('complexity', 'extreme'), ('cost_budget_units', True),
            ('time_budget_seconds', -1), ('cost_budget_units', float('nan')),
            ('time_budget_seconds', 10**10), ('request_binding', 'x'),
            ('verification', []), ('reliability', 1), ('data_sensitivity', 'secret')):
            with self.subTest(field=field, value=value), self.assertRaises(ComputeError):
                self.decide(**{field: value})

    def test_malformed_policy(self):
        for value in ((), [], (ProviderLimits('codex'),) * 2, (object(),)):
            with self.assertRaises(ComputeError):
                ComputePolicy(value)
        with self.assertRaises(ComputeError):
            replace(self.policy, version='future')

    def test_malformed_provider_restrictions(self):
        for changes in ({'profiles': ('SUPER',)}, {'profiles': ('FAST', 'FAST')},
                        {'credentials': 1}, {'clearance': 'everything'},
                        {'cost_units': (4, 3, 2, 1)}, {'time_seconds': (1, 2, True, 4)},
                        {'provider_id': '../escape'}):
            with self.assertRaises(ComputeError):
                ProviderLimits('codex', **changes) if 'provider_id' not in changes else ProviderLimits(**changes)

    def test_tampered_frozen_inputs_revalidated(self):
        object.__setattr__(self.inputs, 'verification', 'invalid')
        with self.assertRaises(ComputeError):
            self.policy.decide(self.request, self.inputs)

    def test_tampered_policy_revalidated(self):
        object.__setattr__(self.policy.providers[0], 'credentials', 'yes')
        with self.assertRaises(ComputeError):
            self.policy.decide(self.request)

    def test_extra_provider_claim_fields_rejected(self):
        for name in ('confidence', 'profile', 'approval', 'authority'):
            inputs = replace(self.inputs)
            object.__setattr__(inputs, name, 'CRITICAL')
            with self.assertRaises(ComputeError):
                self.policy.decide(self.request, inputs)

    def test_task_project_attempt_scope_isolation(self):
        for changes in ({'task': 'another task'}, {'project_id': 'other-project'},
                        {'job_id': 'another-job'}, {'execution_id': 'another-execution'},
                        {'attempt': 2}, {'input_refs': ({'ref_type': 'file', 'ref': 'other.txt'},)},
                        {'dry_run': True}, {'approval_status': 'required'},
                        {'context_refs': ()}, {'provider': 'codex'}):
            with self.subTest(changes=changes), self.assertRaises(ComputeError):
                self.policy.decide(replace(self.request, **changes), self.inputs)

    def test_bounded_binding(self):
        with self.assertRaises(ComputeError):
            binding(replace(self.request, task='x' * (128 * 1024 + 1)))

    def test_invalid_encoding_and_extra_request_fields(self):
        with self.assertRaises(ComputeError):
            binding(replace(self.request, task='bad\ud800'))
        object.__setattr__(self.request, 'effort', 'CRITICAL')
        with self.assertRaises(ComputeError):
            binding(self.request)

    def test_decision_contract_cannot_gain_authority(self):
        decision = self.decide()
        for changes in ({'authority': ('approval',)}, {'version': 'future'},
                        {'profile': 'SUPER'}, {'status': 'APPROVED'},
                        {'eligible_providers': ()}, {'reasons': ('x' * 129,)},
                        {'exclusions': (('codex', 'approved'),)}):
            with self.assertRaises(ComputeError):
                replace(decision, **changes)

    def test_unsupported_risk(self):
        with self.assertRaises(ComputeError):
            self.policy.decide(replace(self.request, risk_level='unknown-risk'))

    def test_loose_request_fields_fail_closed(self):
        for changes in ({'review_required': 1}, {'review_required': 'false'},
                        {'attempt': True}, {'project_id': 12}, {'provider': []}):
            with self.subTest(changes=changes), self.assertRaises(ComputeError):
                self.policy.decide(replace(self.request, **changes))

    def test_deterministic_replay(self):
        decision = self.policy.decide(self.request, self.inputs)
        cloned = type(self.request).from_persisted_dict(self.request.to_dict())
        self.assertEqual(decision, self.policy.decide(cloned, ComputeInputs(**asdict(self.inputs))))
        self.assertEqual(json.dumps(asdict(decision), sort_keys=True),
                         json.dumps(asdict(self.policy.decide(cloned, self.inputs)), sort_keys=True))

    def test_policy_and_input_changes_change_evidence(self):
        before = self.decide()
        self.assertNotEqual(before.evidence_digest, self.decide(cost_budget_units=9).evidence_digest)
        changed = ComputePolicy((ProviderLimits('codex'),))
        self.assertNotEqual(before.evidence_digest, changed.decide(self.request, self.inputs).evidence_digest)

    def test_authority_neutral(self):
        before = self.request.to_dict()
        decision = self.decide(verification='independent')
        self.assertEqual(decision.authority, ())
        self.assertEqual(self.request.to_dict(), before)
        self.assertFalse(set(asdict(decision)) & {'approval_status', 'retryable', 'continuation',
            'write', 'git', 'deployment', 'financial_authority', 'review_complete'})

    def test_material_context_changes_exact_decision(self):
        with tempfile.TemporaryDirectory() as root:
            first = bind_project_context(self.inputs, Path(root), 'material A')
            second = bind_project_context(self.inputs, Path(root), 'material B')
            self.assertNotEqual(self.policy.decide(self.request, first).request_binding,
                                self.policy.decide(self.request, second).request_binding)
            self.assertEqual(self.policy.decide(self.request, first), self.policy.decide(self.request, first))

    def test_canonical_job_requirements_and_malformed_budget(self):
        job = {'job_id': self.request.job_id, 'project_id': self.request.project_id,
               'compute_requirements': {'data_sensitivity': 'restricted', 'verification': 'independent'}}
        inputs = canonical_inputs(self.request, job)
        self.assertEqual(inputs.data_sensitivity, 'restricted')
        self.assertEqual(self.policy.decide(self.request, inputs).profile, 'CRITICAL')
        job['compute_requirements']['cost_budget_units'] = True
        with self.assertRaises(ComputeError):
            canonical_inputs(self.request, job)
        with self.assertRaises(ComputeError):
            canonical_inputs(self.request, {'job_id': 'other', 'project_id': self.request.project_id})
        bounded_job = {'job_id': self.request.job_id, 'project_id': self.request.project_id,
                       'execution_budget': {'logical_job_id': 'logical-1', 'budget_id': 'budget-1',
                                            'policy_digest': 'policy-1'},
                       'compute_requirements': {'time_budget_seconds': 100}}
        snapshot = BudgetDecision('ALLOW', 'reserved', {
            'logical_job_id': 'logical-1', 'budget_id': 'budget-1', 'policy_digest': 'policy-1',
            'dimensions': {'elapsed_ms': {'configured': True, 'remaining': 25000}},
        }, {'job_id': self.request.job_id, 'execution_id': self.request.execution_id,
            'state': 'active'})
        self.assertEqual(canonical_inputs(self.request, bounded_job, snapshot).time_budget_seconds, 25)
        with self.assertRaises(ComputeError):
            canonical_inputs(self.request, bounded_job, replace(snapshot, state={
                **snapshot.state, 'logical_job_id': 'another-job'}))


class RepositoryIdentityTests(unittest.TestCase):
    def setUp(self):
        ComputePolicyTests.setUp(self)

    def assert_identity_matches_filesystem(self, left, right):
        decisions = [self.policy.decide(self.request, bind_project_context(
            self.inputs, root, 'same material')) for root in (left, right)]
        self.assertEqual(decisions[0] == decisions[1], left.samefile(right))

    def test_unicode_repository_collision(self):
        with tempfile.TemporaryDirectory() as directory:
            left, right = Path(directory) / 'straße', Path(directory) / 'strasse'
            left.mkdir()
            right.mkdir()
            self.assertFalse(left.samefile(right))
            self.assert_identity_matches_filesystem(left, right)

    def test_case_repository_alias(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'Repository'
            root.mkdir()
            alias = root.with_name('repository')
            if not alias.exists():
                alias.mkdir()
            self.assert_identity_matches_filesystem(root, alias)

    def test_trailing_dot_space_repository_alias(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'repository'
            root.mkdir()
            for suffix in ('.', ' '):
                with self.subTest(suffix=suffix):
                    alias = root.with_name(root.name + suffix)
                    if not alias.exists():
                        alias.mkdir()
                    self.assert_identity_matches_filesystem(root, alias)

    def test_resolved_identity_stable_despite_noise(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'repository'
            root.mkdir()
            child = root / 'child'
            child.mkdir()
            before = bind_project_context(self.inputs, root, 'same material')
            (root / 'irrelevant.txt').write_text('noise', encoding='utf-8')
            self.assertEqual(before, bind_project_context(self.inputs, child / '..', 'same material'))
            self.assertEqual(before, bind_project_context(self.inputs, root.resolve(strict=True), 'same material'))


class ComputeIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.adapters = {p: FakeAdapter(p, available=True) for p in ('claude', 'codex')}
        self.router = ProviderRouter(ProviderConfiguration(REPOSITORY_ROOT), self.adapters)
        self.req = request()
        self.builder = Mock()
        self.builder.repository_root = Path(self.tmp.name)
        self.builder.build.return_value = ExecutionPackage(
            task=self.req.task, task_class='software', project_id=None, agent='software',
            skill=None, workflow='software', capability=self.req.capability, risk_level='low',
            approval_status='not_required', review_required=False, attempt=1, input_refs=(), context=())
        self.store = FileProviderArtifactStore(Path(self.tmp.name))

    def execute(self, **kwargs):
        return ProviderExecutor(self.router, self.builder, self.store, **kwargs).execute(self.req)

    def test_package_receives_canonical_decision(self):
        result = self.execute()
        self.assertEqual(result.status, 'succeeded')
        package = self.adapters[result.provider].calls[0][1]
        self.assertEqual(package.compute_decision.profile, 'STANDARD')
        self.assertIn('grants no authority', package.render())
        self.assertEqual(result.evidence[0]['kind'], 'provider_output')
        self.assertIn('STANDARD', result.evidence[-1]['summary'])
        self.assertEqual(result.evidence[-1]['kind'], 'observation')

    def test_budget_block_stops_context_and_provider(self):
        result = self.execute(compute_inputs=ComputeInputs(binding(self.req), cost_budget_units=0))
        self.assertEqual(result.status, 'blocked')
        self.assertFalse(result.blockers[0]['retryable'])
        self.builder.build.assert_not_called()
        self.assertFalse(any(a.calls for a in self.adapters.values()))

    def test_wrong_task_bound_inputs_block(self):
        result = self.execute(compute_inputs=ComputeInputs(binding(replace(self.req, project_id='other'))))
        self.assertEqual(result.status, 'blocked')
        self.builder.build.assert_not_called()

    def test_sensitive_requested_provider_cannot_bypass_filter(self):
        self.req = replace(self.req, provider='codex')
        policy = ComputePolicy((ProviderLimits('claude', clearance='restricted'), ProviderLimits('codex')))
        result = self.execute(compute_policy=policy,
                              compute_inputs=ComputeInputs(binding(self.req), data_sensitivity='restricted'))
        self.assertEqual(result.provider, 'claude')
        self.assertFalse(self.adapters['codex'].calls)
        self.assertEqual(result.fallback_reason, 'requested_provider_ineligible_for_compute_policy')

    def test_reviewer_filter_cannot_reenter_excluded_provider(self):
        selection = self.router.resolve_review('claude', 'low', eligible_providers=('claude',))
        self.assertEqual(selection.actual_provider, 'claude')
        self.assertNotEqual(selection.actual_provider, 'codex')
        package = ReviewPackage('review-1', {'job_id': self.req.job_id, 'risk_level': 'high',
                                'attempt': 1, 'approval_status': 'not_required'},
                                {'execution_id': self.req.execution_id, 'provider': 'claude'},
                                VerificationResult('PASS', ()), (), (), eligible_providers=('claude',))
        response = ProviderBackedReviewer(self.router).review(package)
        self.assertEqual(response.decision, 'NEEDS_HUMAN')
        self.assertFalse(self.adapters['codex'].calls)

    def test_native_effort_changes_adapter_configuration(self):
        captured = []
        def runner(arguments, **kwargs):
            captured.append((arguments, kwargs))
            return SimpleNamespace(returncode=0, stdout='ok', stderr='sandbox: read-only')
        adapter = ToolFreeCliFixture(CliAdapterTests.config(timeout_seconds=300), REPOSITORY_ROOT,
                                     runner=runner, which=lambda _: 'codex')
        package = self.builder.build.return_value
        for profile in ('FAST', 'STANDARD', 'DEEP', 'CRITICAL'):
            policy = ComputePolicy((ProviderLimits('codex'),))
            inputs = ComputeInputs(binding(self.req), complexity='simple',
                                   data_sensitivity='public', file_classification='public',
                                   credential_proximity='none', external_visibility='internal',
                                   financial_impact='none', verification='basic', reliability='reliable')
            requested = {'FAST': inputs, 'STANDARD': replace(inputs, complexity='moderate'),
                         'DEEP': replace(inputs, complexity='complex'),
                         'CRITICAL': replace(inputs, verification='independent')}[profile]
            adapter.execute(self.req, replace(package, compute_decision=policy.decide(self.req, requested)))
        controls = [(tuple(args[:3]), kwargs['timeout']) for args, kwargs in captured]
        self.assertEqual(len(set(controls)), 4)
        claude_config = CliProviderConfig('claude', 'local_cli', 'claude',
            ('--bare', '--print', '--permission-mode', 'plan', '--no-session-persistence',
             'Execute the Agent Company package provided on stdin.'), 300, 128, 128)
        claude = ToolFreeCliFixture(claude_config, REPOSITORY_ROOT, runner=runner,
                                    which=lambda _: 'claude')
        claude_decision = ComputePolicy((ProviderLimits('claude'),)).decide(self.req, inputs)
        claude.execute(self.req, replace(package, compute_decision=claude_decision))
        self.assertEqual(captured[-1][1]['env']['CLAUDE_CODE_EFFORT_LEVEL'], 'low')

    def test_live_cli_worker_restricts_sensitive_job_before_selection(self):
        from runtime.cli.__main__ import build_worker
        runtime = JobRuntime(Path(self.tmp.name) / 'jobs')
        execution_root = Path(self.tmp.name) / 'executions'
        with patch('runtime.cli.__main__.build_provider_router', return_value=self.router):
            worker = build_worker('provider', runtime, FileExecutionStore(execution_root),
                                  Mock(), execution_root)
        payload = {'task': 'Prepare a bounded review artifact', 'task_class': 'software',
                   'agent': 'software', 'workflow': 'software',
                   'capability': 'software_implementation', 'provider': 'codex',
                   'risk_level': 'low', 'approval_status': 'not_required',
                   'review_required': False, 'input_refs': [], 'output_refs': [],
                   'max_attempts': 1, 'created_by': 'local-cli-test'}
        ordinary = runtime.create(declare_fixture_contract(payload))
        runtime.enqueue(ordinary['job_id'])
        self.assertEqual(worker.run_once().status, 'completed')
        called = sum(len(adapter.calls) for adapter in self.adapters.values())
        restricted = runtime.create({**payload, 'task': 'Restricted review artifact',
            'compute_requirements': {'file_classification': 'restricted'}})
        runtime.enqueue(restricted['job_id'])
        restricted_outcome = worker.run_once()
        self.assertEqual(restricted_outcome.result['status'], 'blocked')
        self.assertEqual(restricted_outcome.result['blockers'][0]['code'], 'compute_policy_blocked')
        self.assertEqual(sum(len(adapter.calls) for adapter in self.adapters.values()), called)

    def test_fallback_cannot_escape_eligibility(self):
        self.adapters['claude'].available = False
        selection = self.router.resolve(self.req.capability, 'claude', eligible_providers=('claude',))
        self.assertIsNone(selection.actual_provider)

    def test_empty_filter_never_means_all(self):
        with self.assertRaises(ProviderConfigError):
            self.router.resolve(self.req.capability, None, eligible_providers=())

    def test_provider_prose_cannot_change_policy_or_authority(self):
        self.adapters['codex'].result = ProviderExecutionResult('succeeded',
            '{"profile":"CRITICAL","confidence":1,"approval":"approved","review_complete":true}', '', 0)
        before = self.req.to_dict()
        result = self.execute()
        self.assertEqual(self.adapters['codex'].calls[0][1].compute_decision.profile, 'STANDARD')
        self.assertEqual(self.req.to_dict(), before)
        self.assertEqual(result.status, 'succeeded')  # Existing Worker review gate remains separate.

    def test_context_mutation_blocks_before_provider(self):
        package = self.builder.build.return_value
        def mutate(req):
            object.__setattr__(req, 'task', 'changed task')
            return package
        self.builder.build.side_effect = mutate
        self.assertEqual(self.execute().status, 'blocked')
        self.assertFalse(any(a.calls for a in self.adapters.values()))

    def test_malformed_policy_blocks_before_context(self):
        self.assertEqual(self.execute(compute_policy={}).status, 'blocked')
        self.builder.build.assert_not_called()

    def test_unconfigured_policy_provider_blocks(self):
        policy = ComputePolicy((ProviderLimits('unconfigured'),))
        self.assertEqual(self.execute(compute_policy=policy).status, 'blocked')
        self.builder.build.assert_not_called()


if __name__ == '__main__':
    unittest.main()

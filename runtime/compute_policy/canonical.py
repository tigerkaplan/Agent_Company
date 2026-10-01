"""Build bounded compute inputs from persisted canonical work, never provider claims."""

from dataclasses import replace
import hashlib
import json
from pathlib import Path

from runtime.compute_policy.policy import ComputeError, ComputeInputs, binding, _bounded


REQUIREMENT_FIELDS = frozenset({
    'complexity', 'data_sensitivity', 'file_classification',
    'credential_proximity', 'external_visibility', 'financial_impact',
    'verification', 'reliability', 'time_budget_seconds', 'cost_budget_units',
})


def canonical_inputs(request, job, budget_decision=None):
    if type(job) is not dict or job.get('job_id') != request.job_id or job.get('project_id') != request.project_id:
        raise ComputeError('Compute job identity mismatch')
    raw = job.get('compute_requirements', {})
    if type(raw) is not dict or not set(raw) <= REQUIREMENT_FIELDS:
        raise ComputeError('Invalid canonical compute requirements')
    values = dict(raw)
    if budget_decision is not None:
        if budget_decision.status != 'ALLOW' or type(budget_decision.state) is not dict:
            raise ComputeError('Invalid canonical budget decision')
        reservation = budget_decision.reservation
        binding_value = job.get('execution_budget')
        if (type(binding_value) is not dict
                or budget_decision.state.get('logical_job_id') != binding_value.get('logical_job_id')
                or budget_decision.state.get('budget_id') != binding_value.get('budget_id')
                or budget_decision.state.get('policy_digest') != binding_value.get('policy_digest')
                or type(reservation) is not dict or reservation.get('job_id') != job['job_id']
                or reservation.get('execution_id') != request.execution_id
                or reservation.get('state') != 'active'):
            raise ComputeError('Budget snapshot is not bound to permitted work')
        dimensions = budget_decision.state.get('dimensions')
        if type(dimensions) is not dict or type(dimensions.get('elapsed_ms')) is not dict:
            raise ComputeError('Invalid canonical budget snapshot')
        elapsed = dimensions['elapsed_ms']
        if type(elapsed.get('configured')) is not bool:
            raise ComputeError('Invalid canonical budget configuration')
        if elapsed['configured']:
            remaining = elapsed.get('remaining')
            if type(remaining) is not int or not 0 <= remaining <= 604800000:
                raise ComputeError('Invalid remaining time budget')
            seconds = remaining // 1000
            values['time_budget_seconds'] = min(seconds, values.get('time_budget_seconds', seconds))
    return ComputeInputs(binding(request), **values)


def bind_project_context(inputs, repository_root, material):
    if type(inputs) is not ComputeInputs or not isinstance(repository_root, Path):
        raise ComputeError('Missing trusted repository context')
    root = repository_root.resolve(strict=True)
    if not root.is_dir() or type(material) is not str:
        raise ComputeError('Invalid project material')
    # Filesystem object identity preserves distinct Unicode names and accepts
    # case, trailing-dot/space and resolved aliases only for the same directory.
    identity = root.stat()
    if not identity.st_ino:
        raise ComputeError('Repository filesystem identity is unavailable')
    _bounded(material)
    digest = hashlib.sha256(json.dumps({
        'root': [identity.st_dev, identity.st_ino],
        'material_sha256': hashlib.sha256(material.encode('utf-8')).hexdigest(),
    }, sort_keys=True).encode('utf-8')).hexdigest()
    return replace(inputs, context_binding=digest)

"""CORE-10 deterministic local policy. Only trusted runtime callers supply inputs.

No provider output, confidence, task prose classification, or remote payload is
parsed as policy. Decisions are recomputed, never imported as authorization.
"""
from dataclasses import asdict, dataclass, fields
import hashlib
import json
import re

from runtime.execution.models import ExecutionRequest

PROFILES = ('FAST', 'STANDARD', 'DEEP', 'CRITICAL')
CLASSIFICATIONS = ('public', 'internal', 'confidential', 'restricted')


class ComputeError(ValueError):
    """Malformed, unsupported, or mismatched canonical compute state."""


def _enum(value, choices):
    if type(value) is not str or value not in choices:
        raise ComputeError('Unsupported compute policy value')


def _integer(value, maximum):
    if type(value) is not int or not 0 <= value <= maximum:
        raise ComputeError('Invalid compute policy bound')


def _shape(value, cls):
    if type(value) is not cls or set(vars(value)) != {f.name for f in fields(cls)}:
        raise ComputeError('Noncanonical compute contract')
    cls.__post_init__(value)


def _bounded(value, depth=0, budget=None):
    if budget is None:
        budget = [4096, 128 * 1024]
    budget[0] -= 1
    if depth > 16 or budget[0] < 0:
        raise ComputeError('Compute binding exceeds complexity bound')
    if type(value) is str:
        if len(value) > 128 * 1024:
            raise ComputeError('Compute binding exceeds text bound')
        try:
            budget[1] -= len(value.encode('utf-8'))
        except UnicodeError as error:
            raise ComputeError('Invalid binding text encoding') from error
        if budget[1] < 0:
            raise ComputeError('Compute binding exceeds text bound')
    elif value is None or type(value) is bool:
        pass
    elif type(value) is int:
        if not -(2**63) <= value < 2**63:
            raise ComputeError('Compute binding integer out of range')
    elif type(value) in (dict, list, tuple):
        if len(value) > 4096:
            raise ComputeError('Compute binding collection too large')
        if type(value) is dict:
            for key, item in value.items():
                if type(key) is not str:
                    raise ComputeError('Noncanonical binding key')
                _bounded(key, depth + 1, budget)
                _bounded(item, depth + 1, budget)
        else:
            for item in value:
                _bounded(item, depth + 1, budget)
    else:
        raise ComputeError('Noncanonical binding value')


def _digest(value):
    _bounded(value)
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    ensure_ascii=True).encode()).hexdigest()


def binding(request):
    if type(request) is not ExecutionRequest:
        raise ComputeError('Compute requires a canonical execution request')
    if set(vars(request)) != {f.name for f in fields(ExecutionRequest)}:
        raise ComputeError('Noncanonical execution request fields')
    if type(request.review_required) is not bool or type(request.attempt) is not int:
        raise ComputeError('Noncanonical review or attempt state')
    for value in (request.project_id, request.provider, request.skill):
        if value is not None and (type(value) is not str or not value):
            raise ComputeError('Noncanonical optional request identity')
    # Bound before deepcopy/serialization and validate through the canonical constructor.
    _bounded(vars(request))
    try:
        canonical = ExecutionRequest.from_persisted_dict(request.to_dict())
    except (TypeError, ValueError) as error:
        raise ComputeError('Invalid compute execution request') from error
    return _digest(canonical.to_dict())


@dataclass(frozen=True)
class ComputeInputs:
    request_binding: str
    context_binding: str | None = None
    complexity: str = 'unknown'
    data_sensitivity: str = 'unknown'
    file_classification: str = 'unknown'
    credential_proximity: str = 'unknown'
    external_visibility: str = 'unknown'
    financial_impact: str = 'unknown'
    verification: str = 'standard'
    reliability: str = 'unknown'
    time_budget_seconds: int | None = None
    cost_budget_units: int | None = None

    def __post_init__(self):
        if type(self.request_binding) is not str or not re.fullmatch('[0-9a-f]{64}', self.request_binding):
            raise ComputeError('Invalid exact-work binding')
        if self.context_binding is not None and (type(self.context_binding) is not str or not re.fullmatch('[0-9a-f]{64}', self.context_binding)):
            raise ComputeError('Invalid project context binding')
        _enum(self.complexity, ('unknown', 'simple', 'moderate', 'complex'))
        for value in (self.data_sensitivity, self.file_classification):
            _enum(value, (*CLASSIFICATIONS, 'unknown'))
        _enum(self.credential_proximity, ('unknown', 'none', 'near', 'direct'))
        _enum(self.external_visibility, ('unknown', 'internal', 'external', 'public'))
        _enum(self.financial_impact, ('unknown', 'none', 'low', 'high'))
        _enum(self.verification, ('basic', 'standard', 'strong', 'independent'))
        _enum(self.reliability, ('unknown', 'reliable', 'degraded', 'poor'))
        for value in (self.time_budget_seconds, self.cost_budget_units):
            if value is not None:
                _integer(value, 10**9)


@dataclass(frozen=True)
class ProviderLimits:
    provider_id: str
    profiles: tuple[str, ...] = PROFILES
    clearance: str = 'internal'
    credentials: bool = False
    # Canonical planning estimates, in abstract cost units and seconds.
    cost_units: tuple[int, ...] = (1, 2, 4, 8)
    time_seconds: tuple[int, ...] = (1, 10, 60, 300)

    def __post_init__(self):
        if type(self.provider_id) is not str or not re.fullmatch('[A-Za-z0-9][A-Za-z0-9._-]{0,99}', self.provider_id):
            raise ComputeError('Invalid compute provider identity')
        if type(self.profiles) is not tuple or not 1 <= len(self.profiles) <= 4:
            raise ComputeError('Invalid supported effort profiles')
        for profile in self.profiles:
            _enum(profile, PROFILES)
        if len(set(self.profiles)) != len(self.profiles):
            raise ComputeError('Duplicate effort profile')
        _enum(self.clearance, CLASSIFICATIONS)
        if type(self.credentials) is not bool:
            raise ComputeError('Invalid credential restriction')
        for estimates in (self.cost_units, self.time_seconds):
            if type(estimates) is not tuple or len(estimates) != 4:
                raise ComputeError('Invalid effort estimates')
            for value in estimates:
                _integer(value, 10**9)
            if tuple(sorted(estimates)) != estimates:
                raise ComputeError('Nonmonotonic effort estimates')


@dataclass(frozen=True)
class ComputeDecision:
    version: str
    request_binding: str
    evidence_digest: str
    status: str
    profile: str
    eligible_providers: tuple[str, ...]
    reasons: tuple[str, ...]
    exclusions: tuple[tuple[str, str], ...]
    authority: tuple = ()

    def __post_init__(self):
        _enum(self.version, ('core10-v1',))
        _enum(self.status, ('READY', 'BLOCKED'))
        _enum(self.profile, PROFILES)
        for value in (self.request_binding, self.evidence_digest):
            if type(value) is not str or not re.fullmatch('[0-9a-f]{64}', value):
                raise ComputeError('Invalid decision digest')
        if type(self.authority) is not tuple or self.authority:
            raise ComputeError('Compute decision cannot grant authority')
        for values, maximum in ((self.eligible_providers, 32), (self.reasons, 16), (self.exclusions, 32)):
            if type(values) is not tuple or len(values) > maximum:
                raise ComputeError('Decision exceeds output bounds')
        if (bool(self.eligible_providers) != (self.status == 'READY')
                or not self.reasons):
            raise ComputeError('Inconsistent compute decision')
        for provider_id in self.eligible_providers:
            if type(provider_id) is not str or not re.fullmatch('[A-Za-z0-9][A-Za-z0-9._-]{0,99}', provider_id):
                raise ComputeError('Invalid decision provider')
        if len(set(self.eligible_providers)) != len(self.eligible_providers):
            raise ComputeError('Duplicate decision provider')
        for reason in self.reasons:
            if type(reason) is not str or not 1 <= len(reason) <= 128:
                raise ComputeError('Invalid decision reason')
        for exclusion in self.exclusions:
            if type(exclusion) is not tuple or len(exclusion) != 2:
                raise ComputeError('Invalid decision exclusion')
            if type(exclusion[0]) is not str or not re.fullmatch('[A-Za-z0-9][A-Za-z0-9._-]{0,99}', exclusion[0]):
                raise ComputeError('Invalid excluded provider')
            _enum(exclusion[1], ('classification', 'credentials', 'profile_unsupported', 'cost_budget', 'time_budget'))


@dataclass(frozen=True)
class ComputePolicy:
    providers: tuple[ProviderLimits, ...]
    version: str = 'core10-v1'

    def __post_init__(self):
        _enum(self.version, ('core10-v1',))
        if type(self.providers) is not tuple or not 1 <= len(self.providers) <= 32:
            raise ComputeError('Invalid compute provider set')
        for provider in self.providers:
            _shape(provider, ProviderLimits)
        if len({p.provider_id for p in self.providers}) != len(self.providers):
            raise ComputeError('Duplicate compute provider')

    def decide(self, request, inputs=None):
        _shape(self, ComputePolicy)
        exact = binding(request)
        if inputs is None:
            inputs = ComputeInputs(exact)
        _shape(inputs, ComputeInputs)
        if inputs.request_binding != exact:
            raise ComputeError('Compute task/project/scope binding mismatch')
        _enum(request.risk_level, ('low', 'medium', 'high', 'approval_required'))
        # Unknown fields never qualify a task for FAST. They are not a claim
        # that data is public or that credentials have been cleared.
        ranks = {
            'complexity': {'simple': 0, 'moderate': 1, 'complex': 2, 'unknown': 1}[inputs.complexity],
            'risk': {'low': 0, 'medium': 2, 'high': 3, 'approval_required': 3}[request.risk_level],
            'data_sensitivity': {'public': 0, 'internal': 1, 'confidential': 2, 'restricted': 3, 'unknown': 1}[inputs.data_sensitivity],
            'file_classification': {'public': 0, 'internal': 1, 'confidential': 2, 'restricted': 3, 'unknown': 1}[inputs.file_classification],
            'credential_proximity': {'none': 0, 'near': 2, 'direct': 3, 'unknown': 1}[inputs.credential_proximity],
            'external_visibility': {'internal': 0, 'external': 2, 'public': 3, 'unknown': 1}[inputs.external_visibility],
            'financial_impact': {'none': 0, 'low': 2, 'high': 3, 'unknown': 1}[inputs.financial_impact],
            'verification': {'basic': 0, 'standard': 1, 'strong': 2, 'independent': 3}[inputs.verification],
            'reliability': {'reliable': 0, 'unknown': 1, 'degraded': 2, 'poor': 3}[inputs.reliability],
            'required_review': 2 if request.review_required else 0,
        }
        rank = max(ranks.values())
        observed = asdict(inputs)
        observed.update(risk=request.risk_level, required_review=request.review_required)
        reasons = tuple(f'{key}={observed[key]};floor={PROFILES[value]}'
                        for key, value in sorted(ranks.items()))
        clearance = max(CLASSIFICATIONS.index(v if v != 'unknown' else 'internal')
                        for v in (inputs.data_sensitivity, inputs.file_classification))
        eligible, exclusions = [], []
        for provider in sorted(self.providers, key=lambda p: p.provider_id):
            reason = None
            if CLASSIFICATIONS.index(provider.clearance) < clearance:
                reason = 'classification'
            elif inputs.credential_proximity in ('near', 'direct') and not provider.credentials:
                reason = 'credentials'
            elif PROFILES[rank] not in provider.profiles:
                reason = 'profile_unsupported'
            elif inputs.cost_budget_units is not None and provider.cost_units[rank] > inputs.cost_budget_units:
                reason = 'cost_budget'
            elif inputs.time_budget_seconds is not None and provider.time_seconds[rank] > inputs.time_budget_seconds:
                reason = 'time_budget'
            if reason:
                exclusions.append((provider.provider_id, reason))
            else:
                eligible.append(provider.provider_id)
        evidence = _digest({'policy': asdict(self), 'inputs': asdict(inputs), 'risk': request.risk_level,
                            'review_required': request.review_required})
        work_identity = _digest({'request': exact, 'context': inputs.context_binding})
        return ComputeDecision(self.version, work_identity, evidence, 'READY' if eligible else 'BLOCKED',
                               PROFILES[rank], tuple(eligible), reasons, tuple(exclusions))

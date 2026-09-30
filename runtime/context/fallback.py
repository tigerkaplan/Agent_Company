"""Pure capability fallback planning. No connector invocation or approval."""
from dataclasses import asdict, dataclass
import json

from runtime.context.contracts import DiscoveryError, Material, bounded_text, digest


@dataclass(frozen=True)
class CapabilityRequirement:
    capability: str
    scope: tuple[str, ...]
    authority: tuple[str, ...]
    evidence: tuple[str, ...]
    approvals: tuple[str, ...]

    def __post_init__(self):
        bounded_text(self.capability, 128)
        for values in (self.scope, self.authority, self.evidence, self.approvals):
            if not isinstance(values, tuple) or len(values) > 32 or len(set(values)) != len(values):
                raise DiscoveryError('Invalid fallback requirements')
            for value in values:
                bounded_text(value, 256)


@dataclass(frozen=True)
class CapabilityImplementation:
    identity: str
    tier: str
    contract: CapabilityRequirement
    available: bool

    def __post_init__(self):
        bounded_text(self.identity, 128)
        if self.tier not in {'preferred', 'alternative', 'file', 'manual'} or type(self.available) is not bool:
            raise DiscoveryError('Invalid capability implementation')
        self.contract.__post_init__()


@dataclass(frozen=True)
class FallbackResolution:
    status: str
    selected: str | None
    tier: str | None
    attempts: tuple[tuple[str, str], ...]
    requirement: CapabilityRequirement

    def material(self) -> Material:
        content = json.dumps({'authority_granted': False, **asdict(self)}, sort_keys=True)
        return Material('capability/tool', self.requirement.capability, content, digest(content))


def resolve_fallback(requirement: CapabilityRequirement,
                     implementations: tuple[CapabilityImplementation, ...]) -> FallbackResolution:
    requirement.__post_init__()
    if len(implementations) > 64 or len({i.identity for i in implementations}) != len(implementations):
        raise DiscoveryError('Invalid fallback candidate set')
    order = {'preferred': 0, 'alternative': 1, 'file': 2, 'manual': 3}
    for item in implementations:
        item.__post_init__()
    attempts = []
    for item in sorted(implementations, key=lambda i: (order[i.tier], i.identity)):
        # Exact contract equality is deliberately conservative. Even a seemingly
        # stronger or narrower substitute must be configured against this task.
        if item.contract != requirement:
            attempts.append((item.identity, 'contract_mismatch'))
        elif not item.available:
            attempts.append((item.identity, 'unavailable'))
        else:
            attempts.append((item.identity, 'selected_evidence_only'))
            return FallbackResolution('RESOLVED', item.identity, item.tier, tuple(attempts), requirement)
    return FallbackResolution('BLOCKED', None, None, tuple(attempts), requirement)

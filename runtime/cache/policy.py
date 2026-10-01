"""Bounded process-local reuse after fresh discovery, never an authority store."""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, fields
import hashlib
import json
import math
from threading import RLock
import time

from runtime.context.contracts import ContextPack, DiscoveryError, Limits, Material, assemble


_PACK_FIELDS = frozenset(f.name for f in fields(ContextPack))
_MATERIAL_FIELDS = frozenset(f.name for f in fields(Material))


def _canonical_pack_bytes(pack: ContextPack) -> bytes:
    """Apply identical model and representation checks to fresh and cached data.

    Frozen dataclasses are not validation of stored state. Check exact shapes
    before accessing nested values or serializing, and reconstruct materials
    through their canonical constructor rather than trusting stored methods.
    """
    if (type(pack) is not ContextPack or type(vars(pack)) is not dict
            or len(vars(pack)) != len(_PACK_FIELDS)
            or vars(pack).keys() != _PACK_FIELDS
            or type(pack.materials) is not tuple or len(pack.materials) > 128
            or type(pack.missing) is not tuple or pack.missing):
        raise DiscoveryError('Only canonical ready context packs may be cached')
    materials = []
    for material in pack.materials:
        if (type(material) is not Material or type(vars(material)) is not dict
                or len(vars(material)) != len(_MATERIAL_FIELDS)
                or vars(material).keys() != _MATERIAL_FIELDS):
            raise DiscoveryError('Noncanonical cached material fields')
        values = vars(material)
        if (type(values['start_line']) is not int
                or any(type(value) is not str or len(value) > 1024 * 1024
                       for name, value in values.items() if name != 'start_line')):
            raise DiscoveryError('Noncanonical cached material types')
        try:
            materials.append(Material(**values))
        except (TypeError, ValueError) as error:
            raise DiscoveryError('Invalid context material contract') from error
    try:
        canonical = assemble(tuple(materials), limits=Limits(entries=128, pack_bytes=2 * 1024 * 1024))
        if len(canonical.materials) != len(materials):
            raise DiscoveryError('Duplicate cached context material')
        rendered = canonical.render().encode('utf-8')
        # Detect normalization (such as duplicate removal) without dataclass
        # equality. Exact field/type checks above also reject ignored extras.
        if ContextPack.render(pack).encode('utf-8') != rendered:
            raise DiscoveryError('Noncanonical context pack serialization')
        return rendered
    except (TypeError, ValueError, OverflowError) as error:
        raise DiscoveryError('Invalid context pack serialization') from error


def _binding_value(value, *, depth=0, budget=None):
    """Reject ambiguous JSON keys/types and bound identity construction work."""
    if budget is None:
        budget = [4096, 64 * 1024]
    budget[0] -= 1
    if depth > 16 or budget[0] < 0:
        raise DiscoveryError('Cache binding complexity exceeds bound')
    if type(value) is str:
        budget[1] -= len(value.encode('utf-8'))
        if budget[1] < 0:
            raise DiscoveryError('Cache binding text exceeds bound')
    elif value is None or type(value) is bool:
        pass
    elif type(value) is int:
        if not -(2**63) <= value < 2**63:
            raise DiscoveryError('Cache binding integer exceeds bound')
    elif type(value) in (list, tuple, dict):
        if len(value) > 4096:
            raise DiscoveryError('Cache binding collection exceeds bound')
        if type(value) is dict:
            for key, item in value.items():
                if type(key) is not str:
                    raise DiscoveryError('Cache binding keys must be strings')
                _binding_value(key, depth=depth + 1, budget=budget)
                _binding_value(item, depth=depth + 1, budget=budget)
        else:
            for item in value:
                _binding_value(item, depth=depth + 1, budget=budget)
    else:
        raise DiscoveryError('Noncanonical cache binding type')


@dataclass(frozen=True)
class CachePolicy:
    version: str = 'core09-v1'
    max_entries: int = 16
    max_bytes: int = 4 * 1024 * 1024
    entry_bytes: int = 512 * 1024
    ttl_seconds: int = 300

    def __post_init__(self):
        if type(self.version) is not str or not self.version.strip() or len(self.version) > 128:
            raise ValueError('Invalid cache policy version')
        for value, ceiling in ((self.max_entries, 128), (self.max_bytes, 16 * 1024 * 1024),
                               (self.entry_bytes, 2 * 1024 * 1024), (self.ttl_seconds, 86400)):
            if type(value) is not int or not 1 <= value <= ceiling:
                raise ValueError('Invalid cache bound')


@dataclass(frozen=True)
class CacheResult:
    status: str
    reason: str
    key: str
    pack: ContextPack


@dataclass(frozen=True)
class _Entry:
    key: str
    created: float
    pack: ContextPack
    size: int


class ContextCache:
    """Only local builders call reuse with freshly discovered, validated material.

    No put/import/validity callback exists for provider output. Entries contain
    context only. The caller must never use outcomes as execution permission.
    """

    def __init__(self, policy: CachePolicy = CachePolicy(), *, clock=time.monotonic):
        if type(policy) is not CachePolicy:
            raise ValueError('Invalid cache policy')
        policy.__post_init__()
        self.policy = policy
        self._clock = clock
        self._entries = OrderedDict()
        self._lock = RLock()

    def reuse(self, *, namespace: str, binding: dict, fresh: ContextPack) -> CacheResult:
        # Validate even cache hits. Fresh discovery, not provider claims, is the
        # source of truth. Exact content comparison also rejects forged digests.
        if type(namespace) is not str or not namespace.strip() or len(namespace.encode('utf-8')) > 512:
            raise DiscoveryError('Explicit local cache isolation scope required')
        if type(binding) is not dict or not binding:
            raise DiscoveryError('Cache work binding required')
        _binding_value(binding)
        rendered = _canonical_pack_bytes(fresh)
        try:
            identity = json.dumps({'namespace': namespace, 'binding': binding,
                                   'policy': self.policy.__dict__}, sort_keys=True,
                                  ensure_ascii=True, allow_nan=False, separators=(',', ':'))
        except (ValueError, TypeError, RecursionError) as error:
            raise DiscoveryError('Noncanonical cache binding') from error
        if len(identity.encode('utf-8')) > 64 * 1024:
            raise DiscoveryError('Cache binding exceeds bound')
        slot = hashlib.sha256(identity.encode('utf-8')).hexdigest()
        key = hashlib.sha256(identity.encode('utf-8') + b'\0' + rendered).hexdigest()
        size = len(rendered) + len(identity.encode('utf-8')) + 256
        now = self._clock()
        if type(now) not in (int, float) or not math.isfinite(now):
            raise DiscoveryError('Invalid cache clock')
        with self._lock:
            if (type(self._entries) is not OrderedDict
                    or len(self._entries) > self.policy.max_entries
                    or any(type(e) is not _Entry or type(e.size) is not int
                           or not 1 <= e.size <= self.policy.entry_bytes
                           for e in self._entries.values())):
                self._entries = OrderedDict()
                corrupt = True
            else:
                corrupt = False
            old = self._entries.pop(slot, None)
            status, reason = ('STALE', 'malformed') if corrupt else ('MISS', 'absent')
            if old is not None:
                status, reason = 'STALE', 'malformed'
                if (type(old) is _Entry and type(old.created) in (int, float)
                        and math.isfinite(old.created) and type(old.size) is int
                        and type(old.pack) is ContextPack):
                    try:
                        cached_rendered = _canonical_pack_bytes(old.pack)
                    except DiscoveryError:
                        cached_rendered = None
                    if cached_rendered is None:
                        reason = 'malformed'
                    elif now < old.created or now - old.created >= self.policy.ttl_seconds:
                        reason = 'expired'
                    elif old.key != key or cached_rendered != rendered or old.size != size:
                        reason = 'material_changed'
                    else:
                        self._entries[slot] = old
                        return CacheResult('HIT', 'validated', key, old.pack)
            # No stale material is returned; failed reuse uses fresh evidence.
            if size > self.policy.entry_bytes or size > self.policy.max_bytes:
                return CacheResult('BYPASS', 'entry_bound', key, fresh)
            # Fixed count bounds mean no filesystem scans or unbounded history.
            while self._entries and (len(self._entries) >= self.policy.max_entries
                    or sum(e.size for e in self._entries.values()) + size > self.policy.max_bytes):
                self._entries.popitem(last=False)
            self._entries[slot] = _Entry(key, now, fresh, size)
            return CacheResult(status, reason, key, fresh)

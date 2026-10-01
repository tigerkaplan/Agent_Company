"""Bounded external ingress. Caller supplies provenance; content supplies no policy.

No parsing, instruction detection, execution, or trust promotion occurs here.
All origins use the same inert representation, including tool/connector output.
"""
from runtime.context.contracts import DiscoveryError, Limits, Material, digest


ORIGINS = frozenset({'pasted', 'web', 'email', 'upload', 'retrieved',
                     'scraped', 'connector', 'tool'})
FIELDS = frozenset({'version', 'origin', 'ref', 'content', 'source_digest',
                    'trust', 'authority'})


def external_materials(records: tuple[dict, ...], limits: Limits = Limits()) -> tuple[Material, ...]:
    if type(records) is not tuple or len(records) > limits.entries:
        raise DiscoveryError('External content count exceeds bound')
    result = []
    total = 0
    for record in records:
        if type(record) is not dict or record.keys() != FIELDS:
            raise DiscoveryError('Malformed external provenance fields')
        if (type(record['version']) is not int or record['version'] != 1
                or any(type(record[k]) is not str for k in FIELDS - {'version'})):
            raise DiscoveryError('Malformed external provenance types')
        if (record['origin'] not in ORIGINS or record['trust'] != 'untrusted'
                or record['authority'] != 'none'):
            raise DiscoveryError('External content cannot supply authority')
        content = record['content']
        if len(content) > limits.file_bytes:
            raise DiscoveryError('External content exceeds bound')
        size = len(content.encode('utf-8'))
        total += size
        if size > limits.file_bytes or total > limits.pack_bytes:
            raise DiscoveryError('External content exceeds byte budget')
        if record['source_digest'] != digest(content):
            raise DiscoveryError('External content digest mismatch')
        result.append(Material('external', record['ref'], content, record['source_digest'],
                               origin=record['origin']))
    return tuple(result)


def external_record(origin: str, ref: str, content: str) -> dict:
    """Capture verbatim data at a local ingress, never trust metadata in the text."""
    if type(content) is not str or len(content) > Limits().file_bytes:
        raise DiscoveryError('Invalid external content')
    record = dict(version=1, origin=origin, ref=ref, content=content,
                  source_digest=digest(content), trust='untrusted', authority='none')
    external_materials((record,))
    return record

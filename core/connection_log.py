"""Private, bounded metadata journal; never stores arbitrary engine payloads."""
from collections import deque
import threading
import time
import re
from urllib.parse import urlsplit

_FIELDS = frozenset(('kind', 'session', 'proxy_id', 'process', 'destination',
                     'port', 'protocol', 'route', 'state', 'uploaded', 'downloaded'))

def _safe(value):
    text = str(value)
    text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', text)
    if '://' in text:
        try:
            parsed = urlsplit(text)
            text = parsed.hostname or '[unavailable]'
        except ValueError:
            text = '[unavailable]'
    text = re.sub(r'(?i)(password|authorization|token|secret)\s*[:=]\s*\S+', r'\1=[redacted]', text)
    if "@" in text:
        text = text.rsplit("@", 1)[-1]
    return text[:256]

class ConnectionJournal:
    """Allowlisted metadata only. Sequence numbers remain monotonic after clear."""
    def __init__(self, limit=1000, clock=time.time):
        if not isinstance(limit, int) or not 1 <= limit <= 1000:
            raise ValueError('journal limit must be between 1 and 1000')
        self._rows = deque(maxlen=limit)
        self._clock = clock
        self._sequence = 0
        self._lock = threading.Lock()
        self._source = 'unavailable'

    def source(self, available):
        with self._lock:
            self._source = 'snapshot' if available else 'unavailable'

    def append(self, **metadata):
        row = {}
        for key in _FIELDS:
            value = metadata.get(key)
            if value is not None:
                if key in ('port', 'uploaded', 'downloaded'):
                    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                        row[key] = value
                else:
                    row[key] = _safe(value)
        with self._lock:
            self._sequence += 1
            row.update(sequence=self._sequence, timestamp=self._clock())
            self._rows.append(row)
            return self._sequence

    def read(self, after=0, limit=200, query=''):
        after = max(0, int(after))
        limit = min(200, max(1, int(limit)))
        query = str(query)[:256].casefold()
        with self._lock:
            rows = [dict(row) for row in self._rows if row['sequence'] > after]
            first = self._rows[0]['sequence'] if self._rows else self._sequence + 1
            page = rows[:limit]
            cursor = page[-1]['sequence'] if page else self._sequence
            return {'rows': [row for row in page if query in ' '.join(map(str, row.values())).casefold()],
                    'cursor': cursor, 'truncated': after < first - 1,
                    'source': self._source, 'coverage': 'snapshots may miss short-lived connections',
                    'has_more': len(rows) > limit}

    def clear(self):
        with self._lock:
            self._rows.clear()


class ConnectionSource:
    """Authenticated loopback snapshots only; short-lived flows may be absent."""
    def __init__(self, journal):
        self.journal = journal
        self._seen = set()

    def poll(self, manager, session):
        import json
        import urllib.request
        try:
            port = int(manager.controller_port)
            request = urllib.request.Request('http://127.0.0.1:%d/connections' % port,
                headers={'Authorization': 'Bearer ' + manager.controller_secret})
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(request, timeout=1) as response:
                payload = response.read(524289)
            if len(payload) > 524288:
                raise ValueError('oversized snapshot')
            rows = json.loads(payload)['connections']
            if not isinstance(rows, list):
                raise ValueError('invalid snapshot')
            seen = set()
            for row in rows[:1000]:
                identifier = str(row.get('id', ''))[:128]
                seen.add(identifier)
                if identifier in self._seen:
                    continue
                metadata = row.get('metadata', {})
                self.journal.append(kind='connection', session=session,
                    proxy_id=manager.active_proxy.id if manager.active_proxy else None,
                    process=metadata.get('processPath') or metadata.get('process') or 'unavailable',
                    destination=metadata.get('host') or metadata.get('destinationIP') or 'unavailable',
                    port=int(metadata.get('destinationPort', 0)), protocol=metadata.get('network', 'unavailable'),
                    route=' / '.join(str(x) for x in row.get('chains', [])[:8]) or 'unavailable',
                    state='observed', uploaded=row.get('upload'), downloaded=row.get('download'))
            self._seen = seen
            self.journal.source(True)
        except Exception:
            self.journal.source(False)

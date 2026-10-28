"""SQLite vector retrieval with mandatory tenant and role filtering."""
import hashlib
import json
import math
import re
import sqlite3
import time


def words(text):
    return re.findall(r'[a-z0-9]+', text.lower())


def embed(text, dimensions=256):
    """Offline hashed bag-of-words baseline, NOT a semantic embedding model."""
    vector = [0.0] * dimensions
    for token in words(text):
        digest = hashlib.sha256(token.encode()).digest()
        vector[int.from_bytes(digest[:4], 'big') % dimensions] += 1
    norm = math.sqrt(sum(x*x for x in vector)) or 1
    return [x/norm for x in vector]


class Store:
    def __init__(self, path=':memory:'):
        self.db = sqlite3.connect(path)
        self.db.execute('CREATE TABLE IF NOT EXISTS chunks '
                        '(id TEXT PRIMARY KEY, tenant TEXT, role TEXT, current INTEGER, '
                        'source TEXT, body TEXT, vector TEXT)')

    def ingest(self, docs):
        """Replace a document atomically; IDs include tenant to prevent collisions."""
        count = 0
        with self.db:
            for doc in docs:
                if not all(doc.get(k) for k in ('id', 'tenant', 'role', 'source', 'body')):
                    raise ValueError('Missing required document metadata')
                if type(doc.get('current')) is not bool:
                    raise ValueError('current must be a boolean')
                prefix = doc['tenant'] + ':' + doc['id'] + ':'
                # Exact prefix comparison avoids wildcard injection in document IDs.
                self.db.execute('DELETE FROM chunks WHERE substr(id, 1, ?) = ?', (len(prefix), prefix))
                chunks = [p.strip() for p in doc['body'].split('\n\n') if p.strip()]
                for i, body in enumerate(chunks):
                    self.db.execute('INSERT INTO chunks VALUES (?,?,?,?,?,?,?)',
                        (prefix + str(i), doc['tenant'], doc['role'], doc['current'],
                         doc['source'], body, json.dumps(embed(body))))
                    count += 1
        return count

    def search(self, query, tenant, role, limit=3):
        if not tenant or not role:
            raise ValueError('Trusted tenant and role context is required')
        if not 1 <= limit <= 20:
            raise ValueError('limit must be between 1 and 20')
        # Authorization happens BEFORE vector ranking; role is exact, not hierarchical.
        rows = self.db.execute('SELECT id, source, body, vector FROM chunks '
            'WHERE tenant=? AND role=? AND current=1', (tenant, role)).fetchall()
        query_vector = embed(query)
        terms = set(words(query)) - {'what', 'is', 'the', 'a', 'for', 'how', 'to', 'of', 'and'}
        ranked = []
        for doc_id, source, body, raw in rows:
            # Lexical overlap gate reduces hash-collision false positives.
            overlap = terms.intersection(words(body))
            if not overlap:
                continue
            score = sum(a*b for a, b in zip(query_vector, json.loads(raw)))
            ranked.append({'id': doc_id, 'source': source, 'body': body, 'score': round(score, 5)})
        return sorted(ranked, key=lambda r: (-r['score'], r['id']))[:limit]

    def answer(self, query, tenant, role):
        start = time.perf_counter()
        hits = self.search(query, tenant, role)
        # Extractive baseline: source text, rather than an unsupported generated answer.
        return {'answer': hits[0]['body'] if hits else 'Insufficient authorized evidence.',
                'abstained': not hits, 'citations': [h['id'] for h in hits[:1]],
                'retrieval_ms': round((time.perf_counter()-start)*1000, 3),
                'embedding': 'sha256-hashed-bag-of-words', 'tenant': tenant}

    def close(self):
        self.db.close()

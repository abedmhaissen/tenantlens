import json
from pathlib import Path
import unittest
from retrieval import Store
from main import evaluate


class RetrievalTests(unittest.TestCase):
    def setUp(self):
        self.store = Store()
        self.fixture = json.loads((Path(__file__).parent/'fixtures.json').read_text())
        self.store.ingest(self.fixture['documents'])

    def tearDown(self):
        self.store.close()

    def test_eval_cases(self):
        result = evaluate(self.store, self.fixture['queries'])
        self.assertEqual(result['passed'], result['total'])

    def test_no_cross_tenant_or_stale_evidence(self):
        hits = self.store.search('returns policy', 'northstar', 'support')
        self.assertEqual([h['id'] for h in hits], ['northstar:returns:0'])
        self.assertNotIn('365', hits[0]['body'])

    def test_no_role_escalation(self):
        self.assertTrue(self.store.answer('confidential margin', 'northstar', 'support')['abstained'])
        self.assertFalse(self.store.answer('confidential margin', 'northstar', 'finance')['abstained'])

    def test_parameterized_tenant(self):
        self.assertEqual(self.store.search('returns', "' OR 1=1 --", 'support'), [])

    def test_idempotent_ingest_and_changed_document(self):
        self.store.ingest(self.fixture['documents'])
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM chunks').fetchone()[0], 5)
        changed = dict(self.fixture['documents'][0], body='Updated returns window: 14 days.')
        self.store.ingest([changed])
        self.assertIn('14 days', self.store.answer('returns window', 'northstar', 'support')['answer'])

    def test_metadata_failure_rolls_back_batch(self):
        good = dict(self.fixture['documents'][0], id='new')
        with self.assertRaises(ValueError):
            self.store.ingest([good, {'id': 'invalid'}])
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM chunks').fetchone()[0], 5)

    def test_empty_context_rejected(self):
        with self.assertRaises(ValueError):
            self.store.search('returns', '', 'support')


if __name__ == '__main__':
    unittest.main()

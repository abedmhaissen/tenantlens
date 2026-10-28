import argparse
import json
from pathlib import Path
from retrieval import Store

FIXTURE = Path(__file__).parent / 'fixtures.json'


def evaluate(store, queries):
    results = []
    for q in queries:
        result = store.answer(q['query'], q['tenant'], q['role'])
        correct = (result['abstained'] if q['expected'] is None
                   else q['expected'] in result['citations'])
        results.append({**q, **result, 'passed': correct})
    return {'mode': 'offline-extractive', 'cases': results,
            'passed': sum(r['passed'] for r in results), 'total': len(results)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--query')
    parser.add_argument('--tenant', default='northstar')
    parser.add_argument('--role', default='support')
    parser.add_argument('--gemini', action='store_true')
    parser.add_argument('--output', default='report.json')
    args = parser.parse_args()
    fixture = json.loads(FIXTURE.read_text())
    store = Store()
    try:
        store.ingest(fixture['documents'])
        if args.query and args.gemini:
            from synthesis import grounded_answer
            result = grounded_answer(store, args.query, args.tenant, args.role)
        elif args.query:
            result = store.answer(args.query, args.tenant, args.role)
        else:
            result = evaluate(store, fixture['queries'])
        Path(args.output).write_text(json.dumps(result, indent=2))
        print(json.dumps(result, indent=2))
    finally:
        store.close()


if __name__ == '__main__':
    main()

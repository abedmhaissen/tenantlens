# TenantLens

**A small enterprise knowledge pipeline that filters access before retrieval and makes every answer inspectable.**

The customer problem: a shared support knowledge base contains multiple tenants, finance-only material, and archived policies. A support assistant must retrieve the current authorized policy, cite it, or abstain when it has no relevant evidence.

## Run the demo

```bash
git clone https://github.com/abedmhaissen/tenantlens.git
cd tenantlens
python main.py
python main.py --query 'returns policy' --tenant northstar --role support
python -m unittest discover -v
```

The offline path uses Python's standard library and SQLite. Its six small evaluation cases cover current policy retrieval, shipping, a second tenant, unauthorized finance material, an unknown tenant, and an unrelated question. All six pass in the checked-in [example-report.json](example-report.json); this fixture score does not establish production retrieval quality.

## How it works

1. Validate document metadata and split paragraphs into source-linked chunks.
2. Store text, tenant, role, freshness, and vectors in SQLite in an atomic transaction.
3. Select the exact tenant and role, excluding archived chunks, **before** ranking.
4. Rank authorized candidates by cosine similarity, with a lexical overlap gate.
5. Return an extractive answer with a chunk citation or abstain on zero matching evidence.

Vectors are normalized SHA-256 hashed bag-of-words features. This is a transparent offline vector baseline, not neural semantic search. SQLite stores the vectors as JSON and the application performs exact scans. There is no approximate nearest-neighbor index; large corpora need a dedicated vector backend.

## Why these decisions matter

| Decision | Tradeoff |
|---|---|
| Filter before ranking | Unauthorized evidence never enters the synthesis context |
| Exact role matching | Easy to audit; no implicit admin or role inheritance |
| Atomic, idempotent ingestion | Safe fixture replays and updates; requires trusted metadata |
| Extractive default | Easy to inspect; limited paraphrase and reasoning |
| Citation allowlist in Gemini mode | Rejects unknown IDs; does not prove factual entailment |
| Local exact vector scan | Simple reproducibility; linear retrieval cost |

## Optional Gemini synthesis

Python 3.10+ is required for the optional dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export GOOGLE_API_KEY='your-key'
export GEMINI_MODEL='your-available-gemini-model-id'
python main.py --query 'What is the returns policy?' --gemini
```

[Google Cloud backend configuration](https://docs.langchain.com/oss/python/integrations/chat/google_generative_ai) is also supported by the integration package. Only authorized retrieved chunks are sent to the model. Model outputs use a structured schema and citation IDs must belong to the retrieved set. A valid citation does not verify that the generated sentence follows from its source. Treat generated answers as unverified until an entailment evaluation and adversarial review are added.

## Evaluation and trust boundary

Seven unit tests cover fixture retrieval, stale and cross-tenant exclusion, exact role access, SQL injection attempts, document replacement, atomic rollback, and required context. Retrieval durations are measured wall-clock values and vary by machine.

The CLI's `--tenant` and `--role` flags simulate a trusted calling service. They are **not authentication**. A deployed service must derive these fields from a verified identity and enforce ingestion permissions outside the model. Document IDs and metadata currently come from trusted synthetic fixtures. Prompt text alone cannot enforce permissions.

## Customer discovery and rollout

Before integration, agree on identity mapping, document owners, freshness SLAs, deletion behavior, and an evaluation set representative of real customer queries. Start with a read-only pilot. Measure retrieval recall, unsupported-answer rate, abstention quality, latency, and user corrections before broader adoption.

Next work: neural embeddings and a managed vector index, OIDC/IAM identity propagation, versioned source connectors, explicit deletion APIs, larger adversarial evaluations, and a Cloud Run API. This prototype has no deployed cloud service and makes no claims about production scale or customer adoption.

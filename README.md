# Invoice Processing Pipeline

An end-to-end system that extracts structured data from invoices and receipts, validates it, and writes it to a reviewable ledger. A **fine-tuned small vision-language model** does the extraction cheaply; a **frontier model** is used only as a fallback when the specialist's output is malformed or fails validation. Processing is asynchronous and durable — jobs run on a Redis-backed task queue with automatic retries for transient failures — and every result, clean or not, requires a human to confirm it before it's considered final.

Every routing decision — retry, fallback, when to stop — is plain code checking state. The LLMs are only ever invoked to do one thing, extract structured JSON from an image, at fixed points in a [LangGraph](https://langchain-ai.github.io/langgraph/) state machine.

This is a personal project built to practice taking an LLM system all the way from *fine-tuning a model* to *running it as a service* — dataset preparation, training, serving, workflow orchestration, a task queue, a persistent ledger, an API, and a UI.

## What it does

1. A user uploads an invoice/receipt image through the web UI.
2. The backend saves the file, creates a `Job` record, and enqueues an extraction task on a Redis-backed queue ([Arq](https://arq-docs.helpmanual.io/)). A separate worker process picks it up.
3. A **fine-tuned Qwen3-VL** model (served via vLLM) extracts the invoice as structured JSON.
4. The output is validated against a Pydantic schema and **reconciled** — line items are summed against the subtotal, the grand total is recomputed from its components, and the invoice number is checked against the existing ledger for duplicates.
5. If the specialist's output is malformed or fails reconciliation, the workflow makes **one automatic retry with the frontier model** (Claude Haiku 4.5), re-prompting it with the specific issues found.
6. The result is written to the Postgres ledger. **Every entry requires a human to confirm it** — reconciliation issues are surfaced to prioritize what a reviewer checks first, they don't gate whether a human ever sees it. Internal arithmetic consistency isn't proof the content is correct, and the specialist doesn't have a rigorous accuracy benchmark yet, so nothing publishes unsupervised.
7. Failures are classified as retryable or permanent (`agent/error_categories.py`): a transiently unreachable model endpoint is retried automatically with backoff; a malformed request or bad output is not, since retrying it would fail identically. Jobs that exhaust retries land in a small dead-letter view where they can be manually re-queued or deleted.

The design goal for model routing is cost/latency: the cheap specialist handles the common case, and the expensive model is only invoked when something actually looks wrong. That's a separate concern from *review* — routing decides which model produces the draft; review decides whether it's trusted.

## Architecture

A React SPA uploads to a FastAPI backend, which saves the job and enqueues it on a Redis-backed task queue. A separate **Arq worker** process runs the extraction workflow and writes the outcome to Postgres — durable by design, so a backend restart mid-extraction doesn't lose in-flight work the way an in-process background task would.

The workflow itself is a LangGraph state machine with conditional routing:

| Node | Responsibility |
|---|---|
| `specialist_extract` | Call the fine-tuned model; on a parse failure, route to the frontier extractor |
| `validate_reconcile` | Run schema, arithmetic, and duplicate checks |
| `frontier_extract_fallback` | Re-extract with the frontier model when the specialist's output is unusable |
| `frontier_review_fallback` | One retry with the reconciliation issues fed back as context |
| `ledger_write` | Persist the entry — every entry, always flagged for human confirmation |

Retryable failures (a model endpoint being briefly unreachable) never reach `ledger_write` at all — they propagate uncaught out of the extractor and out of the whole graph, straight to the worker's retry/backoff logic, so Arq can retry the identical call later. Everything else (bad input, malformed output) is caught inside the extractor and routed through the graph as a normal result.

The code is layered so each concern has one owner:

| Module | Owns |
|---|---|
| [`agent/extractors.py`](src/invoice_agent/agent/extractors.py) | The two model clients — no graph or state knowledge |
| [`agent/error_categories.py`](src/invoice_agent/agent/error_categories.py) | Classifies a failure as retryable ("connectivity") or permanent |
| [`agent/nodes.py`](src/invoice_agent/agent/nodes.py) | Translating graph state to and from the extractors |
| [`agent/graph.py`](src/invoice_agent/agent/graph.py) | Graph wiring; the single place dependencies are constructed |
| [`agent/runner.py`](src/invoice_agent/agent/runner.py) | Running the graph and returning a public `ExtractionResult` |
| [`queue/worker.py`](src/invoice_agent/queue/worker.py) | The Arq worker: runs the workflow per job, owns the retry/backoff and terminal-failure policy |
| [`queue/pool.py`](src/invoice_agent/queue/pool.py) | The Redis connection pool the API enqueues jobs through |
| [`config.py`](src/invoice_agent/config.py) | All environment loading, in one place |

The graph's internal state never escapes the workflow package, so the HTTP layer stays purely about HTTP. Validation logic lives in [`reconciliation.py`](src/invoice_agent/reconciliation.py).

## The model

The specialist is **Qwen3-VL-4B-Instruct**, fine-tuned with **LoRA (SFT)** using [Unsloth](https://github.com/unslothai/unsloth), with runs tracked in **MLflow**. Only the language and MLP/attention layers are adapted — the vision tower is frozen. The adapter is merged into the base weights and served through **vLLM**'s OpenAI-compatible API.

Training data is pooled from three sources ([`scripts/build_training_splits.py`](scripts/build_training_splits.py)):
- **[CORD](https://github.com/clovaai/cord)** and **[SROIE](https://huggingface.co/datasets/darentang/sroie)** — real receipts, converted via locale-aware number parsers ([`scripts/converters/`](scripts/converters/)) that handle mixed `.`/`,` thousands/decimal conventions.
- **[FATURA](https://huggingface.co/datasets/mathieu1256/FATURA2-invoices)** — synthetic invoices, labeled by running a **Qwen3-VL-32B-Instruct** model locally via Unsloth with vLLM's continuous batching, on a rented GPU — chosen over frontier-API labeling to keep labeling cost near zero at this volume.

A fourth candidate dataset (mychen76) was evaluated and dropped after inspection showed inconsistent field labeling and a high rate of missing totals — not worth the noise it would have added to the training mix.

- Training: [`scripts/train_qwen_vl.py`](scripts/train_qwen_vl.py)
- Serving locally: [`scripts/serve_vllm.sh`](scripts/serve_vllm.sh)
- Serverless GPU serving: [`deploy/modal_app.py`](deploy/modal_app.py) — deploys the merged model to a Modal **L4** GPU as an autoscaling web server. `@modal.concurrent(max_inputs=16)` with `max_containers=1` was a deliberate, measured fix: without it, Modal serializes one request per container regardless of vLLM's own continuous batching, which throttled throughput to roughly one document every 50 seconds. With it, concurrent requests actually reach vLLM's batching engine.

## The schema

Extraction targets a strict Pydantic model ([`src/invoice_agent/schema.py`](src/invoice_agent/schema.py)) with `extra="forbid"`: an `Invoice` with typed `Party` (vendor/customer), `LineItem`s, `Decimal` money fields, an ISO-4217 currency pattern, and a `document_type` literal (`invoice` / `receipt` — no training data ever contained a credit note, so it isn't a representable output rather than silently mishandled). Using `Decimal` throughout keeps the reconciliation arithmetic exact.

## Backend

- **FastAPI**, fully async, backed by **Redis** + **Arq** for durable job processing. Upload saves the file, creates a `Job` row, and enqueues an extraction task; a separate worker process consumes it, so a backend restart never orphans in-flight work.
- **Postgres** ledger via **SQLModel**, with **Alembic** migrations ([`alembic/versions/`](alembic/versions/)). Two tables: `Job` (processing lifecycle — status, retry `attempts`, last error) and `LedgerEntry` (the extracted invoice + review state).
- Routers for extraction ([upload / status / image](src/invoice_agent/api/routers/extraction.py)) and the ledger ([review queue / full ledger / pending / errored / edit / delete / retry](src/invoice_agent/api/routers/ledger.py)).
- Retries are automatic for retryable failures, with backoff; a job that exhausts its retries is marked `error` and surfaced separately from the review queue (which is for entries with real invoice data to correct) — it can be manually re-queued via `POST /ledger/{job_id}/retry` or deleted.

## Frontend

**React + Vite + Tailwind** SPA with five views: an upload page (with live panels for jobs still processing and jobs that failed permanently, each with retry/delete actions), a review queue (every unconfirmed entry), the full ledger (confirmed entries), a per-job detail view showing the original image alongside the extracted data, and an edit form for human correction. See [`frontend/`](frontend/).

## Running it

```bash
# Backend + Postgres + Redis + worker + frontend
docker compose up

# Or locally:
uv sync
uv run alembic upgrade head                                # build the schema
uv run fastapi dev src/invoice_agent/api/main.py            # backend
uv run arq invoice_agent.queue.worker.WorkerSettings         # worker
cd frontend && npm install && npm run dev                   # frontend
```

`alembic upgrade head` builds the schema from empty — the chain starts by creating `ledgerentry` and `job`, then applies every change on top. It produces a schema identical to `SQLModel.metadata.create_all`, so the two setup paths can't drift.

The specialist model is served separately (see the serving scripts above) and reached via `VLLM_BASE_URL` / `VLLM_API_KEY`; the frontier fallback needs `ANTHROPIC_API_KEY`; the queue needs `REDIS_HOST` / `REDIS_PORT`. Configuration is via a `.env` file, loaded once in [`config.py`](src/invoice_agent/config.py).

## Tests & CI

121 tests across the workflow's routing and retry logic, error categorization, the task queue worker, reconciliation logic, dataset converters, schema, DB operations, and API routers ([`tests/`](tests/)). CI ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) runs `ruff` lint + format checks and the full `pytest` suite on every push.

## Tech stack

**ML / serving:** PyTorch · Unsloth · LoRA/SFT · Qwen3-VL · vLLM · MLflow · Modal
**Backend:** Python 3.12 · FastAPI · Pydantic · LangGraph · Redis · Arq · SQLModel · Alembic · Postgres · Docker
**Frontend:** React · Vite · Tailwind · React Router
**Frontier fallback:** Claude Haiku 4.5 (LangChain, structured output)

## Status & known limitations

This is an actively-developed learning project, not a production product. Honest caveats:

- **No rigorous evaluation harness yet.** There's no benchmark comparing the specialist vs. frontier vs. base model on field-level accuracy against a held-out golden set — the single biggest gap between "a pipeline that runs" and "a pipeline with a measured, defensible accuracy story."
- **No observability/tracing wired in.** Nothing currently traces a run's prompts, latency, or the specialist-vs-frontier split per job.
- **No auth.** The API and UI are wide open — fine for local/personal use, not for anything multi-user.
- Training data leans template-heavy (FATURA is synthetic) and receipt-heavy (CORD/SROIE); real-world invoice layout diversity is still limited, so out-of-domain documents lean more on the frontier fallback.
- The specialist uses manual JSON parsing; moving it to vLLM's **guided/structured decoding** (to constrain generation to the schema) would reduce malformed-output failures, though most observed failures so far are connectivity or schema-representability issues (e.g. a labor line item quantified in hours) rather than syntactically broken JSON.
- Uploaded files are stored on **local disk** (no S3/object storage) — deliberately scoped down for a personal project.

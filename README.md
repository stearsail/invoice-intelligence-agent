# Invoice Intelligence Agent

An end-to-end system that extracts structured data from invoices and receipts, validates it, and writes it to a reviewable ledger. A **fine-tuned small vision-language model** does the extraction cheaply on-device; a **frontier model** is used only as a fallback when the specialist's output fails validation. The whole pipeline is orchestrated as a stateful agent with automatic reconciliation and a human-review queue.

This is a personal project built to practice taking an LLM system all the way from *fine-tuning a model* to *running it as a service* — dataset preparation, training, serving, agent orchestration, a persistent ledger, an API, and a UI.

---

## What it does

1. A user uploads an invoice/receipt image through the web UI.
2. The backend stores the file and kicks off background processing.
3. A **fine-tuned Qwen3-VL-4B** model (served via vLLM) extracts the invoice as structured JSON.
4. The output is validated against a Pydantic schema and **reconciled** — line items are summed against the subtotal, the grand total is recomputed from its components, and the invoice number is checked against the existing ledger for duplicates.
5. If the specialist's output is malformed *or* fails reconciliation, the agent **falls back to a frontier model** (Claude Haiku 4.5), re-prompting it with the specific issues found.
6. The result is written to a Postgres ledger. Clean extractions land in the ledger; anything with unresolved issues is flagged into a **review queue** for a human to correct.

The design goal is cost/latency: the cheap specialist handles the common case, and the expensive model is only invoked when something actually looks wrong.

## Architecture

A React SPA uploads to a FastAPI backend, which records a job and hands off to the agent in the background. The agent calls the fine-tuned specialist (vLLM on a Modal GPU), validates and reconciles the result, escalates to the frontier model when needed, and writes the outcome to the Postgres ledger.

The agent itself is a [LangGraph](https://langchain-ai.github.io/langgraph/) state machine with conditional routing:

| Node | Responsibility |
|---|---|
| `specialist_extract` | Call the fine-tuned model; on a parse failure, route to the frontier extractor |
| `validate_reconcile` | Run schema, arithmetic, and duplicate checks |
| `frontier_extract_fallback` | Re-extract with the frontier model when the specialist's output is unusable |
| `frontier_review_fallback` | Retry with the reconciliation issues fed back as context |
| `ledger_write` | Persist the entry with a structured `review_reason` |

If the frontier retry still leaves issues, the entry is written anyway and marked `needs_review` rather than discarded.

The code is layered so each concern has one owner:

| Module | Owns |
|---|---|
| [`agent/extractors.py`](src/invoice_agent/agent/extractors.py) | The two model clients — no graph or state knowledge |
| [`agent/nodes.py`](src/invoice_agent/agent/nodes.py) | Translating graph state to and from the extractors |
| [`agent/graph.py`](src/invoice_agent/agent/graph.py) | Graph wiring; the single place dependencies are constructed |
| [`agent/runner.py`](src/invoice_agent/agent/runner.py) | Running the graph and returning a public `ExtractionResult` |
| [`services/extraction_job.py`](src/invoice_agent/services/extraction_job.py) | Job lifecycle — the seam a queue worker would consume |
| [`config.py`](src/invoice_agent/config.py) | All environment loading, in one place |

The graph's internal state never escapes the agent package, so the HTTP layer stays purely about HTTP. Validation logic lives in [`reconciliation.py`](src/invoice_agent/reconciliation.py).

## The model

The specialist is **Qwen3-VL-4B-Instruct**, fine-tuned with **LoRA (SFT)** on the [CORD](https://github.com/clovaai/cord) receipt dataset using [Unsloth](https://github.com/unslothai/unsloth), with runs tracked in **MLflow**. Only the language and MLP/attention layers are adapted — the vision tower is frozen. The adapter is merged into the base weights and served through **vLLM**'s OpenAI-compatible API.

- Training: [`scripts/train_qwen_vl.py`](scripts/train_qwen_vl.py)
- Dataset conversion: [`src/invoice_agent/converters/cord.py`](src/invoice_agent/converters/cord.py) — maps CORD's ground-truth annotations into the target `Invoice` schema, including a locale-aware number parser that handles the mixed `.`/`,` thousands/decimal conventions in the (Indonesian) receipts.
- Serving locally: [`scripts/serve_vllm.sh`](scripts/serve_vllm.sh)
- Serverless GPU serving: [`deploy/modal_app.py`](deploy/modal_app.py) — deploys the merged model to a [Modal](https://modal.com) L4 GPU as an autoscaling web server.

## The schema

Extraction targets a strict Pydantic model ([`src/invoice_agent/schema.py`](src/invoice_agent/schema.py)) with `extra="forbid"`: an `Invoice` with typed `Party` (vendor/customer), `LineItem`s, `Decimal` money fields, an ISO-4217 currency pattern, and a `document_type` literal. Using `Decimal` throughout keeps the reconciliation arithmetic exact.

## Backend

- **FastAPI**, fully async. Image upload streams to disk; processing runs as a background task so uploads return immediately with a `job_id` the frontend polls.
- **Postgres** ledger via **SQLModel**, with **Alembic** migrations ([`alembic/versions/`](alembic/versions/)). Two tables: `Job` (processing lifecycle) and `LedgerEntry` (the extracted invoice + review state).
- Routers for extraction ([upload / status / image](src/invoice_agent/api/routers/extraction.py)) and the ledger ([queue / full ledger / edit / delete](src/invoice_agent/api/routers/ledger.py)).

## Frontend

**React + Vite + Tailwind** SPA with four views: a review queue (only items needing attention), the full ledger (clean entries), a per-job detail view showing the original image alongside the extracted data, and an edit form for human correction. See [`frontend/`](frontend/).

## Running it

```bash
# Backend + Postgres + frontend
docker compose up

# Or locally:
uv sync
uv run alembic upgrade head                        # build the schema
uv run fastapi dev src/invoice_agent/api/main.py   # backend
cd frontend && npm install && npm run dev          # frontend
```

`alembic upgrade head` builds the schema from empty — the chain starts by creating `ledgerentry` and `job`, then applies every change on top. It produces a schema identical to `SQLModel.metadata.create_all`, so the two setup paths can't drift.

The specialist model is served separately (see the serving scripts above) and reached via `VLLM_BASE_URL` / `VLLM_API_KEY`; the frontier fallback needs `ANTHROPIC_API_KEY`. Configuration is via a `.env` file, loaded once in [`config.py`](src/invoice_agent/config.py).

## Tests & CI

100 tests across the agent routing, reconciliation logic, dataset converter, schema, DB operations, and API routers ([`tests/`](tests/)). CI ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) runs `ruff` lint + format checks and the full `pytest` suite on every push.

## Tech stack

**ML / serving:** PyTorch · Unsloth · LoRA/SFT · Qwen3-VL · vLLM · MLflow · Modal
**Backend:** Python 3.12 · FastAPI · Pydantic · LangGraph · SQLModel · Alembic · Postgres · Docker
**Frontend:** React · Vite · Tailwind · React Router
**Frontier fallback:** Claude Haiku 4.5 (LangChain, structured output)

## Status & known limitations

This is an actively-developed learning project, not a production product. Honest caveats:

- The specialist was fine-tuned on **CORD**, a single domain (Indonesian restaurant/retail receipts), so out-of-domain invoices lean more heavily on the frontier fallback. The pipeline is built to generalize; the *trained weights* are domain-limited.
- Uploaded files are stored on **local disk** (no S3/object storage) — deliberately scoped down for a personal project.
- The specialist currently uses manual JSON parsing; moving it to vLLM's **guided/structured decoding** (to constrain generation to the schema) is a planned improvement that should cut the malformed-output rate.
- Background processing uses FastAPI's `BackgroundTasks`, which runs in the API process — a restart mid-extraction loses the job. Swapping it for a durable queue is the next structural improvement; `run_extraction_job` is already shaped as the function a worker would consume.

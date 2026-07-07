# Project Plan: Invoice Intelligence Agent

**A document-processing agent powered by a fine-tuned specialist model**

Portfolio project for ML/AI Engineer roles.

## 1. Project Summary

An end-to-end agentic system that ingests messy invoices and receipts (digital PDFs, scans, photos), extracts structured data using a **fine-tuned small vision-language model** served locally, validates and reconciles the results, writes them to a ledger, and flags anomalies. A frontier model (Claude/GPT) acts as the agent's planner and as a fallback for documents the specialist cannot handle confidently.

**The thesis the project demonstrates:** for high-volume, narrow tasks, a fine-tuned 3–8B model can match frontier-model accuracy at a fraction of the cost and latency — and the right production architecture routes routine work to the specialist while reserving the frontier model for reasoning and edge cases.

The project is split into two independently demo-able milestones:

- **Milestone 1 — the specialist:** a fine-tuned, quantized, vLLM-served extraction model with a rigorous benchmark against frontier models.
- **Milestone 2 — the agent:** orchestration, tools, validation, observability, UI, and deployment wrapped around the specialist.

If Milestone 2 stalls, Milestone 1 alone is a complete, polished portfolio piece.

## 2. What This Project Proves (Skills Coverage)

- **Dataset engineering** — normalizing 3 public datasets, synthetic generation, human-verified golden set
- **Fine-tuning** — QLoRA on an 8B model, experiment iterations tracked in MLflow
- **Model optimization** — quantization (AWQ/GGUF), latency benchmarking
- **Inference serving** — vLLM behind an OpenAI-compatible endpoint
- **Evaluation rigor** — per-field metrics, locked test set, cost/latency/accuracy benchmark
- **Agent engineering** — Pydantic AI orchestration, tool calling, retry/fallback routing, MCP
- **Production engineering** — FastAPI, Docker Compose, CI with GitHub Actions, Langfuse tracing
- **Communication** — architecture diagram, benchmark writeup, honest failure analysis

## 3. Target Schema

Defined as Pydantic models and frozen before anything else is built; every component downstream depends on it.

An `Invoice` contains:

- `document_type` — invoice, receipt, or credit_note
- `vendor` — name, address, tax_id (VAT/CUI), optional IBAN
- `customer` — name, address, optional tax_id (invoices only)
- `invoice_number` — string
- `issue_date`, optional `due_date` — dates
- `currency` — ISO 4217 (RON, EUR, USD, ...)
- `line_items` — list of {description, quantity, unit_price, optional vat_rate, line_total}
- `subtotal`, `vat_amount`, `grand_total` — Decimal
- `payment_method` — optional string
- `confidence_notes` — list of model-reported uncertainties

Design rules: monetary values as `Decimal`, dates normalized to ISO 8601, currency always explicit, unknown fields are `null` — never guessed. The `confidence_notes` field gives the agent a signal for retry/escalation decisions.

## 4. Dataset Strategy

Three blended sources, one unified schema.

### 4.1 Public datasets (real-world noise for free)

- **CORD** — ~1,000 receipt images with detailed field annotations
- **SROIE** — ~1,000 scanned receipts, key-field extraction labels
- **DocILE** — business documents closest to real invoices

Task: write converters mapping each dataset's annotation format into the unified schema. Expect this to be fiddly — document the mapping decisions.

### 4.2 Synthetic invoice generator

- 6–10 HTML/CSS invoice templates rendered to PDF (WeasyPrint or Playwright)
- Populated via Faker: vendors, line items, VAT rates, currencies, dates
- Controlled edge cases: multi-page invoices, discounts, credit notes (negative lines), mixed date formats, RON/EUR/USD
- **Multilingual angle:** Romanian and English variants from the same templates — a genuine differentiator versus US-centric portfolio clones
- Optional degradation pass: render, rasterize, add noise/skew, then OCR, to simulate scan artifacts

### 4.3 Frontier-labeled real documents

- Collect unlabeled real invoices (personal, public samples)
- Label with a frontier model; **manually verify a subset**

### 4.4 Splits and the golden rule

- Training set: ~3,000–5,000 examples (mix of all three sources)
- **Golden test set: 150–300 documents, 100% human-verified, locked away from all training and tuning decisions.** Model-labeled data never enters the test set. No exceptions — this is what makes the benchmark credible.

## 5. Architecture

### 5.1 Extraction pipeline decision

**Primary path (build this):** fine-tune a small VLM (Qwen-VL family) directly on `image → JSON` — no OCR step in the critical path.

**Stretch comparison arm:** text pipeline — OCR first (PyMuPDF for digital PDFs, Tesseract for scans), fine-tune on `raw OCR text → JSON`, and add "end-to-end VLM vs OCR+LLM" as a benchmark dimension in the final writeup. (Investigated early: default Tesseract output on low-contrast, photographed receipts was poor enough — including some images returning no text at all — to motivate leading with the VLM path instead.)

### 5.2 System overview

Documents enter as a folder of PDFs or uploads through the UI. A Pydantic AI agent, with a frontier model as its planner, orchestrates four tools:

- **ingest_document** — render documents to images (PyMuPDF for PDFs; scans/photos used as-is)
- **extract_invoice** — the fine-tuned VLM specialist served via vLLM
- **validate_and_reconcile** — Pydantic schema checks plus math checks
- **ledger_write / flag_anomaly** — persistence to SQLite/Postgres and anomaly flagging

When extraction comes back with low confidence or fails validation, the agent falls back to frontier-model extraction; if that still fails, the document goes to a human-review queue.

Every run is traced in Langfuse, and at least one tool is exposed via MCP.

### 5.3 Agent behavior

1. Scan input folder / receive upload; classify document type
2. Render to image(s), then call `extract_invoice` (VLM specialist)
3. Validate: schema conformance, line items sum to subtotal, VAT math, duplicate invoice-number check
4. On low confidence or validation failure: retry with adjusted context, then escalate to the frontier model, then escalate to the human-review queue
5. Write validated records to ledger; flag anomalies (duplicates, outlier amounts, failed reconciliation)
6. Produce a batch summary report

The fallback chain **is** the cost-optimization story: measure what fraction of documents the specialist handles end-to-end.

## 6. Tech Stack

- **Base model:** Qwen2-VL (2B/7B) — small vision-language model, good multilingual (RO/EN), permissive license
- **Fine-tuning:** HF Transformers + PEFT (QLoRA) via Axolotl or Unsloth — single-GPU friendly
- **Compute:** RunPod / Vast.ai / Kaggle / Colab Pro — a QLoRA run on 8B costs a few dollars
- **Experiment tracking:** MLflow (self-hosted) — every run logged from day one; also serves as the model registry for versioning fine-tuned and quantized checkpoints
- **Quantization:** AWQ or GGUF — compare quality drop post-quantization
- **Serving:** vLLM, OpenAI-compatible endpoint
- **Agent framework:** Pydantic AI — typed, modern; raw tool-calling acceptable alternative
- **Tool protocol:** MCP for at least one tool — shows currency with the ecosystem
- **Validation:** Pydantic everywhere
- **Observability:** Langfuse (self-hosted) — trace every agent run
- **Ingestion:** PyMuPDF (PDF-to-image rendering only — no OCR in the primary pipeline; Tesseract stays scoped to the stretch comparison arm)
- **Backend:** FastAPI
- **Frontend demo:** Streamlit or Gradio — upload, watch the agent work, browse the ledger
- **Storage:** SQLite (dev), Postgres (compose)
- **Packaging:** Docker + docker-compose — one command boots vLLM + API + Langfuse + MLflow + UI
- **CI:** GitHub Actions — lint (ruff) and tests (pytest) on every push
- **Publishing:** HF Hub (model), HF Spaces or small VPS (demo)

## 7. Evaluation Plan

Built **before** fine-tuning, and never modified after the first fine-tuning run.

**Model-level metrics (per document, on the golden set):**

- Per-field exact match and F1 (string fields)
- Numeric accuracy with tolerance for totals/amounts; date accuracy after normalization
- Line-item alignment score (matched, missing, hallucinated items)
- Valid-JSON / schema-conformance rate
- Latency (p50/p95) and cost per document

**Benchmark matrix:** golden set × {GPT-4-class, Claude, base Qwen2-VL untuned, fine-tuned, fine-tuned + quantized}. This table is the centerpiece of the project.

**System-level metrics (Milestone 2):**

- End-to-end success rate per batch
- Specialist-only resolution rate vs fallback rate vs human-queue rate
- Cost per 1,000 invoices: frontier-only vs specialist + fallback architecture
- Anomaly detection precision on seeded errors (planted duplicates, broken sums)

## 8. Roadmap

### Milestone 1 — The Specialist

**Phase 1: Foundations**

- Repo scaffold, ruff + pytest + GitHub Actions CI, MLflow tracking server
- Freeze Pydantic schema
- Download CORD/SROIE/DocILE; write first converter (CORD)
- Deliverable: green CI, schema module with tests, CORD converted

**Phase 2: Data at scale**

- Remaining converters; synthetic generator with 6–10 templates, RO/EN
- Assemble training set (3–5k) and candidate golden set
- Begin human verification of golden set (150–300 docs)
- Deliverable: versioned dataset + datasheet documenting composition

**Phase 3: Evaluation harness**

- Implement all model-level metrics + benchmark runner
- Image ingestion module (PyMuPDF for PDF rendering)
- Deliverable: `evaluate.py` producing a full metrics report from any endpoint

**Phase 4: Baselines**

- Benchmark frontier models + untuned base model on golden set
- Analyze failure patterns to inform the data mixture
- Deliverable: baseline benchmark table ("the before picture")

**Phase 5: Fine-tuning**

- QLoRA runs: iterate on data mixture, prompt format, epochs (3–5 experiments in MLflow)
- Deliverable: best checkpoint beating base model meaningfully

**Phase 6: Optimize, serve, publish**

- Quantize best model; measure quality delta
- Serve via vLLM; re-run full benchmark including latency/cost
- Publish model card on HF Hub; polish Milestone 1 README
- Deliverable: **complete benchmark table + served model — Milestone 1 demo-able**

### Milestone 2 — The Agent

**Phase 7: Agent skeleton**

- Pydantic AI agent, frontier planner, tools: `ingest_document`, `extract_invoice`
- Langfuse wired in from the first run
- Deliverable: single-invoice happy path, fully traced

**Phase 8: Validation & routing**

- `validate_and_reconcile` (schema + math + duplicates)
- Retry logic, frontier fallback, human-review queue
- Deliverable: agent surviving a deliberately nasty test folder

**Phase 9: Ledger, anomalies, MCP**

- `ledger_write`, `flag_anomaly`, batch summary report
- Expose at least one tool via MCP; agent behavior tests in pytest (seeded error cases)
- Deliverable: batch run producing a populated ledger + anomaly report

**Phase 10: API & UI**

- FastAPI backend (upload, status, results, ledger endpoints)
- Streamlit/Gradio front-end: drag-and-drop, live agent progress, ledger browser
- Deliverable: local end-to-end demo through the UI

**Phase 11: Ship**

- docker-compose for full system; deploy demo (HF Spaces or VPS)
- System-level benchmark: cost per 1k invoices, specialist resolution rate
- Demo video (2–3 min)
- Deliverable: public live demo + system metrics

**Phase 12: The writeup**

- Architecture diagram, benchmark story, failure analysis, design decisions
- Blog-style post; final README pass; LinkedIn/portfolio publishing
- Deliverable: the document that gets you interviews

## 9. Risks & Mitigations

- **Dataset conversion drags on** — timebox converters; the synthetic generator can cover gaps
- **Fine-tuned model underperforms** — the baseline phase catches this early; iterate on the data mixture before blaming the model
- **VLM fine-tuning is heavier than a text-only path** — a small model size (2B) and single-GPU QLoRA keep it tractable; the OCR+LLM arm stays available as a fallback comparison if VLM training stalls
- **Scope creep (categorization, chatbots, dashboards)** — hard rule: no new features after the ledger/MCP phase. Depth over breadth
- **Golden set contamination** — test set locked in a separate directory, touched only by `evaluate.py`
- **Milestone 2 stalls** — Milestone 1 is independently complete and polished, by design
- **GPU costs** — QLoRA + spot instances; budget ceiling ~$30–50 total

## 10. Definition of Done (Portfolio Checklist)

- [ ] Public repo, clean structure, green CI badge
- [ ] README with architecture diagram + quickstart (`docker compose up`)
- [ ] Model published on HF Hub with a proper model card
- [ ] Benchmark table: accuracy / latency / cost across 5 model configurations
- [ ] Live demo link + 2–3 minute demo video
- [ ] Langfuse trace screenshots in the writeup
- [ ] Blog-style writeup including honest failure analysis
- [ ] System-level cost comparison: frontier-only vs specialist + fallback

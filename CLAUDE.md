# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Working style — most important rule

The user is building this project to learn the technologies hands-on. **Do not write implementation code unless explicitly asked.** Instead:

- Explain concepts and trade-offs before the user builds something
- Propose designs and assign tasks
- Review the user's code like a strict senior engineer — production bar, point out what's wrong and why, but let the user write the fix

## What this project is

An invoice-processing agent: a fine-tuned small LLM (served via vLLM) extracts structured data from invoices/receipts, wrapped in a Pydantic AI agent with validation, fallback to a frontier model, a ledger, and observability. The full roadmap, architecture, dataset strategy, and evaluation plan live in `invoice-agent-project-plan.md` — read it before proposing work.

Built in two milestones: (1) the fine-tuned specialist model with a rigorous benchmark, (2) the agent system around it. The golden test set, once created, is human-verified and locked — it must never be used for training or tuning decisions.


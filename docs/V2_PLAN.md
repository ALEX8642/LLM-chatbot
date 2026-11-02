# LLM-chatbot v2: plan and brief

Owner: Alexander Feht. This file briefs the coding-agent session that builds v2. Read it in full
before changing anything, and keep it current as decisions are made.

> **Superseded in detail by the approved design,**
> [`docs/superpowers/specs/2026-11-01-v2-design.md`](superpowers/specs/2026-11-01-v2-design.md)
> (2026-11-01). Where the two differ, the design wins. Main changes: verifiable claim-level citations
> are the core goal; the best generator is chosen by eval (Command R7B is kept as a like-for-like row,
> not the default); no Haystack; a held-out test set with a pre-registered headline; a demo stage;
> delivery tiers starting from a minimum credible version.

## Goal

Turn this manual-QA chatbot into a **measured** retrieval and agent system. The deliverable is not
only better code: it is a before/after story backed by an evaluation.

1. **Build the eval first, score v1 as it is today.** That is the baseline.
2. **Rebuild on a branch**, using the eval to decide every change.
3. **Score v2 with the same eval** and merge with a before/after table in the README.
4. **Add an agent layer** (tools + multi-step tasks) with its own scored task set.

The audience is a hiring engineer at an AI company (Cohere, for one) reading the repo for 2–5
minutes. They should see sound retrieval, honest evaluation that reports misses, and clean
engineering.

## Ground rules

- **Git:** tag the current `main` as `v1` before any change, then work on branch `v2`. Never rewrite
  history. Push the branch as you go. Merge to `main` only with Alexander's approval.
- **Show Alexander every change before pushing to a public branch** (this repo is public).
- **No secrets in the repo.** Endpoints, keys and hostnames go in `.env` (gitignored). The repo must
  run against any OpenAI-compatible endpoint, not just the owner's.
- **Public data only.** Bundle a few public-domain or permissively licensed manuals (US government
  publications, open-hardware documentation, and so on) so anyone can clone and run it. Record the
  source and licence of each one in `manuals/SOURCES.md`.
- **No invented numbers.** Every figure in the README comes from a committed results file.
- **Report misses.** Keep failures and negative results in the docs; don't tune them away.
- **Authorship framing:** the README says the code was written with AI coding agents (Claude Code,
  Codex, GitHub Copilot CLI) under Alexander's specification and review. Never claim hand-written code.
- Keep the closing licensing paragraph of the README (personal time, personal hardware, MIT).

## v1 review findings (2026-11-01)

- **No evaluation at all.** The tests cover helper functions only. This is the biggest gap.
- **Single-turn only**, with no conversation history. Answers are buffered and returned whole, not
  streamed to the UI.
- **Hard-wired to Ollama's `/api/chat`**, so it cannot use an OpenAI-compatible gateway (LiteLLM, vLLM).
- **Ingestion is PyMuPDF text only**, so tables and figures are lost. Docling would preserve structure.
- **Embeddings are `all-MiniLM-L6-v2`** (2021, 384-dim, 256-token window), weak for technical text.
- **The pipeline's MMR stage is a no-op.** The cross-encoder keeps 5 chunks, then MMR picks 5 of those 5.
  Diversity should select from a larger reranked pool.
- **Two relevance thresholds disagree:** the `MIN_DOC_SCORE` constant defaults to 0.2, the runtime
  default is 0.35.
- **Abstention is prompt-only.** With no eligible chunks the model is still called with an empty
  context. Decide whether v2 abstains in code.
- **Heavy dependencies** (`unstructured`, `pandas`, `scikit-learn`, Jupyter) that look unused.
- **No sample manuals**, so a reviewer cannot run it.

## Phase 1: evaluation (before touching the app)

- **Corpus:** 3–5 bundled public manuals of different styles (procedures, spec tables, troubleshooting).
- **Eval set:** about 40 questions in `evals/qa.jsonl`. Each has the gold page(s) and a short
  reference answer. Include answerable questions (single-page, multi-page, table lookups) and
  unanswerable ones (the manual does not cover it, so the right answer is to decline).
- Include figure-dependent questions (see Phase 2). v1 will mostly fail them; that is the baseline.
- **Retrieval metrics:**
  - recall@k for k = 1, 5, 10
  - MRR
  - citation correctness: the cited page holds the answer
- **Answer metrics:**
  - faithfulness: every claim is supported by the retrieved text. Use an LLM judge with a fixed
    prompt, and spot-check it by hand.
  - correctness against the reference answer
  - abstention: precision and recall on the unanswerable items
- **Runtime metrics:** latency p50 and p95.
- **Harness:** `evals/run_eval.py`, which writes results JSON to `evals/results/`. It must be
  re-runnable and deterministic where possible (fixed seeds, temperature 0 for the judge).
- **Score v1 unchanged.** Commit those results as the baseline.

## Phase 2: rebuild (branch `v2`)

Make one change at a time where practical and re-run the eval, so each gain can be attributed.

- **LLM client:** OpenAI-compatible (`/v1/chat/completions`), with base URL, key and model from env.
  Keep Ollama working through its OpenAI-compatible endpoint. Command R7B is kept as the like-for-like
  row against v1; the default generator is whichever model wins the eval (see the design).
- **Ingestion: choose the parser by eval, not by default.** Docling is the starting candidate (the
  owner's stack already runs docling-serve), but pull in something better if it exists. Shortlist
  current open-source parsers (for example Docling, MinerU, Marker, olmOCR and similar), run 2–3 of
  them on the bundled manuals, and score them on the eval's retrieval metrics plus table and figure
  fidelity. Record the comparison in a decision record (`docs/decisions/`), summarised in the README. Whichever parser wins: keep page numbers for
  citations, chunk by document structure rather than fixed length, and keep figures as images
  with their captions.
- **Embeddings:** a stronger current model, chosen by the eval rather than by reputation.
- **Retrieval:** keep the hybrid design (dense + BM25 → fusion → cross-encoder rerank), and fix the
  MMR ordering. Consider local, serverless stores for development (for example Qdrant local mode and
  an in-memory BM25) so the app runs without Docker. Keep the Docker Compose path for full deployment.
- **Chat:** multi-turn history and streamed answers to the UI.
- **Charts, graphs and figures (owner-requested feature).** The assistant must be able to *interpret*
  figures in the manuals (charts, graphs, wiring and exploded diagrams, tables rendered as images) and
  *show* them in its answers.
  - Extract figures at ingestion with page number, bounding box and caption.
  - Make them retrievable. Options to compare by eval:
    - a vision model writes a description or a data table for each figure, and that text is indexed
    - visual page retrieval (ColPali-style page-image embeddings) alongside text retrieval
  - At answer time, pass the relevant figure image to a vision-capable model when the question
    depends on it, for example reading a value off a curve.
  - Return the figure (image plus page citation) in the response, and render it inline in the UI.
  - **Eval:** add figure-dependent questions to `evals/qa.jsonl` (read a value from a chart, identify
    a part in a diagram) and report them as their own category, including misses.
- **Abstention:** decide on threshold behaviour in code, and measure it.
- **Cleanup:** prune unused dependencies, add tests for the pipeline, keep CI green.

## Phase 3: agent

- **Tools:** `search_manuals` (the v2 retriever), `web_search` (SearXNG, URL from env, optional),
  `ask_user` (a clarifying question), and possibly `read_page`.
- **Loop:** ReAct or plan-and-execute. Choose by measured task success, not fashion.
- **Task set:** 20–30 multi-step tasks in `evals/agent_tasks.jsonl`, for example "find the torque spec
  in manual A, then check whether manual B's procedure uses the same value", or "the manual doesn't
  cover X: ask or decline".
- **Score:** task success, tool-call correctness, number of steps and latency.
- Run it against at least two models through the gateway (for example Command R7B and a larger
  model) and report both.

## README for v2 (in this order; see the design's Presentation section)

1. What it is, in one paragraph, with a short GIF of a claim lighting up its source.
2. **Evaluation:** the pre-registered v1 → v2 headline table, then misses; method in `EVAL.md`.
3. Architecture diagram.
4. How to run it: local mode, Docker Compose, and replay mode.
5. How it was built.

## Reporting

At the end of each working session, commit to the branch and give Alexander a short summary: what
was done, the numbers, blockers and the next step.

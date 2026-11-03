# Overlay UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The core promise on screen: an answer whose claims light up their source regions on the page beside it, streamed claim by claim, with removed claims behind a "see why" disclosure, multi-turn chat, and a replay mode that plays recorded runs without the home network.

**Architecture:** A FastAPI server (`manualqa/server.py`) streams the events of `answer_stream` as server-sent events and serves page renders; every live answer is recorded as an event log, and `--replay` serves recorded logs instead of calling models. The React frontend (v1's stack: React 19, Vite, Tailwind) is rebuilt around two panels: the conversation with claims, and a page viewer that draws boxes as an overlay on the 150 dpi page render, so stored page-normalised boxes map to CSS percentages with no conversion.

**Tech Stack:** FastAPI + uvicorn (already dependencies), sse via `StreamingResponse`; React 19, TypeScript, Vite, Tailwind 4, Vitest; Playwright (pre-installed Chromium) for one end-to-end check in replay mode.

**Spec:** `docs/superpowers/specs/2026-11-01-v2-design.md` (Goal 1, Query 6 and 8, Demo stage, M1 review). Inputs: plan 3's `answer_stream` and events; plan 2's `data/ingest/pages/`.

## Global Constraints

- A claim appears only after its quote matched (event `claim_shown`), with a neutral "checking" mark until `claim_settled`; a removed claim disappears from the answer into "N claims removed, see why" with its reason.
- Highlights are drawn from stored boxes over the page render, never from a PDF text layer. Box → CSS: `left = x0·100%`, `top = y0·100%`, `width = (x1−x0)·100%`, `height = (y1−y0)·100%` of the rendered image.
- Click or hover a claim → the viewer shows its page and its boxes (no continuous scroll sync). Figure claims show "read from figure" and the figure's box.
- An abstention shows the fixed text and the pages that were looked at, as links to those pages.
- Replay mode never calls the generator, embedder or reranker; it serves recorded events and page images only.
- No endpoints, keys or host names in the frontend bundle or recordings; the frontend calls its own origin (`/api`).

## Review Focus

1. **Out-of-order or dropped SSE frames** (a frame split across network chunks, a final frame without trailing blank line): the client parser must assemble frames correctly. `parseSSE splits frames across chunks` (Task 3).
2. **A claim removed after it was shown**: it must leave the answer and the overlay, and appear under "removed". `removed claim leaves the answer` (Task 3).
3. **Boxes on a different page from the one in view**: clicking the claim switches page first, then draws. `click switches page then highlights` (Task 3).
4. **Replay of a question that was not recorded**: a clear "not in this recording" message, not a hang. `test_replay_unknown_question` (Task 2).
5. **Follow-up turns**: history goes to the server, and the rewritten standalone question is shown in the event log. `test_follow_up_sends_history` (Task 1).

---

### Task 1: Server: SSE answers, pages, manuals, recordings

**Files:** create `manualqa/server.py`, `tests/manualqa/test_server.py`.

**Interfaces — produces:** `create_app(ctx: IngestContext | None, gen, recordings: Path, replay: Path | None = None) -> FastAPI` with
- `GET /api/manuals` → `[{"file", "title", "pages"}]` (titles from `manuals/SOURCES.md` table, falling back to the file stem);
- `GET /api/pages/{stem}/{page}` → the display JPEG from `data/ingest/pages/`;
- `POST /api/ask` body `{"question", "manual", "history": [{"role","content"}]}` → `text/event-stream` of `event: <kind>\ndata: <json>\n\n` for `retrieved` (pages, evidence count, standalone question), `claim_shown` / `claim_settled` / `claim_removed` (claim, block, quote, page, boxes, status, reason), `done` (text, abstained, abstain_reason, removed count, timings);
- each live answer appended to `recordings/<date>.jsonl` as `{"question", "manual", "history", "events": [...]}`.
- CLI `python -m manualqa.server --ingest data/ingest [--replay FILE] [--port 8000]`.

- [ ] Tests (FastAPI `TestClient`, the fixture `ctx`, plan 3's `FakeGen`): `test_ask_streams_events_in_order`; `test_event_payload_has_boxes`; `test_pages_served`; `test_manuals_listed`; `test_answer_recorded`; `test_follow_up_sends_history`. FAIL → implement → PASS → commit `manualqa: server (SSE answers, pages, manuals, recordings)`.

### Task 2: Replay mode

**Files:** modify `manualqa/server.py`; extend `tests/manualqa/test_server.py`.

Behaviour: with `replay=FILE`, `/api/ask` looks up the recording by (`manual`, normalised question, history length) and streams its events with the recorded spacing capped at 300 ms; unknown → one `done` event with `{"text": "This question is not in the recording.", "replay_miss": true}`. `/api/manuals` lists only manuals in the recording; pages are served as usual.

- [ ] Tests: `test_replay_serves_recorded_events_without_models` (ctx and gen are None); `test_replay_unknown_question`. FAIL → implement → PASS → commit `manualqa: replay mode`.

### Task 3: Frontend: conversation, claims, overlay viewer

**Files:** replace `frontend/src/SupportAssistant.tsx` with `frontend/src/App.tsx`, `src/api.ts` (SSE client), `src/sse.ts` (frame parser), `src/Conversation.tsx`, `src/ClaimList.tsx`, `src/PageViewer.tsx`, `src/boxes.ts`; tests in `frontend/src/*.test.ts(x)` (Vitest + Testing Library); `vite.config.ts` proxy `/api` → `http://localhost:8000`.

**Interfaces — produces:** `parseSSE(chunks: AsyncIterable<string>): AsyncIterable<{event: string, data: any}>`; `boxStyle(box: Box): CSSProperties`; `ask(question, manual, history): AsyncIterable<AnswerEvent>`.

- [ ] Tests: `parseSSE splits frames across chunks`; `boxStyle maps normalised box to percentages`; `claim shows checking mark until settled`; `removed claim leaves the answer` (and appears under "N claims removed, see why" with its reason); `click switches page then highlights`; `abstention lists pages as links`. FAIL → implement → PASS (`npm test`), `npm run lint`, `npm run build` → commit `frontend: v2 conversation with claim overlays`.

### Task 4: End-to-end check, reference screenshots, M1 package

**Files:** create `frontend/e2e/replay.spec.ts` (Playwright), `docs/m1/` (screenshots, live answers, notes).

- [ ] With a recording of 10 live dev answers (made in plan 3's dev run, through the server), start the server in replay mode and the built frontend; the Playwright test asks two recorded questions and checks: claims appear, a removed claim is listed with its reason, clicking a claim highlights boxes on the right page (screenshot), the abstention case lists pages.
- [ ] Commit the screenshots (parts row highlight with the CAGE trap removed, rating-plate figure claim, letter-spaced operator page highlight, an abstention) and the 10 answers to `docs/m1/`, with a one-page note for the M1 review: does the promise look true; are removed claims sensible.
- [ ] Commit `docs/m1: reference screenshots and live answers for the M1 review`; push; then dispatch the M1 review (fresh reviewer on the most capable model) on `docs/m1/` and the code.

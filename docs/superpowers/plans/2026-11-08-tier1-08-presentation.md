# Tier 1 plan 8: presentation

**Goal:** a reader can see the result, its limits and the misses in a minute, and reproduce them. **Spec:**
`docs/superpowers/specs/2026-11-01-v2-design.md`, "Presentation".

- [x] README: headline table, judge caveat, misses, cost, not yet tested.
- [x] `EVAL.md`: the method in one place (split, judge, registration, analysis, blind check, deviations).
- [x] Demo GIF from the replay of real answers, replacing the still image.
- [x] Running v2: ingest, serve, replay, with the hardware it needs.
- [x] Repository layout section brought up to date.
- [x] External benchmark: decision 005, if Alexander agrees; a section left for it in the README.
- [x] Cold clone (2026-11-09), commit `8223b9e` from GitHub on a fresh directory: `uv sync --extra dev` in 1.5 s with a
  warm cache; 348 tests passed, 6 skipped (laptop, GPU); `evals.analysis` reproduces 0.805 / 0.420, +0.385, 0.209 to
  0.516; replay serves 3 manuals, renders page 59 on demand and replays a recorded answer. Interface: `npm ci`, build and
  9 unit tests pass. Not repeated: the five-hour parse and a live answer, which need a GPU and a generator endpoint.
- [ ] M4 review by Alexander.

# Results

| File | What it is |
|---|---|
| `TEST.md` | The registered held-out result, checks and misses |
| `test/` | Judge outputs for the test runs (`<system>-test-<judge>.json`), the analysis, v2's labelled misses, the failed attempt's log |
| `raw/` | Generated answers, one file per system and item set (`*-test.json`, `*-dev172.json`, earlier `*-dev*.json`) |
| `NOTES-v2-dev.md` | Development runs on the dev set, in order, with what each change did |
| `v1-dev172-*.json`, `v1-t0-dev172-*.json`, `v2-dev172-*.json` | Judge outputs for the dev set (phi4, mistral) |
| `NOTES.md`, `v1.json`, `v1-strict.json`, `v2-dev*.json` | History: the first 42 questions under the old holistic judge |
| `selection/` | Embedder and reranker comparison, 16 GB and 32 GB |
| `vidore/` | ViDoRe V3 industrial retrieval run |

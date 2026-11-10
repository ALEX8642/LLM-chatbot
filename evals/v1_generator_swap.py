"""Run v1 with another generator, for a like-for-like comparison with v2.

v1 (tag ``v1``) answers through one function, ``api.query_ollama``. This loads the registered
harness (tag ``prereg``) and, before it wraps that function, points it at the OpenAI-compatible
endpoint v2 uses (GEN_BASE_URL, GEN_API_KEY, GEN_MODEL) with v2's settings: temperature 0, seed
0, thinking off. v1's code, prompt, retrieval and citations are unchanged; only the model is.

    python -m evals.v1_generator_swap --harness ../llm-prereg/evals/run_eval.py \\
        generate --system v1 --app-dir ../LLM-chatbot-v1 --qa evals/test.jsonl --out RAW.json
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path


def query_openai(prompt: str, model: str | None = None, url: str | None = None) -> str:
    """v1's query_ollama signature, answered by the GEN_* endpoint."""
    import requests

    key = os.environ.get("GEN_API_KEY")
    resp = requests.post(
        f"{os.environ['GEN_BASE_URL'].rstrip('/')}/v1/chat/completions",
        json={
            "model": os.environ["GEN_MODEL"],
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "seed": 0,
            "chat_template_kwargs": {"enable_thinking": False},
        },
        headers={"Authorization": f"Bearer {key}"} if key else {},
        timeout=300,
    )
    resp.raise_for_status()
    return (resp.json()["choices"][0]["message"]["content"] or "").strip()


def main(argv: list[str]) -> None:
    harness_path = Path(argv[argv.index("--harness") + 1]).resolve()
    rest = [
        a for i, a in enumerate(argv) if a != "--harness" and argv[i - 1] != "--harness"
    ]
    app_dir = Path(rest[rest.index("--app-dir") + 1]).resolve()

    os.environ["OLLAMA_MODEL"] = os.environ[
        "GEN_MODEL"
    ]  # so the run records the real model
    sys.path.insert(0, str(app_dir))
    import api  # v1's module; the harness imports this same object

    api.query_ollama = query_openai
    sys.path.insert(0, str(harness_path.parents[1]))
    spec = importlib.util.spec_from_file_location("prereg_run_eval", harness_path)
    harness = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(harness)
    for name, make in list(harness.ADAPTERS.items()):

        def swapped(a, make=make):
            run = make(a)
            run.config.update(
                llm_backend="openai-compatible (evals/v1_generator_swap.py)",
                temperature=0,
            )
            return run

        harness.ADAPTERS[name] = swapped
    sys.argv = [str(harness_path), *rest]
    harness.main()


if __name__ == "__main__":
    main(sys.argv[1:])

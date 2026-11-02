"""Summarise spike metrics of all parsers as one markdown table.

uv run python -m evals.spike.report docs/spike/*/metrics.json
"""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

HEADER = (
    "| parser | pages | errors | validate problems | coord agreement (median IoU) "
    "| CER letter-spaced (median) | cell checks | cells with boxes | s/page |\n"
    "|---|---|---|---|---|---|---|---|---|"
)


def _median(values: list) -> str:
    values = [v for v in values if v is not None]
    return f"{statistics.median(values):.2f}" if values else "n/a"


def summarise(all_metrics: list[dict]) -> str:
    rows = [HEADER]
    for m in all_metrics:
        pages = m["pages"]
        cells = sum(p["cells"] for p in pages)
        boxed = sum(p["cells_with_boxes"] for p in pages)
        checks = m["cell_checks"]
        rows.append(
            "| "
            + " | ".join(
                [
                    m["parser"],
                    str(len(pages)),
                    str(sum(p["error"] is not None for p in pages)),
                    str(sum(len(p["problems"]) for p in pages)),
                    _median([p["coord_agreement"] for p in pages]),
                    _median([p["cer"] for p in pages]),
                    f"{sum(c['passed'] for c in checks)}/{len(checks)}",
                    f"{boxed}/{cells}" if cells else "n/a",
                    _median([p["seconds"] for p in pages]),
                ]
            )
            + " |"
        )
    return "\n".join(rows)


def main(argv: list[str] | None = None) -> int:
    paths = argv if argv is not None else sys.argv[1:]
    print(summarise([json.loads(Path(p).read_text()) for p in paths]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

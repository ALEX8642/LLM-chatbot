"""Re-run the wording check on every claim a recorded v2 run verified, from the block text the
raw file keeps. No model or index is needed.

    python -m evals.wording_audit evals/results/raw/v2-test.json evals/results/raw/v2-dev172.json
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from manualqa.facts import check_wording
from manualqa.quotes import match_quote
from manualqa.retrieve import Evidence

_BLOCK = re.compile(r"^\[([^\]]+)\] \(page (\d+)\) ", re.M)


def blocks(context: str) -> dict[str, str]:
    """Block id to text, from the context a raw record shows the model."""
    out, found = {}, list(_BLOCK.finditer(context))
    for i, m in enumerate(found):
        end = found[i + 1].start() if i + 1 < len(found) else len(context)
        out[m.group(1)] = context[m.end() : end].rstrip("\n")
    return out


def audit(path: Path) -> tuple[int, list[tuple[str, str, str]]]:
    """Verified claims, and those the wording check would remove: (item, quote, reason)."""
    data = json.loads(Path(path).read_text())
    verified, refused = 0, []
    for repeat in data["repeats"]:
        for record in repeat:
            text_of = blocks(record.get("context") or "")
            for c in record.get("claims") or []:
                if c["status"] != "verified" or c["block"] not in text_of:
                    continue
                verified += 1
                text = text_of[c["block"]]
                ev = Evidence(
                    c["block"], "text", "", c["page"] or 0, c["block"], text, []
                )
                m = match_quote(c["quote"], ev)
                result = (
                    check_wording(c["quote"], m.source, text[: m.span[0]])
                    if m
                    else None
                )
                if result is not None and not result.ok:
                    refused.append((record["id"], c["quote"], result.reason or ""))
    return verified, refused


def main(argv: list[str] | None = None) -> int:
    for path in argv if argv is not None else sys.argv[1:]:
        verified, refused = audit(Path(path))
        print(f"{path}: {verified} verified, {len(refused)} the wording check refuses")
        for item, quote, reason in refused:
            print(f"  {item}: {reason}: {quote[:100]!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Parser adapters. Each turns PDF pages into ``PageParse`` objects (see
``manualqa.blocks``). Heavy libraries are imported only inside the chosen adapter."""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Callable, Protocol

from manualqa.blocks import PageParse
from manualqa.ocr_detect import OcrDecision


class Parser(Protocol):
    name: str

    def parse(
        self, pdf: Path, pages: list[int], ocr: dict[int, OcrDecision]
    ) -> list[PageParse]: ...


def _lazy(module: str, cls: str) -> Callable[[], Parser]:
    def make() -> Parser:
        return getattr(importlib.import_module(module), cls)()

    return make


PARSERS: dict[str, Callable[[], Parser]] = {
    "textlayer": _lazy("manualqa.parsers.textlayer", "TextLayerParser"),
    "docling": _lazy("manualqa.parsers.docling_parser", "DoclingParser"),
    "paddle": _lazy("manualqa.parsers.paddle_parser", "PaddleParser"),
}


def get_parser(name: str) -> Parser:
    try:
        return PARSERS[name]()
    except KeyError:
        raise ValueError(f"unknown parser {name!r}; known: {sorted(PARSERS)}") from None

"""Generator client and the streaming claim parser.

The generator is any OpenAI-compatible chat endpoint (settings from the environment:
GEN_BASE_URL, GEN_API_KEY, GEN_MODEL). Claims arrive one JSON object per line and are
parsed as soon as their line closes, so each can be checked and shown while the rest
of the answer streams.
"""

from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from manualqa.prompts import SYSTEM
from manualqa.retrieve import Evidence


@dataclass
class RawClaim:
    claim: str
    block: str
    quote: str
    raw: str


class ClaimParser:
    def __init__(self) -> None:
        self._buffer = ""
        self.ignored: list[str] = []
        self.abstain: str | None = None

    def _line(self, line: str) -> list[RawClaim]:
        line = line.strip()
        if not line or line.startswith("```"):
            return []
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            self.ignored.append(line)
            return []
        if isinstance(obj, dict) and "abstain" in obj:
            self.abstain = str(obj["abstain"])
            return []
        if isinstance(obj, dict) and {"claim", "block"} <= obj.keys():
            return [
                RawClaim(
                    str(obj["claim"]),
                    str(obj["block"]),
                    str(obj.get("quote", "")),
                    line,
                )
            ]
        self.ignored.append(line)
        return []

    def feed(self, text: str) -> list[RawClaim]:
        """Claims whose line was completed by this piece of text."""
        self._buffer += text
        *lines, self._buffer = self._buffer.split("\n")
        return [c for line in lines for c in self._line(line)]

    def close(self) -> list[RawClaim]:
        rest, self._buffer = self._buffer, ""
        return self._line(rest)


def _image_part(path: Path) -> dict:
    data = base64.b64encode(Path(path).read_bytes()).decode()
    return {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{data}"}}


def build_messages(
    question: str,
    history: list[dict],
    evidence: list[Evidence],
    page_images: list[Path],
) -> list[dict]:
    lines = [
        f"[{e.id}] (page {e.page}{f', under: {e.under}' if e.under else ''}) {e.text}"
        for e in evidence
    ]
    text = "Evidence:\n" + "\n\n".join(lines) + f"\n\nQuestion: {question}"
    content = [{"type": "text", "text": text}] + [_image_part(p) for p in page_images]
    return [
        {"role": "system", "content": SYSTEM},
        *history,
        {"role": "user", "content": content},
    ]


class Generator:
    def __init__(self, base_url: str, api_key: str | None, model: str, session=None):
        import requests

        self.base_url, self.api_key, self.model = base_url.rstrip("/"), api_key, model
        self._session = session or requests.Session()
        self.extra_body = {"chat_template_kwargs": {"enable_thinking": False}}

    @classmethod
    def from_env(cls) -> Generator:
        return cls(
            os.environ["GEN_BASE_URL"],
            os.environ.get("GEN_API_KEY"),
            os.environ["GEN_MODEL"],
        )

    def stream(self, messages: list[dict]) -> Iterator[str]:
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        body = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "temperature": 0,
            "seed": 0,
            **self.extra_body,
        }
        resp = self._session.post(
            f"{self.base_url}/v1/chat/completions",
            json=body,
            headers=headers,
            stream=True,
            timeout=300,
        )
        resp.raise_for_status()
        for raw in resp.iter_lines(decode_unicode=True):
            if not raw or not raw.startswith("data:"):
                continue
            data = raw[5:].strip()
            if data == "[DONE]":
                break
            delta = json.loads(data)["choices"][0].get("delta", {})
            if delta.get("content"):
                yield delta["content"]

    def complete(self, messages: list[dict]) -> str:
        return "".join(self.stream(messages))

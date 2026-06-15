"""
Unit tests for the pure utility functions in api.py.
No running services are required — conftest.py stubs out all heavy imports.
"""
import pytest
from unittest.mock import MagicMock, patch
import api


# ── Helpers ──────────────────────────────────────────────────────────────────

def make_doc(content="some text", page=1, score=0.9, product_id="P1", manual_id="M1"):
    doc = MagicMock()
    doc.content = content
    doc.score = score
    doc.meta = {"page": page, "product_id": product_id, "manual_id": manual_id}
    return doc


# ── make_prompt ───────────────────────────────────────────────────────────────

class TestMakePrompt:
    def test_question_appears_in_prompt(self):
        prompt = api.make_prompt("What is the focus distance?", [])
        assert "What is the focus distance?" in prompt

    def test_no_docs_shows_fallback_message(self):
        prompt = api.make_prompt("anything", [])
        assert "No sufficiently relevant" in prompt

    def test_doc_content_and_page_appear(self):
        doc = make_doc(content="Minimum focus distance is 30 cm.", page=42)
        prompt = api.make_prompt("focus?", [doc])
        assert "30 cm" in prompt
        assert "Page 42" in prompt

    def test_top_k_limits_context(self):
        docs = [make_doc(content=f"chunk {i}", page=i) for i in range(10)]
        prompt = api.make_prompt("q", docs, top_k=3)
        assert "chunk 0" in prompt
        assert "chunk 1" in prompt
        assert "chunk 2" in prompt
        assert "chunk 3" not in prompt

    def test_empty_docs_with_top_k_zero(self):
        prompt = api.make_prompt("q", [], top_k=0)
        assert "No sufficiently relevant" in prompt


# ── build_citations ───────────────────────────────────────────────────────────

class TestBuildCitations:
    def test_returns_page_and_product(self):
        docs = [make_doc(page=5, product_id="CAM-X")]
        result = api.build_citations(docs)
        assert result == [{"page": 5, "product": "CAM-X"}]

    def test_empty_input_returns_empty(self):
        assert api.build_citations([]) == []

    def test_multiple_docs(self):
        docs = [make_doc(page=1, product_id="A"), make_doc(page=2, product_id="B")]
        result = api.build_citations(docs)
        assert len(result) == 2
        assert result[0]["page"] == 1
        assert result[1]["product"] == "B"

    def test_missing_meta_uses_defaults(self):
        doc = MagicMock()
        doc.meta = {}
        result = api.build_citations([doc])
        assert result[0]["page"] == 1       # build_citations defaults to 1
        assert result[0]["product"] is None


# ── build_manual_sections ─────────────────────────────────────────────────────

class TestBuildManualSections:
    def test_snippet_truncated_at_limit(self):
        long_text = "x" * 500
        doc = make_doc(content=long_text, page=1)
        sections = api.build_manual_sections([doc], snippet_chars=280)
        assert len(sections[0]["snippet"]) <= 284  # 280 + "…"
        assert sections[0]["snippet"].endswith("…")

    def test_short_text_not_truncated(self):
        doc = make_doc(content="Short text.", page=1)
        sections = api.build_manual_sections([doc])
        assert sections[0]["snippet"] == "Short text."
        assert not sections[0]["snippet"].endswith("…")

    def test_max_sections_limits_output(self):
        docs = [make_doc(page=i) for i in range(5)]
        sections = api.build_manual_sections(docs, max_sections=2)
        assert len(sections) == 2

    def test_empty_content_handled(self):
        doc = make_doc(content="")
        sections = api.build_manual_sections([doc])
        assert sections[0]["snippet"] == ""

    def test_newlines_collapsed(self):
        doc = make_doc(content="line one\nline two\nline three")
        sections = api.build_manual_sections([doc])
        assert "\n" not in sections[0]["snippet"]


# ── query_ollama ──────────────────────────────────────────────────────────────

class TestQueryOllama:
    def test_concatenates_streamed_chunks(self):
        import json
        lines = [
            json.dumps({"message": {"content": "Hello "}}),
            json.dumps({"message": {"content": "world"}}),
            json.dumps({"done": True}),
        ]
        mock_response = MagicMock()
        mock_response.iter_lines.return_value = [l.encode() for l in lines]

        with patch("api.requests.post", return_value=mock_response):
            result = api.query_ollama("say hi", model="test-model", url="http://fake")
        assert result == "Hello world"

    def test_raises_on_http_error(self):
        # requests is mocked in conftest, so we use a plain exception
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = RuntimeError("500 Server Error")

        with patch("api.requests.post", return_value=mock_response):
            with pytest.raises(RuntimeError):
                api.query_ollama("q", url="http://fake")

    def test_skips_malformed_json_lines(self):
        import json
        lines = [
            b"not-json",
            json.dumps({"message": {"content": "ok"}}).encode(),
            json.dumps({"done": True}).encode(),
        ]
        mock_response = MagicMock()
        mock_response.iter_lines.return_value = lines

        with patch("api.requests.post", return_value=mock_response):
            result = api.query_ollama("q", url="http://fake")
        assert result == "ok"

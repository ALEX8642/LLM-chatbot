"""Deterministic stand-ins for model-backed components in tests."""

import hashlib

from manualqa.index import tokens


class FakeEmbedder:
    """Bag-of-tokens vectors: enough to exercise the dense path."""

    name, dim = "fake", 64

    def embed(self, texts, query=False):
        out = []
        for t in texts:
            v = [0.0] * self.dim
            for tok in tokens(t):
                v[int(hashlib.md5(tok.encode()).hexdigest(), 16) % self.dim] += 1.0
            norm = sum(x * x for x in v) ** 0.5 or 1.0
            out.append([x / norm for x in v])
        return out


class FakeReranker:
    """Scores by the share of query tokens found in the text."""

    name = "fake"

    def score(self, query, texts):
        q = set(tokens(query))
        return [len(q & set(tokens(t))) / (len(q) or 1) for t in texts]

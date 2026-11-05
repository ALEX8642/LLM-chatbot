"""Does the source say what the claim says? The layer the deterministic checks cannot be.

A claim can hold every right number and still say the opposite ("may crank as long as
needed" on "do not crank in excess of"). The checker compares its meaning with the source.
"""

from __future__ import annotations

from manualqa.prompts import CLAIM_CHECK
from manualqa.retrieve import Evidence

PREMISE_CHARS = 2000  # a long block is cut, keeping the claim's quote in view


def premise_for(ev: Evidence, match_span: tuple[int, int] | None = None) -> str:
    """What the claim is judged against: its whole block or row, and the headings above it.

    Not the quote alone: a claim's subject is often in the sentence before ("Step 1. Check
    for dirty air cleaner element" under the malfunction it treats).
    """
    text = ev.text
    if len(text) > PREMISE_CHARS:
        middle = sum(match_span) // 2 if match_span else 0
        start = max(0, middle - PREMISE_CHARS // 2)
        text = text[start : start + PREMISE_CHARS]
    return f"({ev.under})\n{text}" if ev.under else text


class LLMChecker:
    """The generator asked yes or no."""

    def __init__(self, generator):
        self.generator = generator

    def supported(self, claim: str, premise: str) -> float:
        reply = self.generator.complete(
            [
                {
                    "role": "user",
                    "content": CLAIM_CHECK.format(premise=premise, claim=claim),
                }
            ]
        )
        return 1.0 if reply.strip().lower().startswith("yes") else 0.0


class NLIChecker:
    """A cross-encoder trained for entailment; returns the probability of entailment."""

    def __init__(self, model: str, device: str | None = None):
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        self.torch = torch
        self.tokenizer = AutoTokenizer.from_pretrained(model)
        self.model = AutoModelForSequenceClassification.from_pretrained(model).eval()
        if device:
            self.model.to(device)
        self.device = device
        labels = {v.lower(): k for k, v in self.model.config.id2label.items()}
        self.entailment = labels["entailment"]

    def supported(self, claim: str, premise: str) -> float:
        batch = self.tokenizer(
            premise, claim, truncation=True, max_length=512, return_tensors="pt"
        )
        if self.device:
            batch = batch.to(self.device)
        with self.torch.no_grad():
            logits = self.model(**batch).logits[0]
        return float(logits.softmax(-1)[self.entailment])

"""Does the source say what the claim says? The layer the deterministic checks cannot be.

A claim can hold every right number and still say the opposite ("may crank as long as
needed" on "do not crank in excess of"). The checker compares its meaning with the source.
"""

from __future__ import annotations

from manualqa.retrieve import Evidence

PROMPT = """You check one claim against an excerpt from a technical manual.

Answer yes only if the excerpt says what the claim says, including its conditions, direction
and any negation. A claim may reword the excerpt, and may name the subject the excerpt sits
under. Answer no if the excerpt contradicts the claim, or the claim adds something the excerpt
does not state.

Excerpt:
{premise}

Claim: {claim}

Reply with yes or no only."""


def premise_for(ev: Evidence, source: str) -> str:
    """What the claim is judged against: the matched text, or the whole row, and its heading."""
    text = ev.text if ev.kind == "row" else source
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
                    "content": PROMPT.format(premise=premise, claim=claim),
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

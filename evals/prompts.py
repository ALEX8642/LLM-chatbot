"""Prompts for the key-fact judge. Bump PROMPT_VERSION when any of them changes."""

PROMPT_VERSION = 1

KEY_FACTS = """KEY FACTS CHECK. You grade an answer from a technical-manual assistant.

Question: {question}

Key facts the answer must state:
{facts}

Assistant answer:
<<<
{answer}
>>>

For each key fact, decide whether the answer states it. Equivalent wording and units count;
a different value does not. Extra detail does not matter.
"abstained" is true if the assistant does not commit to an answer: it declines, or says the
manual does not contain the information.

Reply with JSON only, one entry per key fact, in order:
{{"abstained": true|false, "facts": [{{"fact": "<the key fact>", "present": true|false}}]}}"""

SOURCE_SUPPORT = """SOURCE CHECK. You check whether a cited source supports key facts.

Key facts:
{facts}

Cited source (extracted from a PDF; tables may be flattened):
<<<
{source}
>>>

"supported" is true only if every key fact can be found in the cited source.

Reply with JSON only: {{"supported": true|false, "missing": ["<fact not found>"]}}"""

ABSTAINED = """You read an answer from a technical-manual assistant.

Question: {question}

Assistant answer:
<<<
{answer}
>>>

"abstained" is true if the assistant does not commit to an answer: it declines, or says the
manual does not contain the information, even if it then suggests where else to look. It is
false if it gives a substantive answer, even a wrong or hedged one.

Reply with JSON only: {{"abstained": true|false}}"""

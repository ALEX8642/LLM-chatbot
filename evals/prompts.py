"""Prompts for the key-fact judge. Bump PROMPT_VERSION when any of them changes."""

PROMPT_VERSION = 3  # 2: an off-topic answer is not an abstention (ABSTAINED only)
# 3: a long cited source is checked one key fact at a time, on its passages nearest that fact
#    (evals/grade.py); a reply with the wrong number of facts is asked again; the source check
#    is given the question, since a fact alone ("life is cut by 50%") reads as a general claim

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

FACT_COUNT = """

There are exactly {n} key facts above. Reply with exactly {n} entries in "facts", one per key
fact, in the order given, even if a fact is not stated."""

SOURCE_SUPPORT = """SOURCE CHECK. You check whether a cited source supports key facts.

Question: {question}

Key facts (parts of the answer to the question):
{facts}

Cited source (extracted from a PDF; tables may be flattened):
<<<
{source}
>>>

"supported" is true only if every key fact can be found in the cited source, stated for what the
question asks about. Equivalent wording and units count; a different value does not.

Reply with JSON only: {{"supported": true|false, "missing": ["<fact not found>"]}}"""

ABSTAINED = """You read an answer from a technical-manual assistant.

Question: {question}

Assistant answer:
<<<
{answer}
>>>

"abstained" is true only if the assistant says it cannot answer, or says the manual does not
contain the information, even if it then suggests where else to look or adds related facts.
It is false if it states facts without saying the information is missing, even if those facts
are off-topic and do not answer the question, and false for a wrong or hedged answer.

Reply with JSON only: {{"abstained": true|false}}"""

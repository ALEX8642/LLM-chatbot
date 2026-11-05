"""Build the labelled claim set for choosing the meaning check. Dev items only.

Supported claims are real ones from a dev run, read by hand. Unsupported claims are written
by hand from those: each keeps the numbers and identifiers of a real claim and changes what
it says, because that is what the deterministic checks cannot see. They show what a checker
can catch, not how often the generator makes such errors.

    python -m evals.claims.build RAW COMPOSED TABLES > evals/claims/labelled.jsonl
"""

from __future__ import annotations

import json
import random
import re
import sys
from pathlib import Path
from types import SimpleNamespace

from manualqa.blocks import load_pages
from manualqa.claimcheck import premise_for
from manualqa.quotes import match_quote
from manualqa.retrieve import _block_evidence, row_evidence, titles_by_page
from manualqa.tables import TableStore

SAMPLE_SEED, SAMPLE = 5, 70
UNSUPPORTED = {
    0: "The voltage reconnection switch cannot be set for 120-volt, single phase, 2 wire.",
    3: "The operator manual says not to use LO 9-6115-641-12 for lubrication information.",
    4: "The zeroing process is done once and must not be repeated.",
    7: "If the coolant level is full, the procedure says to skip Step 4.",
    8: "In level flight the wings of a 3,000-pound airplane must support 6,000 pounds.",
    12: "Check the reset button for a green band.",
    13: "Open the drain cock (1).",
    14: "The starter must not be allowed to cool for more than fifteen seconds between attempted starts.",
    17: "Permanent ballast is usually made of blocks of lead painted blue and may be removed.",
    18: "When the press to test light is released, the light should stay on.",
    19: "The battery charging alternator is gear driven by the engine.",
    20: "For 20 passengers in the forward compartment, the weight is 1,979 lb and the moment/1,000 is 3,400.",
    21: "The engine thermostat closes when the engine reaches normal operating temperature.",
    23: "If the CG is too far forward, there might not be enough elevator nose-down authority to recover.",
    24: "The fuel goes to the injectors first and then to the injection pumps.",
    28: "An adverse-loading check is not needed if the newly calculated EWCG falls outside the EWCG range.",
    29: "Keep the air cleaner element if it is fouled.",
    30: "The restriction indicator turns red when the air filter element is new.",
    31: "The allowable CG range in a light aircraft should be at least 20 percent MAC.",
    33: "The OEW and CG need reestablishing only when the cumulative CG change stays under one-half of 1 percent of the MAC.",
    34: "Acrobatic category aircraft need not withstand 6.0 times their weight.",
    35: "The generator set keeps running when the coolant temperature exceeds 225 ± 5°F (107 ± 3°C).",
    36: "Temporary ballast must stay installed when the aircraft is weighed.",
    39: "For a symmetrically-tapered wing, the MAC is the sum of the root chord and the tip chord.",
    40: "The ground rod is stored in a holding clip on the left side of the skid base.",
    41: "For engine starting, the DEAD CRANK switch must not be in the NORMAL position.",
    43: "In hot weather, the MASTER SWITCH should be placed in the PREHEAT position for approximately 30 seconds.",
    44: "This position is 13.2 inches aft of the main-wheel weighing points.",
    50: "The coolant recovery bottle should be filled to the COLD line if the coolant is hot.",
    51: "The fuel level float switch turns on the auxiliary fuel pump when the generator fuel tank is full.",
    54: "The convenience receptacle is rated at 120 Amps and 10 VAC.",
    55: "The weight of the adjustable co-pilot seat (Item No: 25-01-R) is 33.8 lbs.",
    57: "The crank disconnect switch closes and energizes the cranking relay to keep the starter engaged.",
    59: "The bags are marked to say removal does not require a weight and balance check.",
    62: "Tare weight is the weight of the aircraft with the chocks removed.",
    67: "Weight changes may be computed even when the weight and CG location of the modifications are unknown.",
    68: "This ballast is attached to the floor at fuselage station 228.",
    69: "The generator set must be refueled before 8 hours of operation.",
}
EXTRA_UNSUPPORTED = [
    (
        "op-08",
        "You may crank the engine for as long as needed.",
        "Do not crank engine in excess of fifteen seconds.",
    ),
]


def main(raw: str, composed: str, tables: str) -> None:
    pages = load_pages(Path(composed))
    blocks = {b.id: b for p in pages for b in p.blocks}
    where = {b.id: (p.manual, p.page) for p in pages for b in p.blocks}
    ctx = SimpleNamespace(blocks=blocks, block_page=where, under=titles_by_page(pages))
    store, rows = TableStore(tables), {}

    def evidence(eid: str):
        m = re.match(r"(.*):r(\d+)$", eid)
        if not m:
            return _block_evidence(ctx, eid)
        table = rows.setdefault(
            m.group(1),
            {h.row: h for h in store.lookup_table(block_id=m.group(1), limit=10000)},
        )
        hit = table.get(int(m.group(2)))
        return hit and row_evidence(hit, ctx.under.get((hit.manual, hit.page), ""))

    data = json.loads(Path(raw).read_text())
    found = [
        (x["id"], c)
        for x in data["repeats"][0]
        for c in x["claims"]
        if c["status"] == "verified" and len(c["quote"]) >= 15
    ]
    random.Random(SAMPLE_SEED).shuffle(found)
    seen, sample = set(), []
    for item, c in found:
        if item not in seen:
            seen.add(item)
            sample.append((item, c))
    for i, (item, c) in enumerate(sample[:SAMPLE]):
        ev = evidence(c["block"])
        match = ev and match_quote(c["quote"], ev)
        if not match:
            continue
        premise = premise_for(ev, match.source)
        _emit(item, c["claim"], premise, True, "real")
        if i in UNSUPPORTED:
            _emit(item, UNSUPPORTED[i], premise, False, "constructed")
    for item, claim, premise in EXTRA_UNSUPPORTED:
        _emit(item, claim, premise, False, "constructed")


def _emit(item: str, claim: str, premise: str, supported: bool, origin: str) -> None:
    print(
        json.dumps(
            {
                "item": item,
                "claim": claim,
                "premise": premise,
                "supported": supported,
                "origin": origin,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main(*sys.argv[1:4])

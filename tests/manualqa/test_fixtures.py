from manualqa.blocks import validate

PARTS = "Army_5kW_Generator_Parts_Manual.pdf"


def test_fixture_pages_load_and_validate(raw_pages):
    assert len(raw_pages) == 6
    assert all(validate(pp) == [] for pp in raw_pages.values())
    tables = [b for b in raw_pages[(PARTS, 59)].blocks if b.kind == "table"]
    assert len(tables) == 1 and len(tables[0].cells) >= 150

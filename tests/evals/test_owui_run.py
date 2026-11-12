from evals.owui_run import chunks, cited, record


def reply(answer, docs):
    return {
        "choices": [{"message": {"content": answer}}],
        "sources": [
            {
                "source": {"type": "collection", "id": "kb"},
                "document": [d for d, _, _ in docs],
                "metadata": [{"source": f, "name": f, "page": p} for _, f, p in docs],
            }
        ],
    }


DOCS = [("a1", "A.pdf", 0), ("b1", "B.pdf", 4), ("a2", "A.pdf", 9)]


def test_sources_are_numbered_by_file_as_the_prompt_shows_them():
    got = chunks(reply("", DOCS)["sources"])
    assert [c["id"] for c in got] == [1, 2, 1]


def test_an_answer_citing_one_file_is_judged_on_that_file_s_chunks():
    r = record({"id": "x"}, reply("It is so [2].", DOCS), 1.0)
    assert r["cited_text"] == "b1" and r["cited_pages"] == [5] and r["cites"]


def test_an_answer_citing_nothing_is_judged_on_every_chunk_it_was_given():
    r = record({"id": "x"}, reply("It is so.", DOCS), 1.0)
    assert r["cited_text"] == "a1\n\nb1\n\na2" and not r["cites"]
    assert r["cited_pages"] == [1, 5, 10]


def test_several_ids_in_one_bracket():
    given = chunks(reply("", DOCS)["sources"])
    assert [c["text"] for c in cited("See [1, 2].", given)] == ["a1", "b1", "a2"]


def test_pages_of_a_split_part_map_back_to_the_whole_pdf():
    from evals.owui_run import page_of

    assert page_of({"name": "FAA__p041-080.pdf", "page": 0}) == 41
    assert page_of({"name": "FIST.pdf", "page": 3}) == 4
    assert page_of({"name": "FIST.pdf"}) is None

from evals.batch_run import (
    Anthropic,
    CachedGenerator,
    Pending,
    load_cache,
    request_key,
    hybrid,
    run_rounds,
    split_by_size,
    to_anthropic,
)


def test_messages_convert_to_anthropic_with_system_and_images():
    messages = [
        {"role": "system", "content": "Be exact."},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Evidence"},
                {
                    "type": "image_url",
                    "image_url": {"url": "data:image/jpeg;base64,QUJD"},
                },
            ],
        },
    ]
    system, out = to_anthropic(messages)
    assert system == "Be exact."
    assert out == [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Evidence"},
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": "QUJD",
                    },
                },
            ],
        }
    ]
    assert to_anthropic([{"role": "user", "content": "yes?"}])[1][0]["content"] == [
        {"type": "text", "text": "yes?"}
    ]


def test_cache_misses_are_queued_and_hits_are_answered():
    msgs = [{"role": "user", "content": "q"}]
    gen = CachedGenerator("m", {})
    try:
        gen.complete(msgs)
        raise AssertionError("expected Pending")
    except Pending:
        pass
    assert list(gen.pending.values()) == [msgs]
    gen.cache[request_key(msgs, "m")] = {"text": "a"}
    assert gen.complete(msgs) == "a"
    assert request_key(msgs, "m") != request_key(msgs, "other model")


def test_rounds_reach_one_call_further_each_time(tmp_path):
    gen = CachedGenerator("m", {})

    def run(question, manual):  # an answer, then a check that depends on it
        answer = gen.complete([{"role": "user", "content": question}])
        verdict = gen.complete([{"role": "user", "content": f"check {answer}"}])
        return {"answer": answer, "verdict": verdict}

    def fill(pending):
        return {
            k: {"text": m[0]["content"].upper(), "usage": {"input_tokens": 1}}
            for k, m in pending.items()
        }

    qa = [
        {"id": "a", "question": "x", "manual": "M"},
        {"id": "b", "question": "y", "manual": "M"},
    ]
    cache = tmp_path / "cache.jsonl"
    rows = run_rounds(qa, run, gen, fill, cache)
    assert [r["id"] for r in rows] == ["a", "b"]
    assert rows[0]["answer"] == "X" and rows[0]["verdict"] == "CHECK X"
    assert len(load_cache(cache)) == 4  # two answers, two checks, kept for a rerun
    again = CachedGenerator("m", load_cache(cache))
    gen.cache, gen.pending = again.cache, {}
    assert (
        run_rounds(
            qa, run, gen, lambda p: (_ for _ in ()).throw(AssertionError), cache
        )[1]["answer"]
        == "Y"
    )


def test_count_only_prices_the_first_round_and_sends_nothing(tmp_path):
    gen = CachedGenerator("m", {})

    def run(question, manual):
        return {"answer": gen.complete([{"role": "user", "content": question}])}

    sent = []
    rows = run_rounds(
        [{"id": "a", "question": "x", "manual": "M"}],
        run,
        gen,
        lambda p: sent.append(p) or {},
        tmp_path / "c.jsonl",
        count=lambda p: 123,
    )
    assert rows is None and sent == []


def test_batches_are_cut_under_the_size_limit_in_order():
    reqs = [{"custom_id": str(i), "params": {"x": "y" * 40}} for i in range(10)]
    chunks = split_by_size(reqs, limit=200)
    assert [r for c in chunks for r in c] == reqs
    assert len(chunks) > 1 and all(len(c) >= 1 for c in chunks)
    assert split_by_size([], limit=10) == []


def test_small_rounds_go_live_and_large_ones_batch():
    used = []
    fill = hybrid(
        lambda p: used.append("batch") or {}, lambda p: used.append("live") or {}, 3
    )
    fill({"a": [], "b": [], "c": []})
    fill({"a": []})
    assert used == ["batch", "live"]


def test_a_batch_left_uncollected_is_collected_before_anything_is_resent(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    ledger = tmp_path / "c.batches.jsonl"
    ledger.write_text(
        '{"id": "b1", "submitted": 2}\n{"id": "b1", "collected": true}\n{"id": "b2", "submitted": 3}\n'
    )
    client = Anthropic("m", ledger=ledger)
    assert client.uncollected() == ["b2"]
    collected = []
    monkeypatch.setattr(
        client,
        "_collect",
        lambda bid, poll_s: collected.append(bid) or {"k": {"text": "t"}},
    )
    assert client.recover() == {"k": {"text": "t"}} and collected == ["b2"]

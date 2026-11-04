from types import SimpleNamespace

from evals.run_eval import ADAPTERS, force_temperature


def fake_module():
    calls = []

    def post(url, json=None, **kw):
        calls.append((url, json, kw))
        return "response"

    return SimpleNamespace(requests=SimpleNamespace(post=post, get="kept")), calls


def test_v1_temperature_reaches_generator():
    api, calls = fake_module()
    force_temperature(api, 0)
    got = api.requests.post("u/api/chat", json={"model": "m"}, stream=True, timeout=180)
    assert got == "response"
    url, body, kw = calls[0]
    assert body == {"model": "m", "options": {"temperature": 0}}
    assert kw == {"stream": True, "timeout": 180}
    assert api.requests.get == "kept"  # nothing else in the module's requests changes


def test_existing_options_are_kept():
    api, calls = fake_module()
    force_temperature(api, 0)
    api.requests.post("u", json={"options": {"seed": 1}})
    assert calls[0][1]["options"] == {"seed": 1, "temperature": 0}


def test_v1_t0_is_a_system_and_v1_as_shipped_is_unchanged():
    assert "v1-t0" in ADAPTERS and "v1" in ADAPTERS

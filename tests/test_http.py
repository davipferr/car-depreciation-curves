import httpx
import pytest

from pipeline import http


@pytest.fixture
def mock_client(tmp_path, monkeypatch):
    """Route the shared client through a mock transport; record every request."""
    seen: list[httpx.Request] = []
    responses: dict[str, list[httpx.Response]] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        queue = responses.get(request.url.path)
        return queue.pop(0) if queue else httpx.Response(200, content=b"ok")

    monkeypatch.setattr(http, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(http, "OFFLINE", False)
    monkeypatch.setattr(http, "_client", httpx.Client(transport=httpx.MockTransport(handler)))
    monkeypatch.setattr(http.time, "sleep", lambda s: None)
    return seen, responses


def test_requests_share_one_client(mock_client):
    seen, _ = mock_client
    client = http._get_client(10)
    assert http.fetch("https://example.test/a") == b"ok"
    assert http.fetch("https://example.test/b", data={"x": 1}) == b"ok"
    assert http._get_client(10) is client
    assert [(r.method, r.url.path) for r in seen] == [("GET", "/a"), ("POST", "/b")]


def test_cache_hit_skips_network_and_form_data_is_part_of_the_key(mock_client):
    seen, _ = mock_client
    url = "https://example.test/ConsultarValorComTodosParametros"
    assert http.cached_path(url, data={"ano": 2020}) is None
    http.fetch(url, data={"ano": 2020}, max_age=None)
    http.fetch(url, data={"ano": 2020}, max_age=None)
    assert len(seen) == 1
    assert http.cached_path(url, data={"ano": 2020}).read_bytes() == b"ok"
    assert http.cached(url, data={"ano": 2020})
    assert not http.cached(url, data={"ano": 2021})


def test_body_less_post_still_sends_a_body(mock_client):
    # FIPE answers "411 Length Required" to an empty POST.
    seen, _ = mock_client
    http.fetch("https://example.test/ConsultarTabelaDeReferencia", data={})
    assert seen[0].method == "POST" and seen[0].content


def test_retries_then_succeeds_and_not_found(mock_client):
    seen, responses = mock_client
    responses["/flaky"] = [httpx.Response(429), httpx.Response(503), httpx.Response(200, content=b"done")]
    limiter = http.RateLimiter(per_minute=60_000)
    assert http.fetch("https://example.test/flaky", limiter=limiter) == b"done"
    assert limiter.interval > limiter.min_interval  # the 429 slowed it down
    responses["/gone"] = [httpx.Response(404)]
    with pytest.raises(http.NotFound):
        http.fetch("https://example.test/gone")


def test_forbidden_is_not_retried(mock_client):
    seen, responses = mock_client
    responses["/blocked"] = [httpx.Response(403)] * 5
    with pytest.raises(PermissionError, match="CDC_OFFLINE"):
        http.fetch("https://example.test/blocked")
    assert len(seen) == 1


def test_offline_serves_stale_cache_and_never_touches_the_network(mock_client, monkeypatch):
    seen, _ = mock_client
    http.fetch("https://example.test/old")
    monkeypatch.setattr(http, "OFFLINE", True)
    assert http.fetch("https://example.test/old", max_age=http.timedelta(seconds=0)) == b"ok"
    with pytest.raises(RuntimeError, match="not in"):
        http.fetch("https://example.test/never-downloaded")
    assert len(seen) == 1


def test_headers_are_sent_but_not_part_of_cache_key(mock_client):
    seen, _ = mock_client
    http.fetch("https://example.test/k", headers={"Referer": "https://veiculos.fipe.org.br/"})
    assert seen[0].headers["Referer"] == "https://veiculos.fipe.org.br/"
    assert http.cached_path("https://example.test/k") is not None

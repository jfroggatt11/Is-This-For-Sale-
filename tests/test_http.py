import httpx
import pytest

from itsfs.adapters.base import AccessDenied, SourceError
from itsfs.http import PoliteHTTP


def setup(monkeypatch, response):
    monkeypatch.setattr("itsfs.http.time.sleep", lambda seconds: None)
    calls = []

    def handler(request):
        calls.append(request)
        return response(request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    return PoliteHTTP("IsThisForSale/0.1", client=client), calls


@pytest.mark.parametrize("status", [401, 403, 429, 500, 302])
def test_http_failure_stops_without_retry(monkeypatch, status):
    http, calls = setup(monkeypatch, lambda r: httpx.Response(status, text="secret"))
    with pytest.raises(SourceError) as exc:
        http.get("https://example.invalid/feed?token=secret")
    assert len(calls) == 1 and "secret" not in str(exc.value)


def test_robots_deny(monkeypatch):
    http, calls = setup(
        monkeypatch, lambda r: httpx.Response(200, text="User-agent: *\nDisallow: /")
    )
    with pytest.raises(AccessDenied, match="robots"):
        http.get("https://example.invalid/feed")
    assert len(calls) == 1


def test_robots_missing_feed_cached_and_user_agent(monkeypatch):
    http, calls = setup(
        monkeypatch,
        lambda r: (
            httpx.Response(404)
            if r.url.path == "/robots.txt"
            else httpx.Response(200, content=b"<root/>")
        ),
    )
    assert http.get("https://example.invalid/feed") == b"<root/>"
    assert http.get("https://example.invalid/feed") == b"<root/>"
    assert len(calls) == 2 and calls[1].headers["User-Agent"].startswith("IsThisForSale")


def test_crawl_delay(monkeypatch):
    http, _ = setup(
        monkeypatch,
        lambda r: httpx.Response(
            200,
            text="User-agent: *\nAllow: /\nCrawl-delay: 3\n"
            if r.url.path == "/robots.txt"
            else "feed",
        ),
    )
    delays = []
    monkeypatch.setattr("itsfs.http.time.sleep", delays.append)
    http.get("https://example.invalid/feed")
    assert http.min_interval == 3 and 2.9 < delays[0] <= 3


def test_size_limit(monkeypatch):
    monkeypatch.setattr("itsfs.http.MAX_BYTES", 4)
    http, _ = setup(
        monkeypatch,
        lambda r: (
            httpx.Response(404)
            if r.url.path == "/robots.txt"
            else httpx.Response(200, content=b"too large")
        ),
    )
    with pytest.raises(SourceError, match="limit"):
        http.get("https://example.invalid/feed")


def test_timeout_redaction(monkeypatch):
    def timeout(r):
        raise httpx.ReadTimeout("secret-url")

    http, _ = setup(monkeypatch, timeout)
    with pytest.raises(SourceError, match="timed out") as exc:
        http.get("https://example.invalid/feed")
    assert "secret" not in str(exc.value)


@pytest.mark.parametrize(
    "url",
    [
        "http://example.invalid/feed",
        "ftp://example.invalid/feed",
        "https://user:secret@example.invalid/feed",
    ],
)
def test_disallowed_urls(monkeypatch, url):
    http, calls = setup(monkeypatch, lambda r: pytest.fail("no request expected"))
    with pytest.raises(AccessDenied):
        http.get(url)
    assert not calls


def test_wildcards_and_allow_precedence(monkeypatch):
    robots = "User-agent: *\nDisallow: /private/*\nAllow: /private/public.xml$\n"
    http, calls = setup(
        monkeypatch,
        lambda r: httpx.Response(200, text=robots if r.url.path == "/robots.txt" else "feed"),
    )
    with pytest.raises(AccessDenied):
        http.get("https://example.invalid/private/secret.xml")
    assert http.get("https://example.invalid/private/public.xml") == b"feed"
    assert len(calls) == 2


def test_robots_html_fails_closed(monkeypatch):
    http, calls = setup(monkeypatch, lambda r: httpx.Response(200, text="<html>Captcha</html>"))
    with pytest.raises(AccessDenied, match="policy"):
        http.get("https://example.invalid/feed")
    assert len(calls) == 1

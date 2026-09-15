"""Bounded, identifiable requests with robots checks and no automatic retries."""

import time
from urllib.parse import urlsplit

import httpx
from protego import Protego

from .adapters.base import AccessDenied, SourceError

MAX_BYTES = 10 * 1024 * 1024


class PoliteHTTP:
    def __init__(
        self, user_agent: str, *, client: httpx.Client | None = None, min_interval: float = 1.0
    ):
        if not user_agent.strip() or "\n" in user_agent or "\r" in user_agent:
            raise ValueError("a valid identifying User-Agent is required")
        self.user_agent = user_agent
        self.client = client or httpx.Client(timeout=20, follow_redirects=False)
        self.owns_client = client is None
        self.min_interval = max(1.0, min_interval)
        self.last_request: dict[str, float] = {}
        self.robots: dict[str, Protego] = {}
        self.cache: dict[str, tuple[float, bytes]] = {}

    def close(self) -> None:
        if self.owns_client:
            self.client.close()

    def _request(self, url: str, *, allow_missing: bool = False, data=None) -> bytes | None:
        host = urlsplit(url).netloc
        wait = self.min_interval - (time.monotonic() - self.last_request.get(host, -1e9))
        if wait > 0:
            time.sleep(wait)
        self.last_request[host] = time.monotonic()
        try:
            with self.client.stream(
                "POST" if data is not None else "GET",
                url,
                headers={"User-Agent": self.user_agent},
                data=data,
            ) as r:
                if allow_missing and r.status_code == 404:
                    return None
                if r.status_code in {401, 403, 429}:
                    raise AccessDenied(f"HTTP {r.status_code}; access stopped, no retry")
                if 300 <= r.status_code < 400:
                    raise AccessDenied("redirect refused; configure the approved canonical URL")
                if r.status_code != 200:
                    raise SourceError(f"HTTP {r.status_code}; source unavailable")
                chunks, size = [], 0
                for chunk in r.iter_bytes():
                    size += len(chunk)
                    if size > MAX_BYTES:
                        raise SourceError("response exceeds the 10 MiB limit")
                    chunks.append(chunk)
                body = b"".join(chunks)
                lower = body.lower()
                if any(
                    marker in lower
                    for marker in (
                        b"<title>just a moment...",
                        b'id="challenge-form"',
                        b"geo.captcha-delivery.com/captcha/",
                    )
                ):
                    raise AccessDenied("source returned an access challenge; stopped")
                return body
        except httpx.HTTPError:
            raise SourceError("network request failed or timed out") from None

    def _check_policy(self, url: str) -> None:
        parts = urlsplit(url)
        if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
            raise AccessDenied("feed URL must use HTTPS without embedded credentials")
        origin = f"https://{parts.netloc}"
        if origin not in self.robots:
            raw = self._request(origin + "/robots.txt", allow_missing=True)
            if raw is not None:
                text = raw.decode("utf-8", errors="replace")
                if "<html" in text.lower() or "<!doctype" in text.lower():
                    raise AccessDenied("robots.txt returned HTML; access policy cannot be checked")
                parser = Protego.parse(text)
            else:
                parser = Protego.parse("")
            self.robots[origin] = parser
        parser = self.robots[origin]
        if not parser.can_fetch(url, self.user_agent):
            raise AccessDenied("robots.txt disallows this feed")
        delay = parser.crawl_delay(self.user_agent) or 0
        rate = parser.request_rate(self.user_agent)
        if parser.visit_time(self.user_agent) or (rate and (rate.start_time or rate.end_time)):
            raise AccessDenied(
                "robots.txt has a time window; scheduled fetching is not implemented"
            )
        if rate:
            delay = max(delay, rate.seconds / rate.requests)
        if delay > 60:
            raise AccessDenied(
                "robots.txt requires a delay over 60s; use an authorized local export"
            )
        self.min_interval = max(self.min_interval, delay)

    def check_policy(self, url: str) -> None:
        """Check a browser navigation against the same live robots policy."""
        self._check_policy(url)

    def get(self, url: str) -> bytes:
        self._check_policy(url)
        if url in self.cache and time.monotonic() - self.cache[url][0] < 300:
            return self.cache[url][1]
        body = self._request(url)
        self.cache[url] = (time.monotonic(), body)
        return body

    def post_form(self, url: str, data: dict[str, str]) -> bytes:
        """Only for reviewed read-only public search forms. No retries or redirects."""
        self._check_policy(url)
        return self._request(url, data=data)

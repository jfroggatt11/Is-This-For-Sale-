"""Fresh bundled Chromium transport. No personal Chrome, profile import or bypasses."""

import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

from .adapters.base import AccessDenied, SourceChanged, SourceError
from .geocoding import normalize

BASE = "https://www.idealista.it"


@contextmanager
def fresh_chromium(playwright, *, headless=False):
    """Own a new browser process and empty context, closing both even on failure.

    No channel, executable path, saved storage, profile path or connection endpoint
    is accepted. Playwright launches its separate bundled Chromium with temporary
    browser data. A context is never borrowed from an existing browser.
    """
    with TemporaryDirectory(prefix="itsfs-browser-") as profile:
        context = playwright.chromium.launch_persistent_context(
            profile, headless=headless, accept_downloads=False
        )
        try:
            yield context
        finally:
            context.close()


# Capture facts only; do not persist descriptions, photos, contacts or browser state.
SEARCH_DOM = """() => {
  const out = document.createElement('main');
  for (const selector of ['#h1-container', '#tab-buy', '#qa_adfilter_auctionability']) {
    const node = document.querySelector(selector);
    if (node) out.append(node.cloneNode(true));
  }
  for (const node of document.querySelectorAll('article.item[data-element-id]')) {
    const card = document.createElement('article');
    card.className = 'item';
    for (const key of ['data-element-id', 'data-is-offmarket']) {
      if (node.hasAttribute(key)) card.setAttribute(key, node.getAttribute(key));
    }
    for (const selector of [
      'a.item-link', '.item-price', '.item-detail', '.listing-tags-container'
    ]) {
      for (const fact of node.querySelectorAll(selector)) card.append(fact.cloneNode(true));
    }
    out.append(card);
  }
  return out.outerHTML;
}"""


@dataclass(frozen=True)
class BrowserPage:
    url: str
    body: str
    captured_at: datetime


def check_url(url):
    p = urlsplit(url)
    if p.scheme != "https" or p.netloc != "www.idealista.it" or p.query or p.fragment:
        raise AccessDenied("browser navigation must stay on canonical Italian Idealista pages")
    if p.path != "/" and not p.path.startswith("/vendita-case/"):
        raise AccessDenied("unreviewed Idealista browser route")


def municipality_link(body, aliases, *, autocomplete=False):
    """Follow observed links, never synthesize place slugs or private search endpoints."""
    soup = BeautifulSoup(body, "html.parser")
    matches = set()
    selector = "a:has(span.icon-location-outline)" if autocomplete else "a.icon-elbow"
    for a in soup.select(selector):
        if autocomplete:
            kind = a.select_one("span.icon-location-outline")
            label = a.select_one("i")
            if kind.get_text(strip=True) != "Comune" or label is None:
                continue
            name = label.get_text(" ", strip=True).split(",")[0]
        else:
            name = a.get_text(" ", strip=True)
        if normalize(name) not in aliases:
            continue
        path = a.get("href", "")
        url = BASE + path if path.startswith("/") else path
        check_url(url)
        if len(urlsplit(url).path.strip("/").split("/")) == 2:
            matches.add(url)
    if len(matches) > 1:
        raise SourceChanged("ambiguous Idealista municipality; no route selected")
    return next(iter(matches), None)


def has_access_challenge(page):
    """A device-check frame can navigate without updating its iframe src attribute."""
    if page.locator('iframe[src*="/captcha/"], #challenge-form').count():
        return True
    return any(
        urlsplit(frame.url).hostname == "geo.captcha-delivery.com"
        and urlsplit(frame.url).path.startswith("/captcha/")
        for frame in page.frames
    )


def browser_failure(stage, error):
    """Return an actionable message without exposing page content or browser state."""
    message = str(error).casefold()
    if "has been closed" in message or "target page, context or browser has been closed" in message:
        return SourceError("isolated browser was closed before the Idealista search finished")
    return SourceError(f"isolated Chromium failed during {stage}; no personal Chrome was used")


class IdealistaBrowser:
    """One fresh, visible bundled Chromium process and context per search."""

    def __init__(self, policy, *, timeout_s=30, verification="none", verification_timeout_s=300):
        if not 5 <= timeout_s <= 60:
            raise ValueError("browser timeout must be 5..60 seconds")
        if verification not in {"none", "human"}:
            raise ValueError("browser verification must be none or human")
        if not 30 <= verification_timeout_s <= 600:
            raise ValueError("verification timeout must be 30..600 seconds")
        self.policy = policy
        self.timeout_s = timeout_s
        self.verification = verification
        self.verification_timeout_s = verification_timeout_s
        self.navigation_log = []
        self.last_navigation = 0.0

    def _wait_for_human_verification(self, page, selector):
        if self.verification != "human":
            raise AccessDenied("Idealista presented an access challenge; stopped, no retry")
        print(
            "Idealista needs verification in the isolated browser. Complete it there; "
            "the search will continue automatically. Do not close the browser.",
            file=sys.stderr,
        )
        deadline = time.monotonic() + self.verification_timeout_s
        while time.monotonic() < deadline:
            if page.locator(selector).count():
                check_url(page.url)
                return
            page.wait_for_timeout(250)
        raise AccessDenied("Idealista verification was not completed before the timeout")

    def _allow(self, url):
        check_url(url)
        self.policy.check_policy(url)
        delay = max(2.0, self.policy.min_interval)
        time.sleep(max(0, delay - (time.monotonic() - self.last_navigation)))
        self.last_navigation = time.monotonic()
        self.navigation_log.append(url)

    def _ready(self, page, selector):
        """An automatic device check may finish; interactive challenges stop the run."""
        deadline = time.monotonic() + self.timeout_s
        while time.monotonic() < deadline:
            if has_access_challenge(page):
                self._wait_for_human_verification(page, selector)
                return
            if page.locator(selector).count():
                check_url(page.url)
                return
            page.wait_for_timeout(250)
        raise AccessDenied("Idealista page did not become available; no challenge bypass attempted")

    def _goto(self, page, url, ready):
        self._allow(url)
        response = page.goto(url, wait_until="domcontentloaded", timeout=self.timeout_s * 1000)
        if has_access_challenge(page):
            self._wait_for_human_verification(page, ready)
            if page.url != url:
                raise AccessDenied("Idealista redirected the requested page; stopped")
            return
        if (
            response
            and response.status == 403
            and page.locator('iframe[title="DataDome Device Check"][src*="/interstitial/"]').count()
        ):
            # Let a normal automatic check finish; never interact, reload or change identity.
            self._ready(page, ready)
            if page.url != url:
                raise AccessDenied("Idealista redirected the requested page; stopped")
            return
        if response and response.status in {401, 403, 429}:
            raise AccessDenied(f"Idealista HTTP {response.status}; stopped, no retry")
        if response and response.status >= 400:
            raise SourceError(f"Idealista HTTP {response.status}; source unavailable")
        self._ready(page, ready)
        if page.url != url:
            raise AccessDenied("Idealista redirected the requested page; stopped")

    def search(self, town):
        try:
            from playwright.sync_api import Error, sync_playwright
        except ImportError:
            raise SourceError(
                "install the browser extra: pip install 'is-this-for-sale[browser]'"
            ) from None
        self.navigation_log = []
        stage = "browser launch"
        try:
            with sync_playwright() as pw:
                with fresh_chromium(pw) as context:
                    page = context.new_page()
                    page.set_default_timeout(self.timeout_s * 1000)
                    stage = "homepage access or verification"
                    self._goto(page, BASE + "/", "#campoBus")
                    stage = "cookie preference"
                    decline = page.get_by_role(
                        "button", name="Continua senza accettare", exact=True
                    )
                    if decline.count() and decline.is_visible():
                        decline.click()
                    stage = "municipality resolution"
                    links = page.locator("a.icon-elbow").evaluate_all(
                        "nodes => nodes.map(n => n.outerHTML).join('')"
                    )
                    url = municipality_link(links, town["names"])
                    if url is None:
                        field = page.locator("#campoBus")
                        field.fill("")
                        field.press_sequentially(town["name"])
                        self._ready(page, "a span.icon-location-outline")
                        links = page.locator("a:has(span.icon-location-outline)").evaluate_all(
                            "nodes => nodes.map(n => n.outerHTML).join('')"
                        )
                        url = municipality_link(links, town["names"], autocomplete=True)
                    if url is None:
                        raise SourceChanged(
                            "Idealista did not resolve the nearest town to a municipality"
                        )
                    stage = "municipality sale catalogue"
                    self._goto(page, url, "#qa_adfilter_auctionability")
                    stage = "auction exclusion"
                    page.locator("#qa_adfilter_auctionability").click()
                    # This route was observed from the site's actual auction-exclusion control.
                    target = url + "con-aste_no/"
                    self._allow(target)
                    page.locator("#qa_adfilter_auctionability_option_1").click()
                    stage = "filtered sale catalogue"
                    page.wait_for_url(target, timeout=self.timeout_s * 1000)
                    self._ready(page, "#h1-container")
                    stage = "listing fact capture"
                    return BrowserPage(page.url, page.evaluate(SEARCH_DOM), datetime.now(UTC))
        except Error as exc:
            raise browser_failure(stage, exc) from None

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from itsfs.adapters.base import AccessDenied
from itsfs.browser import IdealistaBrowser, browser_failure, has_access_challenge

HOME = "https://www.idealista.it/"
DEVICE = 'iframe[title="DataDome Device Check"][src*="/interstitial/"]'


def page(*, status=403, frame="", device=False):
    result = MagicMock()
    result.url = HOME
    result.frames = [SimpleNamespace(url=frame)] if frame else []
    result.goto.return_value.status = status
    result.locator.side_effect = lambda selector: SimpleNamespace(
        count=lambda: int(selector == DEVICE and device)
    )
    return result


def test_navigated_frame_is_detected_even_with_stale_iframe_src():
    tab = page(frame="https://geo.captcha-delivery.com/captcha/?opaque=omitted", device=True)
    assert tab.locator('iframe[src*="/captcha/"], #challenge-form').count() == 0
    assert has_access_challenge(tab)
    browser = IdealistaBrowser(MagicMock())
    with pytest.raises(AccessDenied, match="challenge"):
        browser._ready(tab, "#campoBus")
    tab.wait_for_timeout.assert_not_called()


def test_automatic_device_check_is_not_an_interactive_challenge():
    tab = page(frame="https://geo.captcha-delivery.com/interstitial/", device=True)
    assert not has_access_challenge(tab)
    browser = IdealistaBrowser(MagicMock())
    browser._allow = MagicMock()
    browser._ready = MagicMock()
    browser._goto(tab, HOME, "#campoBus")
    browser._ready.assert_called_once_with(tab, "#campoBus")
    tab.goto.assert_called_once()  # No retry, challenge action or identity change.


@pytest.mark.parametrize("status", [401, 403, 429])
def test_explicit_denial_does_not_wait_or_retry(status):
    tab = page(status=status)
    browser = IdealistaBrowser(MagicMock())
    browser._allow = MagicMock()
    browser._ready = MagicMock()
    with pytest.raises(AccessDenied, match=f"HTTP {status}"):
        browser._goto(tab, HOME, "#campoBus")
    browser._ready.assert_not_called()
    tab.goto.assert_called_once()


def test_interactive_challenge_stops_even_if_initial_response_was_success():
    tab = page(status=200, frame="https://geo.captcha-delivery.com/captcha/")
    browser = IdealistaBrowser(MagicMock())
    browser._allow = MagicMock()
    browser._ready = MagicMock()
    with pytest.raises(AccessDenied, match="challenge"):
        browser._goto(tab, HOME, "#campoBus")
    browser._ready.assert_not_called()


def test_human_verification_waits_for_ready_page(capsys):
    tab = MagicMock()
    tab.url = HOME
    counts = iter([0, 1])
    tab.locator.return_value.count.side_effect = lambda: next(counts)
    browser = IdealistaBrowser(MagicMock(), verification="human")
    browser._wait_for_human_verification(tab, "#campoBus")
    tab.wait_for_timeout.assert_called_once_with(250)
    assert "Complete it there" in capsys.readouterr().err


def test_human_verification_timeout(monkeypatch):
    tab = MagicMock()
    tab.locator.return_value.count.return_value = 0
    clock = iter([0, 31])
    monkeypatch.setattr("itsfs.browser.time.monotonic", lambda: next(clock))
    browser = IdealistaBrowser(MagicMock(), verification="human", verification_timeout_s=30)
    with pytest.raises(AccessDenied, match="not completed"):
        browser._wait_for_human_verification(tab, "#campoBus")


def test_goto_delegates_challenge_only_in_human_mode():
    tab = page(status=403, frame="https://geo.captcha-delivery.com/captcha/")
    browser = IdealistaBrowser(MagicMock(), verification="human")
    browser._allow = MagicMock()
    browser._wait_for_human_verification = MagicMock()
    browser._goto(tab, HOME, "#campoBus")
    browser._wait_for_human_verification.assert_called_once_with(tab, "#campoBus")
    tab.goto.assert_called_once()


def test_browser_failures_are_sanitized_by_stage():
    closed = str(browser_failure("verification", RuntimeError("Target page has been closed")))
    assert "closed" in closed and "verification" in closed
    message = str(browser_failure("listing fact capture", RuntimeError("secret page content")))
    assert "listing fact capture" in message
    assert "secret page content" not in message

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from itsfs.adapters.italy.idealista import IdealistaAdapter
from itsfs.browser import IdealistaBrowser, fresh_chromium
from itsfs.cli import parser
from itsfs.registry import Registry


@pytest.mark.parametrize("fail", [False, True])
def test_fresh_process_without_personal_browser_configuration(fail):
    chromium = MagicMock()
    context = chromium.launch_persistent_context.return_value
    pw = SimpleNamespace(chromium=chromium)
    try:
        with fresh_chromium(pw) as active:
            assert active is context
            profile = Path(chromium.launch_persistent_context.call_args.args[0])
            assert profile.is_dir()
            if fail:
                raise RuntimeError("source failed")
    except RuntimeError:
        assert fail
    chromium.launch_persistent_context.assert_called_once_with(
        str(profile), headless=False, accept_downloads=False
    )
    context.close.assert_called_once()
    assert not profile.exists()


def test_launch_failure_removes_fresh_profile():
    chromium = MagicMock()
    chromium.launch_persistent_context.side_effect = RuntimeError("failed")
    with pytest.raises(RuntimeError):
        with fresh_chromium(SimpleNamespace(chromium=chromium)):
            pytest.fail("must not yield a failed context")
    assert not Path(chromium.launch_persistent_context.call_args.args[0]).exists()


def test_persistent_profile_is_app_owned_and_retained(tmp_path):
    chromium = MagicMock()
    context = chromium.launch_persistent_context.return_value
    profile = tmp_path / "idealista"
    with fresh_chromium(SimpleNamespace(chromium=chromium), profile_dir=profile) as active:
        assert active is context
        assert profile.is_dir()
    chromium.launch_persistent_context.assert_called_once_with(
        str(profile), headless=False, accept_downloads=False
    )
    context.close.assert_called_once()
    assert profile.exists()


def test_cli_and_registry_default_to_isolated_browser():
    assert parser().parse_args(["search", "--idealista-browser"]).idealista_browser == "playwright"
    registry = Registry()
    try:
        registry.enable_idealista_browser()
        spec = next(s for s in registry.specs if s.source == "idealista")
        assert isinstance(registry.load(spec).browser, IdealistaBrowser)
        assert registry.load(spec).browser.verification == "none"
        assert registry.load(spec).browser.persistent is False
        with pytest.raises(ValueError, match="isolated"):
            registry.enable_idealista_browser("extension")
        with pytest.raises(ValueError, match="isolated"):
            IdealistaAdapter(registry.http, backend="extension")
    finally:
        registry.close()


def test_cli_rejects_retired_shared_extension_backend():
    with pytest.raises(SystemExit):
        parser().parse_args(["search", "--idealista-browser", "extension"])


def test_human_verification_is_explicit_and_reaches_adapter():
    args = parser().parse_args(
        ["search", "--idealista-browser", "--idealista-verification", "human"]
    )
    registry = Registry()
    try:
        registry.enable_idealista_browser(args.idealista_browser, args.idealista_verification)
        spec = next(s for s in registry.specs if s.source == "idealista")
        assert registry.load(spec).browser.verification == "human"
    finally:
        registry.close()


def test_persistent_profile_is_explicit_and_reaches_adapter():
    args = parser().parse_args(["search", "--idealista-browser", "--idealista-persistent-profile"])
    registry = Registry()
    try:
        registry.enable_idealista_browser(
            args.idealista_browser,
            args.idealista_verification or "none",
            args.idealista_persistent_profile,
        )
        spec = next(s for s in registry.specs if s.source == "idealista")
        browser = registry.load(spec).browser
        assert browser.persistent is True
        assert browser.profile_dir.name == "idealista-chromium"
    finally:
        registry.close()


def test_human_verification_without_browser_is_rejected(capsys):
    from itsfs.cli import main

    assert main(["search", "--idealista-verification", "human"]) == 2
    assert "requires --idealista-browser" in capsys.readouterr().err


def test_persistent_profile_without_browser_is_rejected(capsys):
    from itsfs.cli import main

    assert main(["search", "--idealista-persistent-profile"]) == 2
    assert "requires --idealista-browser" in capsys.readouterr().err

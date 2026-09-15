"""Exercise the actual browser lifecycle twice with synthetic, intercepted pages.

Run after installing the browser extra and `python -m playwright install chromium`.
No external website is requested, no personal browser or profile is inspected.
"""

import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from playwright.sync_api import sync_playwright

from itsfs.browser import fresh_chromium


def main():
    origin = "https://browser-isolation.invalid/"
    runs = []
    with sync_playwright() as pw:
        executable = pw.chromium.executable_path
        for _ in range(2):
            with (
                patch.object(
                    pw.chromium,
                    "launch_persistent_context",
                    wraps=pw.chromium.launch_persistent_context,
                ) as launch,
                fresh_chromium(pw) as context,
            ):
                profile = launch.call_args.args[0]
                page = context.new_page()
                page.route(
                    "**/*",
                    lambda route: route.fulfill(
                        status=200, content_type="text/html", body="<title>Isolation test</title>"
                    ),
                )
                page.goto(origin)
                assert context.cookies() == []
                assert page.evaluate("localStorage.length") == 0
                context.add_cookies([{"name": "isolation_test", "value": "set", "url": origin}])
                page.evaluate("localStorage.setItem('isolation_test', 'set')")
                assert context.cookies()[0]["value"] == "set"
                assert page.evaluate("localStorage.getItem('isolation_test')") == "set"
            assert not Path(profile).exists(), "temporary browser profile was not removed"
            runs.append({"profile": profile, "started_empty": True, "profile_removed": True})
    assert runs[0]["profile"] != runs[1]["profile"]
    print(
        json.dumps(
            {
                "checked_at": datetime.now(UTC).isoformat(),
                "browser_executable": executable,
                "external_requests": 0,
                "runs": runs,
                "personal_chrome_used": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

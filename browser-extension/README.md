# Retired browser companion

The CLI no longer uses this extension or a local pairing bridge. The shared-profile
route was retired when the owner required a fresh browser, separate from personal
Chrome. The connection page is inert, and the old `extension` CLI backend is rejected.
Do not install or pair this extension. An already installed copy is no longer needed.

Use the separately installed Playwright Chromium browser:

```sh
python -m pip install -e '.[browser]'
python -m playwright install chromium
itsfs search --location 'Firenze, FI' --radius 5km --source idealista \
  --idealista-browser --include-unlocated --json
```

Every search launches a fresh browser process and empty context. Browser data is
temporary and removed at shutdown. There is no browser attachment, personal profile
path, cookie import, saved storage, extension connection, or fallback to Chrome.

The fresh-browser access result is recorded separately from the earlier personal
Chrome observation. Reachability in that earlier session does not prove access in
the fresh browser. Interactive challenges and HTTP access denials still stop a run.

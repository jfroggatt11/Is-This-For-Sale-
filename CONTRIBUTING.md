# Contributing

Start with [ADAPTER_SPEC.md](ADAPTER_SPEC.md). Open source code does not imply
permission to collect every source's inventory. Review access before extraction,
and keep source-specific decisions in `adapter_specs/`.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
pytest
ruff check src tests scripts
ruff format --check src tests scripts
python -m build
```

Submit an isolated adapter with synthetic/minimal licensed fixtures, shared
conformance coverage, registry metadata, access notes and a reproducible location
search. Document whether demonstrated output was live or simulated. Do not
commit credentials, session tokens, personal contact data or full property-site
archives. Additional runtime dependencies should justify their weight.

Changes are validated by CI and human review. The framework must remain usable
when an individual provider fails. Keep matching, geocoding and country detection
replaceable, and keep agents out of ordinary runtime searches. Do not add a web
app, database or autonomous repair service to solve an adapter problem.

The MIT license applies to contributions to the code and original fixtures.
Preserve the separate licenses and attribution of bundled geographical data.

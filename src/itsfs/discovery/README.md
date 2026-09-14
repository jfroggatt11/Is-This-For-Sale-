# Discovery belongs in development

No discovery engine or LLM executes at runtime. The CLI reports absent coverage;
an agent can separately investigate and propose reusable adapters following the
repository's `ADAPTER_SPEC.md` and `docs/ADDING_A_COUNTRY_WITH_AN_AGENT.md`.
Registry inclusion requires source access review, deterministic parsing,
conformance tests and human/CI validation. Do not infer sale availability from
failed sources or trigger credential acquisition as a side effect of search.

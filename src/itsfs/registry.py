"""A packaged JSON registry with explicit, allowlisted adapter factories."""

import json
import re
from dataclasses import asdict, dataclass, field, replace
from importlib.resources import files
from pathlib import Path

from .adapters.base import SourceError
from .http import PoliteHTTP
from .models import PROPERTY_TYPES


@dataclass(frozen=True)
class SourceSpec:
    source: str
    country_codes: list[str]
    property_types: list[str]
    access_method: str
    status: str
    location_search: bool
    location_precision: str
    adapter: str | None = None
    enabled: bool = False
    options: dict = field(default_factory=dict)
    notes: str = ""
    review: str = ""

    def __post_init__(self):
        if not isinstance(self.options, dict):
            raise ValueError("source options must be an object")
        if not isinstance(self.enabled, bool) or not isinstance(self.location_search, bool):
            raise ValueError("enabled and location_search must be boolean")
        if not re.fullmatch(r"[a-z][a-z0-9_-]*", self.source):
            raise ValueError("invalid source identifier")
        if not self.country_codes or any(
            not re.fullmatch(r"[A-Z]{2}", c) for c in self.country_codes
        ):
            raise ValueError("invalid source country codes")
        if not self.property_types or set(self.property_types) - PROPERTY_TYPES:
            raise ValueError("invalid source property types")
        if self.status not in {
            "working",
            "experimental",
            "needs_access",
            "investigating",
            "rejected",
            "unavailable",
        }:
            raise ValueError("invalid registry status")
        if self.enabled and (
            self.status not in {"working", "experimental"}
            or self.adapter not in {"demanio", "kyero", "risorseimmobiliari", "caasa", "idealista"}
        ):
            raise ValueError("only implemented working or experimental adapters may be enabled")
        if self.enabled and not self.review:
            raise ValueError("enabled sources need an access-review reference")


class Registry:
    def __init__(self, specs=None, *, http=None):
        if specs is None:
            data = json.loads(files("itsfs").joinpath("data/sources.json").read_text())
            specs = [SourceSpec(**entry) for entry in data]
        self.specs = specs
        if len({s.source for s in specs}) != len(specs):
            raise ValueError("duplicate source name")
        self.http = http or PoliteHTTP("IsThisForSale/0.1 (public property search CLI)")
        self.instances = {}

    def enable_idealista_browser(self, backend="playwright", verification="none", persistent=False):
        """Explicit opt-in: launch bundled Chromium with optional app-owned storage."""
        if backend != "playwright":
            raise ValueError("only fresh isolated Chromium is supported")
        if verification not in {"none", "human"}:
            raise ValueError("Idealista verification must be none or human")
        self.specs = [
            replace(
                s,
                enabled=True,
                status="experimental",
                adapter="idealista",
                access_method="browser_dom",
                property_types=["residential"],
                location_precision="area_only",
                options={
                    "backend": backend,
                    "verification": verification,
                    "persistent": persistent,
                },
            )
            if s.source == "idealista"
            else s
            for s in self.specs
        ]

    def add_config(self, path: str) -> None:
        """Feed paths resolve relative to the config. Never dynamically import code from JSON."""
        config = Path(path).resolve()
        try:
            data = json.loads(config.read_text())
            additions = []
            for entry in data:
                spec = SourceSpec(**entry)
                if spec.adapter != "kyero":
                    raise ValueError("custom source configuration supports Kyero feeds only")
                location = spec.options.get("location")
                if not isinstance(location, str) or not location:
                    raise ValueError("Kyero source requires options.location")
                if "://" in location and not location.startswith("https://"):
                    raise ValueError("remote feeds must use HTTPS")
                if not location.startswith("https://"):
                    spec.options["location"] = str(config.parent / location)
                additions.append(spec)
            combined = self.specs + additions
            if len({s.source for s in combined}) != len(combined):
                raise ValueError("duplicate source name")
            self.specs = combined
        except (OSError, json.JSONDecodeError, TypeError, KeyError):
            raise ValueError("invalid or unreadable sources configuration") from None

    def relevant(self, country, property_types=None, sources=None):
        if sources and set(sources) - {s.source for s in self.specs}:
            raise ValueError("unknown source; run itsfs sources")
        return [
            s
            for s in self.specs
            if s.enabled
            and country in s.country_codes
            and (not property_types or set(s.property_types).intersection(property_types))
            and (not sources or s.source in sources)
        ]

    def load(self, spec):
        if spec.source not in self.instances:
            if spec.adapter == "demanio":
                from .adapters.italy.demanio import DemanioAdapter

                adapter = DemanioAdapter(self.http, **spec.options)
            elif spec.adapter == "risorseimmobiliari":
                from .adapters.italy.risorseimmobiliari import RisorseimmobiliariAdapter

                adapter = RisorseimmobiliariAdapter(self.http, **spec.options)
            elif spec.adapter == "caasa":
                from .adapters.italy.caasa import CaasaAdapter

                adapter = CaasaAdapter(self.http, **spec.options)
            elif spec.adapter == "kyero":
                from .adapters.italy.kyero_feed import KyeroFeedAdapter

                adapter = KyeroFeedAdapter(spec.source, spec.options["location"], self.http)
            elif spec.adapter == "idealista":
                from .adapters.italy.idealista import IdealistaAdapter

                adapter = IdealistaAdapter(self.http, **spec.options)
            else:
                raise SourceError("adapter not implemented")
            self.instances[spec.source] = adapter
        return self.instances[spec.source]

    def to_dict(self):
        # Configured feed URLs may contain bearer tokens. Never expose options.
        return [{k: v for k, v in asdict(s).items() if k != "options"} for s in self.specs]

    def close(self):
        self.http.close()

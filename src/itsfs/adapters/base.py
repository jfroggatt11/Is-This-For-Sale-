from abc import ABC, abstractmethod

from itsfs.models import Listing


class SourceError(Exception):
    """A safe, actionable message; never include secrets or response bodies."""


class AccessDenied(SourceError):
    pass


class SourceChanged(SourceError):
    pass


class PropertySourceAdapter(ABC):
    source_name: str
    country_codes: list[str]

    def __init__(self) -> None:
        self.warnings: list[str] = []

    @abstractmethod
    def search(
        self,
        latitude: float,
        longitude: float,
        radius_m: float,
        property_types: list[str] | None = None,
    ) -> list[Listing]:
        """Validate first. Return candidates; engine applies final geographic filtering.

        Unlocated candidates are allowed and must carry honest precision. Reset warnings
        on every call. One instance is used sequentially, not concurrently.
        """

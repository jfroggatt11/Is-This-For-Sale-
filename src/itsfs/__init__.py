"""Ordinary software at runtime; agents build and maintain adapters."""

from .models import Listing, SearchQuery, SearchReport
from .search import SearchEngine

__all__ = ["Listing", "SearchEngine", "SearchQuery", "SearchReport"]
__version__ = "0.1.0"

"""Conservative identity matching. Shared coordinates/prices alone are insufficient."""

from dataclasses import replace
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .models import SearchHit


def canonical_url(url: str | None) -> str | None:
    if not url:
        return None
    p = urlsplit(url)
    query = [
        (k, v)
        for k, v in parse_qsl(p.query, keep_blank_values=True)
        if not k.lower().startswith("utm_") and k.lower() not in {"fbclid", "gclid"}
    ]
    return urlunsplit(
        (p.scheme.lower(), p.netloc.lower(), p.path.rstrip("/"), urlencode(sorted(query)), "")
    )


def deduplicate(hits: list[SearchHit]) -> list[SearchHit]:
    result, seen = [], {}
    for hit in hits:
        listing = hit.listing
        keys = [("id", listing.source, listing.source_id)]
        if url := canonical_url(listing.url):
            keys.append(("url", url))
        existing = next((seen[k] for k in keys if k in seen), None)
        if existing is not None:
            refs = set(existing.listing.publisher_references) | set(listing.publisher_references)
            existing.listing = replace(
                existing.listing,
                publisher_references=tuple(
                    sorted(refs, key=lambda ref: (ref.publisher, ref.url, ref.observed_via))
                ),
            )
            existing.duplicates.append(
                {"source": listing.source, "source_id": listing.source_id, "url": listing.url}
            )
        else:
            existing = hit
            result.append(hit)
        for key in keys:
            seen[key] = existing
    return result

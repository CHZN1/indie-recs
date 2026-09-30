"""Rules that tag a TMDB title as indie."""

from __future__ import annotations

import re

INDIE_STUDIO_TOKENS = (
    "a24",
    "annapurna",
    "searchlight",
    "fox searchlight",
    "neon",
    "magnolia pictures",
    "magnolia",
    "ifc films",
    "ifc midnight",
    "ifc",
    "bleecker street",
    "oscilloscope",
    "sony pictures classics",
    "focus features",
    "roadside attractions",
    "film4",
    "bbc films",
    "killer films",
    "cinereach",
    "elevation pictures",
    "mubi",
    "janus films",
)

INDIE_KEYWORD_PHRASES = (
    "independent film",
    "indie film",
    "independent cinema",
)

FESTIVAL_PHRASES = (
    "sundance film festival",
    "sundance",
    "sxsw",
    "south by southwest",
    "tribeca film festival",
    "tribeca",
    "un certain regard",
    "cannes un certain regard",
    "directors' fortnight",
    "quinzaine des realisateurs",
)


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _contains_any(haystack: str, needles: tuple[str, ...]) -> bool:
    return any(needle in haystack for needle in needles)


def classify_indie(
    *,
    production_companies: list[str],
    genres: list[str],
    keywords: list[str],
) -> bool:
    company_blob = " | ".join(_normalize(name) for name in production_companies)
    if _contains_any(company_blob, INDIE_STUDIO_TOKENS):
        return True

    tag_blob = " | ".join(_normalize(x) for x in [*genres, *keywords])
    if _contains_any(tag_blob, INDIE_KEYWORD_PHRASES):
        return True
    if _contains_any(tag_blob, FESTIVAL_PHRASES):
        return True
    return False

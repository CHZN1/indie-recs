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


def indie_evidence(
    *, production_companies: list[str], genres: list[str], keywords: list[str],
) -> list[str]:
    """Explain a discovery tag; missing evidence is not a non-indie verdict."""
    reasons = []
    for label, values, phrases in (
        ("company", production_companies, INDIE_STUDIO_TOKENS),
        ("independent keyword", [*genres, *keywords], INDIE_KEYWORD_PHRASES),
        ("festival keyword", [*genres, *keywords], FESTIVAL_PHRASES),
    ):
        for value in values:
            normalized = " " + _normalize(value) + " "
            if any(" " + _normalize(phrase) + " " in normalized for phrase in phrases):
                reasons.append(f"{label}: {value}")
    return sorted(set(reasons))


def classify_indie(
    *, production_companies: list[str], genres: list[str], keywords: list[str],
) -> bool:
    return bool(indie_evidence(production_companies=production_companies,
                              genres=genres, keywords=keywords))

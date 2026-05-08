"""Optional web-assisted topic expansion helpers."""

from __future__ import annotations

from schemas import TopicExpansion
from tools.web_search_tool import search_web_brave

JWST_SURVEYS = {
    "CEERS",
    "JADES",
    "GLASS-JWST",
    "GLASS",
    "UNCOVER",
    "COSMOS-Web",
    "PRIMER",
    "EXCELS",
    "FRESCO",
}
JWST_INSTRUMENTS = {"NIRCam", "NIRSpec", "MIRI", "NIRISS"}
JWST_SYSTEMATICS = {
    "photometric redshift uncertainty",
    "photometric redshift",
    "spectroscopic redshift",
    "dusty interloper",
    "low-redshift interloper",
    "AGN contamination",
    "nebular emission contamination",
    "stellar population synthesis assumptions",
    "SPS assumptions",
    "IMF assumptions",
    "dust attenuation modeling",
    "cosmic variance",
    "selection completeness",
    "selection function",
    "lensing magnification uncertainty",
}


def _find_terms(text: str, vocabulary: set[str]) -> list[str]:
    found: set[str] = set()
    lower = text.lower()
    for term in vocabulary:
        if term.lower() in lower:
            found.add(term)
    return sorted(found)


def expand_topic_with_web(topic: str) -> TopicExpansion:
    """Expand topic using web-discovered vocabulary from Brave snippets."""
    search_queries = [
        topic,
        f"{topic} arXiv",
        f"{topic} JWST NIRCam NIRSpec",
        f"{topic} systematics photometric redshift AGN contamination",
    ]
    snippets: list[str] = []
    urls: list[str] = []
    for query in search_queries:
        try:
            results = search_web_brave(query, count=10)
        except Exception:
            continue
        for result in results:
            title = result.get("title") or ""
            desc = result.get("description") or ""
            url = result.get("url") or ""
            snippets.append(f"{title}\n{desc}")
            if url:
                urls.append(url)

    text = "\n".join(snippets)
    surveys = _find_terms(text, JWST_SURVEYS)
    instruments = _find_terms(text, JWST_INSTRUMENTS)
    systematics = _find_terms(text, JWST_SYSTEMATICS)

    canonical_queries = [
        topic,
        f'"{topic}"',
    ]
    for survey in surveys[:6]:
        canonical_queries.append(f'"{survey}" "JWST" "massive galaxies"')
        canonical_queries.append(f'"{survey}" "stellar mass" "high redshift"')
    for instrument in instruments[:4]:
        canonical_queries.append(f'"JWST" "{instrument}" "massive galaxies" "high redshift"')
    canonical_queries.extend(
        [
            '"JWST" "massive galaxies" "high redshift"',
            '"JWST" "stellar mass density" "z > 8"',
            '"red candidate massive galaxies" "600 Myr after the Big Bang"',
            '"JWST" "quiescent galaxies" "z > 3"',
        ]
    )

    dedup_queries = list(dict.fromkeys(canonical_queries))

    return TopicExpansion(
        original_topic=topic,
        canonical_queries=dedup_queries,
        surveys=surveys,
        instruments=instruments,
        observables=[
            "NIRCam photometry",
            "NIRSpec spectroscopy",
            "photometric redshift",
            "spectroscopic redshift",
            "stellar mass function",
            "UV luminosity function",
            "rest-frame optical photometry",
        ],
        parameters=[
            "stellar mass",
            "stellar mass density",
            "galaxy number density",
            "redshift",
            "star-formation rate",
            "stellar age",
        ],
        systematics=systematics,
        negative_terms=[
            "axion",
            "exoplanet",
            "planetary",
            "cell migration",
            "biology",
            "medicine",
        ],
        source_urls=urls[:20],
    )

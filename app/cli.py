"""Typer CLI for the Astro Research Assistant pipeline."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
import time
from typing import Any

import typer
import yaml

from app.config import load_config
from schemas import (
    PaperAnalysis,
    PaperMetadata,
    ResearchHypothesis,
    ResearchReport,
    TopicExpansion,
    TopicProfile,
)
from schemas.topic_profile import ProfileSource
from tools.ads_tool import search_ads_papers
from tools.arxiv_tool import search_arxiv_papers
from tools.metadata_resolver import deduplicate_papers
from tools.openalex_tool import search_openalex_works
from tools.pdf_tool import download_pdf, extract_text_from_pdf
from tools.paper_role_classifier import (
    classify_paper_role,
    select_primary_ranked_with_quotas,
    selection_policy_from_profile,
)
from tools.query_generator import topic_profile_to_expansion
from tools.ranking_tool import rank_papers, select_recent_high_signal_papers, topic_relevance_score
from tools.topic_profiler import build_topic_profile
from tools.semantic_scholar_tool import enrich_paper_with_semantic_scholar
from tools.topic_expansion_tool import expand_topic_with_web
from tools.wiki_tool import write_source_page

app = typer.Typer(help="Astro research assistant CLI")
@app.callback()
def _root() -> None:
    """Astro research assistant CLI."""


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ONTOLOGY_DIR = PROJECT_ROOT / "ontology"
REPORTS_DIR = PROJECT_ROOT / "reports"
PAPERS_DIR = PROJECT_ROOT / "storage" / "raw" / "papers"

ASTRO_RELEVANCE_TERMS = {
    "cosmology",
    "astrophysics",
    "astronomy",
    "planck",
    "cmb",
    "lensing",
    "weak lensing",
    "cosmic shear",
    "s8",
    "sigma8",
    "omega_m",
    "dark energy",
    "hubble",
    "bao",
    "galaxy",
    "galaxies",
    "large-scale structure",
    "kids",
    "des",
    "hsc",
    "desi",
    "lambda cdm",
    "lcdm",
}

DATASET_HINTS = ("DES Y3", "KiDS-450", "KiDS", "DES", "HSC", "Planck", "ACT", "SPT", "DESI")
METHOD_HINTS = (
    "cosmic shear",
    "tomographic weak lensing",
    "weak gravitational lensing",
    "two-point correlation functions",
    "bayesian parameter inference",
    "cmb lensing",
    "galaxy clustering",
)
SYSTEMATIC_HINTS = (
    "intrinsic alignment",
    "photometric redshift uncertainty",
    "photo-z",
    "shear calibration",
    "baryonic feedback",
    "nonlinear matter power spectrum",
    "lensing reconstruction bias",
)
JWST_OBSERVABLES = {
    "NIRCam photometry",
    "NIRSpec spectroscopy",
    "photometric redshift",
    "spectroscopic redshift",
    "stellar mass function",
    "UV luminosity function",
    "rest-frame optical photometry",
    "emission line fluxes",
}
JWST_SURVEYS = {
    "JWST",
    "CEERS",
    "JADES",
    "GLASS-JWST",
    "UNCOVER",
    "COSMOS-Web",
    "PRIMER",
    "EXCELS",
}
JWST_PARAMETERS = {
    "stellar mass",
    "stellar mass density",
    "galaxy number density",
    "star-formation rate",
    "stellar age",
    "redshift",
    "UV luminosity density",
    "dust attenuation",
}
JWST_SYSTEMATICS = {
    "photometric redshift uncertainty",
    "dusty low-redshift interlopers",
    "AGN contamination",
    "nebular emission contamination",
    "stellar population synthesis assumptions",
    "IMF assumptions",
    "dust attenuation modeling",
    "cosmic variance",
    "selection completeness",
    "lensing magnification uncertainty",
}
JWST_INSTRUMENTS = {"NIRCam", "NIRSpec", "MIRI", "NIRISS"}
DARK_ENERGY_OBSERVABLES = {
    "Type Ia supernova distance modulus",
    "BAO distance scale",
    "CMB anisotropies",
    "galaxy clustering",
    "redshift-space distortions",
    "weak lensing",
}
DARK_ENERGY_SURVEYS = {
    "Planck",
    "SDSS",
    "BOSS",
    "eBOSS",
    "DESI",
    "Pantheon",
    "Pantheon+",
    "Union2.1",
    "DES",
    "KiDS",
}
DARK_ENERGY_PARAMETERS = {
    "w",
    "w0",
    "wa",
    "Omega_Lambda",
    "Omega_m",
    "Omega_K",
    "H0",
    "rho_DE(z)",
}
DARK_ENERGY_SYSTEMATICS = {
    "SN calibration",
    "host-galaxy mass correction",
    "Malmquist bias",
    "photometric calibration",
    "BAO reconstruction systematics",
    "CMB lensing amplitude anomaly",
    "selection effects",
}
DARK_ENERGY_NEGATIVE_TERMS = {"gw150914", "binary black hole merger", "stellar-mass black hole"}
TOPIC_STOPWORDS = {
    "the",
    "and",
    "from",
    "with",
    "for",
    "into",
    "between",
    "using",
    "through",
    "high",
    "low",
    "new",
    "results",
    "paper",
    "study",
}


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:120] or "topic"


def _paper_key(paper: PaperMetadata) -> str:
    return paper.doi or paper.arxiv_id or paper.ads_bibcode or paper.openalex_id or paper.title or "unknown"


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _extract_aliases(entry: Any) -> list[str]:
    if isinstance(entry, dict):
        aliases = entry.get("aliases", [])
        if isinstance(aliases, list):
            return [str(a).strip() for a in aliases if str(a).strip()]
    return []


def _term_in_text(term: str, text_lower: str) -> bool:
    return term.lower() in text_lower


def _survey_or_dataset_in_text(term: str, text_lower: str) -> bool:
    """Match survey codes without substring false positives (e.g. DES inside 'addresses')."""
    t = (term or "").strip().lower()
    if not t:
        return False
    if " " in t or "-" in t or len(t) >= 5:
        return t in text_lower
    return re.search(rf"(?<![a-z0-9]){re.escape(t)}(?![a-z0-9])", text_lower) is not None


def _extract_terms(terms: list[str] | tuple[str, ...], text_lower: str) -> list[str]:
    return sorted({term for term in terms if _term_in_text(term, text_lower)})


def _extract_datasets_from_paper(paper: PaperMetadata, text_lower: str) -> list[str]:
    title_lower = (paper.title or "").lower()
    merged = f"{title_lower}\n{text_lower}"
    seeded = set(paper.datasets)
    for term in DATASET_HINTS:
        if _survey_or_dataset_in_text(term, merged):
            seeded.add(term)
    return sorted(seeded)


def _extract_methods_from_text(text_lower: str) -> list[str]:
    return _extract_terms(METHOD_HINTS, text_lower)


def _extract_systematics_from_text(text_lower: str) -> list[str]:
    return _extract_terms(SYSTEMATIC_HINTS, text_lower)


def _extract_instruments_from_text(text_lower: str) -> list[str]:
    return _extract_terms(tuple(JWST_INSTRUMENTS), text_lower)


def _merge_topic_expansions(base: TopicExpansion, extra: TopicExpansion) -> TopicExpansion:
    """Deterministically merge two topic expansions."""
    return TopicExpansion(
        original_topic=base.original_topic,
        canonical_queries=sorted(set(base.canonical_queries) | set(extra.canonical_queries)),
        aliases=sorted(set(base.aliases) | set(extra.aliases)),
        observables=sorted(set(base.observables) | set(extra.observables)),
        surveys=sorted(set(base.surveys) | set(extra.surveys)),
        instruments=sorted(set(base.instruments) | set(extra.instruments)),
        parameters=sorted(set(base.parameters) | set(extra.parameters)),
        systematics=sorted(set(base.systematics) | set(extra.systematics)),
        negative_terms=sorted(set(base.negative_terms) | set(extra.negative_terms)),
        source_urls=sorted(set(base.source_urls) | set(extra.source_urls)),
        subfields=sorted(set(base.subfields) | set(extra.subfields)),
        arxiv_categories=sorted(set(base.arxiv_categories) | set(extra.arxiv_categories)),
    )


def _is_jwst_highz_topic(topic: str) -> bool:
    topic_l = topic.lower()
    return any(token in topic_l for token in ("jwst", "james webb", "high z", "high-z", "high redshift"))


def _is_dark_energy_topic(topic: str) -> bool:
    topic_l = topic.lower()
    return any(
        token in topic_l
        for token in ("dark energy", "equation of state", "w0", "wa", "expansion history", "time evolution")
    )


def _apply_topic_relevance_filter(
    papers: list[PaperMetadata],
    topic: str,
    negative_terms: list[str],
    threshold: float = 0.25,
    topic_profile: TopicProfile | None = None,
) -> tuple[list[PaperMetadata], list[PaperMetadata]]:
    kept: list[PaperMetadata] = []
    filtered: list[PaperMetadata] = []
    for paper in papers:
        score = topic_relevance_score(
            paper,
            topic=topic,
            topic_profile=topic_profile,
            extra_negative_terms=negative_terms,
        )
        if score >= threshold:
            kept.append(paper)
        else:
            filtered.append(paper)
    return kept, filtered


def _paper_evidence_text(paper: PaperMetadata, extracted_text: str) -> str:
    return " ".join(
        [
            paper.title or "",
            paper.abstract or "",
            paper.journal or "",
            paper.venue or "",
            " ".join(paper.fields_of_study or []),
            extracted_text or "",
        ]
    ).lower()


def _paper_metadata_text(paper: PaperMetadata) -> str:
    return " ".join(
        [
            paper.title or "",
            paper.abstract or "",
            paper.journal or "",
            paper.venue or "",
            " ".join(paper.fields_of_study or []),
            " ".join(paper.arxiv_categories or []),
        ]
    ).lower()


def _keep_if_mentioned(items: list[str], evidence_text: str) -> list[str]:
    return sorted({item for item in items if item and item.lower() in evidence_text})


def _keep_if_soft_mentioned(items: list[str], evidence_text: str) -> list[str]:
    kept: set[str] = set()
    for item in items:
        if not item:
            continue
        text = item.lower().replace("_", " ")
        if text in evidence_text:
            kept.add(item)
            continue
        pieces = [p for p in re.findall(r"[a-z0-9]+", text) if len(p) > 2]
        if pieces and sum(1 for p in pieces if p in evidence_text) >= max(1, min(2, len(pieces))):
            kept.add(item)
    return sorted(kept)


def _clean_paper_analysis_against_text(
    analysis: PaperAnalysis,
    metadata_text: str,
    evidence_text: str,
) -> PaperAnalysis:
    """Remove analysis items not explicitly present in paper evidence text."""
    analysis.datasets = _keep_if_mentioned(analysis.datasets, metadata_text)
    analysis.instruments = _keep_if_mentioned(analysis.instruments, metadata_text)
    analysis.missions = _keep_if_mentioned(analysis.missions, metadata_text)
    analysis.observables = _keep_if_soft_mentioned(analysis.observables, evidence_text)
    analysis.parameters = _keep_if_soft_mentioned(analysis.parameters, evidence_text)
    analysis.systematics = _keep_if_soft_mentioned(analysis.systematics, evidence_text)
    return analysis


def _topic_keywords(topic: str) -> set[str]:
    tokens = {tok for tok in re.findall(r"[a-z0-9]+", topic.lower()) if len(tok) >= 2}
    return {tok for tok in tokens if tok not in TOPIC_STOPWORDS}


def _fixture_topic_overlap(topic: str, papers: list[PaperMetadata]) -> float:
    keywords = _topic_keywords(topic)
    if not keywords:
        return 0.0
    best = 0.0
    for paper in papers:
        text = f"{paper.title or ''} {paper.abstract or ''}".lower()
        hits = sum(1 for kw in keywords if kw in text)
        score = hits / max(1, len(keywords))
        if score > best:
            best = score
    return best


def _legacy_yaml_topic_expand(topic: str) -> TopicExpansion:
    """Legacy per-file ontology expansion merged into profile-driven TopicExpansion."""
    topic_l = topic.lower()
    observables_db = _load_yaml(ONTOLOGY_DIR / "observables.yaml")
    surveys_db = _load_yaml(ONTOLOGY_DIR / "surveys_and_missions.yaml")
    parameters_db = _load_yaml(ONTOLOGY_DIR / "parameters.yaml")
    systematics_db = _load_yaml(ONTOLOGY_DIR / "systematics.yaml")
    topics_db = _load_yaml(ONTOLOGY_DIR / "cosmology_topics.yaml")

    aliases: set[str] = set()
    observables: set[str] = set()
    surveys: set[str] = set()
    instruments: set[str] = set()
    parameters: set[str] = set()
    systematics: set[str] = set()
    negative_terms: set[str] = {"axion", "exoplanet", "planetary", "cell migration", "biology", "medicine"}
    subfields: set[str] = set()
    arxiv_categories: set[str] = set()

    canonical_queries = {
        topic.strip(),
        f"{topic.strip()} cosmology",
        f"{topic.strip()} observational constraints",
        f"{topic.strip()} review",
    }

    for name, entry in topics_db.items():
        keys = [name.lower(), *_extract_aliases(entry)]
        if any(k.lower() in topic_l for k in keys):
            aliases.update(_extract_aliases(entry))
            subfields.add(name.replace("_", " "))
            params = entry.get("key_parameters", []) if isinstance(entry, dict) else []
            if isinstance(params, list):
                parameters.update(str(p) for p in params)
            obs = entry.get("key_observables", []) if isinstance(entry, dict) else []
            if isinstance(obs, list):
                observables.update(str(o) for o in obs)

    for name, entry in observables_db.items():
        keys = [name.lower(), *_extract_aliases(entry)]
        if any(k.lower() in topic_l for k in keys):
            observables.add(name.replace("_", " "))
            aliases.update(_extract_aliases(entry))
            related = entry.get("related_parameters", []) if isinstance(entry, dict) else []
            if isinstance(related, list):
                parameters.update(str(r) for r in related)
            sys_list = entry.get("common_systematics", []) if isinstance(entry, dict) else []
            if isinstance(sys_list, list):
                systematics.update(str(s) for s in sys_list)

    for name, entry in parameters_db.items():
        keys = [name.lower(), *_extract_aliases(entry)]
        if any(k.lower() in topic_l for k in keys):
            parameters.add(name)
            aliases.update(_extract_aliases(entry))
            related_obs = entry.get("related_observables", []) if isinstance(entry, dict) else []
            if isinstance(related_obs, list):
                observables.update(str(o) for o in related_obs)

    for name, entry in surveys_db.items():
        keys = [name.lower(), *_extract_aliases(entry)]
        if any(k.lower() in topic_l for k in keys):
            surveys.add(name)
            probes = entry.get("probes", []) if isinstance(entry, dict) else []
            if isinstance(probes, list):
                observables.update(str(p) for p in probes)

    # Add broad heuristics
    if any(k in topic_l for k in ["s8", "weak lensing", "cosmic shear", "planck", "cmb", "hubble"]):
        arxiv_categories.update(["astro-ph.CO", "astro-ph.GA"])
        subfields.add("cosmology")
    if "s8" in topic_l or "weak lensing" in topic_l or "cosmic shear" in topic_l:
        canonical_queries.update(
            {
                '"S8 tension" "weak lensing"',
                '"S_8" "cosmic shear" Planck',
                '"sigma8 tension" KiDS DES HSC Planck',
                '"cosmic shear" "Planck" "S8"',
            }
        )
        observables.update(
            {
                "cosmic shear",
                "weak gravitational lensing",
                "weak lensing two-point functions",
                "galaxy clustering",
                "CMB lensing",
                "CMB anisotropies",
            }
        )
        surveys.update({"Planck", "DES", "KiDS", "HSC", "ACT", "SPT"})
        parameters.update({"S8", "sigma8", "Omega_m"})
        systematics.update(
            {
                "intrinsic alignment",
                "photometric redshift uncertainty",
                "shear calibration",
                "baryonic feedback",
                "nonlinear matter power spectrum modeling",
                "lensing reconstruction bias",
            }
        )
    if "x-ray" in topic_l or "agn" in topic_l:
        arxiv_categories.add("astro-ph.HE")
    if _is_jwst_highz_topic(topic):
        canonical_queries.update(
            {
                '"JWST" "massive galaxies" "high redshift"',
                '"JWST" "stellar mass" "z > 8"',
                '"CEERS" "massive galaxies"',
                '"JADES" "stellar mass function"',
                '"GLASS-JWST" "luminous galaxies" "z > 7"',
                '"UNCOVER" "NIRSpec" "z > 8"',
                '"red candidate massive galaxies" "600 Myr after the Big Bang"',
                '"JWST" "quiescent galaxies" "z > 3"',
                '"JWST" "stellar mass density" "high redshift"',
            }
        )
        observables.update(JWST_OBSERVABLES)
        surveys.update(JWST_SURVEYS)
        instruments.update(JWST_INSTRUMENTS)
        parameters.update(JWST_PARAMETERS)
        systematics.update(JWST_SYSTEMATICS)
        arxiv_categories.update({"astro-ph.GA", "astro-ph.CO"})
    if _is_dark_energy_topic(topic):
        canonical_queries.update(
            {
                '"dark energy equation of state" "w0" "wa"',
                '"time evolving dark energy" "BAO" "supernovae"',
                '"dark energy density evolution" "Type Ia supernovae"',
                '"DESI" "evolving dark energy"',
                '"Pantheon+" "dark energy equation of state"',
                '"eBOSS" "dark energy" "w0 wa"',
                '"Planck" "BAO" "SNe" "dark energy equation of state"',
                '"CPL parametrization" "dark energy"',
            }
        )
        observables.update(DARK_ENERGY_OBSERVABLES)
        surveys.update(DARK_ENERGY_SURVEYS)
        parameters.update(DARK_ENERGY_PARAMETERS)
        systematics.update(DARK_ENERGY_SYSTEMATICS)
        negative_terms.update(DARK_ENERGY_NEGATIVE_TERMS)
        arxiv_categories.update({"astro-ph.CO"})

    for group in systematics_db.values():
        if isinstance(group, list):
            for item in group:
                if isinstance(item, str) and any(tok in topic_l for tok in item.lower().split()):
                    systematics.add(item)

    return TopicExpansion(
        original_topic=topic,
        canonical_queries=sorted(canonical_queries),
        aliases=sorted(aliases),
        observables=sorted(observables),
        surveys=sorted(surveys),
        instruments=sorted(instruments),
        parameters=sorted(parameters),
        systematics=sorted(systematics),
        negative_terms=sorted(negative_terms),
        source_urls=[],
        subfields=sorted(subfields),
        arxiv_categories=sorted(arxiv_categories),
    )


def build_topic_profile_and_expansion(
    topic: str,
    *,
    profile_source: ProfileSource = "ontology",
) -> tuple[TopicProfile, TopicExpansion]:
    """Build TopicProfile and merged TopicExpansion (astro ontology + legacy YAML)."""
    profile = build_topic_profile(topic, source=profile_source)
    expansion = topic_profile_to_expansion(profile)
    return profile, _merge_topic_expansions(expansion, _legacy_yaml_topic_expand(topic))


def bootstrap_paper_analysis(
    paper: PaperMetadata,
    topic: str,
    extracted_text: str,
    expansion: TopicExpansion,
    *,
    topic_profile: TopicProfile | None = None,
) -> PaperAnalysis:
    """Deterministic paper analysis bootstrap; optional profile enriches lists from title/abstract text only."""
    analysis = _bootstrap_analysis(paper, topic, extracted_text, expansion)
    if topic_profile is None:
        return analysis
    evidence_text = _paper_evidence_text(paper, extracted_text)
    metadata_text = _paper_metadata_text(paper)
    enriched = _enrich_analysis_from_profile(analysis, paper, topic_profile, evidence_text)
    return _clean_paper_analysis_against_text(
        enriched, metadata_text=metadata_text, evidence_text=evidence_text
    )


def _enrich_analysis_from_profile(
    analysis: PaperAnalysis,
    paper: PaperMetadata,
    profile: TopicProfile,
    evidence_text: str,
) -> PaperAnalysis:
    """Add profile vocabulary terms only when they appear literally in title/abstract/extracted text."""
    pool = f"{paper.title or ''} {paper.abstract or ''} {evidence_text or ''}".lower()

    def pick_extra(profile_list: list[str], current: list[str]) -> list[str]:
        seen = {x.lower() for x in current if x}
        out = [x for x in current if x]
        for term in profile_list:
            if not term:
                continue
            tl = term.lower()
            if tl in seen:
                continue
            if tl in pool:
                out.append(term)
                seen.add(tl)
        return sorted(set(out), key=str.lower)

    return analysis.model_copy(
        update={
            "observables": pick_extra(profile.observables, list(analysis.observables or [])),
            "parameters": pick_extra(profile.parameters, list(analysis.parameters or [])),
            "methods": pick_extra(profile.methods, list(analysis.methods or [])),
            "systematics": pick_extra(profile.systematics, list(analysis.systematics or [])),
            "instruments": pick_extra(profile.instruments, list(analysis.instruments or [])),
        }
    )


def _astro_relevance_score(paper: PaperMetadata) -> float:
    text = " ".join(
        [
            paper.title or "",
            paper.abstract or "",
            paper.journal or "",
            paper.venue or "",
            " ".join(paper.fields_of_study or []),
            " ".join(paper.arxiv_categories or []),
        ]
    ).lower()
    hits = sum(1 for term in ASTRO_RELEVANCE_TERMS if term in text)
    return min(1.0, hits / 4.0)


def _filter_astro_relevant(papers: list[PaperMetadata], threshold: float = 0.25) -> list[PaperMetadata]:
    return [paper for paper in papers if _astro_relevance_score(paper) >= threshold]


def _search_arxiv_with_backoff(
    query: str,
    max_results: int,
    max_attempts: int = 4,
    base_delay_seconds: float = 4.0,
) -> list[PaperMetadata]:
    """Search arXiv with retries/backoff on rate-limit errors."""
    last_error: Exception | None = None
    for attempt in range(max_attempts):
        try:
            return search_arxiv_papers(query, max_results=max_results)
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            msg = str(exc).lower()
            is_rate_limited = "429" in msg or "rate limit" in msg or "too many requests" in msg
            if not is_rate_limited or attempt == max_attempts - 1:
                raise
            sleep_s = base_delay_seconds * (2**attempt)
            typer.secho(
                (
                    f"arXiv rate-limited for '{query}'. "
                    f"Retrying in {sleep_s:.1f}s (attempt {attempt + 2}/{max_attempts})..."
                ),
                fg=typer.colors.YELLOW,
            )
            time.sleep(sleep_s)
    if last_error is not None:
        raise last_error
    return []


def _parse_sources(sources_csv: str) -> set[str]:
    selected = {part.strip().lower() for part in sources_csv.split(",") if part.strip()}
    valid = {"openalex", "arxiv", "ads"}
    unknown = selected - valid
    if unknown:
        raise typer.BadParameter(
            f"Invalid source(s): {', '.join(sorted(unknown))}. Valid: openalex, arxiv, ads."
        )
    return selected or {"openalex", "arxiv", "ads"}


def _search_sources(
    expansion: TopicExpansion,
    max_papers: int,
    include_ads: bool,
    sources: set[str],
    skip_arxiv: bool,
) -> list[PaperMetadata]:
    papers: list[PaperMetadata] = []
    queries = expansion.canonical_queries[:3] if expansion.canonical_queries else [expansion.original_topic]
    openalex_n = max(1, max_papers // 2)
    arxiv_n = max(1, max_papers // 2)

    if "openalex" in sources:
        for query in queries:
            try:
                papers.extend(search_openalex_works(query, max_results=openalex_n))
            except Exception as exc:  # noqa: BLE001
                typer.secho(f"OpenAlex search failed for '{query}': {exc}", fg=typer.colors.YELLOW)

    arxiv_enabled = "arxiv" in sources and not skip_arxiv
    if arxiv_enabled:
        # Intentionally constrained to reduce arXiv rate-limit pressure.
        arxiv_queries = queries[:1]
        for idx, query in enumerate(arxiv_queries):
            try:
                papers.extend(_search_arxiv_with_backoff(query, max_results=arxiv_n))
                # Keep additional cool-down to avoid bursty API behavior.
                if idx < len(arxiv_queries) - 1:
                    time.sleep(5.0)
            except Exception as exc:  # noqa: BLE001
                typer.secho(f"arXiv search failed for '{query}': {exc}", fg=typer.colors.YELLOW)

    if "ads" in sources and include_ads:
        for query in queries[:2]:
            try:
                papers.extend(search_ads_papers(query, max_results=max(3, max_papers // 3)))
            except Exception as exc:  # noqa: BLE001
                typer.secho(f"ADS search skipped/failed for '{query}': {exc}", fg=typer.colors.YELLOW)

    return papers


def _build_paper_payload(
    selected_papers: list[PaperMetadata],
    extracted_text_by_key: dict[str, str] | None = None,
    max_chars_per_paper: int = 8000,
) -> str:
    extracted_text_by_key = extracted_text_by_key or {}
    blocks: list[str] = []

    for i, paper in enumerate(selected_papers, start=1):
        title = paper.title or "Untitled"
        key = _paper_key(paper)
        text = (extracted_text_by_key.get(key) or paper.abstract or "").strip()
        if len(text) > max_chars_per_paper:
            text = text[:max_chars_per_paper] + "\n...[truncated]"
        authors = ", ".join(paper.authors[:10]) if paper.authors else "unknown"
        block = (
            f"[Paper {i}]\n"
            f"Title: {title}\n"
            f"Year: {paper.year or 'unknown'}\n"
            f"Authors: {authors}\n"
            f"DOI: {paper.doi or 'unknown'}\n"
            f"arXiv: {paper.arxiv_id or 'unknown'}\n"
            f"ADS bibcode: {paper.ads_bibcode or 'unknown'}\n"
            f"OpenAlex ID: {paper.openalex_id or 'unknown'}\n"
            f"Semantic Scholar ID: {paper.semantic_scholar_id or 'unknown'}\n"
            f"Citation count: {paper.citation_counts.selected or 'unknown'} "
            f"({paper.citation_counts.selected_source or 'unknown'})\n"
            f"Journal/Venue: {paper.journal or paper.venue or 'unknown'}\n"
            f"PDF URL: {paper.pdf_url or 'unknown'}\n"
            f"Landing Page: {paper.landing_page_url or 'unknown'}\n"
            "Abstract / Extracted Text:\n"
            f"{text if text else 'not available'}"
        )
        blocks.append(block)

    return "\n\n---\n\n".join(blocks)


def _load_papers_fixture(path: Path) -> tuple[list[PaperMetadata], dict[str, str]]:
    """
    Load offline fixture JSON for pipeline testing.

    Supported shapes:
    - list[paper_dict]
    - {"papers": [...]} or {"selected_papers": [...]}
    Optional:
    - {"extracted_text_by_key": {...}}
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    extracted_text_by_key: dict[str, str] = {}

    if isinstance(data, list):
        papers_raw = data
    elif isinstance(data, dict):
        papers_raw = data.get("papers", data.get("selected_papers", []))
        raw_text = data.get("extracted_text_by_key", {})
        if isinstance(raw_text, dict):
            extracted_text_by_key = {
                str(k): str(v) for k, v in raw_text.items() if isinstance(v, (str, int, float))
            }
    else:
        raise ValueError("Fixture must be a list or an object with 'papers' or 'selected_papers'.")

    if not isinstance(papers_raw, list):
        raise ValueError("Fixture papers must be a list.")

    papers = [PaperMetadata.model_validate(item) for item in papers_raw]
    return papers, extracted_text_by_key


def _bootstrap_analysis(
    paper: PaperMetadata,
    topic: str,
    extracted_text: str,
    expansion: TopicExpansion,
) -> PaperAnalysis:
    evidence_text = _paper_evidence_text(paper, extracted_text)
    metadata_text = _paper_metadata_text(paper)

    observables = sorted(set(paper.observables))
    datasets = sorted({*_extract_datasets_from_paper(paper, metadata_text)})
    parameters = sorted(set(paper.parameters))
    systematics = sorted(set(_extract_systematics_from_text(evidence_text)))
    methods = sorted({*_extract_methods_from_text(evidence_text)})
    instruments = sorted({*paper.instruments, *_extract_instruments_from_text(metadata_text)})
    key_results: list[str] = []
    if paper.abstract:
        key_results.append(paper.abstract[:300])
    elif extracted_text:
        key_results.append(extracted_text[:300])
    if not key_results:
        key_results.append("not extracted")

    topic_terms = [t for t in _slugify(topic).split("-") if len(t) > 2]
    relation = (
        "directly relevant"
        if any(t in evidence_text for t in topic_terms)
        else "not extracted"
    )

    analysis = PaperAnalysis(
        paper=paper,
        main_question="not extracted",
        paper_type=paper.paper_type,
        observables=observables,
        datasets=datasets,
        instruments=instruments,
        missions=paper.missions,
        parameters=parameters,
        redshift_range="not extracted",
        wavelength_band="not extracted",
        cosmological_model="not extracted",
        systematics=systematics,
        methods=methods,
        key_results=key_results,
        limitations=["not extracted"],
        open_questions=["not extracted"],
        relation_to_topic=relation,
    )
    return _clean_paper_analysis_against_text(analysis, metadata_text=metadata_text, evidence_text=evidence_text)


def _paper_matches_hypothesis_mechanism(analysis: PaperAnalysis, mechanism_terms: tuple[str, ...]) -> bool:
    evidence_pool = " ".join(
        [
            *(analysis.systematics or []),
            *(analysis.methods or []),
            *(analysis.key_results or []),
            *(analysis.datasets or []),
            *(analysis.observables or []),
        ]
    ).lower()
    return any(term.lower() in evidence_pool for term in mechanism_terms)


def _make_hypothesis(
    statement: str,
    rationale: str,
    analyses: list[PaperAnalysis],
    mechanism_terms: tuple[str, ...],
    proposed_test: str,
    required_data: list[str],
    required_method: list[str],
    falsification_criteria: list[str],
    novelty_score: int,
    testability_score: int,
    data_availability_score: int,
    impact_score: int,
    difficulty_score: int,
    already_done_risk: int,
) -> ResearchHypothesis:
    supporting = [a.paper for a in analyses if _paper_matches_hypothesis_mechanism(a, mechanism_terms)]
    # Conservative rule for MVP: require explicit mechanism support across multiple analyses.
    is_validated = len(supporting) >= 2
    validation_status = "validated" if is_validated else "plausible"
    grounding_notes = (
        "Validated because mechanism terms were explicitly extracted from paper analyses."
        if is_validated
        else "Plausible but not directly grounded in supplied extracted mechanisms."
    )
    evidence_basis = []
    if is_validated:
        for analysis in analyses:
            if _paper_matches_hypothesis_mechanism(analysis, mechanism_terms):
                evidence_basis.extend(analysis.systematics[:2])
                evidence_basis.extend(analysis.methods[:1])
    else:
        evidence_basis.append("No direct mechanism phrase extracted from supplied analyses.")

    return ResearchHypothesis(
        statement=statement,
        rationale=rationale,
        supporting_evidence_papers=supporting,
        status="supported" if is_validated else "refined",
        validation_status=validation_status,
        grounding_notes=grounding_notes,
        evidence_basis=sorted(set(evidence_basis)),
        proposed_test=proposed_test,
        required_data=required_data,
        required_method=required_method,
        falsification_criteria=falsification_criteria,
        novelty_score=novelty_score,
        testability_score=testability_score,
        data_availability_score=data_availability_score,
        impact_score=impact_score,
        difficulty_score=difficulty_score,
        already_done_risk=already_done_risk,
    )


def _build_structured_hypotheses(topic: str, analyses: list[PaperAnalysis]) -> list[ResearchHypothesis]:
    topic_l = topic.lower()
    if not analyses:
        return []
    hypotheses: list[ResearchHypothesis] = []
    if any(token in topic_l for token in ("s8", "weak lensing", "cosmic shear")):
        hypotheses.extend(
            [
                _make_hypothesis(
                    statement="IA-photo-z nuisance covariance can shift weak-lensing S8 inference.",
                    rationale="Weak-lensing constraints are sensitive to intrinsic alignment and photometric-redshift systematics.",
                    analyses=analyses,
                    mechanism_terms=("intrinsic alignment", "photometric redshift uncertainty", "photo-z"),
                    proposed_test=(
                        "Run joint nuisance-parameter fits with and without IA-photo-z covariance terms and compare posterior shift in S8."
                    ),
                    required_data=["DES Y3 or KiDS-like tomographic shear catalogs", "photo-z calibration samples"],
                    required_method=["Tomographic weak lensing", "Bayesian parameter inference"],
                    falsification_criteria=[
                        "S8 posterior shift remains statistically negligible when covariance terms are added."
                    ],
                    novelty_score=3,
                    testability_score=5,
                    data_availability_score=4,
                    impact_score=4,
                    difficulty_score=3,
                    already_done_risk=3,
                ),
                _make_hypothesis(
                    statement="Baryonic feedback modeling can mimic an S8-like shift in shear-inferred structure growth.",
                    rationale="Matter power modeling choices can project into weak-lensing parameter shifts when small scales are included.",
                    analyses=analyses,
                    mechanism_terms=("baryonic feedback", "nonlinear matter power spectrum"),
                    proposed_test="Re-fit S8 with alternative baryonic feedback priors and scale cuts across matched lensing pipelines.",
                    required_data=["Cosmic shear two-point measurements", "Hydrodynamical calibration priors"],
                    required_method=["Scale-cut sensitivity analysis", "Hierarchical Bayesian modeling"],
                    falsification_criteria=["S8 remains stable across feedback model families within quoted uncertainty."],
                    novelty_score=2,
                    testability_score=4,
                    data_availability_score=3,
                    impact_score=4,
                    difficulty_score=4,
                    already_done_risk=4,
                ),
            ]
        )
    if _is_jwst_highz_topic(topic):
        hypotheses.extend(
            [
                _make_hypothesis(
                    statement="Photometric-redshift and dusty low-z interlopers inflate inferred abundance of massive high-z galaxy candidates.",
                    rationale="JWST high-z candidate samples are sensitive to redshift misclassification and dust degeneracies.",
                    analyses=analyses,
                    mechanism_terms=("photometric redshift", "interloper", "dust"),
                    proposed_test="Cross-match NIRCam-selected candidates with NIRSpec confirmation and re-estimate high-mass number densities.",
                    required_data=["JWST NIRCam catalogs", "NIRSpec follow-up spectra"],
                    required_method=["Photometric-redshift recalibration", "Spectroscopic validation"],
                    falsification_criteria=["Number density remains unchanged after spectroscopic confirmation and interloper filtering."],
                    novelty_score=3,
                    testability_score=5,
                    data_availability_score=4,
                    impact_score=5,
                    difficulty_score=3,
                    already_done_risk=3,
                ),
                _make_hypothesis(
                    statement="SPS/IMF/dust modeling assumptions can bias stellar-mass estimates upward for early JWST massive-galaxy claims.",
                    rationale="Mass estimates at high redshift depend strongly on SED priors and stellar-population assumptions.",
                    analyses=analyses,
                    mechanism_terms=("stellar population", "imf", "dust attenuation", "stellar mass"),
                    proposed_test="Re-fit the same JWST photometric and spectroscopic samples under alternative SPS/IMF/dust priors.",
                    required_data=["JWST photometry", "JWST spectroscopy", "SPS model grids"],
                    required_method=["SED fitting sensitivity analysis", "Hierarchical Bayesian model comparison"],
                    falsification_criteria=["Stellar-mass posteriors are stable across SPS/IMF/dust prior choices."],
                    novelty_score=3,
                    testability_score=4,
                    data_availability_score=4,
                    impact_score=5,
                    difficulty_score=4,
                    already_done_risk=3,
                ),
                _make_hypothesis(
                    statement="Cosmic variance and selection completeness jointly explain part of the apparent excess of ultra-massive galaxies at high redshift.",
                    rationale="Small-area deep fields can produce abundance fluctuations and completeness-driven bias.",
                    analyses=analyses,
                    mechanism_terms=("cosmic variance", "selection completeness", "number density"),
                    proposed_test="Compare inferred high-mass abundances across independent JWST fields with matched selection and completeness corrections.",
                    required_data=["CEERS/JADES/GLASS-like field catalogs", "Survey selection functions"],
                    required_method=["Field-to-field variance modeling", "Completeness-corrected abundance inference"],
                    falsification_criteria=["Cross-field abundance discrepancy persists after variance and completeness modeling."],
                    novelty_score=2,
                    testability_score=4,
                    data_availability_score=3,
                    impact_score=4,
                    difficulty_score=4,
                    already_done_risk=4,
                ),
            ]
        )
    if _is_dark_energy_topic(topic):
        hypotheses.extend(
            [
                _make_hypothesis(
                    statement="Time-evolving dark energy (w0-wa/CPL) improves consistency across SNe+BAO+CMB compared to constant-w fits.",
                    rationale="Dark-energy evolution analyses commonly test whether evolving equations of state reduce multi-probe tension.",
                    analyses=analyses,
                    mechanism_terms=("dark energy", "equation of state", "w0", "wa", "cpl"),
                    proposed_test="Perform joint SNe+BAO+CMB fits under wCDM and w0waCDM and compare evidence and residual tension metrics.",
                    required_data=["Type Ia supernova compilations", "BAO distances", "CMB constraints"],
                    required_method=["Joint likelihood inference", "Model comparison"],
                    falsification_criteria=["w0wa model fails to improve fit or shows no meaningful posterior preference over constant-w."],
                    novelty_score=2,
                    testability_score=5,
                    data_availability_score=5,
                    impact_score=5,
                    difficulty_score=3,
                    already_done_risk=4,
                ),
                _make_hypothesis(
                    statement="Calibration and selection systematics in SNe samples can mimic apparent dark-energy evolution signatures.",
                    rationale="Photometric calibration and selection effects are known to bias distance-redshift inference.",
                    analyses=analyses,
                    mechanism_terms=("supernova", "calibration", "selection", "distance modulus", "malmquist"),
                    proposed_test="Re-analyze supernova Hubble-diagram constraints with alternate calibration/selection models and compare w0-wa shifts.",
                    required_data=["SNe light-curve data", "Calibration metadata", "Host-galaxy covariates"],
                    required_method=["Systematics stress-testing", "Hierarchical Bayesian inference"],
                    falsification_criteria=["w0-wa posterior remains stable under broad calibration/selection model variants."],
                    novelty_score=3,
                    testability_score=4,
                    data_availability_score=4,
                    impact_score=4,
                    difficulty_score=4,
                    already_done_risk=3,
                ),
            ]
        )
    if not hypotheses:
        return []
    for idx, hypothesis in enumerate(hypotheses, start=1):
        hypothesis.display_rank = idx
    return hypotheses


def _normalize_validation_status(raw: str | None) -> str:
    value = (raw or "").strip().lower()
    if "reject" in value:
        return "rejected"
    if "valid" in value:
        return "validated"
    if "plaus" in value:
        return "plausible"
    return "plausible"


def _map_supporting_papers(raw_support: list[str], selected_papers: list[PaperMetadata]) -> list[PaperMetadata]:
    if not raw_support:
        return []
    matched: list[PaperMetadata] = []
    for token in raw_support:
        token_l = token.lower()
        for paper in selected_papers:
            title = (paper.title or "").lower()
            if token_l and (token_l in title or title in token_l):
                matched.append(paper)
                break
    return matched


def _extract_hypotheses_from_crew_text(
    crew_result_text: str,
    selected_papers: list[PaperMetadata],
) -> list[ResearchHypothesis]:
    """Try to parse structured hypotheses JSON embedded in crew output text."""
    candidates = re.findall(r"\{[\s\S]*\}", crew_result_text)
    for blob in reversed(candidates):
        try:
            payload = json.loads(blob)
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        raw_hypotheses = payload.get("hypotheses")
        if not isinstance(raw_hypotheses, list):
            continue
        parsed: list[ResearchHypothesis] = []
        for idx, item in enumerate(raw_hypotheses, start=1):
            if not isinstance(item, dict):
                continue
            claim = str(item.get("claim") or item.get("statement") or "").strip()
            if not claim:
                continue
            status = _normalize_validation_status(str(item.get("status") or ""))
            supporting_titles = [str(x) for x in item.get("supporting_papers", []) if isinstance(x, str)]
            supporting_papers = _map_supporting_papers(supporting_titles, selected_papers)
            parsed.append(
                ResearchHypothesis(
                    statement=claim,
                    rationale=str(item.get("grounding_notes") or item.get("rationale") or ""),
                    supporting_evidence_papers=supporting_papers,
                    status="supported" if status == "validated" else "refined",
                    validation_status=status,  # type: ignore[arg-type]
                    grounding_notes=str(item.get("grounding_notes") or ""),
                    evidence_basis=[str(x) for x in item.get("evidence_basis", []) if isinstance(x, str)],
                    proposed_test=str(item.get("proposed_test") or "") or None,
                    required_data=[str(x) for x in item.get("required_data", []) if isinstance(x, str)],
                    required_method=[str(x) for x in item.get("required_methods", []) if isinstance(x, str)],
                    falsification_criteria=[str(item.get("falsification_criteria") or "")] if item.get("falsification_criteria") else [],
                    novelty_score=item.get("novelty_score"),
                    testability_score=item.get("testability_score"),
                    data_availability_score=item.get("data_availability_score"),
                    impact_score=item.get("impact_score"),
                    difficulty_score=item.get("difficulty_score"),
                    already_done_risk=item.get("already_done_risk"),
                    display_rank=idx,
                )
            )
        if parsed:
            return parsed
    return []


def _run_crew_or_fallback(
    topic: str,
    selected_papers: list[PaperMetadata],
    analyses: list[PaperAnalysis],
    paper_payload: str,
) -> tuple[str, str]:
    """
    Run CrewAI pipeline when available.

    Returns tuple: (crew_result_text, mode)
    """
    try:
        from crews.research_crew import build_research_crew

        config = load_config()
        llm = config.llm_model
        crew = build_research_crew(llm=llm)
        result = crew.kickoff(
            inputs={
                "topic": topic,
                "paper_payload": paper_payload,
                "selected_papers": [p.model_dump(mode="json") for p in selected_papers],
                "paper_analyses": [a.model_dump(mode="json") for a in analyses],
            }
        )
        return str(result), "crew"
    except Exception as exc:  # noqa: BLE001
        fallback = (
            f"Crew execution unavailable; using deterministic fallback summary.\n"
            f"Reason: {exc}\n\n"
            f"Analyzed papers: {len(analyses)}"
        )
        return fallback, "fallback"


def _render_report_markdown(
    topic: str,
    expansion: TopicExpansion,
    primary: list[PaperMetadata],
    recent: list[PaperMetadata],
    background: list[PaperMetadata],
    analyses: list[PaperAnalysis],
    hypotheses: list[ResearchHypothesis],
    crew_result_text: str,
    mode: str,
    fixture_mode: bool,
    topic_profile: TopicProfile | None = None,
    *,
    debug_report: bool = True,
    selection_diagnostics: list[str] | None = None,
    primary_paper_roles: dict[str, str] | None = None,
) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
    primary_keys = {_paper_key(p) for p in primary}
    recent_unique = [paper for paper in recent if _paper_key(paper) not in primary_keys]
    cited_unique = primary + [p for p in recent_unique if p not in primary]
    report = ResearchReport(
        title=f"Research Report: {topic}",
        query_or_brief=topic,
        executive_summary=crew_result_text[:1200],
        paper_analyses=analyses,
        hypotheses=hypotheses,
        cited_papers=cited_unique,
    )
    primary_paper_heading = "## Selected Fixture Papers" if fixture_mode else "## Selected Primary Papers"

    lines = [
        f"# {report.title}",
        "",
        f"- Generated: {now}",
        f"- Mode: {mode}",
        f"- Topic: {topic}",
    ]
    if fixture_mode:
        lines.append(
            "- Note: Fixture mode active; citation ranking and retrieval confidence are limited to provided fixture metadata."
        )
    lines.extend(
        [
            "",
            "## Topic Expansion",
            f"- Retrieval queries: {', '.join(expansion.canonical_queries) if expansion.canonical_queries else 'None'}",
            f"- Observables: {', '.join(expansion.observables) if expansion.observables else 'None'}",
            f"- Surveys: {', '.join(expansion.surveys) if expansion.surveys else 'None'}",
            f"- Instruments: {', '.join(expansion.instruments) if expansion.instruments else 'None'}",
            f"- Parameters: {', '.join(expansion.parameters) if expansion.parameters else 'None'}",
            f"- Systematics: {', '.join(expansion.systematics) if expansion.systematics else 'None'}",
            "",
            primary_paper_heading,
        ]
    )
    for i, p in enumerate(primary, 1):
        rk = _paper_key(p)
        role = primary_paper_roles.get(rk) if primary_paper_roles else None
        role_suffix = f" — {role}" if role else ""
        lines.append(f"{i}. {p.title or 'Untitled'} ({p.year or 'n/a'}){role_suffix}")
    lines.extend(["", "## Selected Recent High-Signal Papers"])
    if not recent_unique:
        lines.append("Recent high-signal papers are the same as the primary selected set for this run.")
    for i, p in enumerate(recent_unique, 1):
        lines.append(f"{i}. {p.title or 'Untitled'} ({p.year or 'n/a'})")
    if background:
        lines.extend(["", "## Background / Infrastructure Papers"])
        for i, p in enumerate(background, 1):
            lines.append(f"{i}. {p.title or 'Untitled'} ({p.year or 'n/a'})")
    if debug_report and selection_diagnostics:
        lines.extend(["", "## Selection Diagnostics", *selection_diagnostics])
    if topic_profile and debug_report:
        lines.extend(
            [
                "",
                "## TopicProfile (debug)",
                f"- profile_version: {topic_profile.profile_version}",
                f"- source: {topic_profile.source}",
                f"- primary_domain: {topic_profile.primary_domain or 'unknown'}",
                f"- profile_confidence: {topic_profile.profile_confidence}",
            ]
        )
    lines.extend(["", "## Structured Hypotheses"])
    if not hypotheses:
        lines.append("No structured hypotheses generated.")
    for h in hypotheses:
        rank = h.display_rank or 0
        lines.extend(
            [
                f"### Hypothesis {rank if rank > 0 else '?'} ({h.validation_status})",
                f"- Claim: {h.statement}",
                f"- Grounding: {h.grounding_notes or 'not extracted'}",
                f"- Evidence basis: {', '.join(h.evidence_basis) if h.evidence_basis else 'none'}",
            ]
        )
    lines.extend(["", "## Crew Output", crew_result_text, "", "## Structured Report Snapshot", "```json", report.model_dump_json(indent=2), "```", ""])
    return "\n".join(lines)


@app.command("research")
def research(
    topic: str = typer.Argument(..., help="Research topic, e.g. 'S8 tension between weak lensing and Planck'"),
    max_papers: int = typer.Option(10, "--max-papers", min=1, max=200, help="Max papers to keep after ranking"),
    download: bool = typer.Option(False, "--download", help="Download PDFs for selected papers"),
    input_json: Path | None = typer.Option(
        None,
        "--input-json",
        help="Offline fixture JSON path (bypasses live retrieval APIs).",
    ),
    strict_fixture_topic_match: bool = typer.Option(
        True,
        "--strict-fixture-topic-match/--no-strict-fixture-topic-match",
        help=(
            "When using --input-json, require at least minimal keyword overlap between topic and fixture papers."
        ),
    ),
    skip_arxiv: bool = typer.Option(
        False,
        "--skip-arxiv",
        help="Skip arXiv retrieval in live mode.",
    ),
    sources: str = typer.Option(
        "openalex,arxiv,ads",
        "--sources",
        help="Comma-separated retrieval sources in live mode: openalex,arxiv,ads",
    ),
    web_expand: bool = typer.Option(
        False,
        "--web-expand",
        help="Use optional web-assisted topic expansion discovery before retrieval.",
    ),
    relevance_threshold: float = typer.Option(
        0.25,
        "--relevance-threshold",
        min=0.0,
        max=1.0,
        help="Minimum topic relevance score to keep candidate papers before ranking.",
    ),
    debug_report: bool = typer.Option(
        True,
        "--debug-report/--no-debug-report",
        help="Include selection diagnostics and TopicProfile summary in the report.",
    ),
) -> None:
    """Run end-to-end research pipeline on a topic."""
    config = load_config()
    typer.secho("Starting research pipeline...", fg=typer.colors.CYAN)
    selected_sources = _parse_sources(sources)

    profile_source: ProfileSource = "fixture" if input_json else "ontology"
    topic_profile, expansion = build_topic_profile_and_expansion(topic, profile_source=profile_source)
    if web_expand:
        try:
            web_expansion = expand_topic_with_web(topic)
            expansion = _merge_topic_expansions(expansion, web_expansion)
            topic_profile = topic_profile.model_copy(update={"source": "ontology+web"})
            typer.secho(
                f"Web expansion added {len(web_expansion.canonical_queries)} discovered queries.",
                fg=typer.colors.CYAN,
            )
        except Exception as exc:  # noqa: BLE001
            typer.secho(f"Web topic expansion skipped: {exc}", fg=typer.colors.YELLOW)
    typer.echo(f"Expanded topic with {len(expansion.canonical_queries)} retrieval queries.")

    fixture_text_by_key: dict[str, str] = {}
    filter_reject_count = 0
    if input_json is not None:
        papers, fixture_text_by_key = _load_papers_fixture(input_json)
        typer.secho(f"Loaded {len(papers)} papers from fixture: {input_json}", fg=typer.colors.CYAN)
        overlap = _fixture_topic_overlap(topic, papers)
        if strict_fixture_topic_match and overlap < 0.08:
            typer.secho(
                (
                    "Fixture/topic mismatch detected. The provided fixture papers do not appear to match the topic.\n"
                    f"- Topic: {topic}\n"
                    f"- Fixture: {input_json}\n"
                    f"- Best keyword overlap score: {overlap:.2f}\n\n"
                    "Use a topic-aligned fixture, run without --input-json for live retrieval, "
                    "or pass --no-strict-fixture-topic-match to force this run."
                ),
                fg=typer.colors.RED,
            )
            raise typer.Exit(code=2)
        astro_relevant = _filter_astro_relevant(papers)
        if not astro_relevant:
            typer.secho("No astro-relevant fixture papers after filtering; using all fixture papers.", fg=typer.colors.YELLOW)
            astro_relevant = papers
        relevant, filtered_out = _apply_topic_relevance_filter(
            astro_relevant,
            topic=topic,
            negative_terms=expansion.negative_terms,
            threshold=relevance_threshold,
            topic_profile=topic_profile,
        )
        filter_reject_count = len(filtered_out)
        if not relevant:
            typer.secho(
                "No fixture papers met topic relevance threshold; using astro-filtered fixture papers.",
                fg=typer.colors.YELLOW,
            )
            relevant = astro_relevant
            _filtered_out = []
        deduped = deduplicate_papers(relevant)
        typer.echo(f"Fixture papers filtered to {len(relevant)} and deduplicated to {len(deduped)}.")
        enriched = deduped
    else:
        if skip_arxiv:
            typer.secho("Live mode: arXiv retrieval disabled via --skip-arxiv.", fg=typer.colors.CYAN)
        if "arxiv" not in selected_sources:
            typer.secho("Live mode: arXiv retrieval disabled via --sources.", fg=typer.colors.CYAN)
        papers = _search_sources(
            expansion=expansion,
            max_papers=max_papers * 2,
            include_ads=bool(config.nasa_ads_api_key),
            sources=selected_sources,
            skip_arxiv=skip_arxiv,
        )
        if not papers:
            raise typer.Exit(code=1)

        astro_relevant = _filter_astro_relevant(papers)
        if not astro_relevant:
            typer.secho("No astro-relevant papers after filtering; falling back to unfiltered set.", fg=typer.colors.YELLOW)
            astro_relevant = papers
        relevant, filtered_out = _apply_topic_relevance_filter(
            astro_relevant,
            topic=topic,
            negative_terms=expansion.negative_terms,
            threshold=relevance_threshold,
            topic_profile=topic_profile,
        )
        filter_reject_count = len(filtered_out)
        if not relevant:
            typer.secho(
                "No live papers met topic relevance threshold; using astro-filtered set.",
                fg=typer.colors.YELLOW,
            )
            relevant = astro_relevant
            _filtered_out = []
        deduped = deduplicate_papers(relevant)
        typer.echo(
            f"Retrieved {len(papers)} papers; astro-filtered to {len(astro_relevant)}, "
            f"topic-filtered to {len(relevant)}, deduplicated to {len(deduped)}."
        )

        enriched: list[PaperMetadata] = []
        for paper in deduped:
            try:
                enriched.append(enrich_paper_with_semantic_scholar(paper))
            except Exception:  # noqa: BLE001
                enriched.append(paper)

    ranked = rank_papers(
        enriched,
        topic=topic,
        negative_terms=expansion.negative_terms,
        topic_profile=topic_profile,
    )
    pol = selection_policy_from_profile(topic_profile, max_papers)
    primary_cut = (
        max(relevance_threshold, 0.35) if topic_profile.primary_domain == "cosmology" else relevance_threshold
    )
    primary_ranked, background_md, rejected_roles = select_primary_ranked_with_quotas(
        ranked,
        topic_profile,
        topic,
        relevance_threshold=relevance_threshold,
        primary_threshold=primary_cut,
        policy=pol,
    )
    recent_ranked = select_recent_high_signal_papers(ranked, n=min(5, max_papers))

    selected_ranked = primary_ranked + [
        r for r in recent_ranked if r.metadata not in [c.metadata for c in primary_ranked]
    ]
    selected_papers = deduplicate_papers([r.metadata for r in selected_ranked])[:max_papers]

    flat_matches: list[str] = []
    for vals in topic_profile.matched_terms.values():
        flat_matches.extend(vals)
    selection_diagnostics = [
        f"- Topic profile domain: {topic_profile.primary_domain or 'unknown'}",
        f"- Topic profile source: {topic_profile.source}",
        f"- Papers dropped by relevance pre-filter: {filter_reject_count}",
        f"- Papers rejected as off-topic (role): {len(rejected_roles)}",
        f"- Relevance threshold: {relevance_threshold}",
        f"- Primary relevance cutoff: {primary_cut}",
        (
            f"- Selection policy: max_papers={pol.max_papers}, min_direct_evidence={pol.min_direct_evidence}, "
            f"max_theory={pol.max_theory_interpretation}, max_method_or_instrument={pol.max_method_or_instrument}, "
            f"max_background_slot={pol.max_background}, max_background_roles_in_primary={pol.max_background_roles_in_primary}"
        ),
    ]
    if flat_matches:
        selection_diagnostics.append(
            f"- Matched profile terms: {', '.join(sorted(set(flat_matches))[:48])}"
        )

    text_by_paper: dict[str, str] = {}
    downloaded_paths: list[Path] = []
    for paper in selected_papers:
        pdf_path: Path | None = None
        if download:
            pdf_path = download_pdf(paper, PAPERS_DIR)
            if pdf_path:
                downloaded_paths.append(pdf_path)
        text = extract_text_from_pdf(pdf_path, max_pages=20) if pdf_path else ""
        if not text:
            text = fixture_text_by_key.get(_paper_key(paper), "").strip() or (paper.abstract or "").strip()
        text_by_paper[_paper_key(paper)] = text

    analyses = [
        bootstrap_paper_analysis(
            paper=paper,
            topic=topic,
            extracted_text=text_by_paper.get(_paper_key(paper), ""),
            expansion=expansion,
            topic_profile=topic_profile,
        )
        for paper in selected_papers
    ]
    fallback_hypotheses = _build_structured_hypotheses(topic=topic, analyses=analyses)

    paper_payload = _build_paper_payload(
        selected_papers=selected_papers,
        extracted_text_by_key=text_by_paper,
    )
    typer.echo("\nCrew paper payload preview:")
    typer.echo(paper_payload[:2000])
    typer.echo(f"\nPayload length: {len(paper_payload)}")

    crew_result_text, mode = _run_crew_or_fallback(
        topic=topic,
        selected_papers=selected_papers,
        analyses=analyses,
        paper_payload=paper_payload,
    )
    parsed_hypotheses = _extract_hypotheses_from_crew_text(
        crew_result_text=crew_result_text,
        selected_papers=selected_papers,
    )
    hypotheses = parsed_hypotheses or fallback_hypotheses

    primary_roles_by_key = {
        _paper_key(r.metadata): classify_paper_role(r.metadata, topic_profile, topic) for r in primary_ranked
    }

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    topic_slug = _slugify(topic)
    report_path = REPORTS_DIR / f"{topic_slug}.md"
    report_md = _render_report_markdown(
        topic=topic,
        expansion=expansion,
        primary=[r.metadata for r in primary_ranked],
        recent=[r.metadata for r in recent_ranked],
        background=background_md[: min(10, max_papers)],
        analyses=analyses,
        hypotheses=hypotheses,
        crew_result_text=crew_result_text,
        mode=mode,
        fixture_mode=input_json is not None,
        topic_profile=topic_profile,
        debug_report=debug_report,
        selection_diagnostics=selection_diagnostics if debug_report else None,
        primary_paper_roles=primary_roles_by_key,
    )
    report_path.write_text(report_md, encoding="utf-8")

    wiki_paths: list[Path] = []
    for paper, analysis in zip(selected_papers, analyses):
        wiki_paths.append(write_source_page(paper, analysis))

    typer.secho("\nPipeline complete.", fg=typer.colors.GREEN)
    typer.echo(f"Report: {report_path}")
    if downloaded_paths:
        typer.echo(f"Downloaded PDFs ({len(downloaded_paths)}):")
        for p in downloaded_paths[:10]:
            typer.echo(f"- {p}")
    typer.echo("Wiki source pages:")
    for p in wiki_paths[:10]:
        typer.echo(f"- {p}")
    typer.echo(f"Wiki index: {PROJECT_ROOT / 'storage' / 'wiki' / 'index.md'}")
    typer.echo(f"Wiki log:   {PROJECT_ROOT / 'storage' / 'wiki' / 'log.md'}")


if __name__ == "__main__":
    app()

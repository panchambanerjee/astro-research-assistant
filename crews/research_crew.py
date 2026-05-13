"""CrewAI assembly for sequential research synthesis and hypothesis workflow."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from crewai import Agent, Crew, Process, Task

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROMPTS_DIR = PROJECT_ROOT / "prompts"


def _prompt(name: str) -> str:
    return (PROMPTS_DIR / name).read_text(encoding="utf-8").strip()


def build_research_crew(llm: Any) -> Crew:
    """
    Build the core research crew.

    Notes:
    - Assumes paper search/ranking/download happened before kickoff.
    - Expects kickoff inputs to include selected papers and topic context.
    """
    paper_analyzer = Agent(
        role="Paper Analyzer",
        goal=_prompt("paper_analysis.md"),
        backstory="Astrophysics paper analyst specialized in structured extraction.",
        llm=llm,
        allow_delegation=False,
    )
    synthesis_agent = Agent(
        role="Field Synthesis Agent",
        goal=_prompt("synthesis.md"),
        backstory="Synthesizes cross-paper evidence and identifies tensions.",
        llm=llm,
        allow_delegation=False,
    )
    research_strategist = Agent(
        role="Research Strategist",
        goal=_prompt("hypothesis_generation.md"),
        backstory="Generates concrete, testable research hypotheses from evidence.",
        llm=llm,
        allow_delegation=False,
    )
    skeptical_referee = Agent(
        role="Skeptical Referee",
        goal=_prompt("skeptical_review.md"),
        backstory="Critiques hypotheses for rigor, feasibility, and evidence grounding.",
        llm=llm,
        allow_delegation=False,
    )
    report_compiler = Agent(
        role="Report Compiler",
        goal=_prompt("report_compilation.md"),
        backstory="Compiles final evidence-grounded research report.",
        llm=llm,
        allow_delegation=False,
    )

    analyze_selected_papers = Task(
        description=(
            "Analyze the selected papers.\n\n"
            "Topic:\n{topic}\n\n"
            "Selected papers:\n{paper_payload}\n\n"
            "Return ONLY valid JSON with this exact shape:\n"
            "{\n"
            '  "paper_analyses": [\n'
            "    {\n"
            '      "paper_title": "...",\n'
            '      "main_question": "...",\n'
            '      "paper_type": "...",\n'
            '      "observables": [],\n'
            '      "datasets": [],\n'
            '      "instruments": [],\n'
            '      "missions": [],\n'
            '      "parameters": [],\n'
            '      "redshift_range": "not extracted",\n'
            '      "wavelength_band": "not extracted",\n'
            '      "cosmological_model": "not extracted",\n'
            '      "systematics": [],\n'
            '      "methods": [],\n'
            '      "key_results": [],\n'
            '      "limitations": [],\n'
            '      "open_questions": [],\n'
            '      "relation_to_topic": "..."\n'
            "    }\n"
            "  ]\n"
            "}\n\n"
            "Rules:\n"
            "- Extract datasets from titles too (e.g., DES Y3, KiDS-450).\n"
            "- Topic-expansion terms are retrieval hints only; include datasets/instruments/missions only if explicitly present in the paper's supplied text.\n"
            "- Extract methods only when explicit in supplied text.\n"
            "- Extract systematics only when explicit in supplied text.\n"
            "- Use [] for unknown lists.\n"
            '- Use "not extracted" only for unknown scalar fields.\n'
            "- Do not use external memory beyond supplied papers."
        ),
        expected_output=(
            'Valid JSON object containing key "paper_analyses".'
        ),
        agent=paper_analyzer,
    )

    synthesize_field = Task(
        description=(
            "Using the structured analyses from the previous task, synthesize the field status."
        ),
        expected_output=(
            "Field synthesis covering overview, canonical results, consensus, tensions, "
            "recurring systematics, methodological weaknesses, open problems, and promising directions; "
            "explicitly separate evidence from papers vs assistant inference."
        ),
        agent=synthesis_agent,
        context=[analyze_selected_papers],
    )

    generate_hypotheses = Task(
        description=(
            "Generate hypotheses from structured analyses and synthesis.\n"
            "Return ONLY valid JSON with this shape:\n"
            "{\n"
            '  "hypotheses": [\n'
            "    {\n"
            '      "claim": "...",\n'
            '      "status": "source_validated | cross_paper_supported | plausible | unsupported | rejected",\n'
            '      "supporting_papers": ["..."],\n'
            '      "evidence_basis": ["..."],\n'
            '      "proposed_test": "...",\n'
            '      "required_data": ["..."],\n'
            '      "required_methods": ["..."],\n'
            '      "falsification_criteria": "...",\n'
            '      "novelty_score": 1,\n'
            '      "testability_score": 1,\n'
            '      "data_availability_score": 1,\n'
            '      "impact_score": 1,\n'
            '      "difficulty_score": 1,\n'
            '      "already_done_risk": 1,\n'
            '      "grounding_notes": "..."\n'
            "    }\n"
            "  ]\n"
            "}\n\n"
            "Rules:\n"
            '- Use "source_validated" only if the key mechanism appears explicitly in extracted paper analyses (one strong paper).\n'
            '- Use "cross_paper_supported" only if multiple extracted analyses independently support the mechanism.\n'
            '- If mechanism is domain-plausible but not explicit in supplied evidence, mark "plausible".\n'
            '- Use "unsupported" when the corpus does not contain enough extracted evidence to judge.\n'
            '- Use "rejected" when claims are unfalsifiable or clearly contradicted by supplied analyses.\n'
            "- Do not upgrade to source_validated or cross_paper_supported based on general cosmology knowledge alone."
        ),
        expected_output=(
            'Valid JSON object containing key "hypotheses".'
        ),
        agent=research_strategist,
        context=[analyze_selected_papers, synthesize_field],
    )

    critique_hypotheses = Task(
        description=(
            "Critique generated hypotheses and return ONLY valid JSON with key 'hypotheses'. "
            "Each hypothesis must have status in "
            "{source_validated, cross_paper_supported, plausible, unsupported, rejected}. "
            "source_validated / cross_paper_supported require explicit mechanism phrases in extracted analyses."
        ),
        expected_output=(
            "Valid JSON hypotheses list with corrected statuses and grounding notes."
        ),
        agent=skeptical_referee,
        context=[analyze_selected_papers, synthesize_field, generate_hypotheses],
    )

    compile_report = Task(
        description=(
            "Compile the final research report.\n\n"
            "Topic:\n"
            "{topic}\n\n"
            "Original selected papers:\n"
            "{paper_payload}\n\n"
            "Use the previous task outputs:\n"
            "- structured analyses\n"
            "- field synthesis\n"
            "- status-labeled hypotheses "
            "(source_validated / cross_paper_supported / plausible / unsupported / rejected)\n\n"
            "The report must include:\n"
            "1. Executive summary\n"
            "2. Selected papers table\n"
            "3. Per-paper distillation\n"
            "4. Field synthesis\n"
            "5. Tensions/disagreements\n"
            "6. Systematics\n"
            "7. Hypotheses with explicit status labels\n"
            "8. Limitations/open questions\n"
            "9. Bibliography\n\n"
            "Do not say that papers were not provided. They are included above."
        ),
        expected_output=(
            "A structured final report with executive summary, evidence-grounded conclusions, "
            "tensions/disagreements, labeled hypotheses (source_validated / cross_paper_supported / …), limitations, open questions, and explicit paper citations."
        ),
        agent=report_compiler,
        context=[analyze_selected_papers, synthesize_field, critique_hypotheses],
    )

    return Crew(
        agents=[
            paper_analyzer,
            synthesis_agent,
            research_strategist,
            skeptical_referee,
            report_compiler,
        ],
        tasks=[
            analyze_selected_papers,
            synthesize_field,
            generate_hypotheses,
            critique_hypotheses,
            compile_report,
        ],
        process=Process.sequential,
        verbose=True,
    )

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
            "Analyze the selected papers provided at kickoff. "
            "Produce structured astrophysics-specific analyses for each paper."
        ),
        expected_output=(
            "A JSON-like list of structured paper analyses with main question, paper type, "
            "observables, datasets/surveys, instruments/missions, redshift, wavelength/frequency, "
            "model, constrained parameters, methods, key results, systematics, limitations, "
            'open questions, and relation to topic. Use "not extracted" where needed.'
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
            "Generate concrete, testable astrophysics hypotheses grounded in the synthesis and analyzed papers."
        ),
        expected_output=(
            "A list of hypotheses, each with claim, literature motivation, supporting papers, "
            "proposed test, required data, required method, falsification criteria, and "
            "scores (novelty/testability/data availability/impact/difficulty/already-done risk, each 1-5)."
        ),
        agent=research_strategist,
        context=[analyze_selected_papers, synthesize_field],
    )

    critique_hypotheses = Task(
        description=(
            "Critique the generated hypotheses and keep only robust, evidence-grounded, falsifiable items."
        ),
        expected_output=(
            "Only validated hypotheses. Remove or revise hypotheses that are vague, unsupported, "
            "unfalsifiable, already done, disconnected from evidence, or infeasible."
        ),
        agent=skeptical_referee,
        context=[analyze_selected_papers, synthesize_field, generate_hypotheses],
    )

    compile_report = Task(
        description=(
            "Compile the final research report from selected papers, analyses, synthesis, "
            "and validated hypotheses."
        ),
        expected_output=(
            "A structured final report with executive summary, evidence-grounded conclusions, "
            "tensions/disagreements, validated hypotheses, limitations, open questions, and explicit paper citations."
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

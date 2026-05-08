"""Agent scaffolds for topic expansion, analysis, synthesis, and hypothesis review."""

from .paper_analyzer import PaperAnalyzerAgentSpec
from .research_strategist import ResearchStrategistAgentSpec
from .skeptical_referee import SkepticalRefereeAgentSpec
from .synthesis_agent import SynthesisAgentSpec
from .topic_expander import TopicExpanderAgentSpec

__all__ = [
    "PaperAnalyzerAgentSpec",
    "ResearchStrategistAgentSpec",
    "SkepticalRefereeAgentSpec",
    "SynthesisAgentSpec",
    "TopicExpanderAgentSpec",
]

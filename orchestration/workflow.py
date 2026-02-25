"""Sequential research workflow: Agent 1 → 2 → 3 → 4."""

import sys

from observability.arize_logger import setup_observability
from agents.agent1_research import ResearchAgent
from agents.agent2_analyst import AnalystAgent
from agents.agent3_lead import AnalystLead
from agents.agent4_visualization import VisualizationAgent


class ResearchWorkflow:
    """Runs the full buy-side research pipeline in sequence.

    Pipeline:
        Agent 1 — collect raw filings (cache-first)
        Agent 2 — extract compact CompanyFacts + CompanyBrief + QuoteBank per company
                  (one isolated LLM session per company to prevent context overflow)
        Agent 3 — write analyst + sector reports from compact summaries → viz specs
        Agent 4 — generate charts

    Args:
        project: Project name (used for output subdirectory).
        companies: List of dicts with 'name' and 'ticker' keys.
        research_question: The client's primary research question.
    """

    def __init__(self, project: str, companies: list[dict], research_question: str):
        self.project = project
        self.companies = companies
        self.research_question = research_question

    def run(self):
        """Execute the full pipeline."""
        # Start observability (non-fatal if not available)
        observability_session = setup_observability()

        print("\n[Workflow] Phase 1/4 — Filing Collection", file=sys.stderr)
        agent1_summary = ResearchAgent(self.companies, self.project).run()

        print("\n[Workflow] Phase 2/4 — Compact Data Extraction (per-company sessions)", file=sys.stderr)
        agent2_summary = AnalystAgent(self.companies, self.project).run()

        print("\n[Workflow] Phase 3/4 — Investment Analysis", file=sys.stderr)
        agent3_result = AnalystLead(
            self.project, self.companies, self.research_question
        ).run()
        viz_specs = agent3_result.get("viz_specs", [])

        print("\n[Workflow] Phase 4/4 — Chart Generation", file=sys.stderr)
        agent4_summary = VisualizationAgent(self.project, viz_specs).run()

        print("\n[Workflow] All phases complete.", file=sys.stderr)

        return {
            "research_summary": agent1_summary,
            "data_summary": agent2_summary,
            "sector_report": agent3_result.get("sector_report", ""),
            "viz_summary": agent4_summary,
            "viz_specs": viz_specs,
        }

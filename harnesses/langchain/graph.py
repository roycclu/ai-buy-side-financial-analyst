"""LangChain harness — stateful LangGraph workflow for the buy-side pipeline.

State transitions: START → research → extract → analyze → visualize → END

Each node creates a fresh ReAct agent, invokes it with phase-specific context,
and updates the typed WorkflowState for the next node.

Phoenix project: "buy-side-langchain-team"
"""

import operator
import sys
from typing import Annotated, TypedDict

from harnesses.base import BaseHarness


class WorkflowState(TypedDict):
    """Typed state passed between LangGraph nodes."""
    project: str
    companies: list[dict]
    research_question: str
    messages: Annotated[list, operator.add]   # message history accumulates
    filings_done: list[str]                   # tickers with files fetched
    extractions_done: list[str]               # tickers with data extracted
    analyst_reports: dict                     # ticker → report filepath
    sector_report: str                        # sector report filepath
    viz_files: list[str]                      # generated chart filepaths
    current_phase: str                        # "research"|"extract"|"analyze"|"visualize"|"done"


class LangChainWorkflow(BaseHarness):
    """LangGraph stateful workflow for the buy-side research pipeline.

    Requires: pip install langchain langchain-core langchain-anthropic langgraph
    """

    def run(self) -> dict:
        try:
            from langgraph.graph import StateGraph, START, END
        except ImportError as exc:
            raise ImportError(
                "LangGraph not installed. Run: pip install langchain langgraph "
                "langchain-anthropic langchain-openai"
            ) from exc

        from observability.arize_logger import setup_observability
        setup_observability("langchain")

        print("\n[LangChain Harness] Starting stateful LangGraph pipeline...", file=sys.stderr)

        # Build graph
        graph = StateGraph(WorkflowState)
        graph.add_node("research",   self._research_node)
        graph.add_node("extract",    self._extract_node)
        graph.add_node("analyze",    self._analyze_node)
        graph.add_node("visualize",  self._visualize_node)
        graph.add_edge(START,        "research")
        graph.add_edge("research",   "extract")
        graph.add_edge("extract",    "analyze")
        graph.add_edge("analyze",    "visualize")
        graph.add_edge("visualize",  END)

        app = graph.compile()

        initial_state: WorkflowState = {
            "project": self.project,
            "companies": self.companies,
            "research_question": self.question,
            "messages": [],
            "filings_done": [],
            "extractions_done": [],
            "analyst_reports": {},
            "sector_report": "",
            "viz_files": [],
            "current_phase": "research",
        }

        print(f"\n[LangChain Harness] Invoking graph for project: {self.project}", file=sys.stderr)
        final_state = app.invoke(initial_state)

        print("\n[LangChain Harness] All phases complete.", file=sys.stderr)

        return {
            "harness": "langchain",
            "project": self.project,
            "filings_done": final_state.get("filings_done", []),
            "extractions_done": final_state.get("extractions_done", []),
            "analyst_reports": final_state.get("analyst_reports", {}),
            "sector_report": final_state.get("sector_report", ""),
            "viz_files": final_state.get("viz_files", []),
        }

    # ── Node implementations ───────────────────────────────────────────────────

    def _research_node(self, state: WorkflowState) -> dict:
        """Phase 1 — Filing collection via EDGAR."""
        from langchain_core.messages import HumanMessage
        from langgraph.prebuilt import create_react_agent
        from harnesses.llm import get_langchain_llm
        from harnesses.tools.langchain_adapters import create_langchain_tools

        print("\n[LangChain] Phase 1/4 — Filing Collection", file=sys.stderr)

        llm = get_langchain_llm()
        tools = create_langchain_tools(state["project"], "research")
        agent = create_react_agent(llm, tools)

        companies_str = ", ".join(
            f"{c['name']} ({c['ticker']})" for c in state["companies"]
        )
        prompt = (
            f"Collect recent SEC 10-K and 10-Q filings for: {companies_str}.\n"
            f"Project: {state['project']}\n\n"
            "For each company:\n"
            "1. Call check_local_cache — skip downloading if cache is fresh.\n"
            "2. Call lookup_cik to get the CIK.\n"
            "3. Call search_sec_edgar for 10-K and 10-Q filings (months_back=24).\n"
            "4. Call download_filing for any missing documents.\n"
            "Report which filings were cached vs. newly downloaded."
        )

        result = agent.invoke({"messages": [HumanMessage(content=prompt)]})
        tickers = [c["ticker"] for c in state["companies"]]

        return {
            "messages": result.get("messages", []),
            "filings_done": tickers,
            "current_phase": "extract",
        }

    def _extract_node(self, state: WorkflowState) -> dict:
        """Phase 2 — Data extraction for all companies."""
        from langchain_core.messages import HumanMessage
        from langgraph.prebuilt import create_react_agent
        from harnesses.llm import get_langchain_llm
        from harnesses.tools.langchain_adapters import create_langchain_tools

        print("\n[LangChain] Phase 2/4 — Data Extraction", file=sys.stderr)

        llm = get_langchain_llm()
        tools = create_langchain_tools(state["project"], "extract")
        agent = create_react_agent(llm, tools)

        tickers_str = ", ".join(c["ticker"] for c in state["companies"])
        prompt = (
            f"Extract structured financial data for companies: {tickers_str}.\n"
            f"Project: {state['project']}\n\n"
            "For each ticker call run_company_data_extraction. "
            "This generates facts JSON, company brief, and quote bank per company. "
            "The tool automatically skips companies whose data files already exist."
        )

        result = agent.invoke({"messages": [HumanMessage(content=prompt)]})
        tickers = [c["ticker"] for c in state["companies"]]

        return {
            "messages": result.get("messages", []),
            "extractions_done": tickers,
            "current_phase": "analyze",
        }

    def _analyze_node(self, state: WorkflowState) -> dict:
        """Phase 3 — Investment analysis and report writing."""
        from langchain_core.messages import HumanMessage
        from langgraph.prebuilt import create_react_agent
        from harnesses.llm import get_langchain_llm
        from harnesses.tools.langchain_adapters import create_langchain_tools
        import config

        print("\n[LangChain] Phase 3/4 — Investment Analysis", file=sys.stderr)

        llm = get_langchain_llm()
        tools = create_langchain_tools(state["project"], "analyze")
        agent = create_react_agent(llm, tools)

        companies_str = ", ".join(
            f"{c['name']} ({c['ticker']})" for c in state["companies"]
        )
        prompt = (
            f"Write investment analyst reports for: {companies_str}.\n"
            f"Research question: {state['research_question']}\n"
            f"Project: {state['project']}\n\n"
            "For each company:\n"
            "1. Load financial statements with get_financial_statements.\n"
            "2. Load company brief with get_company_brief.\n"
            "3. Load quotes with get_quote_bank.\n"
            "4. Use search_filings_by_query for supporting evidence.\n"
            "5. Compute multiples with compute_multiples.\n"
            "6. Run DCF with run_dcf where FCF data is available.\n"
            "7. Save the analyst report with save_analyst_report.\n\n"
            "Then save a comprehensive sector synthesis report with save_sector_report "
            f"that directly answers: {state['research_question']}"
        )

        result = agent.invoke({"messages": [HumanMessage(content=prompt)]})

        # Build expected output paths
        analyst_reports = {
            c["ticker"]: (
                f"{config.FINANCIAL_ANALYSES_DIR}/{state['project']}/analyst_reports/"
                f"{c['ticker'].lower()}_analyst_report.md"
            )
            for c in state["companies"]
        }
        sector_report_path = (
            f"{config.FINANCIAL_ANALYSES_DIR}/{state['project']}/sector_reports/sector_report.md"
        )

        return {
            "messages": result.get("messages", []),
            "analyst_reports": analyst_reports,
            "sector_report": sector_report_path,
            "current_phase": "visualize",
        }

    def _visualize_node(self, state: WorkflowState) -> dict:
        """Phase 4 — Chart generation."""
        from langchain_core.messages import HumanMessage
        from langgraph.prebuilt import create_react_agent
        from harnesses.llm import get_langchain_llm
        from harnesses.tools.langchain_adapters import create_langchain_tools

        print("\n[LangChain] Phase 4/4 — Chart Generation", file=sys.stderr)

        llm = get_langchain_llm()
        tools = create_langchain_tools(state["project"], "visualize")
        agent = create_react_agent(llm, tools)

        tickers_str = ", ".join(c["ticker"] for c in state["companies"])
        prompt = (
            f"Create financial comparison charts for companies: {tickers_str}.\n"
            f"Project: {state['project']}\n\n"
            "Load financial statements for each company then generate:\n"
            "1. A revenue comparison chart (create_comparison_chart).\n"
            "2. A profitability / margin comparison chart.\n"
            "3. A CapEx or investment trend line chart if time-series data is available.\n"
            f"Focus on metrics relevant to: {state['research_question']}"
        )

        result = agent.invoke({"messages": [HumanMessage(content=prompt)]})

        return {
            "messages": result.get("messages", []),
            "viz_files": [],
            "current_phase": "done",
        }

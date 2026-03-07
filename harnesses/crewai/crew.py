"""CrewAI harness — 4-agent crew running the buy-side research pipeline.

4 CrewAI Agents + 4 Tasks, Process.sequential:
  edgar_researcher → data_extractor → lead_analyst → viz_specialist

Phoenix project: "buy-side-crewai-team"
"""

import sys

from harnesses.base import BaseHarness


class CrewAIWorkflow(BaseHarness):
    """CrewAI-based orchestration for the buy-side research pipeline.

    Requires: pip install crewai crewai-tools
    """

    def run(self) -> dict:
        try:
            from crewai import Agent, Task, Crew, Process
        except ImportError as exc:
            raise ImportError(
                "CrewAI not installed. Run: pip install crewai crewai-tools"
            ) from exc

        from observability.arize_logger import setup_observability
        setup_observability("crewai")

        from harnesses.llm import get_crewai_llm
        from harnesses.tools.crewai_adapters import create_crewai_tools

        print("\n[CrewAI Harness] Starting buy-side research pipeline...", file=sys.stderr)

        llm = get_crewai_llm()
        companies_str = ", ".join(f"{c['name']} ({c['ticker']})" for c in self.companies)
        tickers_str = ", ".join(c["ticker"] for c in self.companies)
        n = len(self.companies)

        # ── Agents ────────────────────────────────────────────────────────────

        edgar_researcher = Agent(
            role="SEC Filing Researcher",
            goal=(
                "Efficiently collect and cache recent SEC filings (10-K and 10-Q) "
                f"for all {n} target companies, using the local cache whenever possible."
            ),
            backstory=(
                "You are an expert at navigating SEC EDGAR to locate and download "
                "annual and quarterly filings. You always check the local cache first "
                "to avoid redundant downloads."
            ),
            tools=create_crewai_tools(self.project, "research"),
            llm=llm,
            verbose=True,
        )

        data_extractor = Agent(
            role="Financial Data Extractor",
            goal=(
                f"Extract compact, structured financial data from raw filings for all {n} companies, "
                "producing facts JSON, company briefs, and quote banks."
            ),
            backstory=(
                "You specialise in parsing SEC filings to extract key financial metrics, "
                "narrative summaries, and management quotes. You use the extraction tool "
                "which runs an isolated high-quality LLM session per company."
            ),
            tools=create_crewai_tools(self.project, "extract"),
            llm=llm,
            verbose=True,
        )

        lead_analyst = Agent(
            role="Lead Investment Analyst",
            goal=(
                f"Produce detailed analyst reports for all {n} companies and a sector synthesis "
                f"report that answers the research question: {self.question}"
            ),
            backstory=(
                "You are a senior buy-side analyst with deep expertise in cross-company comparison, "
                "DCF modelling, and investment thesis development. You base conclusions on "
                "extracted financial data and targeted filing excerpts."
            ),
            tools=create_crewai_tools(self.project, "analyze"),
            llm=llm,
            verbose=True,
        )

        viz_specialist = Agent(
            role="Visualization Specialist",
            goal=(
                "Generate publication-quality charts comparing key financial metrics "
                f"across {tickers_str} to visually support the analyst findings."
            ),
            backstory=(
                "You are a data visualisation expert specialising in financial comparisons. "
                "You load financial data and create clear, informative charts."
            ),
            tools=create_crewai_tools(self.project, "visualize"),
            llm=llm,
            verbose=True,
        )

        # ── Tasks ─────────────────────────────────────────────────────────────

        research_task = Task(
            description=(
                f"Download and cache recent SEC filings for these companies: {companies_str}.\n"
                f"Project: {self.project}\n\n"
                "For each company:\n"
                "1. Call check_local_cache — skip download if cache is fresh.\n"
                "2. Call lookup_cik to get the CIK number.\n"
                "3. Call search_sec_edgar for 10-K filings (months_back=24).\n"
                "4. Call search_sec_edgar for 10-Q filings (months_back=24).\n"
                "5. Call download_filing for each missing filing document.\n"
                "Report which filings were cached vs. newly downloaded."
            ),
            expected_output=(
                f"Filing status report for all {n} companies: "
                "which filings were already cached, which were downloaded, any errors."
            ),
            agent=edgar_researcher,
        )

        extract_task = Task(
            description=(
                f"Extract structured financial data for all companies: {tickers_str}.\n"
                f"Project: {self.project}\n\n"
                "For each ticker, call run_company_data_extraction. "
                "This generates three output files per company:\n"
                "  - {TICKER}_facts_latest.json\n"
                "  - {TICKER}_brief_latest.md\n"
                "  - {TICKER}_quote_bank.json\n"
                "The tool skips companies whose data files already exist."
            ),
            expected_output=(
                f"Extraction complete for all {n} companies. "
                "List each ticker with status (complete / skipped / error) and file paths."
            ),
            agent=data_extractor,
            context=[research_task],
        )

        analyze_task = Task(
            description=(
                f"Write investment analyst reports for all companies and a sector synthesis.\n"
                f"Research question: {self.question}\n"
                f"Companies: {companies_str}\n"
                f"Project: {self.project}\n\n"
                "For each company:\n"
                "1. Load financial statements with get_financial_statements.\n"
                "2. Load company brief with get_company_brief.\n"
                "3. Load quotes with get_quote_bank.\n"
                "4. Use search_filings_by_query to find supporting evidence.\n"
                "5. Run compute_multiples and run_dcf where data permits.\n"
                "6. Save the report with save_analyst_report.\n\n"
                "Then write a comprehensive sector report with save_sector_report "
                f"that directly answers: {self.question}"
            ),
            expected_output=(
                f"Individual analyst reports for all {n} companies plus a sector synthesis report, "
                f"all focused on answering: {self.question}"
            ),
            agent=lead_analyst,
            context=[extract_task],
        )

        viz_task = Task(
            description=(
                f"Create financial comparison charts for the sector analysis.\n"
                f"Companies: {tickers_str}\n"
                f"Project: {self.project}\n\n"
                "1. Load financial statements for each company.\n"
                "2. Create a revenue comparison chart (create_comparison_chart).\n"
                "3. Create an operating margin or profitability comparison.\n"
                "4. Create a CapEx or investment trend line chart if data is available.\n"
                f"Focus on metrics most relevant to: {self.question}"
            ),
            expected_output=(
                "PNG chart files saved to the visualizations directory, "
                "with descriptive filenames. Report each chart's filepath."
            ),
            agent=viz_specialist,
            context=[analyze_task],
        )

        # ── Crew ──────────────────────────────────────────────────────────────

        crew = Crew(
            agents=[edgar_researcher, data_extractor, lead_analyst, viz_specialist],
            tasks=[research_task, extract_task, analyze_task, viz_task],
            process=Process.sequential,
            verbose=True,
        )

        print(f"\n[CrewAI Harness] Kicking off crew for project: {self.project}", file=sys.stderr)

        result = crew.kickoff(inputs={
            "project": self.project,
            "companies": companies_str,
            "tickers": tickers_str,
            "question": self.question,
        })

        print("\n[CrewAI Harness] All phases complete.", file=sys.stderr)

        return {
            "harness": "crewai",
            "project": self.project,
            "result": str(result),
        }

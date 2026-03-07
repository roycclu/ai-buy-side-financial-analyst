"""LlamaIndex harness — RAG-first research pipeline using ReActAgent.

Phase 0: Build a VectorStoreIndex over all local filing documents.
Phase 1: Research agent checks RAG index before hitting EDGAR.
Phase 2: Per-company data extraction (run_company_data_extraction).
Phase 3: Analysis agent writes reports (can query RAG for citations).
Phase 4: Visualization agent generates charts.

Phoenix project: "buy-side-llamaindex-team"
"""

import os
import sys

from harnesses.base import BaseHarness


class LlamaIndexWorkflow(BaseHarness):
    """LlamaIndex RAG-first orchestration for the buy-side research pipeline.

    Requires: pip install llama-index-core llama-index-llms-anthropic (or -openai)
    """

    def run(self) -> dict:
        try:
            from llama_index.core import Settings
            from llama_index.core.agent import ReActAgent
        except ImportError as exc:
            raise ImportError(
                "LlamaIndex not installed. Run: pip install llama-index-core "
                "llama-index-llms-anthropic llama-index-embeddings-openai"
            ) from exc

        from observability.arize_logger import setup_observability
        setup_observability("llamaindex")

        from harnesses.llm import get_llamaindex_llm
        from harnesses.tools.llamaindex_adapters import create_llamaindex_tools

        print("\n[LlamaIndex Harness] Starting RAG-first research pipeline...", file=sys.stderr)

        llm = get_llamaindex_llm()
        Settings.llm = llm

        companies_str = ", ".join(f"{c['name']} ({c['ticker']})" for c in self.companies)
        tickers_str = ", ".join(c["ticker"] for c in self.companies)

        # Phase 0 — Build RAG index over local filings
        print("\n[LlamaIndex] Phase 0/4 — Building RAG index over local filings...", file=sys.stderr)
        rag_engine = self._build_rag_index()

        # Phase 1 — Research (check RAG cache before downloading)
        print("\n[LlamaIndex] Phase 1/4 — Filing Collection", file=sys.stderr)
        research_tools = create_llamaindex_tools(self.project, "research", rag_engine)
        research_agent = ReActAgent.from_tools(
            research_tools, llm=llm, verbose=True, max_iterations=40,
        )
        research_result = research_agent.chat(
            f"Collect recent SEC 10-K and 10-Q filings for these companies: {companies_str}.\n"
            f"Project: {self.project}\n\n"
            "First query the RAG index (query_local_documents) to check which filings are already "
            "available locally. For each company with sufficient local data, skip downloading. "
            "For any missing filings: look up the CIK, search EDGAR, and download. "
            "Always check local cache with check_local_cache before downloading."
        )

        # Phase 2 — Data extraction (one extraction call per company)
        print("\n[LlamaIndex] Phase 2/4 — Data Extraction", file=sys.stderr)
        for company in self.companies:
            ticker = company["ticker"]
            extract_tools = create_llamaindex_tools(self.project, "extract")
            extract_agent = ReActAgent.from_tools(
                extract_tools, llm=llm, verbose=True, max_iterations=10,
            )
            extract_agent.chat(
                f"Extract structured financial data for {ticker} in project '{self.project}'. "
                "Call run_company_data_extraction to generate the facts JSON, company brief, "
                "and quote bank. The tool will skip if data already exists."
            )

        # Phase 3 — Investment analysis
        print("\n[LlamaIndex] Phase 3/4 — Investment Analysis", file=sys.stderr)
        analyze_tools = create_llamaindex_tools(self.project, "analyze", rag_engine)
        analyze_agent = ReActAgent.from_tools(
            analyze_tools, llm=llm, verbose=True, max_iterations=60,
        )
        analyze_result = analyze_agent.chat(
            f"Write investment analyst reports for all companies: {companies_str}.\n"
            f"Research question: {self.question}\n"
            f"Project: {self.project}\n\n"
            "For each company:\n"
            "1. Load financial statements with get_financial_statements.\n"
            "2. Load company brief with get_company_brief.\n"
            "3. Load quotes with get_quote_bank.\n"
            "4. Use search_filings_by_query for targeted evidence.\n"
            "5. Compute multiples and run DCF analysis.\n"
            "6. Save the analyst report.\n\n"
            "Then save a comprehensive sector report that directly answers the research question."
        )

        # Phase 4 — Visualization
        print("\n[LlamaIndex] Phase 4/4 — Chart Generation", file=sys.stderr)
        viz_tools = create_llamaindex_tools(self.project, "visualize")
        viz_agent = ReActAgent.from_tools(
            viz_tools, llm=llm, verbose=True, max_iterations=30,
        )
        viz_result = viz_agent.chat(
            f"Create financial comparison charts for companies: {tickers_str}.\n"
            f"Project: {self.project}\n\n"
            "Load financial data for each company and generate:\n"
            "1. A revenue comparison chart.\n"
            "2. A profitability or margin comparison.\n"
            "3. A CapEx or investment trend chart if data is available.\n"
            f"Focus on metrics relevant to: {self.question}"
        )

        print("\n[LlamaIndex Harness] All phases complete.", file=sys.stderr)

        return {
            "harness": "llamaindex",
            "project": self.project,
            "research_result": str(research_result),
            "analyze_result": str(analyze_result),
            "viz_result": str(viz_result),
        }

    def _build_rag_index(self):
        """Build or load a VectorStoreIndex over local filing documents.

        Returns:
            A QueryEngine, or None if no documents are available or index fails.
        """
        import config
        try:
            from llama_index.core import (
                VectorStoreIndex, SimpleDirectoryReader,
                StorageContext, load_index_from_storage,
            )

            files_dir = os.path.join(config.FINANCIAL_FILES_DIR, self.project)
            index_dir = os.path.join(config.FINANCIAL_DATA_DIR, self.project, "rag_index")

            # Load from persisted index if available
            if os.path.isdir(index_dir) and os.listdir(index_dir):
                print(
                    f"[LlamaIndex] Loading persisted RAG index from {index_dir}",
                    file=sys.stderr,
                )
                storage_context = StorageContext.from_defaults(persist_dir=index_dir)
                index = load_index_from_storage(storage_context)
                return index.as_query_engine()

            # Build from local filing documents
            if os.path.isdir(files_dir) and os.listdir(files_dir):
                print(
                    f"[LlamaIndex] Building RAG index from filings in {files_dir}...",
                    file=sys.stderr,
                )
                reader = SimpleDirectoryReader(
                    input_dir=files_dir,
                    recursive=True,
                    required_exts=[".htm", ".html", ".txt", ".md"],
                )
                documents = reader.load_data()
                print(
                    f"[LlamaIndex] Loaded {len(documents)} documents for indexing.",
                    file=sys.stderr,
                )
                index = VectorStoreIndex.from_documents(documents)
                os.makedirs(index_dir, exist_ok=True)
                index.storage_context.persist(persist_dir=index_dir)
                print(f"[LlamaIndex] RAG index persisted to {index_dir}.", file=sys.stderr)
                return index.as_query_engine()

            # No local documents yet — return None (RAG tool won't be added)
            print(
                f"[LlamaIndex] No local filings found at {files_dir}. "
                "RAG tool will not be available in Phase 1.",
                file=sys.stderr,
            )
            return None

        except Exception as exc:
            print(
                f"[LlamaIndex] RAG index build failed: {exc}. Continuing without RAG.",
                file=sys.stderr,
            )
            return None

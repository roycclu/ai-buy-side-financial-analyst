"""Agent 0 — Project Manager: CLI user journey and orchestration launcher."""

import json
import os
import sys
from datetime import datetime

from config import PROJECTS_FILE, FINANCIAL_ANALYSES_DIR, FINANCIAL_DATA_DIR, FINANCIAL_FILES_DIR
from utils.file_manager import scaffold_project_dirs


_BANNER = """
╔══════════════════════════════════════════════════════════════════════════╗
║          BUY-SIDE FINANCIAL ANALYST AGENT TEAM  —  v1.0                ║
║                                                                          ║
║  5-agent system: Research → Extract → Analyze → Visualize               ║
║  Powered by Claude Opus 4.6 with adaptive thinking                      ║
╚══════════════════════════════════════════════════════════════════════════╝
"""


class ProjectManager:
    """CLI orchestrator that guides the user through project setup."""

    def __init__(self):
        self._ensure_projects_file()

    # ── Public entry point ────────────────────────────────────────────────────

    def start(self):
        """Main CLI entry point."""
        print(_BANNER)
        project_name, companies, question = self._collect_inputs()
        self._run_workflow(project_name, companies, question)

    # ── Input collection ──────────────────────────────────────────────────────

    def _collect_inputs(self) -> tuple[str, list[dict], str]:
        """Walk the user through project setup. Returns (project_name, companies, question)."""
        mode = self._ask_project_mode()

        if mode == "existing":
            project_name, companies, question = self._load_existing_project()
        else:
            project_name, companies, question = self._create_new_project()

        return project_name, companies, question

    def _ask_project_mode(self) -> str:
        projects = self._load_projects()
        if not projects:
            print("No existing projects found. Starting a new project.\n")
            return "new"

        print("What would you like to do?")
        print("  [1] Start a new project")
        print("  [2] Continue an existing project")
        choice = input("\nEnter 1 or 2: ").strip()
        return "existing" if choice == "2" else "new"

    def _create_new_project(self) -> tuple[str, list[dict], str]:
        print("\n── NEW PROJECT SETUP ──────────────────────────────────────────")

        # Project name
        while True:
            name = input("Project name (no spaces, e.g. 'AI_Capex_2025'): ").strip()
            if name:
                break
            print("  Project name cannot be empty.")

        # Companies
        print("\nEnter companies to research.")
        print("Format: CompanyName:TICKER (comma-separated)")
        print("Example: Microsoft Corporation:MSFT, Apple Inc:AAPL\n")
        while True:
            raw = input("Companies: ").strip()
            if not raw:
                print("  At least one company is required.")
                continue
            companies = self._parse_companies(raw)
            if companies:
                break
            print("  Could not parse companies. Use 'Name:TICKER' format.")

        # Research question
        print()
        while True:
            question = input("What is your biggest research question for this project?\n> ").strip()
            if question:
                break
            print("  Research question cannot be empty.")

        # Persist
        self._save_project(name, companies, question)
        scaffold_project_dirs(name)

        print(f"\n Project '{name}' created with {len(companies)} company/companies.")
        return name, companies, question

    def _load_existing_project(self) -> tuple[str, list[dict], str]:
        projects = self._load_projects()
        print("\n── EXISTING PROJECTS ──────────────────────────────────────────")
        for i, p in enumerate(projects, 1):
            tickers = ", ".join(c["ticker"] for c in p["companies"])
            print(f"  [{i}] {p['name']}  ({tickers})  — created {p['created'][:10]}")

        while True:
            try:
                idx = int(input("\nSelect project number: ").strip()) - 1
                if 0 <= idx < len(projects):
                    project = projects[idx]
                    break
                print(f"  Please enter a number between 1 and {len(projects)}.")
            except ValueError:
                print("  Invalid input.")

        print(f"\n Loaded project: {project['name']}")
        print(f" Companies: {', '.join(c['ticker'] for c in project['companies'])}")
        print(f" Research question: {project['question']}")

        # Allow overriding the research question
        override = input("\nUse the same research question? [Y/n]: ").strip().lower()
        if override in ("n", "no"):
            question = input("New research question:\n> ").strip() or project["question"]
        else:
            question = project["question"]

        return project["name"], project["companies"], question

    # ── Workflow launcher ─────────────────────────────────────────────────────

    def _run_workflow(self, project: str, companies: list[dict], question: str):
        from orchestration.workflow import ResearchWorkflow

        print("\n" + "═" * 72)
        print(f" Starting research pipeline for project: {project}")
        print(f" Companies: {', '.join(c['ticker'] for c in companies)}")
        print(f" Question:  {question}")
        print("═" * 72 + "\n")

        workflow = ResearchWorkflow(project, companies, question)
        workflow.run()

        # Print output summary
        print("\n" + "═" * 72)
        print(" RESEARCH COMPLETE — Output locations:")
        print(f"  Raw filings  : {FINANCIAL_FILES_DIR}/")
        for c in companies:
            print(f"                   └─ {c['ticker']}/")
        print(f"  Financial data: {FINANCIAL_DATA_DIR}/")
        print(f"  Analysis      : {FINANCIAL_ANALYSES_DIR}/{project}/")
        print(f"    ├─ analyst_reports/")
        print(f"    ├─ sector_reports/")
        print(f"    └─ visualizations/")
        print("\n  Observability: http://localhost:6006")
        print("═" * 72)

    # ── Project persistence ───────────────────────────────────────────────────

    def _ensure_projects_file(self):
        os.makedirs(os.path.dirname(PROJECTS_FILE), exist_ok=True)
        if not os.path.isfile(PROJECTS_FILE):
            with open(PROJECTS_FILE, "w") as fh:
                json.dump({"projects": []}, fh, indent=2)

    def _load_projects(self) -> list[dict]:
        try:
            with open(PROJECTS_FILE, "r") as fh:
                data = json.load(fh)
            return data.get("projects", [])
        except Exception:
            return []

    def _save_project(self, name: str, companies: list[dict], question: str):
        projects = self._load_projects()
        # Update if already exists
        for p in projects:
            if p["name"] == name:
                p["companies"] = companies
                p["question"] = question
                p["updated"] = datetime.now().isoformat()
                break
        else:
            projects.append({
                "name": name,
                "companies": companies,
                "question": question,
                "created": datetime.now().isoformat(),
            })
        with open(PROJECTS_FILE, "w") as fh:
            json.dump({"projects": projects}, fh, indent=2)

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _parse_companies(raw: str) -> list[dict]:
        """Parse 'Name:TICKER, Name:TICKER' into list of dicts."""
        companies = []
        for part in raw.split(","):
            part = part.strip()
            if ":" in part:
                name, ticker = part.rsplit(":", 1)
                name = name.strip()
                ticker = ticker.strip().upper()
                if name and ticker:
                    companies.append({"name": name, "ticker": ticker})
        return companies

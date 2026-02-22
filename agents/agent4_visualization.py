"""Agent 4 — Visualization Agent: generates charts from Agent 3's viz specs."""

import sys

from config import MAX_AGENT_TURNS, FINANCIAL_DATA_DIR, FINANCIAL_ANALYSES_DIR
from llm import create_adapter
from tools import get_agent4_tool_definitions, get_agent4_functions, execute_tool
from utils.prompts import AGENT4_SYSTEM_PROMPT, build_agent4_message


class VisualizationAgent:
    """Creates charts from visualization specifications produced by Agent 3.

    Args:
        project: Project name.
        viz_specs: List of visualization specification dicts.
    """

    def __init__(self, project: str, viz_specs: list[dict]):
        self.project = project
        self.viz_specs = viz_specs
        self.adapter = create_adapter(thinking=False)

    def run(self) -> str:
        """Execute the visualization agent loop and return a summary."""
        if not self.viz_specs:
            print("[Agent 4 — Visualization] No viz specs provided — skipping.", file=sys.stderr)
            return "No visualizations requested."

        print(
            f"\n[Agent 4 — Visualization] Creating {len(self.viz_specs)} chart(s)...",
            file=sys.stderr,
        )

        user_message = build_agent4_message(
            self.project,
            self.viz_specs,
            FINANCIAL_DATA_DIR,
            FINANCIAL_ANALYSES_DIR,
        )
        messages = [{"role": "user", "content": user_message}]
        tool_definitions = get_agent4_tool_definitions()
        tool_functions = get_agent4_functions()

        for turn in range(MAX_AGENT_TURNS):
            print(f"  [Turn {turn + 1}] Calling LLM...", file=sys.stderr)

            response = self.adapter.chat(messages, AGENT4_SYSTEM_PROMPT, tool_definitions)

            print(f"  Stop reason: {response.stop_reason}", file=sys.stderr)

            if response.stop_reason == "tool_use":
                results = []
                for tc in response.tool_calls:
                    print(f"  Tool: {tc.name}({tc.input})", file=sys.stderr)
                    results.append(execute_tool(tc.name, tc.input, tool_functions))
                messages.append(self.adapter.make_assistant_message(response))
                messages.extend(self.adapter.make_tool_results_messages(response.tool_calls, results))

            elif response.stop_reason == "end_turn":
                print(f"[Agent 4] Done. ({len(response.text)} chars)", file=sys.stderr)
                return response.text

            else:
                print(f"  Unexpected stop reason: {response.stop_reason}", file=sys.stderr)
                return response.text

        print(f"[Agent 4] Warning: reached max turns ({MAX_AGENT_TURNS})", file=sys.stderr)
        return response.text if response else ""

"""Agent 4 — Visualization Agent: generates charts from Agent 3's viz specs."""

import sys

import anthropic

from config import MODEL, MAX_TOKENS, MAX_AGENT_TURNS, FINANCIAL_DATA_DIR, FINANCIAL_ANALYSES_DIR
from tools import get_agent4_tool_definitions, get_agent4_functions, execute_tool
from utils.prompts import AGENT4_SYSTEM_PROMPT, build_agent4_message


def _extract_text(content_blocks) -> str:
    return "\n".join(b.text for b in content_blocks if hasattr(b, "text"))


class VisualizationAgent:
    """Creates charts from visualization specifications produced by Agent 3.

    Args:
        project: Project name.
        viz_specs: List of visualization specification dicts.
    """

    def __init__(self, project: str, viz_specs: list[dict]):
        self.project = project
        self.viz_specs = viz_specs
        self.client = anthropic.Anthropic()

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
            print(f"  [Turn {turn + 1}] Calling Claude...", file=sys.stderr)

            response = self.client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=AGENT4_SYSTEM_PROMPT,
                tools=tool_definitions,
                messages=messages,
            )

            print(f"  Stop reason: {response.stop_reason}", file=sys.stderr)

            if response.stop_reason == "tool_use":
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        print(f"  Tool: {block.name}({block.input})", file=sys.stderr)
                        result = execute_tool(block.name, block.input, tool_functions)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result,
                        })
                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": tool_results})

            elif response.stop_reason == "end_turn":
                summary = _extract_text(response.content)
                print(f"[Agent 4] Done. ({len(summary)} chars)", file=sys.stderr)
                return summary

            else:
                print(f"  Unexpected stop reason: {response.stop_reason}", file=sys.stderr)
                return _extract_text(response.content)

        print(f"[Agent 4] Warning: reached max turns ({MAX_AGENT_TURNS})", file=sys.stderr)
        return _extract_text(response.content) if response else ""

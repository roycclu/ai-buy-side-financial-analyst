"""Agent 3 — Lead Analyst: investment thesis + sector report with adaptive thinking."""

import json
import re
import sys

import anthropic

from config import (
    MODEL, MAX_TOKENS, MAX_AGENT_TURNS,
    FINANCIAL_FILES_DIR, FINANCIAL_DATA_DIR, FINANCIAL_ANALYSES_DIR,
)
from tools import AGENT3_TOOL_DEFINITIONS, AGENT3_FUNCTIONS, execute_tool
from utils.prompts import AGENT3_SYSTEM_PROMPT, build_agent3_message


def _extract_text(content_blocks) -> str:
    return "\n".join(b.text for b in content_blocks if hasattr(b, "text"))


def _parse_viz_specs(text: str) -> list[dict]:
    """Extract the JSON viz_specs block from Agent 3's output."""
    try:
        # Look for a ```json ... ``` block containing "viz_specs"
        match = re.search(r"```json\s*(\{.*?\"viz_specs\".*?\})\s*```", text, re.DOTALL)
        if match:
            data = json.loads(match.group(1))
            return data.get("viz_specs", [])
    except Exception:
        pass

    # Fallback: look for any JSON object with viz_specs key
    try:
        match = re.search(r'\{[^{}]*"viz_specs"\s*:\s*\[.*?\]\s*\}', text, re.DOTALL)
        if match:
            data = json.loads(match.group(0))
            return data.get("viz_specs", [])
    except Exception:
        pass

    return []


class AnalystLead:
    """Writes per-company analyst reports and a sector synthesis report.

    Args:
        project: Project name.
        companies: List of dicts with 'name' and 'ticker' keys.
        research_question: The client's primary research question.
    """

    def __init__(self, project: str, companies: list[dict], research_question: str):
        self.project = project
        self.companies = companies
        self.research_question = research_question
        self.client = anthropic.Anthropic()

    def run(self) -> dict:
        """Execute the lead analyst loop.

        Returns:
            Dict with 'sector_report' text and 'viz_specs' list.
        """
        print("\n[Agent 3 — Lead Analyst] Writing investment analysis...", file=sys.stderr)
        print(f"  Project: {self.project}", file=sys.stderr)
        print(f"  Research question: {self.research_question}", file=sys.stderr)

        user_message = build_agent3_message(
            self.project,
            self.companies,
            self.research_question,
            FINANCIAL_FILES_DIR,
            FINANCIAL_DATA_DIR,
            FINANCIAL_ANALYSES_DIR,
        )
        messages = [{"role": "user", "content": user_message}]

        last_response = None
        for turn in range(MAX_AGENT_TURNS):
            print(f"  [Turn {turn + 1}] Calling Claude...", file=sys.stderr)

            response = self.client.beta.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                thinking={"type": "enabled", "budget_tokens": 8000},
                system=AGENT3_SYSTEM_PROMPT,
                tools=AGENT3_TOOL_DEFINITIONS,
                messages=messages,
                betas=["interleaved-thinking-2025-05-14"],
            )
            last_response = response

            print(f"  Stop reason: {response.stop_reason}", file=sys.stderr)

            if response.stop_reason == "tool_use":
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        print(f"  Tool: {block.name}({block.input})", file=sys.stderr)
                        result = execute_tool(block.name, block.input, AGENT3_FUNCTIONS)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result,
                        })
                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": tool_results})

            elif response.stop_reason == "end_turn":
                final_text = _extract_text(response.content)
                viz_specs = _parse_viz_specs(final_text)
                print(
                    f"[Agent 3] Done. ({len(final_text)} chars, "
                    f"{len(viz_specs)} viz specs)",
                    file=sys.stderr,
                )
                return {"sector_report": final_text, "viz_specs": viz_specs}

            else:
                print(f"  Unexpected stop reason: {response.stop_reason}", file=sys.stderr)
                final_text = _extract_text(response.content)
                return {"sector_report": final_text, "viz_specs": []}

        print(f"[Agent 3] Warning: reached max turns ({MAX_AGENT_TURNS})", file=sys.stderr)
        final_text = _extract_text(last_response.content) if last_response else ""
        return {"sector_report": final_text, "viz_specs": _parse_viz_specs(final_text)}

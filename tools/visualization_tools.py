"""Visualization tools — matplotlib chart generators."""

import os
from typing import Optional

import matplotlib
matplotlib.use("Agg")  # Non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

from config import FINANCIAL_ANALYSES_DIR


def _get_viz_dir(project: str) -> str:
    viz_dir = os.path.join(FINANCIAL_ANALYSES_DIR, project, "visualizations")
    os.makedirs(viz_dir, exist_ok=True)
    return viz_dir


# ── Chart generators ─────────────────────────────────────────────────────────

def create_bar_chart(
    title: str,
    labels: list,
    values: list,
    project: str,
    filename: str,
    colors: Optional[list] = None,
    y_label: str = "",
    x_label: str = "",
) -> dict:
    """Create a simple bar chart and save it as PNG.

    Args:
        title: Chart title.
        labels: X-axis category labels.
        values: Numeric values for each bar.
        project: Project name (determines save directory).
        filename: Output filename (e.g. 'revenue_comparison.png').
        colors: Optional list of bar colors.
        y_label: Optional Y-axis label.
        x_label: Optional X-axis label.

    Returns:
        Dict with 'success' and 'filepath'.
    """
    try:
        fig, ax = plt.subplots(figsize=(max(8, len(labels) * 1.5), 6))
        x = np.arange(len(labels))
        bar_colors = colors or ["#2196F3"] * len(labels)
        bars = ax.bar(x, values, color=bar_colors[:len(labels)], edgecolor="white", linewidth=0.8)

        # Value labels on bars
        for bar, val in zip(bars, values):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() * 1.01,
                f"{val:,.1f}" if isinstance(val, float) else str(val),
                ha="center", va="bottom", fontsize=9,
            )

        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=30, ha="right", fontsize=10)
        ax.set_title(title, fontsize=14, fontweight="bold", pad=12)
        if y_label:
            ax.set_ylabel(y_label, fontsize=10)
        if x_label:
            ax.set_xlabel(x_label, fontsize=10)
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.grid(axis="y", alpha=0.3)
        fig.tight_layout()

        filepath = os.path.join(_get_viz_dir(project), filename)
        fig.savefig(filepath, dpi=150, bbox_inches="tight")
        plt.close(fig)
        return {"success": True, "filepath": filepath, "chart_type": "bar"}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def create_line_chart(
    title: str,
    x_labels: list,
    series_dict: dict,
    project: str,
    filename: str,
    y_label: str = "",
    x_label: str = "",
) -> dict:
    """Create a multi-line chart and save it as PNG.

    Args:
        title: Chart title.
        x_labels: X-axis tick labels (e.g. quarters or years).
        series_dict: {series_name: [values]} mapping for multiple lines.
        project: Project name (determines save directory).
        filename: Output filename.
        y_label: Optional Y-axis label.
        x_label: Optional X-axis label.

    Returns:
        Dict with 'success' and 'filepath'.
    """
    try:
        fig, ax = plt.subplots(figsize=(max(10, len(x_labels) * 1.2), 6))
        colors = ["#2196F3", "#F44336", "#4CAF50", "#FF9800", "#9C27B0", "#00BCD4"]

        for idx, (series_name, values) in enumerate(series_dict.items()):
            color = colors[idx % len(colors)]
            ax.plot(
                x_labels, values,
                marker="o", label=series_name,
                color=color, linewidth=2, markersize=6,
            )

        ax.set_title(title, fontsize=14, fontweight="bold", pad=12)
        ax.legend(fontsize=9, loc="best")
        if y_label:
            ax.set_ylabel(y_label, fontsize=10)
        if x_label:
            ax.set_xlabel(x_label, fontsize=10)
        ax.tick_params(axis="x", rotation=30)
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.grid(alpha=0.3)
        fig.tight_layout()

        filepath = os.path.join(_get_viz_dir(project), filename)
        fig.savefig(filepath, dpi=150, bbox_inches="tight")
        plt.close(fig)
        return {"success": True, "filepath": filepath, "chart_type": "line"}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def create_comparison_chart(
    title: str,
    companies: list,
    metric_name: str,
    values_dict: dict,
    project: str,
    filename: str,
    y_label: str = "",
) -> dict:
    """Create a grouped bar chart comparing a metric across companies and periods.

    Args:
        title: Chart title.
        companies: List of company names (one group per company).
        metric_name: Name of the metric being compared.
        values_dict: {company: [values_per_period]} or {company: single_value}.
        project: Project name (determines save directory).
        filename: Output filename.
        y_label: Optional Y-axis label.

    Returns:
        Dict with 'success' and 'filepath'.
    """
    try:
        fig, ax = plt.subplots(figsize=(max(10, len(companies) * 2), 6))
        colors = ["#2196F3", "#F44336", "#4CAF50", "#FF9800", "#9C27B0"]

        # Determine if values are single numbers or lists
        first_val = next(iter(values_dict.values()), None)
        if isinstance(first_val, (int, float)):
            # Simple single-value per company bar chart
            vals = [values_dict.get(c, 0) for c in companies]
            bar_colors = [colors[i % len(colors)] for i in range(len(companies))]
            bars = ax.bar(companies, vals, color=bar_colors, edgecolor="white", linewidth=0.8)
            for bar, val in zip(bars, vals):
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_height() * 1.01,
                    f"{val:,.1f}" if isinstance(val, float) else str(val),
                    ha="center", va="bottom", fontsize=9,
                )
        else:
            # Grouped bars — one group per period
            periods = list(first_val) if hasattr(first_val, "__len__") else [metric_name]
            n_groups = len(companies)
            n_bars = len(periods)
            x = np.arange(n_groups)
            width = 0.8 / n_bars

            for i, period in enumerate(periods):
                period_vals = [
                    values_dict.get(c, [0] * n_bars)[i] if isinstance(values_dict.get(c), list)
                    else values_dict.get(c, 0)
                    for c in companies
                ]
                offset = (i - n_bars / 2 + 0.5) * width
                rects = ax.bar(x + offset, period_vals, width * 0.9,
                               label=str(period), color=colors[i % len(colors)],
                               edgecolor="white", linewidth=0.5)

            ax.set_xticks(x)
            ax.set_xticklabels(companies, rotation=15, ha="right")
            ax.legend(fontsize=9)

        ax.set_title(title, fontsize=14, fontweight="bold", pad=12)
        if y_label:
            ax.set_ylabel(y_label, fontsize=10)
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.grid(axis="y", alpha=0.3)
        fig.tight_layout()

        filepath = os.path.join(_get_viz_dir(project), filename)
        fig.savefig(filepath, dpi=150, bbox_inches="tight")
        plt.close(fig)
        return {"success": True, "filepath": filepath, "chart_type": "comparison_bar"}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


# ── Tool Definitions ──────────────────────────────────────────────────────────

CREATE_BAR_CHART_TOOL = {
    "name": "create_bar_chart",
    "description": (
        "Create a bar chart and save it as a PNG image to the project visualizations folder. "
        "Use for single-category comparisons (e.g. revenue by company)."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Chart title."},
            "labels": {"type": "array", "items": {"type": "string"}, "description": "X-axis category labels."},
            "values": {"type": "array", "items": {"type": "number"}, "description": "Numeric values for each bar."},
            "project": {"type": "string", "description": "Project name."},
            "filename": {"type": "string", "description": "Output PNG filename (e.g. 'revenue.png')."},
            "colors": {"type": "array", "items": {"type": "string"}, "description": "Optional list of hex colors."},
            "y_label": {"type": "string", "description": "Optional Y-axis label."},
            "x_label": {"type": "string", "description": "Optional X-axis label."},
        },
        "required": ["title", "labels", "values", "project", "filename"],
    },
}

CREATE_LINE_CHART_TOOL = {
    "name": "create_line_chart",
    "description": (
        "Create a multi-line time-series chart and save as PNG. "
        "Use for trends over time (e.g. quarterly revenue for multiple companies)."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Chart title."},
            "x_labels": {"type": "array", "items": {"type": "string"}, "description": "X-axis tick labels."},
            "series_dict": {
                "type": "object",
                "description": "Mapping of series name to list of numeric values. E.g. {\"MSFT\": [100, 110, 120]}.",
                "additionalProperties": {"type": "array", "items": {"type": "number"}},
            },
            "project": {"type": "string", "description": "Project name."},
            "filename": {"type": "string", "description": "Output PNG filename."},
            "y_label": {"type": "string", "description": "Optional Y-axis label."},
            "x_label": {"type": "string", "description": "Optional X-axis label."},
        },
        "required": ["title", "x_labels", "series_dict", "project", "filename"],
    },
}

CREATE_COMPARISON_CHART_TOOL = {
    "name": "create_comparison_chart",
    "description": (
        "Create a grouped bar chart comparing a metric across companies. "
        "Use for cross-company comparisons of a single KPI."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Chart title."},
            "companies": {"type": "array", "items": {"type": "string"}, "description": "List of company names."},
            "metric_name": {"type": "string", "description": "Name of the metric being compared."},
            "values_dict": {
                "type": "object",
                "description": "Mapping of company name to a single value or list of values.",
            },
            "project": {"type": "string", "description": "Project name."},
            "filename": {"type": "string", "description": "Output PNG filename."},
            "y_label": {"type": "string", "description": "Optional Y-axis label."},
        },
        "required": ["title", "companies", "metric_name", "values_dict", "project", "filename"],
    },
}

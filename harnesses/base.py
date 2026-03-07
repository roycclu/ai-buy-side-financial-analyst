"""Abstract base class for all harness implementations."""

from abc import ABC, abstractmethod


class BaseHarness(ABC):
    """Common interface that every orchestration harness must implement.

    Args:
        project: Project name (maps to output subdirectories).
        companies: List of dicts with 'name' and 'ticker' keys.
        question: The client's primary research question.
    """

    def __init__(self, project: str, companies: list[dict], question: str):
        self.project = project
        self.companies = companies
        self.question = question

    @abstractmethod
    def run(self) -> dict:
        """Execute the full research pipeline.

        Returns:
            A dict summarising the run result (harness-specific keys).
        """
        ...

"""Workflow factory — returns the appropriate workflow for the configured HARNESS."""


def create_workflow(project: str, companies: list, question: str):
    """Factory that returns the appropriate workflow for the configured HARNESS.

    Reads HARNESS from config and dispatches to the matching harness class.
    Falls back to NativeWorkflow if HARNESS is unrecognized.

    Args:
        project: Project name (used for output subdirectory).
        companies: List of dicts with 'name' and 'ticker' keys.
        question: The client's primary research question.

    Returns:
        An object with a .run() method.
    """
    from config import HARNESS

    if HARNESS == "crewai":
        from harnesses.crewai.crew import CrewAIWorkflow
        return CrewAIWorkflow(project, companies, question)
    elif HARNESS == "llamaindex":
        from harnesses.llamaindex.pipeline import LlamaIndexWorkflow
        return LlamaIndexWorkflow(project, companies, question)
    elif HARNESS == "langchain":
        from harnesses.langchain.graph import LangChainWorkflow
        return LangChainWorkflow(project, companies, question)
    from harnesses.native.pipeline import NativeWorkflow
    return NativeWorkflow(project, companies, question)

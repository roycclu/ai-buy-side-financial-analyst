"""Harness package — optional orchestration frameworks for the buy-side pipeline.

Supported harnesses (set HARNESS= in .env):
  native     → built-in 5-agent pipeline (default)
  crewai     → CrewAI multi-agent crew
  llamaindex → LlamaIndex RAG-first pipeline
  langchain  → LangChain / LangGraph stateful workflow
"""

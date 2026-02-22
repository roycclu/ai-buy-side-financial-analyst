"""LLM provider abstraction — import create_adapter to get a configured adapter."""

from .factory import create_adapter

__all__ = ["create_adapter"]

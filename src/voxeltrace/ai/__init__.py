"""Local AI reasoning layer. Talks only to a local OpenAI-compatible endpoint."""

from voxeltrace.ai.client import LocalAIClient, LocalAIUnavailableError

__all__ = ["LocalAIClient", "LocalAIUnavailableError"]

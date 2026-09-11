"""Base agent package — contracts live in agent.py."""

from backend.agents.base.agent import (
    MAX_PROMPT_CHARS,
    AgentError,
    AgentModelUnavailable,
    AgentRegistry,
    AgentResult,
    AgentSpec,
    BaseAgent,
    logger,
)

__all__ = [
    "AgentError",
    "AgentModelUnavailable",
    "AgentRegistry",
    "AgentResult",
    "AgentSpec",
    "BaseAgent",
    "MAX_PROMPT_CHARS",
    "logger",
]

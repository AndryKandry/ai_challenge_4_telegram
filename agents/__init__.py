"""
Модуль agents для системы subagents.

Предоставляет базовые классы и оркестратор для координации работы
специализированных агентов (DocsAgent, GitAgent, HelpCommandAgent).
"""

from .base_agent import BaseAgent
from .orchestrator import AgentOrchestrator
from .docs_agent import DocsAgent
from .git_agent import GitAgent
from .help_command_agent import HelpCommandAgent

__all__ = [
    "BaseAgent",
    "AgentOrchestrator",
    "DocsAgent",
    "GitAgent",
    "HelpCommandAgent",
]

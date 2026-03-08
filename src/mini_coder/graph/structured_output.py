"""Structured output schemas for multi-agent system.

This module defines JSON schemas for structured agent outputs,
enabling reliable parsing and downstream processing.

Each agent produces structured JSON output instead of free-form text.
"""

from typing import List, Optional, Dict, Any, Literal
from dataclasses import dataclass, field, asdict
from enum import Enum
import json


# ==================== Coder Output ====================

@dataclass
class CodeChunk:
    """A single code modification/creation."""
    path: str  # File path (relative to project root)
    action: Literal["create", "modify", "delete"]
    content: Optional[str] = None  # Full file content for create, diff for modify
    description: str = ""  # Brief description of changes

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CoderOutput:
    """Structured output from Coder agent."""
    code_chunks: List[CodeChunk]
    summary: str  # Brief summary of implementation
    incomplete_items: List[str] = field(default_factory=list)
    memory_notes: Optional[str] = None  # Key learnings to remember

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code_chunks": [c.to_dict() for c in self.code_chunks],
            "summary": self.summary,
            "incomplete_items": self.incomplete_items,
            "memory_notes": self.memory_notes,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CoderOutput":
        chunks = [CodeChunk(**c) for c in data.get("code_chunks", [])]
        return cls(
            code_chunks=chunks,
            summary=data.get("summary", ""),
            incomplete_items=data.get("incomplete_items", []),
            memory_notes=data.get("memory_notes"),
        )


# ==================== Planner Output ====================

class TaskPriority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class TodoTask:
    """A single task in the implementation plan."""
    id: str  # e.g., "1.1", "2.3"
    title: str
    description: str
    is_test: bool = False  # TDD: test tasks come first
    priority: TaskPriority = TaskPriority.MEDIUM
    dependencies: List[str] = field(default_factory=list)  # IDs of dependent tasks
    estimated_complexity: str = "medium"  # low, medium, high

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["priority"] = self.priority.value
        return d


@dataclass
class PlannerOutput:
    """Structured output from Planner agent."""
    title: str  # Plan title
    overview: str  # Brief overview
    phases: Dict[str, List[TodoTask]]  # Phase name -> tasks
    tech_decisions: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "overview": self.overview,
            "phases": {
                phase: [t.to_dict() for t in tasks]
                for phase, tasks in self.phases.items()
            },
            "tech_decisions": self.tech_decisions,
            "risks": self.risks,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)

    def get_all_tasks(self) -> List[TodoTask]:
        """Flatten all tasks into a single list."""
        result = []
        for tasks in self.phases.values():
            result.extend(tasks)
        return result


# ==================== Reviewer Output ====================

class ReviewDecision(str, Enum):
    PASS = "pass"
    REJECT = "reject"


@dataclass
class ReviewIssue:
    """A single issue found during review."""
    file: str
    line: Optional[int]
    category: Literal["architecture", "quality", "style", "security"]
    message: str
    suggestion: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ReviewerOutput:
    """Structured output from Reviewer agent."""
    decision: ReviewDecision
    issues: List[ReviewIssue] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision": self.decision.value,
            "issues": [i.to_dict() for i in self.issues],
            "summary": self.summary,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)


# ==================== Explorer Output ====================

@dataclass
class FileFinding:
    """A file discovered during exploration."""
    path: str
    relevance: str  # Why this file is relevant
    key_functions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ExplorerOutput:
    """Structured output from Explorer agent."""
    findings: List[FileFinding]
    summary: str
    suggested_next_steps: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "findings": [f.to_dict() for f in self.findings],
            "summary": self.summary,
            "suggested_next_steps": self.suggested_next_steps,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)


# ==================== Bash Output ====================

@dataclass
class TestResult:
    """Result of a test run."""
    passed: int
    failed: int
    skipped: int
    coverage_percent: Optional[float] = None
    details: List[str] = field(default_factory=list)


@dataclass
class BashOutput:
    """Structured output from Bash agent."""
    tests: Optional[TestResult] = None
    type_check_passed: Optional[bool] = None
    lint_passed: Optional[bool] = None
    commands_run: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "commands_run": self.commands_run,
            "errors": self.errors,
        }
        if self.tests:
            d["tests"] = self.tests.to_dict() if hasattr(self.tests, 'to_dict') else asdict(self.tests)
        if self.type_check_passed is not None:
            d["type_check_passed"] = self.type_check_passed
        if self.lint_passed is not None:
            d["lint_passed"] = self.lint_passed
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)


# ==================== Router Output ====================

class RouterDestination(str, Enum):
    """Routing destinations."""
    EXPLORER = "explorer"
    PLANNER = "planner"
    CODER = "coder"
    REVIEWER = "reviewer"
    BASH = "bash"
    GENERAL_PURPOSE = "general_purpose"


@dataclass
class RouterOutput:
    """Structured output from Router agent.

    Determines which agent should handle the user request.
    """
    destination: RouterDestination
    reasoning: str  # Why this agent was chosen
    bash_mode: Optional[str] = None  # Only for BASH destination: "quality_report", "single_command", "confirm_save"
    command: Optional[str] = None  # Only for single_command mode
    confidence: float = 1.0  # 0.0 - 1.0

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "destination": self.destination.value,
            "reasoning": self.reasoning,
            "confidence": self.confidence,
        }
        if self.bash_mode:
            d["bash_mode"] = self.bash_mode
        if self.command:
            d["command"] = self.command
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)


# ==================== Exports ====================

__all__ = [
    # Coder
    "CodeChunk",
    "CoderOutput",
    # Planner
    "TodoTask",
    "TaskPriority",
    "PlannerOutput",
    # Reviewer
    "ReviewDecision",
    "ReviewIssue",
    "ReviewerOutput",
    # Explorer
    "FileFinding",
    "ExplorerOutput",
    # Bash
    "TestResult",
    "BashOutput",
    # Router
    "RouterDestination",
    "RouterOutput",
]
"""LangGraph structured output integration.

This module provides integration between LangGraph's with_structured_output
and our structured output schemas.

Usage:
    from mini_coder.graph.output_parser import create_structured_coder_agent

    agent = create_structured_coder_agent(llm)
    result = await agent.ainvoke({"messages": [...]})
    # result is now a CoderOutput object
"""

from typing import Any, Dict, List, Literal, Optional, Type, Union
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

from .structured_output import (
    CodeChunk,
    CoderOutput,
    TodoTask,
    TaskPriority,
    PlannerOutput,
    ReviewDecision,
    ReviewIssue,
    ReviewerOutput,
    FileFinding,
    ExplorerOutput,
    TestResult,
    BashOutput,
    RouterDestination,
    RouterOutput,
)
from .few_shot_prompts import (
    CODER_FEW_SHOT_PROMPT,
    PLANNER_FEW_SHOT_PROMPT,
    REVIEWER_FEW_SHOT_PROMPT,
    EXPLORER_FEW_SHOT_PROMPT,
    BASH_FEW_SHOT_PROMPT,
    ROUTER_FEW_SHOT_PROMPT,
)


# ==================== Pydantic Models for Structured Output ====================

class CodeChunkModel(BaseModel):
    """Pydantic model for CodeChunk."""
    path: str
    action: Literal["create", "modify", "delete"]
    content: Optional[str] = None
    description: str = ""


class CoderOutputModel(BaseModel):
    """Pydantic model for CoderOutput."""
    code_chunks: List[CodeChunkModel]
    summary: str
    incomplete_items: List[str] = []
    memory_notes: Optional[str] = None


class TodoTaskModel(BaseModel):
    """Pydantic model for TodoTask."""
    id: str
    title: str
    description: str
    is_test: bool = False
    priority: str = "medium"
    dependencies: List[str] = []
    estimated_complexity: str = "medium"


class PlannerOutputModel(BaseModel):
    """Pydantic model for PlannerOutput."""
    title: str
    overview: str
    phases: Dict[str, List[TodoTaskModel]]
    tech_decisions: List[str] = []
    risks: List[str] = []


class ReviewIssueModel(BaseModel):
    """Pydantic model for ReviewIssue."""
    file: str
    line: Optional[int] = None
    category: str
    message: str
    suggestion: str


class ReviewerOutputModel(BaseModel):
    """Pydantic model for ReviewerOutput."""
    decision: str  # "pass" or "reject"
    issues: List[ReviewIssueModel] = []
    summary: str = ""


class FileFindingModel(BaseModel):
    """Pydantic model for FileFinding."""
    path: str
    relevance: str
    key_functions: List[str] = []


class ExplorerOutputModel(BaseModel):
    """Pydantic model for ExplorerOutput."""
    findings: List[FileFindingModel]
    summary: str
    suggested_next_steps: List[str] = []


class TestResultModel(BaseModel):
    """Pydantic model for TestResult."""
    passed: int
    failed: int
    skipped: int
    coverage_percent: Optional[float] = None
    details: List[str] = []


class BashOutputModel(BaseModel):
    """Pydantic model for BashOutput."""
    tests: Optional[TestResultModel] = None
    type_check_passed: Optional[bool] = None
    lint_passed: Optional[bool] = None
    commands_run: List[str] = []
    errors: List[str] = []


class RouterOutputModel(BaseModel):
    """Pydantic model for RouterOutput."""
    destination: str  # "explorer", "planner", "coder", "reviewer", "bash", "general_purpose"
    reasoning: str
    bash_mode: Optional[str] = None  # "quality_report", "single_command", "confirm_save"
    command: Optional[str] = None
    confidence: float = 1.0


# ==================== Conversion Functions ====================

def model_to_coder_output(model: CoderOutputModel) -> CoderOutput:
    """Convert Pydantic model to dataclass."""
    chunks = [
        CodeChunk(
            path=c.path,
            action=c.action,
            content=c.content,
            description=c.description,
        )
        for c in model.code_chunks
    ]
    return CoderOutput(
        code_chunks=chunks,
        summary=model.summary,
        incomplete_items=model.incomplete_items,
        memory_notes=model.memory_notes,
    )


def model_to_planner_output(model: PlannerOutputModel) -> PlannerOutput:
    """Convert Pydantic model to dataclass."""
    phases = {}
    for phase_name, tasks in model.phases.items():
        phases[phase_name] = [
            TodoTask(
                id=t.id,
                title=t.title,
                description=t.description,
                is_test=t.is_test,
                priority=TaskPriority(t.priority),
                dependencies=t.dependencies,
                estimated_complexity=t.estimated_complexity,
            )
            for t in tasks
        ]
    return PlannerOutput(
        title=model.title,
        overview=model.overview,
        phases=phases,
        tech_decisions=model.tech_decisions,
        risks=model.risks,
    )


def model_to_reviewer_output(model: ReviewerOutputModel) -> ReviewerOutput:
    """Convert Pydantic model to dataclass."""
    issues = [
        ReviewIssue(
            file=i.file,
            line=i.line,
            category=i.category,  # type: ignore
            message=i.message,
            suggestion=i.suggestion,
        )
        for i in model.issues
    ]
    return ReviewerOutput(
        decision=ReviewDecision(model.decision),
        issues=issues,
        summary=model.summary,
    )


def model_to_explorer_output(model: ExplorerOutputModel) -> ExplorerOutput:
    """Convert Pydantic model to dataclass."""
    findings = [
        FileFinding(
            path=f.path,
            relevance=f.relevance,
            key_functions=f.key_functions,
        )
        for f in model.findings
    ]
    return ExplorerOutput(
        findings=findings,
        summary=model.summary,
        suggested_next_steps=model.suggested_next_steps,
    )


def model_to_bash_output(model: BashOutputModel) -> BashOutput:
    """Convert Pydantic model to dataclass."""
    tests = None
    if model.tests:
        tests = TestResult(
            passed=model.tests.passed,
            failed=model.tests.failed,
            skipped=model.tests.skipped,
            coverage_percent=model.tests.coverage_percent,
            details=model.tests.details,
        )
    return BashOutput(
        tests=tests,
        type_check_passed=model.type_check_passed,
        lint_passed=model.lint_passed,
        commands_run=model.commands_run,
        errors=model.errors,
    )


def model_to_router_output(model: RouterOutputModel) -> RouterOutput:
    """Convert Pydantic model to dataclass."""
    return RouterOutput(
        destination=RouterDestination(model.destination),
        reasoning=model.reasoning,
        bash_mode=model.bash_mode,
        command=model.command,
        confidence=model.confidence,
    )


# ==================== Agent Factory Functions ====================

def create_structured_llm(
    llm: BaseChatModel,
    output_model: Type[BaseModel],
    system_prompt: str,
) -> Any:
    """Create an LLM with structured output.

    Uses LangChain's with_structured_output() method.

    Args:
        llm: Base chat model
        output_model: Pydantic model for output schema
        system_prompt: System prompt to use

    Returns:
        LLM chain that produces structured output
    """
    structured_llm = llm.with_structured_output(output_model)

    # Create a chain that prepends the system prompt
    def invoke_with_prompt(messages: List[Any]) -> Any:
        full_messages = [SystemMessage(content=system_prompt)] + messages
        return structured_llm.invoke(full_messages)

    async def ainvoke_with_prompt(messages: List[Any]) -> Any:
        full_messages = [SystemMessage(content=system_prompt)] + messages
        return await structured_llm.ainvoke(full_messages)

    # Return an object with invoke/ainvoke methods
    class StructuredChain:
        def invoke(self, messages: List[Any]) -> Any:
            return invoke_with_prompt(messages)

        async def ainvoke(self, messages: List[Any]) -> Any:
            return await ainvoke_with_prompt(messages)

    return StructuredChain()


def create_coder_agent(llm: BaseChatModel) -> Any:
    """Create a Coder agent with structured output.

    Args:
        llm: Base chat model

    Returns:
        Structured LLM that produces CoderOutputModel
    """
    return create_structured_llm(llm, CoderOutputModel, CODER_FEW_SHOT_PROMPT)


def create_planner_agent(llm: BaseChatModel) -> Any:
    """Create a Planner agent with structured output.

    Args:
        llm: Base chat model

    Returns:
        Structured LLM that produces PlannerOutputModel
    """
    return create_structured_llm(llm, PlannerOutputModel, PLANNER_FEW_SHOT_PROMPT)


def create_reviewer_agent(llm: BaseChatModel) -> Any:
    """Create a Reviewer agent with structured output.

    Args:
        llm: Base chat model

    Returns:
        Structured LLM that produces ReviewerOutputModel
    """
    return create_structured_llm(llm, ReviewerOutputModel, REVIEWER_FEW_SHOT_PROMPT)


def create_explorer_agent(llm: BaseChatModel) -> Any:
    """Create an Explorer agent with structured output.

    Args:
        llm: Base chat model

    Returns:
        Structured LLM that produces ExplorerOutputModel
    """
    return create_structured_llm(llm, ExplorerOutputModel, EXPLORER_FEW_SHOT_PROMPT)


def create_bash_agent(llm: BaseChatModel) -> Any:
    """Create a Bash agent with structured output.

    Args:
        llm: Base chat model

    Returns:
        Structured LLM that produces BashOutputModel
    """
    return create_structured_llm(llm, BashOutputModel, BASH_FEW_SHOT_PROMPT)


def create_router_agent(llm: BaseChatModel) -> Any:
    """Create a Router agent with structured output.

    Args:
        llm: Base chat model

    Returns:
        Structured LLM that produces RouterOutputModel
    """
    return create_structured_llm(llm, RouterOutputModel, ROUTER_FEW_SHOT_PROMPT)


# ==================== Convenience Functions ====================

async def ainvoke_coder(
    llm: BaseChatModel,
    user_request: str,
    context: Optional[Dict[str, Any]] = None,
) -> CoderOutput:
    """Invoke Coder agent and return structured output.

    Args:
        llm: Base chat model
        user_request: The coding task
        context: Optional context (plan, exploration results, etc.)

    Returns:
        CoderOutput dataclass
    """
    agent = create_coder_agent(llm)

    context_str = ""
    if context:
        if context.get("plan"):
            context_str += f"\n\nImplementation Plan:\n{context['plan']}"
        if context.get("exploration"):
            context_str += f"\n\nExploration Results:\n{context['exploration']}"

    message_content = f"{user_request}{context_str}"

    model = await agent.ainvoke([HumanMessage(content=message_content)])
    return model_to_coder_output(model)


async def ainvoke_planner(
    llm: BaseChatModel,
    user_request: str,
    context: Optional[Dict[str, Any]] = None,
) -> PlannerOutput:
    """Invoke Planner agent and return structured output.

    Args:
        llm: Base chat model
        user_request: The feature request
        context: Optional context (exploration results, etc.)

    Returns:
        PlannerOutput dataclass
    """
    agent = create_planner_agent(llm)

    context_str = ""
    if context and context.get("exploration"):
        context_str = f"\n\nCodebase Context:\n{context['exploration']}"

    message_content = f"Plan the following feature:\n{user_request}{context_str}"

    model = await agent.ainvoke([HumanMessage(content=message_content)])
    return model_to_planner_output(model)


async def ainvoke_reviewer(
    llm: BaseChatModel,
    code_chunks: List[Dict[str, Any]],
    plan: Optional[str] = None,
) -> ReviewerOutput:
    """Invoke Reviewer agent and return structured output.

    Args:
        llm: Base chat model
        code_chunks: List of code changes to review
        plan: Optional implementation plan for architecture check

    Returns:
        ReviewerOutput dataclass
    """
    agent = create_reviewer_agent(llm)

    code_str = "\n\n".join(
        f"File: {c.get('path', 'unknown')}\n{c.get('content', '')}"
        for c in code_chunks
    )

    message_content = f"Review the following code changes:\n\n{code_str}"
    if plan:
        message_content += f"\n\nImplementation Plan:\n{plan}"

    model = await agent.ainvoke([HumanMessage(content=message_content)])
    return model_to_reviewer_output(model)


async def ainvoke_explorer(
    llm: BaseChatModel,
    query: str,
    depth: str = "medium",
) -> ExplorerOutput:
    """Invoke Explorer agent and return structured output.

    Args:
        llm: Base chat model
        query: What to search for
        depth: Search depth (quick/medium/thorough)

    Returns:
        ExplorerOutput dataclass
    """
    agent = create_explorer_agent(llm)

    message_content = f"Find the following in the codebase (depth: {depth}):\n{query}"

    model = await agent.ainvoke([HumanMessage(content=message_content)])
    return model_to_explorer_output(model)


async def ainvoke_router(
    llm: BaseChatModel,
    user_request: str,
) -> RouterOutput:
    """Invoke Router agent and return structured output.

    Args:
        llm: Base chat model
        user_request: The user's request to route

    Returns:
        RouterOutput dataclass with destination and bash_mode
    """
    agent = create_router_agent(llm)

    model = await agent.ainvoke([HumanMessage(content=user_request)])
    return model_to_router_output(model)


# ==================== Exports ====================

__all__ = [
    # Pydantic models
    "CodeChunkModel",
    "CoderOutputModel",
    "TodoTaskModel",
    "PlannerOutputModel",
    "ReviewIssueModel",
    "ReviewerOutputModel",
    "FileFindingModel",
    "ExplorerOutputModel",
    "TestResultModel",
    "BashOutputModel",
    "RouterOutputModel",
    # Conversion functions
    "model_to_coder_output",
    "model_to_planner_output",
    "model_to_reviewer_output",
    "model_to_explorer_output",
    "model_to_bash_output",
    "model_to_router_output",
    # Agent factory functions
    "create_structured_llm",
    "create_coder_agent",
    "create_planner_agent",
    "create_reviewer_agent",
    "create_explorer_agent",
    "create_bash_agent",
    "create_router_agent",
    # Convenience functions
    "ainvoke_coder",
    "ainvoke_planner",
    "ainvoke_reviewer",
    "ainvoke_explorer",
    "ainvoke_router",
]
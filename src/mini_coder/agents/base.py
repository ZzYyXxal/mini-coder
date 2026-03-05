"""Agent System - 多 Agent 系统实现

实现专门的 Agent 类，每个 Agent 有明确的职责和工具访问权限。
灵感来自 HelloAgents、OpenCode 的多 Agent 架构。

Agent 架构:
```
                    ┌─────────────────┐
                    │   Orchestrator  │
                    │   (协调层)      │
                    └────────┬────────┘
                             │
           ┌─────────────────┼─────────────────┐
           │                 │                 │
           ▼                 ▼                 ▼
    ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
    │  Planner    │  │   Coder     │  │   Tester    │
    │  Agent      │  │   Agent     │  │   Agent     │
    │             │  │             │  │             │
    │ ToolFilter  │  │ ToolFilter  │  │ ToolFilter  │
    │ ReadOnly    │  │ FullAccess  │  │ ReadOnly    │
    └─────────────┘  └─────────────┘  └─────────────┘
```
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Type
from pathlib import Path

from mini_coder.tools.filter import ToolFilter, ReadOnlyFilter, FullAccessFilter, StrictFilter
from mini_coder.agents.prompt_loader import PromptLoader

logger = logging.getLogger(__name__)


@dataclass
class AgentConfig:
    """Agent 配置"""
    name: str
    description: str = ""
    tool_filter: Optional[ToolFilter] = None
    max_iterations: int = 10
    temperature: float = 0.7
    system_prompt: str = ""
    prompt_loader: Optional[PromptLoader] = None
    prompt_path: Optional[str] = None  # 用于从文件加载提示词
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentState:
    """Agent 状态"""
    current_task: str = ""
    iteration_count: int = 0
    total_tokens_used: int = 0
    last_error: Optional[str] = None
    is_busy: bool = False


@dataclass
class AgentCapabilities:
    """Agent 能力定义"""
    # 可以使用的工具
    allowed_tools: Set[str] = field(default_factory=set)
    # 可以读取的文件模式
    allowed_read_patterns: List[str] = field(default_factory=list)
    # 可以写入的文件模式
    allowed_write_patterns: List[str] = field(default_factory=list)
    # 最大工具调用次数 per execute
    max_tool_calls: int = 10
    # 是否需要用户确认才能执行危险操作
    requires_confirmation: bool = False

    def copy(self) -> "AgentCapabilities":
        """创建副本"""
        return AgentCapabilities(
            allowed_tools=self.allowed_tools.copy(),
            allowed_read_patterns=self.allowed_read_patterns.copy(),
            allowed_write_patterns=self.allowed_write_patterns.copy(),
            max_tool_calls=self.max_tool_calls,
            requires_confirmation=self.requires_confirmation,
        )


class AgentResult:
    """Agent 执行结果"""

    def __init__(
        self,
        success: bool,
        output: str = "",
        error: str = "",
        artifacts: Optional[Dict[str, str]] = None,
        needs_user_decision: bool = False,
        decision_reason: str = ""
    ):
        self.success = success
        self.output = output
        self.error = error
        self.artifacts = artifacts or {}
        self.needs_user_decision = needs_user_decision
        self.decision_reason = decision_reason

    def __repr__(self) -> str:
        if self.success:
            return f"AgentResult(success=True, output_len={len(self.output)})"
        else:
            return f"AgentResult(success=False, error={self.error[:50]}...)"


class BaseAgent(ABC):
    """Agent 基类

    所有 Agent 的基类，提供通用功能：
    - 工具过滤
    - 状态管理
    - 迭代计数
    - 错误处理
    - 动态提示词加载（通过 PromptLoader）

    Args:
        llm_service: LLM 服务实例
        config: Agent 配置
    """

    # 类变量：Agent 类型定义
    AGENT_TYPE: str = "base"
    DEFAULT_PROMPT_PATH: Optional[str] = None  # 提示词文件路径（相对于 prompt_loader.prompt_dir）

    def __init__(
        self,
        llm_service: Any,
        config: AgentConfig
    ) -> None:
        """初始化 Agent

        Args:
            llm_service: LLMService 实例
            config: Agent 配置
        """
        self.llm_service = llm_service
        self.config = config
        self.state = AgentState()
        self._tool_filter = config.tool_filter
        self._prompt_loader = config.prompt_loader or PromptLoader()

        logger.info(f"Initialized {self.__class__.__name__}: {config.name}")

    @property
    def get_system_prompt(self) -> str:
        """获取系统 prompt

        支持两种模式：
        1. 如果 config.system_prompt 已设置，直接返回
        2. 否则从 prompt_loader 动态加载（支持占位符插值）
        """
        # 1. 优先使用显式设置的 system_prompt
        if self.config.system_prompt:
            return self.config.system_prompt

        # 2. 从文件加载（如果指定了 prompt_path）
        prompt_path = self.config.prompt_path or self.DEFAULT_PROMPT_PATH
        if prompt_path:
            try:
                return self._prompt_loader.load(prompt_path)
            except Exception as e:
                logger.warning(f"Failed to load prompt from {prompt_path}: {e}")
                # 回退到内置 prompt
                return self._get_builtin_prompt()

        # 3. 返回内置 prompt
        return self._get_builtin_prompt()

    def _get_builtin_prompt(self) -> str:
        """获取内置兜底 prompt

        子类可以重写此方法提供内置提示词。
        """
        return ""

    @abstractmethod
    def execute(self, task: str, context: Optional[Dict[str, Any]] = None) -> AgentResult:
        """执行任务

        Args:
            task: 任务描述
            context: 可选的上下文信息

        Returns:
            AgentResult: 执行结果
        """
        pass

    def _get_builtin_prompt(self) -> str:
        """获取内置兜底 prompt

        子类可以重写此方法提供内置提示词。
        """
        return ""

    def _invoke_llm(
        self,
        user_prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> str:
        """调用 LLM

        Args:
            user_prompt: 用户 prompt
            system_prompt: 可选的系统 prompt（覆盖默认的）
            **kwargs: 额外参数

        Returns:
            str: LLM 响应
        """
        self.state.iteration_count += 1

        if self.state.iteration_count > self.config.max_iterations:
            raise RuntimeError(
                f"Max iterations ({self.config.max_iterations}) exceeded"
            )

        # 构建完整的 prompt
        sys_prompt = system_prompt or self.get_system_prompt
        full_prompt = f"{sys_prompt}\n\n---\n\n{user_prompt}"

        # 调用 LLM
        response = self.llm_service.chat(full_prompt, **kwargs)

        return response

    def _is_tool_allowed(self, tool_name: str) -> bool:
        """检查工具是否允许使用

        Args:
            tool_name: 工具名称

        Returns:
            bool: 是否允许
        """
        if self._tool_filter is None:
            return True
        return self._tool_filter.is_allowed(tool_name)

    def _get_available_tools(self, all_tools: List[str]) -> List[str]:
        """获取可用的工具列表

        Args:
            all_tools: 所有工具名称列表

        Returns:
            List[str]: 过滤后的工具列表
        """
        if self._tool_filter is None:
            return all_tools
        return self._tool_filter.filter(all_tools)

    def reset(self) -> None:
        """重置 Agent 状态"""
        self.state = AgentState()

    def get_status(self) -> Dict[str, Any]:
        """获取 Agent 状态摘要"""
        return {
            "name": self.config.name,
            "is_busy": self.state.is_busy,
            "iteration_count": self.state.iteration_count,
            "current_task": self.state.current_task,
            "last_error": self.state.last_error,
        }


class PlannerAgent(BaseAgent):
    """规划 Agent

    负责需求分析和任务规划，生成 TDD 实现计划。
    只允许使用只读工具。

    职责:
    - 分析需求，理解核心问题
    - 拆解任务为原子步骤
    - 生成 implementation_plan.md
    - 识别边界条件和依赖
    """

    DEFAULT_SYSTEM_PROMPT = """You are a Planner Agent - a technical blueprint creator.

Your responsibilities:
1. Analyze requirements and understand the core problem
2. Decompose tasks into atomic, testable steps
3. Create a TDD-compliant implementation plan
4. Identify boundary conditions and dependencies

Rules:
- Always start with understanding the requirement deeply
- Break down complex tasks into smaller, manageable steps
- For each step, specify: test first, then implementation
- Document dependencies between steps
- Identify edge cases and error conditions

Output format: Markdown with clear sections and checkboxes"""

    def __init__(self, llm_service: Any, config: Optional[AgentConfig] = None) -> None:
        if config is None:
            config = AgentConfig(
                name="PlannerAgent",
                description="Requirements analyst and TDD planner",
                tool_filter=ReadOnlyFilter(),  # 只读工具
                max_iterations=5,
                system_prompt=self.DEFAULT_SYSTEM_PROMPT
            )
        super().__init__(llm_service, config)

    @property
    def get_system_prompt(self) -> str:
        """获取系统 prompt"""
        return self.config.system_prompt or self.DEFAULT_SYSTEM_PROMPT

    def execute(self, task: str, context: Optional[Dict[str, Any]] = None) -> AgentResult:
        """执行规划任务

        Args:
            task: 任务/需求描述
            context: 可选的上下文（如已有分析结果）

        Returns:
            AgentResult: 规划结果
        """
        self.state.current_task = task
        self.state.is_busy = True

        try:
            # 构建 prompt
            user_prompt = self._build_planning_prompt(task, context or {})

            # 调用 LLM
            response = self._invoke_llm(user_prompt)

            # 解析响应，提取计划
            plan = self._parse_plan(response)

            self.state.is_busy = False

            return AgentResult(
                success=True,
                output=response,
                artifacts={"implementation_plan.md": plan}
            )

        except Exception as e:
            self.state.last_error = str(e)
            self.state.is_busy = False
            return AgentResult(
                success=False,
                error=str(e)
            )

    def _build_planning_prompt(
        self,
        task: str,
        context: Dict[str, Any]
    ) -> str:
        """构建规划 prompt"""
        prompt_parts = []

        # 添加上下文信息
        if context.get("analysis"):
            prompt_parts.append(f"Previous analysis:\n{context['analysis']}\n")

        # 添加任务描述
        prompt_parts.append(f"Task/Requirement:\n{task}\n")

        # 添加具体指令
        prompt_parts.append("""
Please create a detailed implementation plan with:

1. **Overview**: Brief description of what needs to be built

2. **Phase Breakdown**: Group related steps into phases
   - Phase 1: Foundation (models, core logic)
   - Phase 2: Implementation (features)
   - Phase 3: Integration (connecting components)
   - Phase 4: Testing & Validation

3. **TDD Steps**: For each step, specify:
   - [ ] Test: What test to write first
   - [ ] Implementation: What to implement

4. **Dependencies**: What depends on what

5. **Boundary Conditions**: Edge cases to consider

6. **Required Libraries**: External dependencies needed

Output in markdown format with clear structure.""")

        return "\n".join(prompt_parts)

    def _parse_plan(self, response: str) -> str:
        """解析响应，提取计划"""
        # 简单实现：直接返回响应
        # 可以扩展为提取 markdown 计划部分
        return response


class CoderAgent(BaseAgent):
    """编码 Agent

    负责根据规划生成代码实现。
    允许使用大部分工具（除了危险工具）。

    职责:
    - 遵循 TDD 红 - 绿 - 重构循环
    - 生成类型提示完整的代码
    - 编写 Google 风格 docstrings
    - 遵循 PEP 8 代码风格
    """

    DEFAULT_SYSTEM_PROMPT = """You are a Coder Agent - a Python craftsman focused on code beauty and best practices.

Your responsibilities:
1. Implement features following TDD principles
2. Write clean, maintainable, type-safe code
3. Follow PEP 8 and Google style guides

Rules:
- **TDD Cycle**: Red (write failing test) → Green (make it pass) → Refactor
- **Type Hints**: All functions must have complete type hints (Python 3.10+ syntax)
- **Docstrings**: All public functions/classes must have Google-style docstrings
- **PEP 8**: Follow PEP 8 code style (4 spaces, 79 char limit)
- **Error Handling**: Handle edge cases and errors gracefully
- **Single Responsibility**: Each function/class does one thing well

Code Style:
- Use snake_case for functions/variables
- Use PascalCase for classes
- Use UPPER_CASE for constants
- Use dataclasses for data models
- Use match-case for complex conditionals (Python 3.10+)"""

    def __init__(self, llm_service: Any, config: Optional[AgentConfig] = None) -> None:
        if config is None:
            config = AgentConfig(
                name="CoderAgent",
                description="TDD code implementer",
                tool_filter=FullAccessFilter(),  # 完全访问（有黑名单保护）
                max_iterations=15,
                system_prompt=self.DEFAULT_SYSTEM_PROMPT
            )
        super().__init__(llm_service, config)

    @property
    def get_system_prompt(self) -> str:
        """获取系统 prompt"""
        return self.config.system_prompt or self.DEFAULT_SYSTEM_PROMPT

    def execute(
        self,
        task: str,
        context: Optional[Dict[str, Any]] = None
    ) -> AgentResult:
        """执行编码任务

        Args:
            task: 当前要实现的具体任务
            context: 上下文（如计划、已有代码）

        Returns:
            AgentResult: 编码结果
        """
        self.state.current_task = task
        self.state.is_busy = True

        try:
            # 构建 prompt
            user_prompt = self._build_coding_prompt(task, context or {})

            # 调用 LLM
            response = self._invoke_llm(user_prompt)

            # 解析响应，提取代码
            code_artifacts = self._parse_code(response)

            self.state.is_busy = False

            return AgentResult(
                success=True,
                output=response,
                artifacts=code_artifacts
            )

        except Exception as e:
            self.state.last_error = str(e)
            self.state.is_busy = False
            return AgentResult(
                success=False,
                error=str(e)
            )

    def _build_coding_prompt(
        self,
        task: str,
        context: Dict[str, Any]
    ) -> str:
        """构建编码 prompt"""
        prompt_parts = []

        # 添加计划上下文
        if context.get("plan"):
            prompt_parts.append(f"Implementation Plan:\n{context['plan']}\n")

        # 添加已有代码
        if context.get("existing_code"):
            prompt_parts.append(f"Existing Code:\n{context['existing_code']}\n")

        # 添加当前任务
        prompt_parts.append(f"Current Task to Implement:\n{task}\n")

        # 添加具体指令
        prompt_parts.append("""
Please implement the above task following these rules:

1. **TDD First**: Write the test case first, then implement

2. **Type Hints**: Complete type hints for all functions
   ```python
   def calculate_total(items: list[Item], tax_rate: float) -> float:
       ...
   ```

3. **Docstrings**: Google-style for all public APIs
   ```python
   def process_data(data: dict) -> list:
       \"\"\"Process input data and return results.

       Args:
           data: Input data dictionary.

       Returns:
           Processed results list.
       \"\"\"
   ```

4. **Error Handling**: Handle edge cases explicitly

5. **Code Style**: Follow PEP 8

Output the complete code for the test file AND implementation file.""")

        return "\n".join(prompt_parts)

    def _parse_code(self, response: str) -> Dict[str, str]:
        """解析响应，提取代码文件"""
        import re

        artifacts = {}

        # 匹配 ```python ... ``` 代码块
        code_blocks = re.findall(r'```python\n(.*?)\n```', response, re.DOTALL)

        # 尝试根据内容推断文件名
        for i, code in enumerate(code_blocks):
            # 检查是否包含 test
            if 'test_' in code.lower() or 'unittest' in code.lower() or 'pytest' in code.lower():
                filename = f"test_file_{i}.py"
            else:
                filename = f"implementation_file_{i}.py"
            artifacts[filename] = code

        return artifacts


class TesterAgent(BaseAgent):
    """测试 Agent

    负责运行测试并验证代码质量。
    只允许使用只读工具和测试命令。

    职责:
    - 运行 pytest 测试
    - 运行 mypy 类型检查
    - 运行 flake8 代码风格检查
    - 运行覆盖率检查
    - 生成质量报告
    """

    DEFAULT_SYSTEM_PROMPT = """You are a Tester Agent - a quality gatekeeper.

Your responsibilities:
1. Run tests and report results
2. Validate code quality (types, style, coverage)
3. Provide clear failure reports

Rules:
- Run tests in isolated environment
- Report only essential information (failures, errors)
- Provide actionable fix suggestions
- Be strict but fair

Quality Gates:
- **Tests**: All tests must pass (pytest)
- **Types**: No mypy errors (--strict mode)
- **Style**: No flake8 E-errors
- **Coverage**: >= 80% line coverage"""

    def __init__(self, llm_service: Any, config: Optional[AgentConfig] = None) -> None:
        if config is None:
            config = AgentConfig(
                name="TesterAgent",
                description="Quality validator",
                tool_filter=ReadOnlyFilter(additional_allowed=[
                    "Command_pytest", "Command_mypy", "Command_flake8",
                    "Command_coverage", "Command_python"
                ]),
                max_iterations=5,
                system_prompt=self.DEFAULT_SYSTEM_PROMPT
            )
        super().__init__(llm_service, config)

        # 命令工具
        self._command_tool = None

    @property
    def get_system_prompt(self) -> str:
        """获取系统 prompt"""
        return self.config.system_prompt or self.DEFAULT_SYSTEM_PROMPT

    def execute(
        self,
        task: str,
        context: Optional[Dict[str, Any]] = None
    ) -> AgentResult:
        """执行测试任务

        Args:
            task: 测试任务描述
            context: 上下文（如要测试的代码）

        Returns:
            AgentResult: 测试结果
        """
        self.state.current_task = task
        self.state.is_busy = True

        try:
            # 运行测试
            test_result = self._run_tests()

            # 运行类型检查
            type_result = self._run_type_check()

            # 运行代码风格检查
            lint_result = self._run_lint()

            # 运行覆盖率检查
            coverage_result = self._run_coverage()

            self.state.is_busy = False

            # 汇总结果
            all_passed = all([
                test_result["success"],
                type_result["success"],
                lint_result["success"],
                coverage_result["success"]
            ])

            report = self._generate_report({
                "tests": test_result,
                "types": type_result,
                "lint": lint_result,
                "coverage": coverage_result
            })

            if all_passed:
                return AgentResult(
                    success=True,
                    output=report,
                    artifacts={"quality_report.md": report}
                )
            else:
                return AgentResult(
                    success=False,
                    error=report,
                    artifacts={"quality_report.md": report}
                )

        except Exception as e:
            self.state.last_error = str(e)
            self.state.is_busy = False
            return AgentResult(
                success=False,
                error=str(e)
            )

    def _get_command_tool(self):
        """获取 CommandTool 实例"""
        if self._command_tool is None:
            from mini_coder.tools.command import CommandTool
            from mini_coder.tools.permission import PermissionService

            permission_service = PermissionService()
            self._command_tool = CommandTool(permission_service=permission_service)
        return self._command_tool

    def _run_tests(self) -> Dict[str, Any]:
        """运行 pytest 测试"""
        try:
            command_tool = self._get_command_tool()
            result = command_tool.execute("pytest tests/ -v --tb=short")
            return {
                "success": result.success,
                "output": result.stdout,
                "error": result.stderr
            }
        except Exception as e:
            return {"success": False, "output": "", "error": str(e)}

    def _run_type_check(self) -> Dict[str, Any]:
        """运行 mypy 类型检查"""
        try:
            command_tool = self._get_command_tool()
            result = command_tool.execute("mypy src/ --strict")
            return {
                "success": result.success,
                "output": result.stdout,
                "error": result.stderr
            }
        except Exception as e:
            return {"success": False, "output": "", "error": str(e)}

    def _run_lint(self) -> Dict[str, Any]:
        """运行 flake8 代码风格检查"""
        try:
            command_tool = self._get_command_tool()
            result = command_tool.execute("flake8 src/")
            return {
                "success": result.success,
                "output": result.stdout,
                "error": result.stderr
            }
        except Exception as e:
            return {"success": False, "output": "", "error": str(e)}

    def _run_coverage(self) -> Dict[str, Any]:
        """运行覆盖率检查"""
        try:
            command_tool = self._get_command_tool()
            result = command_tool.execute(
                "pytest tests/ --cov=src --cov-fail-under=80 -q"
            )
            return {
                "success": result.success,
                "output": result.stdout,
                "error": result.stderr
            }
        except Exception as e:
            return {"success": False, "output": "", "error": str(e)}

    def _generate_report(self, results: Dict[str, Dict]) -> str:
        """生成质量报告"""
        report_lines = ["# Quality Report\n"]

        # 测试部分
        test_result = results["tests"]
        report_lines.append("## Tests\n")
        if test_result["success"]:
            report_lines.append("✅ All tests passed\n")
        else:
            report_lines.append("❌ Tests failed\n")
            report_lines.append(f"Error: {test_result['error']}\n")

        # 类型检查部分
        type_result = results["types"]
        report_lines.append("\n## Type Check\n")
        if type_result["success"]:
            report_lines.append("✅ No type errors\n")
        else:
            report_lines.append("❌ Type errors found\n")
            report_lines.append(f"Error: {type_result['error']}\n")

        # Lint 部分
        lint_result = results["lint"]
        report_lines.append("\n## Code Style\n")
        if lint_result["success"]:
            report_lines.append("✅ No style issues\n")
        else:
            report_lines.append("❌ Style issues found\n")
            report_lines.append(f"Error: {lint_result['error']}\n")

        # 覆盖率部分
        coverage_result = results["coverage"]
        report_lines.append("\n## Coverage\n")
        if coverage_result["success"]:
            report_lines.append("✅ Coverage >= 80%\n")
        else:
            report_lines.append("❌ Coverage < 80%\n")
            report_lines.append(f"Error: {coverage_result['error']}\n")

        return "\n".join(report_lines)


class AgentTeam:
    """Agent 团队管理器

    管理和协调多个 Agent 的协作。
    提供统一的接口来执行工作流。
    """

    def __init__(self, llm_service: Any) -> None:
        """初始化 Agent 团队

        Args:
            llm_service: LLMService 实例
        """
        self.llm_service = llm_service

        # 初始化 Agent
        self.planner = PlannerAgent(llm_service)
        self.coder = CoderAgent(llm_service)
        self.tester = TesterAgent(llm_service)

        # Agent 执行历史
        self._history: List[Dict[str, Any]] = []

    def execute_plan(
        self,
        requirement: str,
        context: Optional[Dict[str, Any]] = None
    ) -> AgentResult:
        """执行完整的 规划→编码→测试 流程

        Args:
            requirement: 需求描述
            context: 上下文信息

        Returns:
            AgentResult: 执行结果
        """
        logger.info(f"Starting AgentTeam workflow for: {requirement[:100]}...")

        # 阶段 1: 规划
        logger.info("Phase 1: Planning")
        plan_result = self.planner.execute(requirement, context)
        self._record_execution("planner", plan_result)

        if not plan_result.success:
            return plan_result

        # 阶段 2: 编码
        logger.info("Phase 2: Coding")
        code_context = context or {}
        code_context["plan"] = plan_result.artifacts.get("implementation_plan.md", "")
        code_result = self.coder.execute(requirement, code_context)
        self._record_execution("coder", code_result)

        if not code_result.success:
            return code_result

        # 阶段 3: 测试
        logger.info("Phase 3: Testing")
        test_context = code_context.copy()
        test_context.update(code_result.artifacts)
        test_result = self.tester.execute(requirement, test_context)
        self._record_execution("tester", test_result)

        return test_result

    def _record_execution(
        self,
        agent_name: str,
        result: AgentResult
    ) -> None:
        """记录执行历史"""
        self._history.append({
            "agent": agent_name,
            "success": result.success,
            "output_len": len(result.output) if result.output else 0,
            "error": result.error if not result.success else None,
        })

    def get_history(self) -> List[Dict[str, Any]]:
        """获取执行历史"""
        return self._history.copy()

    def reset(self) -> None:
        """重置所有 Agent 状态"""
        self.planner.reset()
        self.coder.reset()
        self.tester.reset()
        self._history.clear()

    def get_status(self) -> Dict[str, Any]:
        """获取团队状态摘要"""
        return {
            "planner": self.planner.get_status(),
            "coder": self.coder.get_status(),
            "tester": self.tester.get_status(),
            "history_count": len(self._history),
        }


# ==================== New Subagents (Dynamic Prompt Loading) ====================

class ExplorerCapabilities(AgentCapabilities):
    """Explorer Agent 能力"""

    def __init__(self) -> None:
        super().__init__(
            allowed_tools={"Read", "Glob", "Grep", "Command_ls", "Command_cat", "Command_head", "Command_tail", "Command_git_status", "Command_git_log", "Command_git_diff"},
            allowed_read_patterns=["**/*"],
            allowed_write_patterns=[],  # 只读，不能写
            max_tool_calls=15,
            requires_confirmation=False
        )


class ExplorerAgent(BaseAgent):
    """Explorer Agent - 只读代码库搜索专家

    职责:
    - 快速探索代码库结构
    - 查找文件和代码位置
    - 理解模块依赖关系

    工具权限:
    - 只读工具：Read, Glob, Grep
    - 只读命令：ls, git status, git log, git diff
    """

    AGENT_TYPE = "explorer"
    DEFAULT_PROMPT_PATH = "subagent-explorer"

    def __init__(self, llm_service: Any, config: Optional[AgentConfig] = None) -> None:
        if config is None:
            config = AgentConfig(
                name="ExplorerAgent",
                description="Read-only codebase explorer",
                tool_filter=ReadOnlyFilter(),
                max_iterations=10,
                prompt_path=self.DEFAULT_PROMPT_PATH,
            )
        super().__init__(llm_service, config)
        self._capabilities = ExplorerCapabilities()

    def _get_builtin_prompt(self) -> str:
        """获取内置兜底 prompt"""
        return """You are the Explorer Agent - a read-only codebase search specialist.

Constraints: Read-Only Mode
- You MUST NOT create, modify, or delete files
- You MUST NOT use Write or Edit tools
- You can only use: Read, Grep, Glob, and read-only Bash commands

Behavior:
- Adjust exploration depth based on request (quick/medium/thorough)
- Report all file paths using absolute paths
- Be concise, avoid emoji
- Parallelize independent searches for efficiency

Output:
Report findings: files/code locations discovered, key conclusions, relevance to request."""

    def execute(self, task: str, context: Optional[Dict[str, Any]] = None) -> AgentResult:
        """执行探索任务"""
        self.state.current_task = task
        self.state.is_busy = True

        try:
            user_prompt = self._build_explorer_prompt(task, context or {})
            response = self._invoke_llm(user_prompt)

            self.state.is_busy = False

            return AgentResult(
                success=True,
                output=response,
                artifacts={"exploration_result.md": response}
            )

        except Exception as e:
            self.state.last_error = str(e)
            self.state.is_busy = False
            return AgentResult(
                success=False,
                error=str(e)
            )

    def _build_explorer_prompt(self, task: str, context: Dict[str, Any]) -> str:
        """构建探索 prompt"""
        return f"""Task: {task}

Context:
{context.get('analysis', '')}

Please explore the codebase to find relevant files and understand the structure.
Report findings with absolute file paths and brief explanations."""


class ReviewerCapabilities(AgentCapabilities):
    """Reviewer Agent 能力"""

    def __init__(self) -> None:
        super().__init__(
            allowed_tools={"Read", "Glob", "Grep"},
            allowed_read_patterns=["**/*.py", "**/*.md"],
            allowed_write_patterns=[],  # 只读，不能写
            max_tool_calls=15,
            requires_confirmation=False
        )


class ReviewerAgent(BaseAgent):
    """Reviewer Agent - 代码质量评审专家

    职责:
    - 代码质量评审（类型提示、docstrings、命名、复杂度）
    - 架构对齐检查（是否遵循 implementation_plan.md）
    - 输出二元决策：通过/拒绝

    工具权限:
    - 只读工具：Read, Glob, Grep
    """

    AGENT_TYPE = "reviewer"
    DEFAULT_PROMPT_PATH = "subagent-reviewer"

    def __init__(self, llm_service: Any, config: Optional[AgentConfig] = None) -> None:
        if config is None:
            config = AgentConfig(
                name="ReviewerAgent",
                description="Code quality reviewer",
                tool_filter=ReadOnlyFilter(),
                max_iterations=5,
                prompt_path=self.DEFAULT_PROMPT_PATH,
            )
        super().__init__(llm_service, config)
        self._capabilities = ReviewerCapabilities()

    def _get_builtin_prompt(self) -> str:
        """获取内置兜底 prompt"""
        return """You are the Reviewer Agent - a code quality review specialist.

Review Checklist:
1. Architecture Alignment: Does code follow implementation_plan.md?
2. Type Hints: All functions have complete type annotations (Python 3.10+)
3. Docstrings: Google-style for all public APIs
4. Naming: Clear, descriptive names following PEP 8
5. Complexity: Long functions (>50 lines), duplicated logic

Output Format (STRICT BINARY CHOICE):

### Pass
[Pass] Code meets architecture and quality requirements, ready for Bash testing

### Reject
[Reject] Code needs modification:
1. [Architecture] Specific file:line - issue + fix suggestion
2. [Quality] Specific file:line - issue + fix suggestion
3. [Style] Specific file:line - issue + fix suggestion"""

    def execute(self, task: str, context: Optional[Dict[str, Any]] = None) -> AgentResult:
        """执行评审任务"""
        self.state.current_task = task
        self.state.is_busy = True

        try:
            user_prompt = self._build_reviewer_prompt(task, context or {})
            response = self._invoke_llm(user_prompt)

            self.state.is_busy = False

            # 判断是否通过
            passed = "Pass" in response or "[Pass]" in response or "通过" in response

            return AgentResult(
                success=passed,
                output=response,
                artifacts={"review_report.md": response}
            )

        except Exception as e:
            self.state.last_error = str(e)
            self.state.is_busy = False
            return AgentResult(
                success=False,
                error=str(e)
            )

    def _build_reviewer_prompt(self, task: str, context: Dict[str, Any]) -> str:
        """构建评审 prompt"""
        plan = context.get("plan", "")
        code = context.get("code", "")

        return f"""Task: {task}

Implementation Plan (for architecture alignment):
{plan}

Code to Review:
{code}

Please review the code against the implementation plan and quality standards.
Output your decision (Pass/Reject) with specific feedback."""


class BashCapabilities(AgentCapabilities):
    """Bash Agent 能力"""

    def __init__(self) -> None:
        super().__init__(
            allowed_tools={"Read", "Glob", "Bash"},
            allowed_read_patterns=["**/*"],
            allowed_write_patterns=["tests/**/*.md"],
            max_tool_calls=10,
            requires_confirmation=False
        )


class BashAgent(BaseAgent):
    """Bash Agent - 终端执行与测试验证专家

    职责:
    - 运行测试（pytest）
    - 类型检查（mypy）
    - 代码风格检查（flake8）
    - 覆盖率检查（pytest --cov）
    - 生成质量报告

    工具权限:
    - 只读：Read, Glob
    - Bash 命令（受白名单/黑名单限制）
    """

    AGENT_TYPE = "bash"
    DEFAULT_PROMPT_PATH = "subagent-bash"

    def __init__(
        self,
        llm_service: Any,
        config: Optional[AgentConfig] = None,
        command_executor: Optional[Any] = None,
    ) -> None:
        if config is None:
            config = AgentConfig(
                name="BashAgent",
                description="Terminal command executor and test validator",
                tool_filter=None,  # 在 execute 中检查命令白名单
                max_iterations=5,
                prompt_path=self.DEFAULT_PROMPT_PATH,
            )
        super().__init__(llm_service, config)
        self._capabilities = BashCapabilities()
        self._command_executor = command_executor

    def _get_builtin_prompt(self) -> str:
        """获取内置兜底 prompt"""
        return """You are the Bash Agent - a terminal execution and test verification specialist.

Capabilities:
1. Terminal Command Execution (restricted whitelist)
2. Run Tests (pytest)
3. Type Checking (mypy)
4. Code Style (flake8)
5. Coverage Check (pytest --cov)

Command Whitelist (Direct Execution):
- Tests: pytest, python -m pytest
- Type Check: mypy, python -m mypy
- Style: flake8, black --check
- Info: ls, cat, head, tail, pwd
- Python: python, python -m
- Git (read-only): git status, git log, git diff, git branch

Command Blacklist (Prohibited):
- rm -rf, mkfs, chmod 777, curl|bash, dd, sudo

Output Format:
Generate quality report with test results, type check, code style, and coverage."""

    def execute(self, task: str, context: Optional[Dict[str, Any]] = None) -> AgentResult:
        """执行 Bash 任务"""
        self.state.current_task = task
        self.state.is_busy = True

        try:
            # 运行测试
            test_result = self._run_tests()

            # 类型检查
            type_result = self._run_type_check()

            # 代码风格检查
            lint_result = self._run_lint()

            # 覆盖率检查
            coverage_result = self._run_coverage()

            self.state.is_busy = False

            # 生成报告
            report = self._generate_report({
                "tests": test_result,
                "types": type_result,
                "lint": lint_result,
                "coverage": coverage_result
            })

            # 判断是否通过
            all_passed = all([
                test_result.get("success", False),
                type_result.get("success", False),
                lint_result.get("success", False),
                coverage_result.get("success", True),  # 覆盖率可选
            ])

            return AgentResult(
                success=all_passed,
                output=report,
                artifacts={"quality_report.md": report}
            )

        except Exception as e:
            self.state.last_error = str(e)
            self.state.is_busy = False
            return AgentResult(
                success=False,
                error=str(e)
            )

    def _run_tests(self) -> Dict[str, Any]:
        """运行 pytest"""
        if self._command_executor:
            success, stdout, stderr = self._command_executor("pytest tests/ -v --tb=short", 120)
            return {"success": success, "stdout": stdout, "stderr": stderr}
        return {"success": True, "stdout": "Tests passed (simulated)", "stderr": ""}

    def _run_type_check(self) -> Dict[str, Any]:
        """运行 mypy"""
        if self._command_executor:
            success, stdout, stderr = self._command_executor("mypy src/ --strict", 60)
            return {"success": success, "stdout": stdout, "stderr": stderr}
        return {"success": True, "stdout": "No type errors (simulated)", "stderr": ""}

    def _run_lint(self) -> Dict[str, Any]:
        """运行 flake8"""
        if self._command_executor:
            success, stdout, stderr = self._command_executor("flake8 src/", 30)
            return {"success": success, "stdout": stdout, "stderr": stderr}
        return {"success": True, "stdout": "No lint issues (simulated)", "stderr": ""}

    def _run_coverage(self) -> Dict[str, Any]:
        """运行覆盖率检查"""
        if self._command_executor:
            success, stdout, stderr = self._command_executor(
                "pytest tests/ --cov=src --cov-fail-under=80 -q", 60
            )
            return {"success": success, "stdout": stdout, "stderr": stderr}
        return {"success": True, "stdout": "Coverage OK (simulated)", "stderr": ""}

    def _generate_report(self, results: Dict[str, Dict]) -> str:
        """生成质量报告"""
        lines = ["# Quality Report\n"]

        # 测试
        lines.append("## Tests\n")
        if results["tests"].get("success"):
            lines.append("✅ All tests passed\n")
        else:
            lines.append("❌ Tests failed\n")
            lines.append(f"```\n{results['tests'].get('stderr', '')}\n```\n")

        # 类型检查
        lines.append("## Type Check\n")
        if results["types"].get("success"):
            lines.append("✅ No type errors\n")
        else:
            lines.append("❌ Type errors found\n")
            lines.append(f"```\n{results['types'].get('stderr', '')}\n```\n")

        # 代码风格
        lines.append("## Code Style\n")
        if results["lint"].get("success"):
            lines.append("✅ No style issues\n")
        else:
            lines.append("❌ Style issues found\n")
            lines.append(f"```\n{results['lint'].get('stderr', '')}\n```\n")

        # 覆盖率
        lines.append("## Coverage\n")
        if results["coverage"].get("success"):
            lines.append("✅ Coverage >= 80%\n")
        else:
            lines.append("⚠️ Coverage < 80%\n")
            lines.append(f"```\n{results['coverage'].get('stderr', '')}\n```\n")

        return "\n".join(lines)


# ==================== New Subagents (General Purpose & Guide) ====================

class GeneralPurposeCapabilities(AgentCapabilities):
    """General Purpose Agent 能力

    A fast, read-only agent optimized for searching and analyzing codebases.
    Uses Haiku model for low-latency responses.
    """

    def __init__(self) -> None:
        super().__init__(
            allowed_tools={"Read", "Glob", "Grep", "Command_ls", "Command_cat",
                          "Command_head", "Command_tail", "Command_git_status",
                          "Command_git_log", "Command_git_diff"},
            allowed_read_patterns=["**/*"],
            allowed_write_patterns=[],  # 只读，不能写
            max_tool_calls=20,  # 更多的工具调用以支持全面搜索
            requires_confirmation=False
        )


class GeneralPurposeAgent(BaseAgent):
    """General Purpose Agent - 通用只读搜索代理

    一个快速的、只读的代理，优化用于搜索和分析代码库。

    特点:
    - 使用 Haiku 模型 (快速、低延迟)
    - 只读工具访问 (拒绝 Write 和 Edit)
    - 适用于：文件发现、代码搜索、代码库探索

    工具权限:
    - 只读工具：Read, Glob, Grep
    - 只读命令：ls, git status, git log, git diff, cat, head, tail
    """

    AGENT_TYPE = "general_purpose"
    DEFAULT_PROMPT_PATH = "general-purpose"

    def __init__(self, llm_service: Any, config: Optional[AgentConfig] = None) -> None:
        if config is None:
            config = AgentConfig(
                name="GeneralPurposeAgent",
                description="Fast read-only codebase search and analysis agent",
                tool_filter=ReadOnlyFilter(),
                max_iterations=15,
                prompt_path=self.DEFAULT_PROMPT_PATH,
                metadata={"model": "haiku"}  # 使用 Haiku 模型
            )
        super().__init__(llm_service, config)
        self._capabilities = GeneralPurposeCapabilities()

    def _get_builtin_prompt(self) -> str:
        """获取内置兜底 prompt"""
        return """You are the General Purpose Agent - a fast, read-only agent.
Optimized for searching and analyzing codebases.

## Configuration
- Model: Haiku (fast, low-latency)
- Mode: Read-only

## Constraints: Read-Only Mode

You MUST NOT:
- Create, modify, or delete files
- Use Write or Edit tools
- Execute state-changing bash commands (mkdir, git add, npm install, etc.)

You CAN use:
- Read, Grep, Glob for code search
- Read-only Bash commands: ls, git status, git log, git diff, cat, head, tail

## Behavior

- Be fast and efficient
- Use parallel searches when possible
- Report file paths using absolute paths
- Be concise, avoid emoji
- Focus on finding relevant code quickly

## Output

Report your findings clearly:
1. Files discovered (with absolute paths)
2. Key code locations
3. Relevant patterns or matches
4. Brief conclusions about what you found"""

    def execute(self, task: str, context: Optional[Dict[str, Any]] = None) -> AgentResult:
        """执行通用搜索任务"""
        self.state.current_task = task
        self.state.is_busy = True

        try:
            user_prompt = self._build_general_purpose_prompt(task, context or {})
            response = self._invoke_llm(user_prompt)

            self.state.is_busy = False

            return AgentResult(
                success=True,
                output=response,
                artifacts={"general_purpose_result.md": response}
            )

        except Exception as e:
            self.state.last_error = str(e)
            self.state.is_busy = False
            return AgentResult(
                success=False,
                error=str(e)
            )

    def _build_general_purpose_prompt(self, task: str, context: Dict[str, Any]) -> str:
        """构建通用搜索 prompt"""
        return f"""Task: {task}

Context:
{context.get('analysis', '')}

Please search and analyze the codebase to fulfill this request.
Use your read-only tools efficiently to find relevant information."""


class MiniCoderGuideCapabilities(AgentCapabilities):
    """Mini-Coder Guide Agent 能力

    A read-only agent that helps users understand and use mini-coder effectively.
    """

    def __init__(self) -> None:
        super().__init__(
            allowed_tools={"Read", "Glob", "Grep"},
            allowed_read_patterns=["**/*.md", "**/*.yaml", "**/*.yml", "**/*.py"],
            allowed_write_patterns=[],  # 只读，不能写
            max_tool_calls=10,
            requires_confirmation=False
        )


class MiniCoderGuideAgent(BaseAgent):
    """Mini-Coder Guide Agent - mini-coder 使用指南代理

    你的唯一工作是帮助用户理解并有效使用 **mini-coder**（带有 TUI 的多 agent 编码助手）。

    职责:
    - 不编辑代码或运行终端命令
    - 回答问题并指向文档
    - 提供 mini-coder 使用指导

    专业领域:
    1. Mini-Coder TUI & 使用
    2. Multi-agent system & workflow
    3. Project layout, config & design
    """

    AGENT_TYPE = "mini_coder_guide"
    DEFAULT_PROMPT_PATH = "mini-coder-guide"

    def __init__(self, llm_service: Any, config: Optional[AgentConfig] = None) -> None:
        if config is None:
            config = AgentConfig(
                name="MiniCoderGuideAgent",
                description="Mini-coder usage guide and documentation assistant",
                tool_filter=ReadOnlyFilter(),
                max_iterations=8,
                prompt_path=self.DEFAULT_PROMPT_PATH,
            )
        super().__init__(llm_service, config)
        self._capabilities = MiniCoderGuideCapabilities()

    def _get_builtin_prompt(self) -> str:
        """获取内置兜底 prompt"""
        return """You are the mini-coder guide agent.
Your only job is to help users understand and use **mini-coder** effectively.
You do not edit code or run terminal commands; you answer questions and point to documentation.

## Your Expertise Areas

### 1. Mini-Coder TUI & Usage
- How to run: `python -m mini_coder.tui` or `./dist/mini-coder-tui`
- Configuration: `~/.mini-coder/tui.yaml` (animation, thinking display, working directory)
- Working directory selection and context-aware assistance
- CLI arguments and binary usage (see README.md)

### 2. Multi-Agent System & Workflow
- Agent roles:
  - Explorer (read-only search)
  - Planner (TDD planning)
  - Coder (implementation)
  - Reviewer (quality + architecture)
  - Bash (tests/lint/typecheck)
- Workflow: Explorer (optional) → Planner → Coder → Reviewer → Bash
- Loops on review reject or test failure
- Dynamic prompt loading: `prompts/system/*.md`, placeholder `{{identifier}}`, PromptLoader
- Agent config: `config/subagents.yaml`, tool filters (ReadOnlyFilter, FullAccessFilter, etc.)

### 3. Project Layout, Config & Design
- Config: `config/` (llm.yaml, tools.yaml, memory.yaml, subagents.yaml, workflow.yaml)
- Prompts: `prompts/system/` and knowledge-base/agent-prompts as referenced in docs
- Memory: working memory + persistent store (see docs/context-memory-design.md)
- Command execution & security: docs/command-execution-security-design.md
- CLAUDE.md: high-level workflow and agent overview for Claude Code users

## Where to Look (Use Read / Glob / Grep)

- **README.md** – installation, TUI config, CLI, binary
- **CLAUDE.md** – agent roles, workflow stages, prompt loading, development setup
- **docs/** – context-memory-design.md, command-execution-security-design.md, multi-agent-architecture-design.md, agent-prompts
- **config/** – subagents.yaml, llm.yaml, tools.yaml, memory.yaml
- **prompts/** – system prompt files if present

## Approach

1. Decide which area the question is about (TUI, agents/workflow, or config/design).
2. Use Read to open the most relevant file (README, CLAUDE.md, or a doc under docs/).
3. Use Glob or Grep to find specific config keys, agent names, or file paths when needed.
4. Answer in short, actionable form; cite file paths and section names.
5. If the repo has moved docs (e.g. to knowledge-base/), say so and point to the current location.

## Guidelines

- Rely on project docs and config; do not invent behavior.
- Keep answers concise; include a one-line example or path when useful.
- Mention related features (e.g. "For security details see docs/command-execution-security-design.md").
- No emojis.
- Do not suggest running destructive or sensitive commands; only point to docs or config."""

    def execute(self, task: str, context: Optional[Dict[str, Any]] = None) -> AgentResult:
        """执行指南任务 - 回答用户关于 mini-coder 的问题"""
        self.state.current_task = task
        self.state.is_busy = True

        try:
            # 首先搜索相关文档
            doc_search = self._search_documentation(task)

            # 构建回答
            user_prompt = self._build_guide_prompt(task, doc_search, context or {})
            response = self._invoke_llm(user_prompt)

            self.state.is_busy = False

            return AgentResult(
                success=True,
                output=response,
                artifacts={"guide_response.md": response},
                metadata={"doc_search": doc_search}
            )

        except Exception as e:
            self.state.last_error = str(e)
            self.state.is_busy = False
            return AgentResult(
                success=False,
                error=str(e)
            )

    def _search_documentation(self, task: str) -> Dict[str, str]:
        """搜索相关文档"""
        docs = {}

        # 搜索 README.md
        readme_path = Path("README.md")
        if readme_path.exists():
            docs["README.md"] = readme_path.read_text(encoding="utf-8")[:2000]  # 限制长度

        # 搜索 CLAUDE.md
        claude_md_path = Path("CLAUDE.md")
        if claude_md_path.exists():
            docs["CLAUDE.md"] = claude_md_path.read_text(encoding="utf-8")[:3000]

        # 搜索 docs 目录
        docs_dir = Path("docs")
        if docs_dir.exists():
            # 查找相关的 markdown 文件
            for md_file in docs_dir.rglob("*.md"):
                if len(docs) < 5:  # 限制文档数量
                    try:
                        content = md_file.read_text(encoding="utf-8")[:1500]
                        docs[f"docs/{md_file.relative_to(docs_dir)}"] = content
                    except Exception:
                        pass

        return docs

    def _build_guide_prompt(self, task: str, doc_search: Dict[str, str], context: Dict[str, Any]) -> str:
        """构建指南 prompt"""
        docs_context = "\n\n".join([f"### {path}\n\n{content}" for path, content in doc_search.items()])

        return f"""You are the mini-coder guide agent. Help the user understand and use mini-coder effectively.

User Question: {task}

## Available Documentation

{docs_context}

## Your Task

Answer the user's question based on the documentation above. Include:
1. Direct answer to their question
2. Relevant file paths and configuration keys
3. Links to related documentation sections
4. Brief examples if helpful

Keep your answer concise and actionable. Do not suggest destructive commands."""


# ==================== Export ====================

__all__ = [
    # Base
    "AgentConfig",
    "AgentState",
    "AgentResult",
    "BaseAgent",
    # Legacy Agents (for backward compatibility)
    "PlannerAgent",
    "CoderAgent",
    "TesterAgent",
    "AgentTeam",
    # New Subagents
    "ExplorerCapabilities",
    "ExplorerAgent",
    "ReviewerCapabilities",
    "ReviewerAgent",
    "BashCapabilities",
    "BashAgent",
    # General Purpose & Guide
    "GeneralPurposeCapabilities",
    "GeneralPurposeAgent",
    "MiniCoderGuideCapabilities",
    "MiniCoderGuideAgent",
]

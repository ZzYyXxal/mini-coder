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
from typing import Any, Dict, List, Optional, Type
from pathlib import Path

from mini_coder.tools.filter import ToolFilter, ReadOnlyFilter, FullAccessFilter, StrictFilter

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
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentState:
    """Agent 状态"""
    current_task: str = ""
    iteration_count: int = 0
    total_tokens_used: int = 0
    last_error: Optional[str] = None
    is_busy: bool = False


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

    Args:
        llm_service: LLM 服务实例
        config: Agent 配置
    """

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

        logger.info(f"Initialized {self.__class__.__name__}: {config.name}")

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

    @property
    @abstractmethod
    def get_system_prompt(self) -> str:
        """获取系统 prompt"""
        pass

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

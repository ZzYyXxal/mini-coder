"""Console-based TUI application using Rich framework.

This module provides a REPL-style interface for mini-coder,
using Rich Console for output and handling user input directly.
"""

import asyncio
import io
import json
import logging
import signal
import sys
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple, TypedDict

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.spinner import Spinner
from rich.syntax import Syntax
from rich.text import Text

from mini_coder.tui.models.config import Config
from mini_coder.tui.models.thinking import ThinkingHistory

# 对话耗时展示阈值（秒）：低于此值为较快(绿)，高于 DURATION_SLOW_S 为较慢(红)，中间为中等(黄)
DURATION_FAST_S = 5.0
DURATION_SLOW_S = 15.0


class AppState(Enum):
    """Application state enumeration."""

    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"


class WorkingMode(Enum):
    """Working mode enumeration (deprecated - kept for backwards compatibility)."""

    PLAN = "plan"
    CODE = "code"
    EXECUTE = "execute"

    def __str__(self) -> str:
        """Return display name for the mode."""
        return self.value.upper()


class AgentDisplay(Enum):
    """Agent display enumeration for TUI."""

    MAIN = "Main"  # 主 Agent（默认）
    EXPLORER = "Explorer"
    PLANNER = "Planner"
    CODER = "Coder"
    REVIEWER = "Reviewer"
    BASH = "Bash"
    TESTER = "Tester"  # 测试 Agent
    GENERAL_PURPOSE = "General"
    MINI_CODER_GUIDE = "Guide"
    UNKNOWN = "Unknown"

    @classmethod
    def from_agent_type(cls, agent_type: Any) -> "AgentDisplay":
        """Convert SubAgentType to AgentDisplay."""
        mapping = {
            "explorer": cls.EXPLORER,
            "planner": cls.PLANNER,
            "coder": cls.CODER,
            "reviewer": cls.REVIEWER,
            "bash": cls.BASH,
            "tester": cls.TESTER,
            "general_purpose": cls.GENERAL_PURPOSE,
            "mini_coder_guide": cls.MINI_CODER_GUIDE,
        }
        # Get the value from enum if needed
        agent_value = agent_type.value if hasattr(agent_type, 'value') else str(agent_type)
        return mapping.get(agent_value, cls.UNKNOWN)

    def __str__(self) -> str:
        """Return display name for the agent."""
        return self.value


@dataclass
class UIState:
    """State of the TUI UI."""

    current_screen: str = "welcome"
    thinking_visible: bool = False
    working_mode: WorkingMode = WorkingMode.PLAN  # Deprecated, kept for compatibility

    # Debug mode
    debug_mode: bool = False  # Debug 模式：显示思考过程和上下文

    # Agent display state (new)
    current_agent: Optional[AgentDisplay] = AgentDisplay.MAIN  # 默认为主 Agent
    agent_history: List[Dict[str, Any]] = None  # List of {agent, status, timestamp}
    tool_logs: List[Dict[str, Any]] = None  # List of {tool, args, status, duration}

    def __post_init__(self):
        if self.agent_history is None:
            self.agent_history = []
        if self.tool_logs is None:
            self.tool_logs = []


class MiniCoderConsole:
    """Console-based TUI for mini-coder using Rich.

    This class provides a REPL-style terminal interface with:
    - Welcome message
    - Working mode indicator
    - Simple input handling with immediate character echo
    - Backspace support
    - Mode switching with Tab
    - Ctrl+C and Ctrl+D for exit
    """

    TITLE = "mini-coder"

    def __init__(self, config: Config, directory: str | None = None) -> None:
        """Initialize the console application.

        Args:
            config: Configuration for the application.
            directory: Optional working directory path.
        """
        self.config = config
        # Use force_terminal to ensure Rich doesn't interfere with cbreak mode
        self._console = Console(force_terminal=True)
        self._working_directory: Path | None = None
        self._state = AppState.IDLE
        self._ui_state = UIState()
        self._thinking_history = ThinkingHistory()

        if directory:
            self._working_directory = Path(directory).resolve()

        # Agent callback support
        self._orchestrator = None  # Will be set when orchestrator is created
        self._tui_task_id = f"tui-session-{int(time.time())}"

        # 非 TTY 时从 /dev/tty 读入，避免 stdin 为管道时执行一次命令后 readline() 即 EOF 导致直接退出
        self._repl_input_stream = None  # 在 run() 中按 is_tty 设置

        # Set up signal handlers for clean exit
        signal.signal(signal.SIGINT, self._handle_sigint)

    def _handle_sigint(self, signum: int, frame: object) -> None:
        """Handle SIGINT (Ctrl+C) for clean exit."""
        self._console.print("\n[yellow]Interrupted by user[/yellow]")
        sys.exit(130)

    @property
    def working_directory(self) -> Path | None:
        """Get the current working directory."""
        return self._working_directory

    @working_directory.setter
    def working_directory(self, value: Path | None) -> None:
        """Set the working directory."""
        self._working_directory = value
        # Update config if remembering last directory
        if value and self.config.working_directory.remember_last:
            self.config.working_directory.default_path = str(value)

    @property
    def state(self) -> AppState:
        """Get the current application state."""
        return self._state

    def set_state(self, state: AppState) -> None:
        """Set the application state.

        Args:
            state: New application state.
        """
        old_state = self._state
        self._state = state
        logging.debug(f"State changed: {old_state.value} -> {state.value}")

    def _toggle_working_mode(self) -> None:
        """Toggle to the next working mode in cycle."""
        modes = list(WorkingMode)
        current_index = modes.index(self._ui_state.working_mode)
        next_index = (current_index + 1) % len(modes)
        self._ui_state.working_mode = modes[next_index]
        logging.info(f"Working mode changed to: {self._ui_state.working_mode}")

    def _display_header(self) -> None:
        """Display the welcome message."""
        self._console.print()
        header_text = "[bold cyan]mini-coder[/bold cyan] [dim]AI Coding Assistant[/dim]"

        # Add debug indicator
        if self._ui_state.debug_mode:
            header_text += "  [bold yellow][DEBUG][/bold yellow]"

        # Add working directory if set
        if self._working_directory:
            header_text += f"  •  [dim]Work Dir: {self._working_directory}[/dim]"

        self._console.print(
            Panel.fit(
                header_text,
                border_style="cyan",
            )
        )
        self._console.print(
            "[dim]Type /help for available commands[/dim]"
        )
        self._console.print()

    def _get_user_input(self) -> str | None:
        """Get user input with agent indicator.

        Uses a custom implementation that provides immediate character echo.
        Handles:
        - Immediate character display
        - Backspace
        - Enter key
        - Ctrl+C and Ctrl+D for exit

        Returns:
            User input string, or None if user wants to exit.
        """
        try:
            # Display current agent name
            mode_display = Text()
            if self._ui_state.current_agent:
                mode_display.append(str(self._ui_state.current_agent), style="bold cyan")
            else:
                mode_display.append("Main", style="bold cyan")
            mode_display.append(" ▶ ", style="default")

            buffer = ""

            while True:
                # Clear and redraw prompt with current buffer
                sys.stdout.write("\r\033[K")  # Clear line
                self._console.print(mode_display, end="")
                sys.stdout.write(buffer)
                sys.stdout.flush()

                # Read single character
                try:
                    char = sys.stdin.read(1)
                except (EOFError, OSError, IOError):
                    # Handle EOF or I/O errors (can occur after Rich Console output in cbreak mode)
                    logging.debug("stdin.read(1) raised exception, returning empty buffer")
                    return buffer.strip() if buffer else ""

                # Handle empty character (EOF in cbreak mode)
                if not char:
                    return buffer.strip() if buffer else ""

                # Handle Ctrl+C：若刚因 None 提示过“再次输入以继续”，则忽略本次 0x03 一次，避免误判为连续两次中断退出（见 docs/tui-repl-exit-analysis.md）
                if ord(char) == 3:  # Ctrl+C
                    if getattr(self, "_repl_ignore_next_interrupt", False):
                        self._repl_ignore_next_interrupt = False
                        continue
                    self._console.print()
                    return None

                # Handle Ctrl+D (EOF)：同上，忽略一次
                if ord(char) == 4:  # Ctrl+D
                    if getattr(self, "_repl_ignore_next_interrupt", False):
                        self._repl_ignore_next_interrupt = False
                        continue
                    self._console.print()
                    return None

                # Handle Enter key
                if char == "\r" or char == "\n":
                    self._console.print()
                    return buffer.strip()

                # Handle backspace
                if char and (char == "\x7f" or char == "\b"):
                    if buffer:
                        buffer = buffer[:-1]
                    continue

                # Handle escape sequences (arrow keys)
                if char and char == "\x1b":
                    try:
                        sys.stdin.read(1)
                        if sys.stdin.read(1):
                            pass  # arrow key - ignored
                    except (EOFError, OSError, IOError):
                        pass  # Ignore I/O errors when reading escape sequences
                    continue

                # Handle printable characters
                if char and ord(char) >= 32:
                    buffer += char

        except KeyboardInterrupt:
            self._console.print()
            return None

    def _get_user_input_simple(self) -> str | None:
        """Get user input for non-TTY (piped/redirected) input.

        This method reads from stdin directly, properly handling EOF for
        piped or redirected stdin without interfering with pytest output capture.

        Returns:
            User input string, or None if EOF reached.
        """
        inp = getattr(self, "_repl_input_stream", None) or sys.stdin
        try:
            mode_display = Text()
            if self._ui_state.current_agent:
                mode_display.append(str(self._ui_state.current_agent), style="bold cyan")
            else:
                mode_display.append("Main", style="bold cyan")
            mode_display.append(" ▶ ", style="default")
            self._console.print(mode_display, end="")

            # Read a line from stdin or /dev/tty（非 TTY 时 run() 会设为 /dev/tty，避免管道首行后即 EOF 退出）
            line = inp.readline()

            if not line:  # EOF reached
                return None

            self._console.print()  # Move to new line after input
            return line.strip()

        except (EOFError, OSError):
            # EOF reached or stdin closed
            return None

    def _get_llm_config_path(self) -> Path | None:
        """Resolve path to LLM config (config/llm.yaml).

        Prefers working_directory/config/llm.yaml, then cwd/config/llm.yaml.
        """
        for base in (self._working_directory, Path.cwd()):
            if base is None:
                continue
            path = base / "config" / "llm.yaml"
            if path.is_file():
                return path
        # Fallback: cwd when no working_directory set
        path = Path.cwd() / "config" / "llm.yaml"
        return path if path.is_file() else None

    def _ensure_llm_service(self, init_session: bool = True) -> bool:
        """确保 LLM 服务已初始化；若尚未初始化则创建，可选恢复/启动会话。

        Args:
            init_session: 为 True 时在首次创建后恢复或启动会话（正常对话需要）；
                为 False 时仅创建服务不恢复/启动会话（用于 /clear 等，避免耗时 I/O）。

        Returns:
            True 表示已有或已成功创建 LLM 服务，False 表示无配置文件无法创建。
        """
        from mini_coder.llm.service import LLMService

        llm_config_path = self._get_llm_config_path()
        if not llm_config_path:
            return False
        if not hasattr(self, '_llm_service') or self._llm_service is None:
            self._llm_service = LLMService(str(llm_config_path))
            need_session = init_session and self._llm_service.memory_enabled
            if need_session:
                if not self._llm_service.restore_latest_session():
                    self._llm_service.start_session(
                        str(self._working_directory) if self._working_directory else None
                    )
            self._llm_session_initialized = need_session
        else:
            # 服务已存在但可能由 /clear 仅创建未初始化会话，在需要时补做
            if init_session and not getattr(self, '_llm_session_initialized', True):
                if self._llm_service.memory_enabled:
                    if not self._llm_service.restore_latest_session():
                        self._llm_service.start_session(
                            str(self._working_directory) if self._working_directory else None
                        )
                self._llm_session_initialized = True
        return True

    def _ensure_orchestrator(self) -> bool:
        """确保已创建 WorkflowOrchestrator 并注册 TUI 回调，用于 agent 派发与流转记录。

        Returns:
            True 表示已有或已成功创建并注册 orchestrator，False 表示无法创建（如无 LLM 配置）。
        """
        if not self._ensure_llm_service():
            return False
        if self._orchestrator is not None:
            return True
        try:
            from mini_coder.agents.orchestrator import (
                WorkflowOrchestrator,
                WorkflowConfig,
            )
            self._orchestrator = WorkflowOrchestrator(
                llm_service=self._llm_service,
                config=WorkflowConfig(),
                command_executor=None,
            )
            # 交互式会话：创建可复用上下文，确保 TUI 跨轮共享 Blackboard
            self._orchestrator.ensure_interactive_context(task_id=self._tui_task_id)
            self.register_agent_callback(self._orchestrator)
            logging.info("Orchestrator created and callbacks registered for TUI")
        except Exception as e:
            logging.exception("Failed to create orchestrator: %s", e)
            self._orchestrator = None
            return False
        return True

    def _set_orchestrator_work_dir(self) -> None:
        """将当前工作目录写入 orchestrator blackboard，供 Coder 等子代理使用真实路径。"""
        if self._orchestrator is None:
            return
        ctx = getattr(self._orchestrator, "_context", None)
        if ctx is None:
            return
        work_dir = getattr(self, "_working_directory", None) or getattr(
            self, "working_directory", None
        )
        if work_dir is not None:
            ctx.blackboard.set_context("work_dir", str(work_dir))

    class _RouteDecision(TypedDict, total=False):
        route: Literal["main", "dispatch", "workflow"]
        agent: Literal[
            "EXPLORER",
            "PLANNER",
            "CODER",
            "REVIEWER",
            "BASH",
            "GENERAL_PURPOSE",
            "MINI_CODER_GUIDE",
        ]
        bash_mode: Literal["quality_report", "confirm_save", "single_command"]
        confidence: float
        reason: str

    # 路由用 system 提示，与主对话隔离，不写入 _context_manager；BASH 的 bash_mode 由路由层决定
    # 各子 agent 职责写清，便于区分 BASH（执行命令）与 CODER（写代码/编辑内容），参考 Claude Code bash command 语义
    _ROUTER_SYSTEM = (
        "你是一个路由器，只负责根据用户输入决定：由主代理直接回答，还是派发到哪个子代理，或进入多阶段工作流。\n"
        "要求：\n"
        "- 只输出一行 JSON，禁止输出除 JSON 以外的任何字符。\n"
        "- JSON 字段：\n"
        '  - route: "main" | "dispatch" | "workflow"\n'
        '  - agent: 仅当 route=dispatch 时必填，取值见下\n'
        '  - bash_mode: 仅当 agent=BASH 时必填，取值 quality_report | confirm_save | single_command（见 BASH 说明）\n'
        "  - confidence: 0~1\n"
        "  - reason: 简短中文原因\n"
        "路由规则：\n"
        '- "main": 闲聊/解释性问答，不需要工具、不需要改代码。\n'
        '- "dispatch": 需要派发到下列某一子代理，按职责选 agent：\n'
        "  - EXPLORER: 只读探索代码库（找文件、看结构、理解依赖），不写代码不执行命令。\n"
        "  - PLANNER: 需求分析、任务拆解、TDD 规划、写 implementation_plan.md。\n"
        "  - CODER: 编写或编辑代码/文件内容（实现功能、新建或修改源文件）。\n"
        "  - REVIEWER: 代码质量与架构对齐评审（只读，不执行命令）。\n"
        "  - BASH: 终端执行。选 BASH 时必填 bash_mode：quality_report=用户要跑测试/验证质量/生成质量报告；confirm_save=用户要「把代码写入本地/保存到本地/确认已写入」仅列目录不跑测试；single_command=用户给了一条具体命令（如 ls、pytest）。若意图是写代码/实现功能应选 CODER。\n"
        "  - GENERAL_PURPOSE: 快速只读搜索、通用代码查找。\n"
        "  - MINI_CODER_GUIDE: 回答与 mini-coder 本身的使用、配置、工作流问题。\n"
        '- "workflow": 用户明确要“从需求到实现到测试”的完整闭环，或多步骤连续执行（规划→实现→测试/验证）。\n'
        "只输出一行 JSON，不要其他字符。"
    )

    def _route_by_heuristic(self, user_input: str) -> Optional["_RouteDecision"]:
        """扩展路由启发式：仅对「几乎不会误判」的输入直接返回 route=main，避免路由 LLM 调用。

        可靠性原则：宁可多走一次路由 LLM（仅多 1～5s），也不把本该派发/工作流的请求误判成主代理直答。
        因此只做「寒暄、致谢/告别、极短确认」等明确场景；不含歧义短句（如「如何优化」可能是解释也可能是派 CODER）。
        未命中返回 None，交给 LLM 路由。
        """
        s = user_input.strip()
        if not s:
            return None
        low = s.lower()

        # 1. 寒暄（几乎不会误判）
        if low in {"hi", "hello", "你好", "在吗", "嗨"} or (
            len(s) <= 4 and any(x in low for x in ("你好", "hi"))
        ):
            return {"route": "main", "confidence": 0.9, "reason": "简单寒暄，主代理可直接回复"}

        # 2. 致谢 / 告别 / 极短确认（主代理即可回复，不会与「派发/工作流」混淆）
        if low in {
            "谢谢", "感谢", "多谢", "再见", "bye", "好的", "ok", "okay",
            "好", "行", "可以", "嗯", "对", "是", "收到", "知道了", "明白了",
            "好哒", "好的呀", "没问题",
        }:
            return {"route": "main", "confidence": 0.85, "reason": "致谢/告别/确认，主代理可直接回复"}

        # 不在此处做「短句纯问答」等歧义规则，避免该路由时不路由（如「如何优化」可能指派 CODER）
        return None

    def _route_user_input(self, user_input: str) -> "_RouteDecision":
        """用 LLM 生成结构化路由决策（主代理直答 vs 子代理派发 vs 工作流）。"""
        # 扩展启发式：命中则直接走主代理，避免路由 LLM 调用
        heuristic = self._route_by_heuristic(user_input)
        if heuristic is not None:
            return heuristic

        if not self._ensure_llm_service():
            return {"route": "dispatch", "confidence": 0.0, "reason": "LLM 服务不可用，回退到 dispatch"}

        try:
            # 一次性调用，不写入主对话历史，避免主 agent 看到“路由器”上下文
            t_route_start = time.perf_counter()
            raw = self._llm_service.chat_one_shot(
                self._ROUTER_SYSTEM,
                user_input,
            ).strip()
            logging.debug(
                "[TUI] _route_user_input: chat_one_shot latency=%.3fs",
                time.perf_counter() - t_route_start,
            )
            decision = json.loads(raw)
            if not isinstance(decision, dict):
                raise ValueError("route decision is not a dict")
            return decision
        except Exception as e:
            logging.warning("Route decision parse failed; fallback to dispatch: %s", e)
            return {"route": "dispatch", "confidence": 0.0, "reason": "路由解析失败，回退到 dispatch"}

    # Loop detection constants
    MAX_RESPONSE_LENGTH = 50000  # Maximum characters in a single response
    MAX_REPEATED_PATTERN = 5     # Maximum times a pattern can repeat consecutively
    PATTERN_MIN_LENGTH = 5       # Minimum length for pattern detection

    def _detect_loop(self, content: str, full_response: str) -> bool:
        """Detect if the LLM is in a loop.

        Args:
            content: The latest chunk of content.
            full_response: The full response so far.

        Returns:
            True if a loop is detected, False otherwise.
        """
        # Check 1: Maximum response length
        if len(full_response) > self.MAX_RESPONSE_LENGTH:
            logging.warning(f"Loop detected: response exceeded {self.MAX_RESPONSE_LENGTH} chars")
            return True

        # Check 2: Repeated pattern detection
        # Look for patterns that repeat consecutively
        if len(content) >= self.PATTERN_MIN_LENGTH:
            # Check if the last N chars repeat more than MAX_REPEATED_PATTERN times
            for pattern_len in range(self.PATTERN_MIN_LENGTH, min(len(content) + 1, 50)):
                pattern = content[-pattern_len:]
                # Count consecutive repetitions at the end of full_response
                count = 0
                pos = len(full_response)
                while pos >= pattern_len and full_response[pos - pattern_len:pos] == pattern:
                    count += 1
                    pos -= pattern_len

                if count >= self.MAX_REPEATED_PATTERN:
                    logging.warning(f"Loop detected: pattern '{pattern[:20]}...' repeated {count} times")
                    return True

        # Check 3: Known loop patterns (e.g., "Unknown" repeating)
        known_patterns = ["Unknown", "undefined", "null", "NaN", "ERROR"]
        for pattern in known_patterns:
            # Check if pattern appears many times consecutively
            repeated = pattern * self.MAX_REPEATED_PATTERN
            if repeated in full_response:
                logging.warning(f"Loop detected: known pattern '{pattern}' repeating")
                return True

        return False

    def _format_duration_color(
        self,
        sec: float,
        no_response: bool = False,
        to_first_sec: Optional[float] = None,
    ) -> str:
        """按耗时返回带 Rich 颜色标记的耗时文案（快绿/中黄/慢红）。"""
        def _color(s: float) -> str:
            if s < DURATION_FAST_S:
                return "green"
            if s < DURATION_SLOW_S:
                return "yellow"
            return "bold red"

        parts: List[str] = []
        if to_first_sec is not None:
            parts.append(f"[{_color(to_first_sec)}]首字 {to_first_sec:.2f}s[/{_color(to_first_sec)}]")
        text = f"本次对话耗时 {sec:.2f}s"
        if no_response:
            text += "（未获得响应）"
        parts.append(f"[{_color(sec)}]{text}[/{_color(sec)}]")
        return "，".join(parts)

    def _call_orchestrator_dispatch_and_display(
        self,
        user_input: str,
        forced_agent: Optional[str] = None,
        route_decision: Optional["_RouteDecision"] = None,
    ) -> Tuple[bool, Optional[float], Optional[float], bool]:
        """经 WorkflowOrchestrator 派发子 agent 执行并展示结果；支持子 agent 流式输出与首字耗时。

        当 forced_agent 为 BASH 时，从 route_decision 读取 bash_mode 传入 context，供 BashAgent 分支（质量流水线 / 确认写入 / 单条命令）。
        Returns:
            (是否成功, 本次总耗时秒数, 首字耗时, 是否有输出内容)
        """
        if self._orchestrator is None:
            return (False, None, None, False)
        t_start = time.perf_counter()
        t_first_token: Optional[float] = None
        had_streaming = False

        def stream_callback(content: str) -> None:
            nonlocal t_first_token, had_streaming
            if t_first_token is None:
                t_first_token = time.perf_counter()
            had_streaming = True
            self._console.print(content, end="")
            if getattr(self._console, "file", None) is not None:
                self._console.file.flush()

        try:
            if forced_agent:
                from mini_coder.agents.orchestrator import SubAgentType

                agent_type = SubAgentType[forced_agent]
                dispatch_context: Optional[Dict[str, Any]] = None
                # 仅当路由明确返回 bash_mode 时传入；不默认 quality_report（质量流水线由用户/Orchestrator 显式触发，见 docs/quality-pipeline-spec.md）
                if agent_type == SubAgentType.BASH and route_decision and route_decision.get("bash_mode"):
                    dispatch_context = {"bash_mode": route_decision["bash_mode"]}
                result = self._orchestrator.dispatch_with_agent(
                    agent_type,
                    user_input,
                    context=dispatch_context,
                    stream_callback=stream_callback,
                )
            else:
                result = self._orchestrator.dispatch(
                    user_input, stream_callback=stream_callback
                )
        except Exception as e:
            logging.exception("Orchestrator dispatch failed: %s", e)
            duration_sec = time.perf_counter() - t_start
            self._console.print(f"[red]派发失败: {e}[/red]")
            return (False, duration_sec, None, False)
        duration_sec = time.perf_counter() - t_start
        ok = getattr(result, "success", False)
        output = getattr(result, "output", "") or ""
        error = getattr(result, "error", "") or ""
        if had_streaming:
            self._console.print()
        elif output:
            self._console.print(Markdown(output))
        if not ok and error:
            self._console.print(Panel(f"[red]{error}[/red]", title="错误", border_style="red"))
        duration_to_first = (t_first_token - t_start) if t_first_token is not None else None
        had_output = had_streaming or bool(output.strip())
        return (ok, duration_sec, duration_to_first, had_output)

    def _call_orchestrator_workflow_and_display(
        self, user_input: str
    ) -> Tuple[bool, Optional[float], Optional[float]]:
        """执行多阶段工作流（主代理依次调用子代理），并展示结果。"""
        if self._orchestrator is None:
            return (False, None, None)
        t_start = time.perf_counter()
        try:
            # 复用 TUI 会话的 task_id/Blackboard，确保跨轮共享工件
            result = self._orchestrator.execute_workflow(user_input, task_id=self._tui_task_id)
        except Exception as e:
            logging.exception("Orchestrator workflow failed: %s", e)
            duration_sec = time.perf_counter() - t_start
            self._console.print(f"[red]工作流失败: {e}[/red]")
            return (False, duration_sec, None)
        duration_sec = time.perf_counter() - t_start
        ok = getattr(result, "success", False)
        output = getattr(result, "output", "") or ""
        error = getattr(result, "error", "") or ""
        if output:
            self._console.print(Markdown(output))
        if not ok and error:
            self._console.print(Panel(f"[red]{error}[/red]", title="错误", border_style="red"))
        return (ok, duration_sec, None)

    # 思考段标签，用于流式解析并红色框显
    _TAG_THINKING_OPEN = "<thinking>"
    _TAG_THINKING_CLOSE = "</thinking>"

    def _parse_thinking_buffer(
        self,
        buffer: str,
        in_thinking: bool,
    ) -> Tuple[str, str, str, bool]:
        """解析 buffer 中的 <thinking> / </thinking>，返回 (普通文本, 红色文本, 剩余 buffer, 是否在 thinking 内)。

        跨 chunk 时保留可能未完整的标签在 buffer 中。
        """
        normal_parts: List[str] = []
        red_parts: List[str] = []
        tag_open = self._TAG_THINKING_OPEN
        tag_close = self._TAG_THINKING_CLOSE

        while True:
            if not in_thinking:
                idx = buffer.find(tag_open)
                if idx != -1:
                    normal_parts.append(buffer[:idx])
                    red_parts.append(tag_open)
                    buffer = buffer[idx + len(tag_open) :]
                    in_thinking = True
                    continue
                # 可能末尾是标签前缀，保留
                keep = len(tag_open) - 1
                if len(buffer) > keep:
                    normal_parts.append(buffer[: -keep] if keep else buffer)
                    buffer = buffer[-keep:] if keep else ""
                break
            else:
                idx = buffer.find(tag_close)
                if idx != -1:
                    red_parts.append(buffer[:idx])
                    red_parts.append(tag_close)
                    buffer = buffer[idx + len(tag_close) :]
                    in_thinking = False
                    continue
                keep = len(tag_close) - 1
                if len(buffer) > keep:
                    red_parts.append(buffer[: -keep] if keep else buffer)
                    buffer = buffer[-keep:] if keep else ""
                break

        normal_str = "".join(normal_parts)
        red_str = "".join(red_parts)
        return (normal_str, red_str, buffer, in_thinking)

    def _call_llm_stream_and_display(
        self, user_input: str
    ) -> Tuple[bool, Optional[float], Optional[float]]:
        """Run streaming LLM call and display output (sync, optimized).

        Returns:
            (是否得到有效响应, 本次对话总耗时秒数, 首字/首 token 耗时秒数；未计时时为 None)
        """
        if not self._ensure_llm_service():
            logging.warning("LLM config not found (config/llm.yaml); skipping LLM call")
            return (False, None, None)
        t_start = time.perf_counter()
        t_first_token: Optional[float] = None
        duration_sec: Optional[float] = None
        got_response = False
        try:
            # Debug 模式：显示上下文信息
            if self._ui_state.debug_mode:
                self._show_debug_context(user_input)

            # 使用同步流式方法（避免 asyncio.run 开销）
            first = True
            full_response = ""
            loop_detected = False
            think_buffer = ""
            in_thinking = False

            for event in self._llm_service.chat_stream(user_input):
                if event.get("type") == "delta":
                    content = event.get("content") or ""
                    if content:
                        # 首字/首 token：第一次收到并即将显示内容时打点
                        if first:
                            t_first_token = time.perf_counter()
                        full_response += content

                        # Check for loop
                        if self._detect_loop(content, full_response):
                            loop_detected = True
                            self._console.print()
                            self._console.print(
                                "\n[yellow]⚠ Response interrupted: loop detected[/yellow]"
                            )
                            logging.warning("LLM response interrupted due to loop detection")
                            break

                        # 解析 <thinking>...</thinking>，红色框显思考段
                        think_buffer += content
                        normal_str, red_str, think_buffer, in_thinking = self._parse_thinking_buffer(
                            think_buffer, in_thinking
                        )
                        if normal_str:
                            self._console.print(normal_str, end="")
                        if red_str:
                            self._console.print(red_str, end="", style="red")
                        if getattr(self._console, "file", None) is not None:
                            self._console.file.flush()
                        first = False

            # 流结束：剩余 buffer 按当前状态输出
            if think_buffer:
                if in_thinking:
                    self._console.print(think_buffer, end="", style="red")
                else:
                    self._console.print(think_buffer, end="")
            self._console.print()

            if loop_detected:
                self._console.print(
                    "[dim]The AI response was interrupted to prevent infinite output. "
                    "This may indicate an issue with the model or context.[/dim]"
                )

            # Debug 模式：显示额外信息
            if self._ui_state.debug_mode:
                self._show_debug_response_info(full_response)

            got_response = not first
        except Exception as e:
            logging.exception("LLM stream failed: %s", e)
        finally:
            duration_sec = time.perf_counter() - t_start
        duration_to_first_sec = (t_first_token - t_start) if t_first_token is not None else None
        return (got_response, duration_sec, duration_to_first_sec)

    def _show_debug_context(self, user_input: str) -> None:
        """Debug 模式下显示 LLM 上下文信息。"""
        self._console.print("\n[dim bold]=== LLM Context (Debug) ===[/dim bold]")

        # 显示上下文统计
        if hasattr(self._llm_service, '_context_builder') and self._llm_service._context_builder:
            builder = self._llm_service._context_builder
            try:
                context = builder.build_with_user_message(user_input, max_tokens=128000)
                total_tokens = builder.estimate_tokens(context)
                msg_count = len(context)

                self._console.print(f"[dim]Messages: {msg_count} | Tokens: ~{total_tokens:,}[/dim]")

                # 显示 system 消息预览
                for msg in context:
                    if msg.get("role") == "system":
                        content = msg.get("content", "")[:200]
                        self._console.print(f"[dim]System: {content}...[/dim]")
                        break
            except Exception as e:
                self._console.print(f"[dim]Context build error: {e}[/dim]")
        else:
            self._console.print("[dim]Context builder not available[/dim]")

        self._console.print()

    def _show_debug_response_info(self, response: str) -> None:
        """Debug 模式下显示响应信息。"""
        self._console.print()
        self._console.print("[dim bold]=== Response Stats (Debug) ===[/dim bold]")
        self._console.print(f"[dim]Response Length: {len(response)} chars[/dim]")

    def _handle_special_commands(self, user_input: str) -> bool:
        """Handle special commands like /memory, /sessions.

        Args:
            user_input: The user input to check.

        Returns:
            True if the input was a special command, False otherwise.
        """
        if not user_input.startswith("/"):
            return False

        command = user_input.lower().strip()

        if command == "/memory":
            self._show_memory_status()
            return True

        if command in ("/sessions", "/session"):
            self._show_sessions()
            return True

        if command.startswith("/save"):
            self._save_current_session()
            return True

        if command.startswith("/restore"):
            self._restore_session(command)
            return True

        if command == "/clear":
            # 清空对话历史。若尚未初始化 LLM 服务则直接提示无历史可清，避免首次创建 LLMService 耗时过长导致卡顿或误触 Ctrl+C 退出。
            try:
                if hasattr(self, "_llm_service") and self._llm_service is not None:
                    self._llm_service.clear_history()
                    self._console.print("[dim yellow]对话历史已清除。[/dim yellow]")
                else:
                    # 未初始化过 LLM 服务则无需创建，直接提示，保证 /clear 瞬时完成
                    self._console.print("[dim yellow]当前无对话历史。[/dim yellow]")
                # Ensure output is flushed before reading next input
                sys.stdout.flush()
            except Exception as e:
                logging.warning(f"/clear failed: {e}", exc_info=True)
                self._console.print(f"[dim yellow]清除对话历史时出错：{e}[/dim yellow]")
            return True

        if command == "/debug":
            # 切换 debug 模式
            self._ui_state.debug_mode = not self._ui_state.debug_mode
            status = "已开启" if self._ui_state.debug_mode else "已关闭"
            self._console.print(f"[dim]Debug 模式{status}。再次输入 /debug 切换。[/dim]")
            if self._ui_state.debug_mode:
                self._console.print("[dim] 将显示思考过程和 LLM 上下文信息[/dim]")
            return True

        if command == "/context":
            # 显示当前 LLM 上下文
            if hasattr(self, '_llm_service') and self._llm_service is not None:
                self._show_context_info()
            else:
                self._console.print("[dim]LLM 服务未初始化[/dim]")
            return True

        if command == "/help":
            self._show_help()
            return True

        if command == "/agents":
            self._display_agent_history()
            return True

        if command == "/tools":
            self._display_tool_logs()
            return True

        # 未匹配到已知的 slash 命令时，不将其发送给 LLM，直接提示用户
        self._console.print(f"[yellow]未知命令: {command}[/yellow]")
        self._console.print("[dim]输入 /help 查看可用命令列表。[/dim]")
        return True

    def _show_memory_status(self) -> None:
        """Display memory status."""
        if not hasattr(self, '_llm_service') or self._llm_service is None:
            self._console.print("[yellow]Memory: LLM service not initialized[/yellow]")
            return

        if not self._llm_service.memory_enabled:
            self._console.print("[yellow]Memory: Disabled[/yellow]")
            return

        manager = self._llm_service._context_manager
        self._console.print(Panel(
            f"[bold]Memory Status[/bold]\n"
            f"Session ID: {manager.current_session_id or 'None'}\n"
            f"Messages: {manager.message_count}\n"
            f"Token Ratio: {manager.token_ratio:.1%}",
            border_style="blue"
        ))

    def _show_context_info(self) -> None:
        """Display current LLM context info."""
        if not hasattr(self, '_llm_service') or self._llm_service is None:
            self._console.print("[yellow]LLM service not initialized[/yellow]")
            return

        self._console.print(Panel(
            f"[bold]LLM Context Info[/bold]\n\n"
            f"Provider: {self._llm_service.provider_name}\n"
            f"Memory Enabled: {self._llm_service.memory_enabled}\n"
            f"Auto-extract Notes: {self._llm_service._auto_extract_notes}\n",
            border_style="blue"
        ))

        # Show context builder info if available
        if hasattr(self._llm_service, '_context_builder') and self._llm_service._context_builder:
            builder = self._llm_service._context_builder
            context = builder.build_with_user_message("test", max_tokens=128000)
            total_tokens = builder.estimate_tokens(context)
            msg_count = len(context)

            self._console.print(Panel(
                f"[bold]Context Stats[/bold]\n\n"
                f"Messages: {msg_count}\n"
                f"Estimated Tokens: {total_tokens:,}\n"
                f"Max Tokens: 128,000\n"
                f"Usage: {total_tokens / 128000 * 100:.1f}%",
                border_style="green"
            ))
        else:
            self._console.print("[dim]Context builder not available[/dim]")

    def _show_sessions(self) -> None:
        """Display saved sessions."""
        if not hasattr(self, '_llm_service') or self._llm_service is None:
            self._console.print("[yellow]Sessions: LLM service not initialized[/yellow]")
            return

        sessions = self._llm_service.list_sessions()
        if not sessions:
            self._console.print("[yellow]No saved sessions[/yellow]")
            return

        self._console.print(Panel(
            "[bold]Saved Sessions[/bold]\n" + "\n".join(f"  • {s}" for s in sessions),
            border_style="blue"
        ))

    def _save_current_session(self) -> None:
        """Save the current session."""
        if not hasattr(self, '_llm_service') or self._llm_service is None:
            self._console.print("[yellow]Session: LLM service not initialized[/yellow]")
            return

        if not self._llm_service.memory_enabled:
            self._console.print("[yellow]Session: Memory disabled[/yellow]")
            return

        self._llm_service.save_session()
        self._console.print(f"[green]Session saved: {self._llm_service.session_id}[/green]")

    def _restore_session(self, command: str) -> None:
        """Restore a session."""
        if not hasattr(self, '_llm_service') or self._llm_service is None:
            self._console.print("[yellow]Session: LLM service not initialized[/yellow]")
            return

        parts = command.split()
        if len(parts) < 2:
            # Try to restore latest session
            if self._llm_service.restore_latest_session():
                self._console.print(f"[green]Restored latest session: {self._llm_service.session_id}[/green]")
            else:
                self._console.print("[yellow]No session to restore[/yellow]")
            return

        session_id = parts[1]
        if self._llm_service.load_session(session_id):
            self._console.print(f"[green]Restored session: {session_id}[/green]")
        else:
            self._console.print(f"[red]Session not found: {session_id}[/red]")

    def _show_help(self) -> None:
        """Display help for special commands."""
        self._console.print(Panel(
            "[bold]Special Commands[/bold]\n"
            "  /memory   - Show memory status\n"
            "  /sessions - List saved sessions\n"
            "  /save     - Save current session\n"
            "  /restore  - Restore latest session\n"
            "  /restore <id> - Restore specific session\n"
            "  /clear    - Clear chat history\n"
            "  /debug    - Toggle debug mode (show thinking & context)\n"
            "  /context  - Show current LLM context info\n"
            "  /agents   - Show agent history\n"
            "  /tools    - Show recent tool calls\n"
            "  /help     - Show this help",
            border_style="blue"
        ))

    def _cleanup(self) -> None:
        """Cleanup resources before exit."""
        if hasattr(self, '_llm_service') and self._llm_service is not None:
            if self._llm_service.memory_enabled:
                self._llm_service.save_session()

    def _display_thinking(self, message: str = "Processing...") -> None:
        """Display thinking status.

        Args:
            message: Status message to display.
        """
        spinner = Spinner("dots", text=f"[bold blue]{message}[/bold blue]")
        self._console.print(spinner)

    def _display_response(self, response: str) -> None:
        """Display AI response.

        Args:
            response: The response text to display.
        """
        self._console.print(Markdown(response))

    def _display_code(self, code: str, language: str = "python") -> None:
        """Display code with syntax highlighting.

        Args:
            code: The code to display.
            language: Programming language for syntax highlighting.
        """
        self._console.print(Syntax(code, language, theme="monokai", line_numbers=True))

    def _display_mode_footer(self) -> None:
        """Display the mode footer."""
        self._console.print(
            f"Mode: [bold green]{self._ui_state.working_mode}[/bold green]",
            justify="right",
        )

    # ==================== Agent Callback Methods ====================

    def on_agent_event(
        self,
        agent_type: Any,
        event_type: str,
        result: Optional[Any] = None
    ) -> None:
        """Agent event callback for TUI display.

        Args:
            agent_type: The agent type (SubAgentType enum value)
            event_type: "started" or "completed"
            result: EnhancedAgentResult (only for completed events)
        """
        agent_display = AgentDisplay.from_agent_type(agent_type)
        loop = asyncio.get_event_loop()
        timestamp = loop.time() if loop.is_running() else 0

        if event_type == "started":
            self._ui_state.current_agent = agent_display
            self._ui_state.agent_history.append({
                "agent": agent_display.value,
                "status": "started",
                "timestamp": timestamp,
            })
            self._console.print()
            self._console.print(f"[bold cyan][{agent_display.value}] 开始执行...[/bold cyan]")

        elif event_type == "completed":
            status = "completed" if result and result.success else "failed"
            self._ui_state.agent_history.append({
                "agent": agent_display.value,
                "status": status,
                "timestamp": timestamp,
            })
            self._console.print(f"[dim][{agent_display.value}] 执行{'完成' if status == 'completed' else '失败'}[/dim]")
            # 恢复为主 Agent 状态
            self._ui_state.current_agent = AgentDisplay.MAIN

    def on_tool_called(
        self,
        tool_name: str,
        args: str,
        status: str = "completed",
        duration: float = 0.0,
        result: Optional[str] = None
    ) -> None:
        """Tool call callback for TUI display.

        Args:
            tool_name: Name of the tool
            args: Tool arguments
            status: Tool status (starting, completed, failed)
            duration: Tool execution duration in seconds
            result: Tool result (optional)
        """
        import time

        log_entry = {
            "tool": tool_name,
            "args": args,
            "status": status,
            "duration": duration,
            "timestamp": time.time(),
        }
        self._ui_state.tool_logs.append(log_entry)

        if status == "starting":
            self._console.print(f"  ↳ [dim][Tool] {tool_name}: {args}[/dim]")
        elif status == "completed":
            self._console.print(f"  ↳ [green][Tool] {tool_name}[/green] [dim]({duration:.2f}s)[/dim]")
        elif status == "failed":
            self._console.print(f"  ↳ [red][Tool] {tool_name} (FAILED)[/red]")

    def register_agent_callback(self, orchestrator: Any) -> None:
        """Register agent callback with orchestrator.

        Args:
            orchestrator: WorkflowOrchestrator instance
        """
        self._orchestrator = orchestrator
        orchestrator.register_agent_callback(self.on_agent_event)
        orchestrator.register_tool_callback(self.on_tool_called)

    def _display_agent_status(self) -> None:
        """Display current agent status."""
        if self._ui_state.current_agent:
            self._console.print(
                f"[dim]Current Agent: {self._ui_state.current_agent.value}[/dim]",
                justify="right",
            )

    def _display_tool_logs(self, limit: int = 10) -> None:
        """Display recent tool logs.

        Args:
            limit: Maximum number of tool logs to display
        """
        recent_logs = self._ui_state.tool_logs[-limit:]
        if recent_logs:
            self._console.print("\n[dim]=== Recent Tool Calls ===[/dim]")
            for log in recent_logs:
                status_icon = "✓" if log["status"] == "completed" else "✗" if log["status"] == "failed" else "…"
                self._console.print(
                    f"  {status_icon} {log['tool']}: {log['args']} [dim]({log['duration']:.2f}s)[/dim]"
                )

    def _display_agent_history(self, limit: int = 5) -> None:
        """Display recent agent history.

        Args:
            limit: Maximum number of agent history entries to display
        """
        recent_history = self._ui_state.agent_history[-limit:]
        if recent_history:
            self._console.print("\n[dim]=== Agent History ===[/dim]")
            for entry in recent_history:
                status_icon = "✓" if entry["status"] == "completed" else "✗" if entry["status"] == "failed" else "…"
                self._console.print(f"  {status_icon} {entry['agent']}")

    def run(self) -> int:
        """Run the console application.

        Returns:
            Exit code (0 for success, non-zero for error).
        """
        # Set terminal to raw mode for character-by-character input
        import termios
        import tty

        old_settings = None
        is_tty = sys.stdin.isatty()

        try:
            logging.info("mini-coder console started")

            # Save terminal settings (if available and it's a TTY)
            if is_tty:
                try:
                    old_settings = termios.tcgetattr(sys.stdin.fileno())
                    tty.setcbreak(sys.stdin.fileno())
                except (OSError, AttributeError, io.UnsupportedOperation, termios.error):
                    # Running in test environment or non-tty
                    is_tty = False

            # Display welcome message
            self._display_header()

            # 非 TTY 时尽量从控制终端读入，避免管道 stdin 在首行后即 EOF 导致退出
            if not is_tty:
                try:
                    self._repl_input_stream = open("/dev/tty", "r", encoding="utf-8")
                except Exception:
                    self._repl_input_stream = sys.stdin
            else:
                self._repl_input_stream = sys.stdin

            # Main REPL loop
            while True:
                # Get user input（捕获 I/O 异常，避免 /clear 等操作后下一轮读输入时直接退出）
                try:
                    if is_tty:
                        user_input = self._get_user_input()
                    else:
                        user_input = self._get_user_input_simple()
                except Exception as e:
                    logging.warning(f"Get input error: {e}", exc_info=True)
                    self._console.print("[yellow]Input error, please try again.[/yellow]")
                    user_input = ""

                # Check for exit conditions：首次收到 EOF/中断不立即退出，避免管道或终端在命令/响应后误报导致直接退出（见 docs/tui-repl-exit-analysis.md）
                if user_input is None:
                    _none_count = getattr(self, "_repl_none_count", 0) + 1
                    self._repl_none_count = _none_count
                    if _none_count >= 2:
                        break
                    self._console.print(
                        "[dim]输入结束 (EOF) 或中断。再次输入以继续，或再触发一次以退出。[/dim]"
                    )
                    # TTY 模式下下一轮读到的第一个 0x03/0x04 视为误触，忽略一次，避免“连续两次中断”误退出
                    if is_tty:
                        self._repl_ignore_next_interrupt = True
                    continue
                self._repl_none_count = 0  # 成功读到输入则重置
                self._repl_ignore_next_interrupt = False

                # Check for quit commands
                if user_input.lower() in ("q", "quit", "exit"):
                    break

                # Check for empty input (Enter without typing)
                if not user_input:
                    continue

                # Handle special commands（捕获 KeyboardInterrupt，避免命令执行中误触 Ctrl+C 导致进程直接退出，见 docs/tui-repl-exit-analysis.md）
                try:
                    if self._handle_special_commands(user_input):
                        continue
                except KeyboardInterrupt:
                    self._console.print("[dim]已取消。[/dim]")
                    continue

                # Process the input
                self.set_state(AppState.RUNNING)
                logging.info(f"Processing user input: {user_input[:50]}...")

                # Show thinking status, then newline so response appears below
                self._display_thinking("Processing your request...")
                self._console.print()

                # 路由：主代理直答 vs 子代理派发 vs 多阶段工作流
                t_before_route = time.perf_counter()
                decision = self._route_user_input(user_input)
                route = decision.get("route") or "dispatch"
                had_output = True  # 非 dispatch 分支不显示「无响应」；dispatch 分支会覆盖
                logging.debug(
                    "[TUI] route decision total=%.3fs, route=%s",
                    time.perf_counter() - t_before_route,
                    route,
                )

                if route == "main":
                    ok, duration_sec, duration_to_first_sec = self._call_llm_stream_and_display(
                        user_input
                    )
                else:
                    use_orchestrator = self._ensure_orchestrator()
                    # 派发前注入工作目录，供 Coder 等子代理使用真实路径（避免模型输出 /home/user/...）
                    self._set_orchestrator_work_dir()
                    if not use_orchestrator:
                        ok, duration_sec, duration_to_first_sec = self._call_llm_stream_and_display(
                            user_input
                        )
                    elif route == "workflow":
                        ok, duration_sec, duration_to_first_sec = self._call_orchestrator_workflow_and_display(
                            user_input
                        )
                    else:
                        forced_agent = decision.get("agent")
                        ok, duration_sec, duration_to_first_sec, had_output = self._call_orchestrator_dispatch_and_display(
                            user_input, forced_agent=forced_agent, route_decision=decision
                        )
                self._console.print()
                if not ok and not had_output:
                    self._console.print(
                        Panel(
                            f"[bold]Input received:[/bold] {user_input}\n\n"
                            "[dim]No response (check config/llm.yaml and API keys).[/dim]",
                            border_style="blue",
                        )
                    )
                    self._console.print()
                # 在响应（或无响应提示）之后展示本次对话耗时（首字 + 总耗时）
                if duration_sec is not None:
                    self._console.print(
                        self._format_duration_color(
                            duration_sec,
                            no_response=not ok,
                            to_first_sec=duration_to_first_sec,
                        )
                    )

                self.set_state(AppState.IDLE)

            self._console.print("[yellow]Goodbye![/yellow]")

            # Save session before exit
            self._cleanup()

            return 0

        except Exception as e:
            logging.error(f"Application error: {e}", exc_info=True)
            self._console.print(f"[red]Error: {e}[/red]")
            return 1
        finally:
            # Restore terminal settings
            if old_settings is not None:
                try:
                    termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, old_settings)
                except Exception:
                    pass
            # 关闭非 stdin 的 REPL 输入流（如 /dev/tty），避免句柄泄漏
            repl_inp = getattr(self, "_repl_input_stream", None)
            if repl_inp is not None and repl_inp is not sys.stdin and not repl_inp.closed:
                try:
                    repl_inp.close()
                except Exception:
                    pass


def run_console_app(config: Config, directory: str | None = None) -> int:
    """Run the console application.

    Args:
        config: Configuration for the application.
        directory: Optional working directory path.

    Returns:
        Exit code (0 for success, non-zero for error).
    """
    app = MiniCoderConsole(config, directory=directory)
    return app.run()

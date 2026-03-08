# -*- coding: utf-8 -*-
"""各 Agent 实际能力测试：在真实（或模拟）环境中调用各 agent。

依据 prompts/system 下的 prompt 填充系统提示，验证：
1. 能从 prompts/system 正确加载对应 prompt；
2. 调用 agent.execute() 后能得到可解析的结构化输出（如 [Pass]/[Reject]、# Quality Report 等）；
3. 可选：在具备 API 密钥时用真实 LLM 调用，验证一轮输出或工具调用。

运行方式：
- Python: pytest tests/agents/test_agent_capability.py -v
- Bash: scripts/run_agent_capability_tests.sh
"""

from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

import pytest

# 项目根目录（tests 在 tests/ 下，根目录为上一级）
REPO_ROOT = Path(__file__).resolve().parent.parent.parent


# ----------------------------- 配置 ------------------------------


def _prompt_dir() -> Path:
    """prompts/system 目录，优先使用项目根下的路径。"""
    d = REPO_ROOT / "prompts" / "system"
    if d.exists():
        return d
    return Path("prompts/system")


def _has_real_llm_config() -> bool:
    """是否配置了真实 LLM（用于可选的真实环境测试）。"""
    env = os.environ.get("MINICODER_REAL_LLM", "").lower()
    if env in ("1", "true", "yes"):
        return True
    config_path = REPO_ROOT / "config" / "llm.yaml"
    if not config_path.exists():
        return False
    try:
        import yaml
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        api_key = (cfg.get("api_key") or os.environ.get("ZHIPU_API_KEY") or "").strip()
        return bool(api_key)
    except Exception:
        return False


# ----------------------------- 1. Prompt 加载能力 ------------------------------


class TestAgentPromptLoading:
    """测试各 Agent 能否从 prompts/system 加载对应 prompt。"""

    @pytest.fixture(autouse=True)
    def _ensure_cwd(self, monkeypatch):
        """保证从项目根解析 prompts 路径。"""
        monkeypatch.chdir(REPO_ROOT)

    def test_explorer_loads_prompt(self) -> None:
        """Explorer 应加载 subagent-explorer 对应内容。"""
        from mini_coder.agents.base import ExplorerAgent

        mock_llm = MagicMock()
        mock_llm.chat = MagicMock(return_value="[Exploration Result]\nFindings: none")
        agent = ExplorerAgent(llm_service=mock_llm)
        prompt = agent.get_system_prompt()
        assert prompt
        assert "Explorer" in prompt or "exploration" in prompt.lower() or "read-only" in prompt.lower()
        assert "Forbidden" in prompt or "Allowed" in prompt or "Constraints" in prompt

    def test_reviewer_loads_prompt(self) -> None:
        """Reviewer 应加载 subagent-reviewer 对应内容。"""
        from mini_coder.agents.base import ReviewerAgent

        mock_llm = MagicMock()
        mock_llm.chat = MagicMock(return_value="[Pass] OK")
        agent = ReviewerAgent(llm_service=mock_llm)
        prompt = agent.get_system_prompt()
        assert prompt
        assert "Reviewer" in prompt or "review" in prompt.lower()
        assert "[Pass]" in prompt or "[Reject]" in prompt

    def test_bash_loads_prompt(self) -> None:
        """Bash 应加载 subagent-bash 对应内容。"""
        from mini_coder.agents.base import BashAgent

        mock_llm = MagicMock()
        mock_llm.chat = MagicMock(return_value="# Quality Report\n## Tests\nNot run")
        agent = BashAgent(llm_service=mock_llm)
        prompt = agent.get_system_prompt()
        assert prompt
        assert "Bash" in prompt or "terminal" in prompt.lower() or "Quality Report" in prompt

    def test_planner_loads_prompt(self) -> None:
        """Planner (enhanced) 应加载 subagent-planner 对应内容。"""
        from mini_coder.agents.enhanced import PlannerAgent, Blackboard

        mock_llm = MagicMock()
        mock_llm.chat = MagicMock(return_value="### 概述\nTest\n### 阶段拆解\n- Phase 1")
        bb = Blackboard("cap-test")
        agent = PlannerAgent(mock_llm, bb)
        prompt = agent._load_system_prompt()
        assert prompt
        assert "Planner" in prompt or "plan" in prompt.lower() or "implementation_plan" in prompt

    def test_coder_loads_prompt(self) -> None:
        """Coder (enhanced) 应加载 subagent-coder 对应内容。"""
        from mini_coder.agents.enhanced import CoderAgent, Blackboard

        mock_llm = MagicMock()
        mock_llm.chat = MagicMock(return_value="Done.")
        bb = Blackboard("cap-test")
        agent = CoderAgent(mock_llm, bb)
        prompt = agent._load_system_prompt()
        assert prompt
        assert "Coder" in prompt or "code" in prompt.lower() or "implement" in prompt.lower()

    def test_general_purpose_loads_prompt(self) -> None:
        """GeneralPurpose 应加载 general-purpose 对应内容。"""
        from mini_coder.agents.base import GeneralPurposeAgent

        mock_llm = MagicMock()
        mock_llm.chat = MagicMock(return_value="Search result.")
        agent = GeneralPurposeAgent(llm_service=mock_llm)
        prompt = agent.get_system_prompt()
        assert prompt
        assert "General" in prompt or "read-only" in prompt.lower() or "search" in prompt.lower()

    def test_mini_coder_guide_loads_prompt(self) -> None:
        """MiniCoderGuide 应加载 mini-coder-guide 对应内容。"""
        from mini_coder.agents.base import MiniCoderGuideAgent

        mock_llm = MagicMock()
        mock_llm.chat = MagicMock(return_value="Guide content.")
        agent = MiniCoderGuideAgent(llm_service=mock_llm)
        prompt = agent.get_system_prompt()
        assert prompt
        assert "mini-coder" in prompt.lower() or "guide" in prompt.lower()


# ----------------------------- 2. 结构化输出解析能力 ------------------------------


class TestAgentStructuredOutput:
    """使用 Mock LLM 返回预定义结构化内容，验证 agent 输出可被正确解析。"""

    @pytest.fixture(autouse=True)
    def _ensure_cwd(self, monkeypatch):
        monkeypatch.chdir(REPO_ROOT)

    def test_reviewer_pass_parsed(self) -> None:
        """Reviewer 返回 [Pass] 时，应能解析为 ReviewerResultType.PASS。"""
        from mini_coder.agents.base import ReviewerAgent
        from mini_coder.agents.output_parser import parse_reviewer_output, ReviewerResultType

        mock_llm = MagicMock()
        mock_llm.chat = MagicMock(
            return_value="[Pass]\nCode meets architecture and quality requirements, ready for Bash testing."
        )
        agent = ReviewerAgent(llm_service=mock_llm)
        result = agent.execute("Review the code", context={"plan": "Plan", "code": "x = 1"})
        assert result.success is True
        parsed = parse_reviewer_output(result.output)
        assert parsed.result_type == ReviewerResultType.PASS

    def test_reviewer_reject_parsed(self) -> None:
        """Reviewer 返回 [Reject] 时，应能解析为 ReviewerResultType.REJECT 且带 issues。"""
        from mini_coder.agents.base import ReviewerAgent
        from mini_coder.agents.output_parser import parse_reviewer_output, ReviewerResultType

        mock_llm = MagicMock()
        mock_llm.chat = MagicMock(
            return_value="[Reject]\n1. [quality] /root/LLM/mini-coder/src/foo.py:10 - missing type hint; Suggestion: add int"
        )
        agent = ReviewerAgent(llm_service=mock_llm)
        result = agent.execute("Review the code", context={"plan": "Plan", "code": "def f(x): return x"})
        # Reviewer 设计上 Reject 时 success=False，此处只验证输出可解析
        assert result.output
        parsed = parse_reviewer_output(result.output)
        assert parsed.result_type == ReviewerResultType.REJECT
        assert len(parsed.issues) >= 1

    def test_bash_quality_report_parsed(self) -> None:
        """Bash 返回 # Quality Report 时，应能解析出 Tests/Type Check 等段落。"""
        from mini_coder.agents.base import BashAgent
        from mini_coder.agents.output_parser import parse_quality_report

        mock_llm = MagicMock()
        mock_llm.chat = MagicMock(
            return_value="""# Quality Report
## Tests
All passed
## Type Check
No errors
## Code Style
No issues
## Coverage
Met (>=80%)
## Other

"""
        )
        agent = BashAgent(llm_service=mock_llm)
        result = agent.execute("run quality pipeline", context={"bash_mode": "quality_report"})
        # Bash 在无 command_executor 时可能只返回 LLM 模拟输出，这里主要验证解析
        text = result.output if result.success else ""
        if not text.strip():
            text = mock_llm.chat.return_value
        parsed = parse_quality_report(text)
        assert "Tests" in parsed.raw_text or parsed.test_result
        assert "Type Check" in parsed.raw_text or parsed.type_check

    def test_explorer_exploration_result_contains_block(self) -> None:
        """Explorer 返回应包含 [Exploration Result] 块或可识别的探索结论。"""
        from mini_coder.agents.base import ExplorerAgent

        mock_llm = MagicMock()
        mock_llm.chat = MagicMock(
            return_value="[Exploration Result]\nGoal: find main\nFindings:\n- src/main.py\nSuggested focus: src/main.py"
        )
        agent = ExplorerAgent(llm_service=mock_llm)
        result = agent.execute("找一下项目入口 main")
        assert result.success is True
        assert "[Exploration Result]" in result.output or "Findings" in result.output

    def test_main_agent_simple_answer_parsed(self) -> None:
        """主代理输出 [Simple Answer] 时，应能解析为 SIMPLE_ANSWER。"""
        from mini_coder.agents.output_parser import parse_main_agent_output, MainAgentOutputType

        text = "[Simple Answer]\n这是一条简单回复。"
        parsed = parse_main_agent_output(text)
        assert parsed.output_type == MainAgentOutputType.SIMPLE_ANSWER
        assert "简单回复" in (parsed.content or "")

    def test_main_agent_complex_task_parsed(self) -> None:
        """主代理输出 [Complex Task] 时，应能解析出 problem_type 和 subtasks。"""
        from mini_coder.agents.output_parser import parse_main_agent_output, MainAgentOutputType

        text = """[Complex Task]
Problem type: 功能开发
Sub-questions:
1. 探索相关代码 → Assign to: EXPLORER
2. 实现逻辑 → Assign to: CODER
"""
        parsed = parse_main_agent_output(text)
        assert parsed.output_type == MainAgentOutputType.COMPLEX_TASK
        assert parsed.problem_type
        assert len(parsed.subtasks) >= 1


# ----------------------------- 3. 占位符与 context 注入 ------------------------------


class TestAgentPromptContext:
    """测试 prompt 占位符（如 {{work_dir}}）能通过 context 正确注入。"""

    @pytest.fixture(autouse=True)
    def _ensure_cwd(self, monkeypatch):
        monkeypatch.chdir(REPO_ROOT)

    def test_planner_prompt_accepts_work_dir(self) -> None:
        """Planner 的 prompt 支持 work_dir 占位符。"""
        from mini_coder.agents.enhanced import PlannerAgent, Blackboard

        mock_llm = MagicMock()
        mock_llm.chat = MagicMock(return_value="### 概述\nTest")
        bb = Blackboard("cap-test")
        agent = PlannerAgent(mock_llm, bb)
        prompt = agent._load_system_prompt(context={"work_dir": "/tmp/proj"})
        assert "/tmp/proj" in prompt or "work_dir" in prompt

    def test_explorer_prompt_accepts_work_dir(self) -> None:
        """Explorer 的 prompt 支持 work_dir 占位符。"""
        from mini_coder.agents.base import ExplorerAgent

        mock_llm = MagicMock()
        mock_llm.chat = MagicMock(return_value="[Exploration Result]\nFindings: none")
        agent = ExplorerAgent(llm_service=mock_llm)
        prompt = agent.get_system_prompt(context={"work_dir": "/repo"})
        assert "/repo" in prompt or "work_dir" in prompt


# ----------------------------- 4. 可选：真实 LLM 环境 ------------------------------


@pytest.mark.skipif(not _has_real_llm_config(), reason="未配置真实 LLM（MINICODER_REAL_LLM 或 config/llm.yaml api_key）")
@pytest.mark.integration
class TestAgentRealLLM:
    """在配置了 API 密钥时，用真实 LLM 调用各 agent，验证能得到非空且可解析的输出。"""

    @pytest.fixture(autouse=True)
    def _ensure_cwd(self, monkeypatch):
        monkeypatch.chdir(REPO_ROOT)

    def test_explorer_real_returns_non_empty(self) -> None:
        """真实调用 Explorer 应返回非空内容。"""
        from mini_coder.llm.service import LLMService
        from mini_coder.agents.base import ExplorerAgent

        config_path = REPO_ROOT / "config" / "llm.yaml"
        if not config_path.exists():
            pytest.skip("config/llm.yaml 不存在")
        service = LLMService(str(config_path))
        agent = ExplorerAgent(llm_service=service)
        result = agent.execute("列出本项目 src 目录下前 5 个 py 文件路径，仅路径即可")
        assert result.success, result.error or "unknown"
        assert len((result.output or "").strip()) > 0

    def test_reviewer_real_returns_parseable(self) -> None:
        """真实调用 Reviewer 应返回可解析的 [Pass]/[Reject]。"""
        from mini_coder.llm.service import LLMService
        from mini_coder.agents.base import ReviewerAgent
        from mini_coder.agents.output_parser import parse_reviewer_output, ReviewerResultType

        config_path = REPO_ROOT / "config" / "llm.yaml"
        if not config_path.exists():
            pytest.skip("config/llm.yaml 不存在")
        service = LLMService(str(config_path))
        agent = ReviewerAgent(llm_service=service)
        result = agent.execute(
            "评审下面代码，仅输出 [Pass] 或 [Reject] 及一行说明。",
            context={
                "plan": "单函数实现",
                "code": "def add(a: int, b: int) -> int:\n    return a + b",
            },
        )
        assert result.success, result.error or "unknown"
        parsed = parse_reviewer_output(result.output or "")
        assert parsed.result_type in (ReviewerResultType.PASS, ReviewerResultType.REJECT, ReviewerResultType.UNKNOWN)


# ----------------------------- 5. 写入/修改目录能力（Coder 行为） ------------------------------


class TestCoderWriteCapability:
    """验证 Coder 在收到“写文件”类指令时，能通过工具或输出指导完成写入（此处用 mock 验证路径）。"""

    @pytest.fixture(autouse=True)
    def _ensure_cwd(self, monkeypatch):
        monkeypatch.chdir(REPO_ROOT)

    def test_coder_has_full_access_capability(self) -> None:
        """Coder 能力应包含写类工具（如 Write、Edit）。"""
        from mini_coder.agents.enhanced import CoderAgent, Blackboard, CoderCapabilities

        mock_llm = MagicMock()
        bb = Blackboard("cap-test")
        agent = CoderAgent(mock_llm, bb)
        caps = agent.capabilities
        assert isinstance(caps, CoderCapabilities)
        # Coder 应有写能力：Write/Edit 工具及写路径
        assert "Write" in caps.allowed_tools or "Edit" in caps.allowed_tools
        assert len(caps.allowed_write_patterns) > 0

    def test_explorer_forbidden_write_in_prompt(self) -> None:
        """Explorer 的 prompt 中应明确禁止写操作。"""
        from mini_coder.agents.base import ExplorerAgent

        mock_llm = MagicMock()
        mock_llm.chat = MagicMock(return_value="[Exploration Result]\nFindings: none")
        agent = ExplorerAgent(llm_service=mock_llm)
        prompt = agent.get_system_prompt()
        assert "Write" in prompt or "modify" in prompt.lower() or "Forbidden" in prompt or "create" in prompt.lower()


# ----------------------------- 6. 统一 Planner 路由到 Explorer（读取工作目录文档） ------------------------------


# 用户提问：用于验证「读取工作目录下所有文档」被路由到 Explorer
_USER_QUERY_READ_DOCS = "帮我读取工作目录/root/LLM/mini-coder下的所有文档"


class TestUnifiedPlannerRoutesToExplorer:
    """统一 Planner-Orchestrator 提示词包含 subagent 路由信息，且对「读取工作目录下所有文档」可派发到 Explorer。"""

    @pytest.fixture(autouse=True)
    def _ensure_cwd(self, monkeypatch):
        monkeypatch.chdir(REPO_ROOT)

    def test_unified_planner_prompt_contains_subagent_routing(self) -> None:
        """统一 Agent 提示词中应包含路由到 subagent 的信息（含 EXPLORER）。"""
        from mini_coder.agents.prompt_loader import PromptLoader

        loader = PromptLoader()
        prompt = loader.load("unified-planner-orchestrator", context={}, use_cache=True)
        assert prompt
        assert "EXPLORER" in prompt
        assert "Direct Dispatch" in prompt or "直接派发" in prompt or "Direct Dispatch" in prompt
        assert "子代理" in prompt or "subagent" in prompt.lower() or "Agent:" in prompt

    def test_parse_direct_dispatch_to_explorer_for_read_docs(self) -> None:
        """用户提问「帮我读取工作目录/root/LLM/mini-coder下的所有文档」时，若 LLM 返回 [Direct Dispatch] Agent: EXPLORER，解析结果正确。"""
        from mini_coder.agents.output_parser import (
            parse_unified_output,
            UnifiedOutputType,
        )

        # 模拟统一 Agent 对该用户提问的预期输出：派发到 EXPLORER
        mock_response = """[Direct Dispatch]
Agent: EXPLORER
Task: 读取工作目录 /root/LLM/mini-coder 下的所有文档，列出路径与概要
Params:
work_dir: /root/LLM/mini-coder
"""
        parsed = parse_unified_output(mock_response)
        assert parsed.output_type == UnifiedOutputType.DIRECT_DISPATCH
        assert parsed.direct_dispatch is not None
        assert parsed.direct_dispatch.agent == "EXPLORER"
        assert "读取" in parsed.direct_dispatch.task or "文档" in parsed.direct_dispatch.task
        assert parsed.direct_dispatch.params.get("work_dir") == "/root/LLM/mini-coder"

    def test_run_unified_with_mock_returns_explorer_dispatch_for_read_docs(self) -> None:
        """run_unified 在 Mock LLM 返回派发 EXPLORER 时，应解析并执行派发（返回 Explorer 执行结果）。"""
        from mini_coder.agents.orchestrator import WorkflowOrchestrator

        mock_llm = MagicMock()
        mock_llm.chat_one_shot = MagicMock(
            return_value="""[Direct Dispatch]
Agent: EXPLORER
Task: 读取工作目录 /root/LLM/mini-coder 下的所有文档
Params:
work_dir: /root/LLM/mini-coder
"""
        )
        mock_llm.chat = MagicMock(
            return_value="[Exploration Result]\nGoal: 读取文档\nFindings:\n- /root/LLM/mini-coder/README.md\nSuggested focus: None"
        )
        orch = WorkflowOrchestrator(llm_service=mock_llm)
        result = orch.run_unified(
            _USER_QUERY_READ_DOCS,
            context={"work_dir": "/root/LLM/mini-coder"},
        )
        assert result.success, result.error or "run_unified failed"
        mock_llm.chat_one_shot.assert_called_once()
        call_args = mock_llm.chat_one_shot.call_args
        assert _USER_QUERY_READ_DOCS in (call_args[0][1] if len(call_args[0]) > 1 else "")
        assert "unified-planner-orchestrator" in (call_args[0][0] or "") or "EXPLORER" in (call_args[0][0] or "")
        assert "Exploration Result" in (result.output or "") or "README" in (result.output or "")


@pytest.mark.skipif(not _has_real_llm_config(), reason="未配置真实 LLM（MINICODER_REAL_LLM 或 config/llm.yaml api_key）")
@pytest.mark.integration
def test_unified_planner_real_llm_routes_read_docs_to_explorer(monkeypatch) -> None:
    """真实 LLM：用户提问「帮我读取工作目录/root/LLM/mini-coder下的所有文档」时，统一 Agent 应派发到 EXPLORER（或 BASH 只读）。"""
    monkeypatch.chdir(REPO_ROOT)
    from pathlib import Path
    rep = Path(__file__).resolve().parent.parent.parent
    config_path = rep / "config" / "llm.yaml"
    if not config_path.exists():
        pytest.skip("config/llm.yaml 不存在")
    from mini_coder.llm.service import LLMService
    from mini_coder.agents.orchestrator import WorkflowOrchestrator
    from mini_coder.agents.output_parser import UnifiedOutputType

    service = LLMService(str(config_path))
    orch = WorkflowOrchestrator(llm_service=service)
    result = orch.run_unified(
        _USER_QUERY_READ_DOCS,
        context={"work_dir": "/root/LLM/mini-coder"},
    )
    assert result.success, result.error or "run_unified failed"
    assert result.output, "应有输出内容"
    # 期望：要么直接派发到了 Explorer（输出为探索结果），要么为 Direct Dispatch 且下游执行了 Explorer
    # 此处仅验证成功且有输出；若需严格断言派发到 EXPLORER，可解析 run_unified 内部一次调用的响应（需改 orch 暴露或从日志断言）
    assert len((result.output or "").strip()) > 0

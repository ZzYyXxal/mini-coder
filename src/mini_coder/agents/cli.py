"""Coding Agent CLI - 自动化 Coding Agent 入口点

提供一个简单的命令行接口，用户可以启动自动化的
需求→代码→测试→(重分析) 循环。

Usage:
    python -m mini_coder.agents.cli "实现一个计算器功能"
    python -m mini_coder.agents.cli --requirement "创建用户认证模块"
    python -m mini_coder.agents.cli --interactive
"""

import argparse
import logging
import sys
import time
from pathlib import Path
from typing import Optional

from mini_coder.agents.orchestrator import (
    WorkflowOrchestrator,
    WorkflowState,
    WorkflowContext,
)
from mini_coder.llm.service import LLMService

# 配置日志（含文件名与行号，便于定位）
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


class Colors:
    """ANSI 颜色代码"""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"


def print_header(text: str) -> None:
    """打印标题"""
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'=' * 60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{text.center(60)}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'=' * 60}{Colors.RESET}\n")


def print_status(state: WorkflowState, message: str = "") -> None:
    """打印状态"""
    state_colors = {
        WorkflowState.PENDING: Colors.WHITE,
        WorkflowState.ANALYZING: Colors.BLUE,
        WorkflowState.PLANNING: Colors.CYAN,
        WorkflowState.IMPLEMENTING: Colors.YELLOW,
        WorkflowState.TESTING: Colors.YELLOW,
        WorkflowState.VERIFYING: Colors.GREEN,
        WorkflowState.COMPLETED: Colors.GREEN,
        WorkflowState.FAILED: Colors.RED,
        WorkflowState.NEEDS_INTERVENTION: Colors.RED,
    }
    color = state_colors.get(state, Colors.RESET)
    print(f"[{color}{state.value.upper()}{Colors.RESET}] {message}")


def print_result(result, context: WorkflowContext) -> None:
    """打印最终结果"""
    print_header("执行结果")

    if result.success:
        print(f"{Colors.GREEN}✓ 任务成功完成{Colors.RESET}")
        print(f"  耗时：{context.elapsed_time:.1f}秒")
        print(f"  重试次数：{context.retry_count}")
    else:
        print(f"{Colors.RED}✗ 任务失败{Colors.RESET}")
        print(f"  错误：{result.error[:200]}")
        print(f"  失败类型：{result.failure_type}")
        if result.needs_user_decision:
            print(f"\n{Colors.YELLOW}需要人工决策：{result.decision_reason}{Colors.RESET}")

    # 显示生成的文件
    if result.artifacts:
        print(f"\n{Colors.BOLD}生成的文件:{Colors.RESET}")
        for filename, content in result.artifacts.items():
            content_preview = content[:100].replace('\n', ' ')
            print(f"  - {filename}: {content_preview}...")


def run_interactive_mode(llm_service: LLMService) -> None:
    """运行交互模式"""
    print_header("Coding Agent - 交互模式")
    print("输入需求描述，按 Enter 开始执行。")
    print("输入 'quit' 或 'exit' 退出。\n")

    orchestrator = WorkflowOrchestrator(
        llm_service=llm_service,
        config={
            "max_retries": 4,
            "timeout_seconds": 600,
        }
    )

    # 注册状态回调
    def on_state_change(ctx: WorkflowContext, new_state: WorkflowState):
        print_status(new_state)

    for state in WorkflowState:
        orchestrator.register_state_callback(state, on_state_change)

    while True:
        try:
            # 获取用户输入
            requirement = input(f"\n{Colors.BOLD}请输入需求描述：{Colors.RESET}").strip()

            if requirement.lower() in ('quit', 'exit', 'q'):
                print(f"\n{Colors.CYAN}再见！{Colors.RESET}")
                break

            if not requirement:
                continue

            # 执行工作流
            print(f"\n{Colors.CYAN}开始执行：{requirement[:100]}...{Colors.RESET}\n")

            result = orchestrator.execute_workflow(requirement)
            context = orchestrator.get_context()

            # 打印结果
            print_result(result, context)

        except KeyboardInterrupt:
            print(f"\n\n{Colors.YELLOW}用户中断执行{Colors.RESET}")
            continue
        except Exception as e:
            print(f"\n{Colors.RED}错误：{e}{Colors.RESET}")
            logger.exception("Unexpected error")


def run_batch_mode(requirement: str, llm_service: LLMService, verbose: bool = False) -> None:
    """运行批量模式（单次执行）"""
    print_header("Coding Agent - 批量模式")

    orchestrator = WorkflowOrchestrator(
        llm_service=llm_service,
        config={
            "max_retries": 4,
            "timeout_seconds": 600,
        }
    )

    # 注册状态回调
    def on_state_change(ctx: WorkflowContext, new_state: WorkflowState):
        print_status(new_state)
        if verbose and ctx.metadata.get("last_error"):
            err = ctx.metadata["last_error"]
            print(f"  错误详情：{err.get('message', 'N/A')[:100]}")

    for state in WorkflowState:
        orchestrator.register_state_callback(state, on_state_change)

    # 执行工作流
    print(f"{Colors.CYAN}需求：{requirement}{Colors.RESET}\n")

    result = orchestrator.execute_workflow(requirement)
    context = orchestrator.get_context()

    # 打印结果
    print_result(result, context)

    # 返回适当的退出码
    if result.success:
        sys.exit(0)
    elif result.needs_user_decision:
        sys.exit(2)  # 需要人工决策
    else:
        sys.exit(1)  # 失败


def main():
    """主入口点"""
    parser = argparse.ArgumentParser(
        description="Coding Agent - 自动化的需求→代码→测试→(重分析) 循环",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s "实现一个计算器功能"
  %(prog)s --requirement "创建用户认证模块"
  %(prog)s --interactive
  %(prog)s --verbose --requirement "添加日志功能"
        """
    )

    parser.add_argument(
        "requirement",
        nargs="?",
        help="需求描述"
    )

    parser.add_argument(
        "-r", "--requirement",
        dest="req_arg",
        help="需求描述（与位置参数相同）"
    )

    parser.add_argument(
        "-i", "--interactive",
        action="store_true",
        help="交互模式"
    )

    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="详细输出"
    )

    parser.add_argument(
        "--config",
        default="config/llm.yaml",
        help="LLM 配置文件路径 (默认：config/llm.yaml)"
    )

    parser.add_argument(
        "--max-retries",
        type=int,
        default=4,
        help="最大重试次数 (默认：4)"
    )

    parser.add_argument(
        "--timeout",
        type=int,
        default=600,
        help="超时时间（秒）(默认：600)"
    )

    args = parser.parse_args()

    # 获取需求
    requirement = args.req_arg or args.requirement

    # 检查是否指定了需求
    if not requirement and not args.interactive:
        parser.print_help()
        print(f"\n{Colors.RED}错误：请提供需求描述或使用 --interactive 模式{Colors.RESET}")
        sys.exit(1)

    # 初始化 LLM 服务
    config_path = Path(args.config)
    if not config_path.exists():
        print(f"{Colors.RED}错误：配置文件不存在：{config_path}{Colors.RESET}")
        print(f"提示：请创建 {config_path} 文件，或指定 --config 参数")
        sys.exit(1)

    try:
        llm_service = LLMService(str(config_path))
    except Exception as e:
        print(f"{Colors.RED}错误：无法初始化 LLM 服务：{e}{Colors.RESET}")
        logger.exception("LLM service initialization failed")
        sys.exit(1)

    # 运行
    if args.interactive:
        run_interactive_mode(llm_service)
    else:
        run_batch_mode(requirement, llm_service, verbose=args.verbose)


if __name__ == "__main__":
    main()

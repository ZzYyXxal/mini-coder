"""LLM Chat TUI component.

使用 OpenAI 兼容接口的 Rich 聊天界面。
支持流式响应和多轮对话。
"""

from rich.console import Console
from rich.live import Live
from rich.spinner import Spinner

from ..llm.service import LLMService


class LLMChatTUI:
    """Rich-based chat interface for LLM conversations."""

    def __init__(self, llm_service: LLMService):
        """Initialize LLM chat TUI.

        Args:
            llm_service: LLM service instance for handling API calls.
        """
        self.llm_service = llm_service
        self.console = Console()
        self.current_turn = 0

    def _display_welcome(self) -> None:
        """Display welcome message."""
        self.console.print()
        self.console.print("[bold cyan]LLM Chat[/bold cyan]", style="cyan")
        self.console.print()
        self.console.print("[dim]输入消息与 AI 对话，或输入 /help 查看命令。[/dim]")
        self.console.print("[dim]输入 /exit 或 /quit 退出。[/dim]")
        self.console.print()

    def _display_help(self) -> None:
        """Display help information."""
        self.console.print()
        self.console.print("[bold]命令列表:[/bold cyan]")
        self.console.print("  /help    - 显示帮助信息")
        self.console.print("  /exit    - 退出聊天")
        self.console.print("  /quit    - 退出聊天")
        self.console.print("  /clear   - 清除对话历史")
        self.console.print("  /status  - 显示当前配置")
        self.console.print()

    def _display_status(self) -> None:
        """Display current configuration status."""
        self.console.print()
        self.console.print(f"[bold]当前提供商:[/bold] {self.llm_service.provider_name}")
        if self.llm_service.provider:
            self.console.print(f"[bold]模型:[/bold] {self.llm_service.provider._model}")
            api_key = self.llm_service.provider._api_key
            masked_key = api_key[:8] + "..." + api_key[-4:] if len(api_key) > 12 else "(not set)"
            self.console.print(f"[bold]API Key:[/bold] {masked_key}")
        self.console.print()

    def run(self) -> None:
        """Run the LLM chat TUI (synchronous)."""
        self._display_welcome()

        while True:
            try:
                # Get user input
                user_input = input(f"{self.current_turn + 1}. You: ").strip()

                # Handle commands
                if not user_input:
                    continue

                if user_input.lower() in ('/exit', '/quit', 'exit', 'quit'):
                    self.console.print("[yellow]再见！[/yellow]")
                    break

                if user_input.lower() in ('/help', 'help'):
                    self._display_help()
                    continue

                if user_input.lower() == '/clear':
                    self.llm_service.clear_history()
                    self.current_turn = 0
                    self.console.print("[dim yellow]对话历史已清除。[/dim]")
                    continue

                if user_input.lower() == '/status':
                    self._display_status()
                    continue

                # Send message and stream response
                self.current_turn += 1
                self.console.print("[dim]AI: [/dim]", end="")

                try:
                    # Use streaming response
                    for chunk in self.llm_service.chat_stream(user_input):
                        if chunk.get('type') == 'delta':
                            content = chunk.get('content', '')
                            self.console.print(content, end='')
                        elif chunk.get('type') == 'done':
                            break

                    self.console.print()  # New line after response

                except Exception as e:
                    self.console.print(f"\n[red]错误: {e}[/red]")
                    self.console.print("[dim]请检查 config/llm.yaml 配置和 API Key。[/dim]")

            except KeyboardInterrupt:
                self.console.print("\n[yellow]再见！[/yellow]")
                break
            except EOFError:
                self.console.print("\n[yellow]再见！[/yellow]")
                break


def run_llm_chat(config_path: str = "config/llm.yaml") -> None:
    """Run LLM chat with default configuration.

    Args:
        config_path: Path to LLM configuration file.
    """
    llm_service = LLMService(config_path)
    chat_tui = LLMChatTUI(llm_service)
    chat_tui.run()

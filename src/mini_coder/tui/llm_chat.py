"""LLM Chat TUI component.

Provides a Rich-based chat interface for LLM integration.
Supports streaming responses and multiple conversation turns.
"""

import asyncio
from typing import List, Optional

from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.spinner import Spinner

from ..service import LLMService


class LLMChatTUI:
    """Rich-based chat interface for LLM conversations."""

    def __init__(self, llm_service: LLMService):
        """Initialize LLM chat TUI.

        Args:
            llm_service: LLM service instance for handling API calls.
        """
        self.llm_service = llm_service
        self.console = Console()
        self.messages: List[List[Dict[str, str]]] = []  # Conversation history
        self.current_turn = 0  # Current conversation turn index

    def _display_welcome(self) -> None:
        """Display welcome message."""
        self.console.print()
        self.console.print(
            "[bold cyan]LLM Chat[/bold cyan]",
            border_style="cyan",
        )
        self.console.print()
        self.console.print("[dim]Enter your message or type /help to see commands.[/dim]")
        self.console.print()

    def _display_messages(self, max_messages: int = 10) -> None:
        """Display conversation history.

        Args:
            max_messages: Maximum number of messages to display.
        """
        display_messages = self.messages[-max_messages:]
        for msg in display_messages:
            role = msg.get('role', 'user')
            content = msg.get('content', '')
            role_color = "cyan" if role == "user" else "green"

            self.console.print(f"[{role_color}]{role}:[/reset] {content}")

    async def _stream_response(self, response: AsyncIterator[Dict[str, str]]) -> None:
        """Stream LLM response to console.

        Args:
            response: Async iterator yielding response chunks.
        """
        buffer = ""

        async for chunk in response:
            if chunk.get('type') == 'delta':
                content = chunk.get('content', '')
                self.console.print(content, end='')
            elif chunk.get('type') == 'message':
                content = chunk.get('content', '')
                buffer += content

                # Add new line after complete message
                if chunk.get('done'):
                    self.console.print()  # Add newline after complete message
                    self.messages.append({
                        'role': 'assistant',
                        'content': buffer
                    })
                    buffer = ""

    async def send_user_message(self, message: str) -> None:
        """Send user message and display streaming response.

        Args:
            message: User message content.
        """
        self.messages.append({'role': 'user', 'content': message})
        self.current_turn += 1

        # Display typing indicator
        with Live("", console=self.console, refresh_per_second=10) as live:
            live.update(Spinner("dots", text=f"[dim]AI is thinking...[/dim]"))

            # Send message and stream response
            response_chunks = []
            async for chunk in self.llm_service.send_message_stream(
                self.messages,
                stream=True
            ):
                if chunk.get('type') == 'delta':
                    live.update(content)
                    response_chunks.append(chunk)
                elif chunk.get('type') == 'message':
                    # Message complete
                    full_response = ''.join([c.get('content', '') for c in response_chunks])
                    self.messages.append({
                        'role': 'assistant',
                        'content': full_response
                    })
                    break

    async def show_help(self) -> None:
        """Display help information."""
        self.console.print()
        self.console.print("[bold]Commands:[/bold cyan]")
        self.console.print("  /help  - Show this help message")
        self.console.print("  /exit or /quit - Exit the chat")
        self.console.print("  /clear - Clear conversation history")
        self.console.print("  /history - Show conversation history")
        self.console.print()
        self.console.print("[dim]LLM Chat Interface - Type messages to chat with AI assistant.[/dim]")

    async def run(self) -> None:
        """Run the LLM chat TUI."""
        self._display_welcome()

        while True:
            # Get user input
            user_input = input(f"[dim]{self.current_turn + 1}. You:[/reset] ")

            # Handle commands
            if user_input.lower() in ('/help', 'exit', 'quit'):
                await self.show_help()
                continue
            elif user_input.lower() == '/clear':
                self.messages.clear()
                self.current_turn = 0
                self.console.print("[dim yellow]Conversation history cleared.[/dim]")
                continue
            elif user_input.lower() == '/history':
                self._display_messages(max_messages=20)
                continue

            # Send message and get response
            elif user_input:
                await self.send_user_message(user_input)

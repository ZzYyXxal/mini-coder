"""Tests for typewriter rendering module."""

import asyncio

import pytest

from mini_coder.tui.rendering import AnimationState, TypewriterRenderer


class TestAnimationState:
    """Tests for AnimationState enum."""

    def test_animation_state_values(self) -> None:
        """Verify all animation states exist."""
        assert AnimationState.IDLE.value == "idle"
        assert AnimationState.RUNNING.value == "running"
        assert AnimationState.PAUSED.value == "paused"
        assert AnimationState.CANCELED.value == "canceled"
        assert AnimationState.COMPLETED.value == "completed"


class TestTypewriterRenderer:
    """Tests for TypewriterRenderer class."""

    @pytest.mark.asyncio
    async def test_render_basic_text(self) -> None:
        """Test rendering basic text."""
        renderer = TypewriterRenderer()
        chunks = []
        async for chunk in renderer.render("Hello, World!", speed="fast"):
            chunks.append(chunk)

        assert "".join(chunks) == "Hello, World!"
        assert renderer.state == AnimationState.COMPLETED

    @pytest.mark.asyncio
    async def test_render_empty_text(self) -> None:
        """Test rendering empty text."""
        renderer = TypewriterRenderer()
        chunks = []
        async for chunk in renderer.render("", speed="fast"):
            chunks.append(chunk)

        assert chunks == [] or chunks == [""]

    @pytest.mark.asyncio
    async def test_render_with_custom_delay(self) -> None:
        """Test rendering with custom delay."""
        renderer = TypewriterRenderer()
        delay = renderer.get_delay(custom_delay=10)
        assert delay == 0.01

    @pytest.mark.asyncio
    async def test_render_with_speed_preset(self) -> None:
        """Test rendering with speed presets."""
        renderer = TypewriterRenderer()

        assert renderer.get_delay(speed="slow") > renderer.get_delay(speed="normal")
        assert renderer.get_delay(speed="normal") > renderer.get_delay(speed="fast")

    @pytest.mark.asyncio
    async def test_render_instant(self) -> None:
        """Test instant rendering."""
        renderer = TypewriterRenderer()
        chunks = []
        async for chunk in renderer.render("Test", instant=True):
            chunks.append(chunk)

        assert len(chunks) == 1
        assert chunks[0] == "Test"
        assert renderer.state == AnimationState.COMPLETED

    @pytest.mark.asyncio
    async def test_pause_and_resume(self) -> None:
        """Test pause and resume functionality."""
        renderer = TypewriterRenderer()
        chunks = []
        pause_triggered = False

        async def render_with_pause() -> None:
            nonlocal pause_triggered
            async for chunk in renderer.render("ABC", speed="fast"):
                if not pause_triggered:
                    renderer.pause()
                    pause_triggered = True
                    await asyncio.sleep(0.05)
                    renderer.resume()
                chunks.append(chunk)

        await render_with_pause()
        assert "".join(chunks) == "ABC"
        assert renderer.state == AnimationState.COMPLETED

    @pytest.mark.asyncio
    async def test_cancel_animation(self) -> None:
        """Test canceling animation."""
        renderer = TypewriterRenderer()
        chunks = []

        async def render_with_cancel() -> None:
            cancel_triggered = False
            async for chunk in renderer.render("ABCDEF", speed="fast"):
                if not cancel_triggered:
                    renderer.cancel()
                    cancel_triggered = True
                    await asyncio.sleep(0.01)
                chunks.append(chunk)

        await render_with_cancel()
        assert "".join(chunks) == "ABCDEF"
        assert renderer.state == AnimationState.CANCELED

    @pytest.mark.asyncio
    async def test_render_with_batch_size(self) -> None:
        """Test rendering with batch size."""
        renderer = TypewriterRenderer()
        chunks = []
        async for chunk in renderer.render("Hello", speed="fast", batch_size=2):
            chunks.append(chunk)

        assert len(chunks) == 3  # "He", "ll", "o"
        assert "".join(chunks) == "Hello"

    def test_pause_state(self) -> None:
        """Test pause state change."""
        renderer = TypewriterRenderer()
        renderer.state = AnimationState.RUNNING

        renderer.pause()
        assert renderer.state == AnimationState.PAUSED

    def test_resume_state(self) -> None:
        """Test resume state change."""
        renderer = TypewriterRenderer()
        renderer.state = AnimationState.PAUSED

        renderer.resume()
        assert renderer.state == AnimationState.RUNNING

    def test_cancel_state(self) -> None:
        """Test cancel state change."""
        renderer = TypewriterRenderer()
        renderer.state = AnimationState.RUNNING

        renderer.cancel()
        assert renderer.state == AnimationState.CANCELED

    def test_reset_state(self) -> None:
        """Test reset state."""
        renderer = TypewriterRenderer()
        renderer.state = AnimationState.RUNNING

        renderer.reset()
        assert renderer.state == AnimationState.IDLE

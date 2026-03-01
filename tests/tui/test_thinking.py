"""Tests for AI thinking message models."""

from datetime import datetime

from mini_coder.tui.models.thinking import (ThinkingHistory, ThinkingMessage,
                                            ThinkingType)


class TestThinkingType:
    """Tests for ThinkingType enum."""

    def test_thinking_type_values(self) -> None:
        """Verify all thinking types exist."""
        assert ThinkingType.PLAN.value == "PLAN"
        assert ThinkingType.ANALYSIS.value == "ANALYSIS"
        assert ThinkingType.REFLECTION.value == "REFLECTION"


class TestThinkingMessage:
    """Tests for ThinkingMessage class."""

    def test_create_message(self) -> None:
        """Test creating a thinking message."""
        message = ThinkingMessage(
            step=1,
            timestamp=datetime.now(),
            message_type=ThinkingType.PLAN,
            content="Planning the implementation",
        )

        assert message.step == 1
        assert message.message_type == ThinkingType.PLAN
        assert message.content == "Planning the implementation"
        assert message.metadata is None

    def test_create_message_with_metadata(self) -> None:
        """Test creating a message with metadata."""
        metadata = {"key": "value"}
        message = ThinkingMessage(
            step=1,
            timestamp=datetime.now(),
            message_type=ThinkingType.ANALYSIS,
            content="Analyzing the code",
            metadata=metadata,
        )

        assert message.metadata == metadata

    def test_to_dict(self) -> None:
        """Test converting message to dictionary."""
        timestamp = datetime.now()
        message = ThinkingMessage(
            step=1,
            timestamp=timestamp,
            message_type=ThinkingType.REFLECTION,
            content="Reflecting on the solution",
        )

        message_dict = message.to_dict()
        assert message_dict["step"] == 1
        assert message_dict["message_type"] == "REFLECTION"
        assert message_dict["content"] == "Reflecting on the solution"

    def test_from_dict(self) -> None:
        """Test creating message from dictionary."""
        data = {
            "step": 2,
            "timestamp": datetime.now().isoformat(),
            "message_type": "PLAN",
            "content": "New plan",
            "metadata": {"test": "value"},
        }

        message = ThinkingMessage.from_dict(data)
        assert message.step == 2
        assert message.message_type == ThinkingType.PLAN
        assert message.content == "New plan"
        assert message.metadata == {"test": "value"}

    def test_to_markdown(self) -> None:
        """Test converting message to markdown."""
        message = ThinkingMessage(
            step=1,
            timestamp=datetime.now(),
            message_type=ThinkingType.PLAN,
            content="Plan content",
        )

        markdown = message.to_markdown()
        assert "[PLAN]" in markdown
        assert "Step 1" in markdown
        assert "Plan content" in markdown

    def test_get_color(self) -> None:
        """Test getting color for message types."""
        plan_msg = ThinkingMessage(
            step=1,
            timestamp=datetime.now(),
            message_type=ThinkingType.PLAN,
            content="Test",
        )
        assert plan_msg.get_color() == "blue"

        analysis_msg = ThinkingMessage(
            step=1,
            timestamp=datetime.now(),
            message_type=ThinkingType.ANALYSIS,
            content="Test",
        )
        assert analysis_msg.get_color() == "purple"

        reflection_msg = ThinkingMessage(
            step=1,
            timestamp=datetime.now(),
            message_type=ThinkingType.REFLECTION,
            content="Test",
        )
        assert reflection_msg.get_color() == "yellow"


class TestThinkingHistory:
    """Tests for ThinkingHistory class."""

    def test_create_history(self) -> None:
        """Test creating thinking history."""
        history = ThinkingHistory()
        assert len(history.get_all()) == 0
        assert history.max_entries == 100

    def test_create_history_with_custom_max(self) -> None:
        """Test creating history with custom max entries."""
        history = ThinkingHistory(max_entries=50)
        assert history.max_entries == 50

    def test_add_message(self) -> None:
        """Test adding a message."""
        history = ThinkingHistory()
        message = ThinkingMessage(
            step=1,
            timestamp=datetime.now(),
            message_type=ThinkingType.PLAN,
            content="Test message",
        )

        history.add(message)
        assert len(history.get_all()) == 1

    def test_max_entries_enforcement(self) -> None:
        """Test that max entries is enforced."""
        history = ThinkingHistory(max_entries=3)

        for i in range(5):
            message = ThinkingMessage(
                step=i,
                timestamp=datetime.now(),
                message_type=ThinkingType.PLAN,
                content=f"Message {i}",
            )
            history.add(message)

        assert len(history.get_all()) == 3

    def test_get_by_type(self) -> None:
        """Test filtering messages by type."""
        history = ThinkingHistory()

        history.add(
            ThinkingMessage(
                step=1,
                timestamp=datetime.now(),
                message_type=ThinkingType.PLAN,
                content="Plan 1",
            )
        )
        history.add(
            ThinkingMessage(
                step=2,
                timestamp=datetime.now(),
                message_type=ThinkingType.ANALYSIS,
                content="Analysis 1",
            )
        )
        history.add(
            ThinkingMessage(
                step=3,
                timestamp=datetime.now(),
                message_type=ThinkingType.PLAN,
                content="Plan 2",
            )
        )

        plans = history.get_by_type(ThinkingType.PLAN)
        assert len(plans) == 2

        analysis = history.get_by_type(ThinkingType.ANALYSIS)
        assert len(analysis) == 1

    def test_search(self) -> None:
        """Test searching messages."""
        history = ThinkingHistory()

        history.add(
            ThinkingMessage(
                step=1,
                timestamp=datetime.now(),
                message_type=ThinkingType.PLAN,
                content="Planning the function",
            )
        )
        history.add(
            ThinkingMessage(
                step=2,
                timestamp=datetime.now(),
                message_type=ThinkingType.ANALYSIS,
                content="Analyzing the implementation",
            )
        )

        results = history.search("function")
        assert len(results) == 1
        assert "function" in results[0].content.lower()

    def test_clear(self) -> None:
        """Test clearing history."""
        history = ThinkingHistory()

        for i in range(3):
            message = ThinkingMessage(
                step=i,
                timestamp=datetime.now(),
                message_type=ThinkingType.PLAN,
                content=f"Message {i}",
            )
            history.add(message)

        history.clear()
        assert len(history.get_all()) == 0

    def test_to_markdown(self) -> None:
        """Test exporting to markdown."""
        history = ThinkingHistory()

        message = ThinkingMessage(
            step=1,
            timestamp=datetime.now(),
            message_type=ThinkingType.PLAN,
            content="Test content",
        )
        history.add(message)

        markdown = history.to_markdown()
        assert "[PLAN]" in markdown
        assert "Step 1" in markdown
        assert "Test content" in markdown

    def test_to_json(self) -> None:
        """Test exporting to JSON."""
        history = ThinkingHistory()

        message = ThinkingMessage(
            step=1,
            timestamp=datetime.now(),
            message_type=ThinkingType.PLAN,
            content="Test content",
        )
        history.add(message)

        json_str = history.to_json()
        assert '"step": 1' in json_str
        assert '"message_type": "PLAN"' in json_str
        assert '"content": "Test content"' in json_str

    def test_get_next_step(self) -> None:
        """Test getting next step number."""
        history = ThinkingHistory()
        assert history.get_next_step() == 1

        history.increment_step()
        assert history.get_next_step() == 2

    def test_increment_step(self) -> None:
        """Test incrementing step counter."""
        history = ThinkingHistory()
        initial_step = history.get_next_step()

        history.increment_step()
        assert history.get_next_step() == initial_step + 1

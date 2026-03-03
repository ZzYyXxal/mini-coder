"""Tests for ToolFilter"""

import pytest
from src.mini_coder.tools.filter import (
    ToolFilter,
    ReadOnlyFilter,
    FullAccessFilter,
    CustomFilter,
    StrictFilter,
)


class TestReadOnlyFilter:
    """Tests for ReadOnlyFilter"""

    @pytest.fixture
    def filter_instance(self) -> ReadOnlyFilter:
        """Create ReadOnlyFilter instance"""
        return ReadOnlyFilter()

    def test_readonly_tools_allowed(self, filter_instance: ReadOnlyFilter) -> None:
        """Test that readonly tools are allowed"""
        assert filter_instance.is_allowed("Read") is True
        assert filter_instance.is_allowed("LS") is True
        assert filter_instance.is_allowed("Glob") is True
        assert filter_instance.is_allowed("Grep") is True
        assert filter_instance.is_allowed("Command_git_status") is True

    def test_write_tools_denied(self, filter_instance: ReadOnlyFilter) -> None:
        """Test that write tools are denied"""
        assert filter_instance.is_allowed("Write") is False
        assert filter_instance.is_allowed("Edit") is False
        assert filter_instance.is_allowed("Command_rm") is False

    def test_filter_method(self, filter_instance: ReadOnlyFilter) -> None:
        """Test filtering a list of tools"""
        all_tools = ["Read", "Write", "LS", "Glob", "Edit", "Grep"]
        filtered = filter_instance.filter(all_tools)

        assert filtered == ["Read", "LS", "Glob", "Grep"]

    def test_additional_allowed(self) -> None:
        """Test adding additional allowed tools"""
        filter_instance = ReadOnlyFilter(additional_allowed=["MyCustomTool"])

        assert filter_instance.is_allowed("MyCustomTool") is True
        assert filter_instance.is_allowed("Read") is True
        assert filter_instance.is_allowed("Write") is False

    def test_add_allowed_tool(self, filter_instance: ReadOnlyFilter) -> None:
        """Test adding tool to allowed list"""
        filter_instance.add_allowed_tool("NewTool")
        assert filter_instance.is_allowed("NewTool") is True

    def test_remove_allowed_tool(self, filter_instance: ReadOnlyFilter) -> None:
        """Test removing tool from allowed list"""
        filter_instance.remove_allowed_tool("Read")
        assert filter_instance.is_allowed("Read") is False


class TestFullAccessFilter:
    """Tests for FullAccessFilter"""

    @pytest.fixture
    def filter_instance(self) -> FullAccessFilter:
        """Create FullAccessFilter instance"""
        return FullAccessFilter()

    def test_most_tools_allowed(self, filter_instance: FullAccessFilter) -> None:
        """Test that most tools are allowed"""
        assert filter_instance.is_allowed("Read") is True
        assert filter_instance.is_allowed("Write") is True
        assert filter_instance.is_allowed("Edit") is True
        assert filter_instance.is_allowed("Command_pytest") is True

    def test_dangerous_tools_denied(self, filter_instance: FullAccessFilter) -> None:
        """Test that dangerous tools are denied"""
        assert filter_instance.is_allowed("Command_sudo") is False
        assert filter_instance.is_allowed("Command_rm_rf") is False
        assert filter_instance.is_allowed("Command_dd") is False
        assert filter_instance.is_allowed("Bash") is False

    def test_additional_denied(self) -> None:
        """Test adding additional denied tools"""
        filter_instance = FullAccessFilter(additional_denied=["DangerousTool"])

        assert filter_instance.is_allowed("DangerousTool") is False
        assert filter_instance.is_allowed("Read") is True

    def test_add_denied_tool(self, filter_instance: FullAccessFilter) -> None:
        """Test adding tool to denied list"""
        filter_instance.add_denied_tool("NewDangerousTool")
        assert filter_instance.is_allowed("NewDangerousTool") is False

    def test_remove_denied_tool(self, filter_instance: FullAccessFilter) -> None:
        """Test removing tool from denied list"""
        filter_instance.remove_denied_tool("Bash")
        assert filter_instance.is_allowed("Bash") is True


class TestCustomFilter:
    """Tests for CustomFilter"""

    def test_whitelist_mode(self) -> None:
        """Test whitelist mode"""
        filter_instance = CustomFilter(
            allowed={"Read", "LS", "Grep"},
            mode="whitelist"
        )

        assert filter_instance.is_allowed("Read") is True
        assert filter_instance.is_allowed("LS") is True
        assert filter_instance.is_allowed("Write") is False
        assert filter_instance.is_allowed("Unknown") is False

    def test_blacklist_mode(self) -> None:
        """Test blacklist mode"""
        filter_instance = CustomFilter(
            denied={"DangerousTool", "BannedTool"},
            mode="blacklist"
        )

        assert filter_instance.is_allowed("Read") is True
        assert filter_instance.is_allowed("Write") is True
        assert filter_instance.is_allowed("DangerousTool") is False
        assert filter_instance.is_allowed("BannedTool") is False

    def test_invalid_mode(self) -> None:
        """Test invalid mode raises error"""
        with pytest.raises(ValueError, match="Invalid mode"):
            CustomFilter(mode="invalid")

    def test_add_allowed_whitelist(self) -> None:
        """Test adding allowed tool in whitelist mode"""
        filter_instance = CustomFilter(
            allowed={"Read"},
            mode="whitelist"
        )

        filter_instance.add_allowed("LS")
        assert filter_instance.is_allowed("LS") is True

    def test_add_denied_blacklist(self) -> None:
        """Test adding denied tool in blacklist mode"""
        filter_instance = CustomFilter(
            denied={"Tool1"},
            mode="blacklist"
        )

        filter_instance.add_denied("Tool2")
        assert filter_instance.is_allowed("Tool2") is False


class TestStrictFilter:
    """Tests for StrictFilter"""

    @pytest.fixture
    def filter_instance(self) -> StrictFilter:
        """Create StrictFilter instance"""
        return StrictFilter()

    def test_strict_allowed_tools(self, filter_instance: StrictFilter) -> None:
        """Test tools allowed in strict mode"""
        assert filter_instance.is_allowed("Read") is True
        assert filter_instance.is_allowed("LS") is True
        assert filter_instance.is_allowed("Glob") is True
        assert filter_instance.is_allowed("Grep") is True

    def test_strict_denies_others(self, filter_instance: StrictFilter) -> None:
        """Test that strict mode denies other tools"""
        assert filter_instance.is_allowed("Write") is False
        assert filter_instance.is_allowed("Edit") is False
        assert filter_instance.is_allowed("Unknown") is False

    def test_additional_allowed(self) -> None:
        """Test adding additional allowed tools"""
        filter_instance = StrictFilter(additional_allowed=["CustomTool"])

        assert filter_instance.is_allowed("CustomTool") is True
        assert filter_instance.is_allowed("Read") is True
        assert filter_instance.is_allowed("Write") is False


class TestToolFilterBase:
    """Tests for ToolFilter base class"""

    def test_filter_base_method(self) -> None:
        """Test that filter base class has filter method"""
        # ReadOnlyFilter implements the base class
        filter_instance = ReadOnlyFilter()

        all_tools = ["Read", "Write", "LS"]
        filtered = filter_instance.filter(all_tools)

        assert isinstance(filtered, list)
        assert "Read" in filtered
        assert "LS" in filtered
        assert "Write" not in filtered

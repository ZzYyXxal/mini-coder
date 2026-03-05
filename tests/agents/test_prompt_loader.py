"""Tests for PromptLoader"""

import pytest
import tempfile
import shutil
from pathlib import Path

from src.mini_coder.agents.prompt_loader import PromptLoader


class TestPromptLoader:
    """Tests for PromptLoader class"""

    @pytest.fixture
    def temp_prompt_dir(self) -> Path:
        """Create a temporary directory with test prompts"""
        temp_dir = Path(tempfile.mkdtemp())

        # Create test prompt files
        explorer_prompt = temp_dir / "subagent-explorer.md"
        explorer_prompt.write_text("""# Explorer Agent Prompt

You are the Explorer Agent.

Thoroughness level: {{thoroughness}}

Project: {{project_name}}
""", encoding="utf-8")

        planner_prompt = temp_dir / "subagent-planner.md"
        planner_prompt.write_text("""# Planner Agent Prompt

You are the Planner Agent.
""", encoding="utf-8")

        yield temp_dir

        # Cleanup
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def loader(self, temp_prompt_dir: Path) -> PromptLoader:
        """Create PromptLoader instance with temp directory"""
        return PromptLoader(prompt_dir=str(temp_prompt_dir))

    def test_load_from_file(self, loader: PromptLoader) -> None:
        """Test loading prompt from file"""
        prompt = loader.load("explorer")

        assert "# Explorer Agent Prompt" in prompt
        assert "You are the Explorer Agent." in prompt

    def test_load_with_interpolation(self, loader: PromptLoader) -> None:
        """Test placeholder interpolation"""
        prompt = loader.load("explorer", context={
            "thoroughness": "high",
            "project_name": "test-project"
        })

        assert "Thoroughness level: high" in prompt
        assert "Project: test-project" in prompt
        assert "{{thoroughness}}" not in prompt  # Placeholder replaced
        assert "{{project_name}}" not in prompt

    def test_load_nonexistent_file_uses_builtin(self, loader: PromptLoader) -> None:
        """Test that nonexistent files fall back to built-in prompts"""
        # "unknown_agent" doesn't have a file, but may have a built-in prompt
        # Test with a type that has no built-in prompt
        with pytest.raises(ValueError, match="No prompt found for agent type"):
            loader.load("nonexistent_agent_type")

    def test_load_builtin_prompt(self) -> None:
        """Test loading built-in prompt when no file exists"""
        # Use default directory which has built-in prompts
        loader = PromptLoader(prompt_dir="/nonexistent/dir")

        # These should fall back to built-in prompts
        prompt = loader.load("explorer")
        assert "Explorer Agent" in prompt or "read-only" in prompt.lower()

    def test_cache_used_on_second_load(self, loader: PromptLoader) -> None:
        """Test that cache is used on second load"""
        # First load reads from file
        loader.load("explorer")

        # Modify the file to verify cache is used
        explorer_file = loader.prompt_dir / "subagent-explorer.md"
        explorer_file.write_text("# Modified Prompt", encoding="utf-8")

        # Second load should use cache
        prompt2 = loader.load("explorer")

        assert "# Explorer Agent Prompt" in prompt2
        assert "# Modified Prompt" not in prompt2

    def test_clear_cache(self, loader: PromptLoader) -> None:
        """Test clearing the cache"""
        # Load into cache
        loader.load("explorer")

        # Clear cache
        loader.clear_cache()

        # Verify cache is empty by checking internal state
        assert len(loader._cache) == 0

    def test_preload_all_prompts(self, loader: PromptLoader) -> None:
        """Test preloading all prompts"""
        # Preload should load all built-in prompts into cache
        loader.preload()

        # Verify some prompts are loaded
        assert len(loader._cache) > 0

    def test_preload_specific_prompts(self, loader: PromptLoader) -> None:
        """Test preloading specific prompt types"""
        loader.preload(["explorer", "planner"])

        # Verify only specified prompts are loaded
        assert "explorer" in loader._cache
        assert "planner" in loader._cache

    def test_interpolate_empty_context(self, loader: PromptLoader) -> None:
        """Test loading with empty context"""
        prompt = loader.load("explorer", context={})

        # Placeholders should remain unchanged
        assert "{{thoroughness}}" in prompt
        assert "{{project_name}}" in prompt

    def test_interpolate_partial_context(self, loader: PromptLoader) -> None:
        """Test loading with partial context"""
        prompt = loader.load("explorer", context={
            "thoroughness": "medium"
        })

        assert "Thoroughness level: medium" in prompt
        assert "{{project_name}}" in prompt  # Not replaced

    def test_load_with_different_filename_patterns(
        self, temp_prompt_dir: Path
    ) -> None:
        """Test loading with different file naming patterns"""
        # Create prompt with alternative naming
        alt_prompt = temp_prompt_dir / "explorer.md"
        alt_prompt.write_text("# Alternative Explorer Prompt",
                              encoding="utf-8")

        # Create a new loader to avoid cache
        loader = PromptLoader(prompt_dir=str(temp_prompt_dir))

        # Should find the file with alternative naming
        prompt = loader.load("explorer")
        # The first matching pattern wins (subagent-explorer.md)
        assert "# Explorer Agent Prompt" in prompt

    def test_prompt_dir_not_exists(self) -> None:
        """Test initialization with nonexistent directory"""
        # Should not raise, just log warning
        loader = PromptLoader(prompt_dir="/nonexistent/path")

        # Loading should still work via built-in prompts
        prompt = loader.load("explorer")
        assert prompt is not None

    def test_load_coder_prompt(self) -> None:
        """Test loading coder prompt"""
        loader = PromptLoader()
        prompt = loader.load("coder")

        assert "Coder" in prompt or "code" in prompt.lower()

    def test_load_reviewer_prompt(self) -> None:
        """Test loading reviewer prompt"""
        loader = PromptLoader()
        prompt = loader.load("reviewer")

        assert "Reviewer" in prompt or "review" in prompt.lower()

    def test_load_bash_prompt(self) -> None:
        """Test loading bash prompt"""
        loader = PromptLoader()
        prompt = loader.load("bash")

        assert "Bash" in prompt or "terminal" in prompt.lower()

    def test_load_main_prompt(self) -> None:
        """Test loading main agent prompt"""
        loader = PromptLoader()
        prompt = loader.load("main")

        assert "Main Agent" in prompt or "Coordinator" in prompt


class TestPromptLoaderInterpolation:
    """Tests for prompt interpolation edge cases"""

    @pytest.fixture
    def temp_prompt_dir(self) -> Path:
        """Create temporary directory with test prompts"""
        temp_dir = Path(tempfile.mkdtemp())

        # Create prompt with various placeholder patterns
        prompt_file = temp_dir / "test.md"
        prompt_file.write_text("""
Single placeholder: {{name}}
Multiple same: {{name}} and {{name}}
Multiple different: {{name}} {{value}} {{other}}
Nested-like (not really): {{outer}} not {{inner}}
With special chars: {{my_var}} {{MY_CONST}} {{camelCase}}
""", encoding="utf-8")

        yield temp_dir
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def loader(self, temp_prompt_dir: Path) -> PromptLoader:
        """Create loader with test directory"""
        return PromptLoader(prompt_dir=str(temp_prompt_dir))

    def test_multiple_same_placeholders(self, loader: PromptLoader) -> None:
        """Test replacing multiple occurrences of same placeholder"""
        prompt = loader.load("test", context={"name": "VALUE"})

        # All occurrences should be replaced
        count = prompt.count("VALUE")
        # Expected: "Single placeholder: VALUE", "Multiple same: VALUE and VALUE", "Multiple different: VALUE..."
        assert count == 4

    def test_multiple_different_placeholders(self, loader: PromptLoader) -> None:
        """Test replacing multiple different placeholders"""
        prompt = loader.load("test", context={
            "name": "A",
            "value": "B",
            "other": "C"
        })

        # "Multiple different: A B C" - all three replaced on that line
        assert "A B C" in prompt
        # Note: {{my_var}}, {{MY_CONST}}, {{camelCase}} remain because not in context

    def test_partial_replacement(self, loader: PromptLoader) -> None:
        """Test partial context replacement"""
        prompt = loader.load("test", context={"name": "ONLY_NAME"})

        assert "ONLY_NAME" in prompt
        assert "{{value}}" in prompt  # Not replaced
        assert "{{other}}" in prompt  # Not replaced

    def test_special_identifier_patterns(self, loader: PromptLoader) -> None:
        """Test placeholder with special identifier patterns"""
        prompt = loader.load("test", context={
            "my_var": "underscore",
            "MY_CONST": "constant",
            "camelCase": "camel"
        })

        assert "underscore" in prompt
        assert "constant" in prompt
        assert "camel" in prompt


class TestBuiltinPrompts:
    """Tests for built-in prompt constants"""

    def test_all_builtin_prompts_exist(self) -> None:
        """Test that all expected built-in prompts exist"""
        from src.mini_coder.agents.prompt_loader import _BUILTIN_PROMPTS

        expected_agents = [
            "explorer",
            "planner",
            "coder",
            "reviewer",
            "bash",
            "main",
        ]

        for agent in expected_agents:
            assert agent in _BUILTIN_PROMPTS, f"Missing built-in prompt for {agent}"

    def test_explorer_prompt_content(self) -> None:
        """Test explorer prompt has expected content"""
        from src.mini_coder.agents.prompt_loader import _BUILTIN_PROMPTS

        prompt = _BUILTIN_PROMPTS["explorer"]

        assert "Explorer" in prompt
        assert "Read-Only" in prompt or "read-only" in prompt
        assert "MUST NOT" in prompt  # Constraints section

    def test_planner_prompt_content(self) -> None:
        """Test planner prompt has expected content"""
        from src.mini_coder.agents.prompt_loader import _BUILTIN_PROMPTS

        prompt = _BUILTIN_PROMPTS["planner"]

        assert "Planner" in prompt
        assert "TDD" in prompt or "test" in prompt.lower()
        assert "implementation_plan" in prompt

    def test_coder_prompt_content(self) -> None:
        """Test coder prompt has expected content"""
        from src.mini_coder.agents.prompt_loader import _BUILTIN_PROMPTS

        prompt = _BUILTIN_PROMPTS["coder"]

        assert "Coder" in prompt
        assert "coding_standards" in prompt  # Placeholder for standards

    def test_reviewer_prompt_content(self) -> None:
        """Test reviewer prompt has expected content"""
        from src.mini_coder.agents.prompt_loader import _BUILTIN_PROMPTS

        prompt = _BUILTIN_PROMPTS["reviewer"]

        assert "Reviewer" in prompt
        assert "Pass" in prompt
        assert "Reject" in prompt

    def test_bash_prompt_content(self) -> None:
        """Test bash prompt has expected content"""
        from src.mini_coder.agents.prompt_loader import _BUILTIN_PROMPTS

        prompt = _BUILTIN_PROMPTS["bash"]

        assert "Bash" in prompt
        assert "Whitelist" in prompt or "whitelist" in prompt
        assert "pytest" in prompt

    def test_main_prompt_content(self) -> None:
        """Test main agent prompt has expected content"""
        from src.mini_coder.agents.prompt_loader import _BUILTIN_PROMPTS

        prompt = _BUILTIN_PROMPTS["main"]

        assert "Main Agent" in prompt or "Coordinator" in prompt
        assert "Dispatch" in prompt or "dispatch" in prompt
        assert "Memory" in prompt or "memory" in prompt

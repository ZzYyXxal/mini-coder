# Tasks: Optimize Multi-Agent Architecture

## 1. Prompt Infrastructure

- [x] 1.1 Create `prompts/system/` directory structure (updated location)
- [x] 1.2 Implement `PromptLoader` class in `src/mini_coder/agents/prompt_loader.py`
- [x] 1.3 Create `subagent-explorer.md` prompt template (migrated to prompts/system/)
- [x] 1.4 Create `subagent-planner.md` prompt template (migrated to prompts/system/)
- [x] 1.5 Create `subagent-coder.md` prompt template (migrated to prompts/system/)
- [x] 1.6 Create `subagent-reviewer.md` prompt template (migrated to prompts/system/)
- [x] 1.7 Create `subagent-bash.md` prompt template with whitelist/blacklist commands
- [x] 1.8 Create `main-agent.md` prompt template (migrated to prompts/system/)
- [x] 1.9 Add built-in default prompts as code constants in `prompt_loader.py` (already done in PromptLoader class)

## 2. Tool Filter Extensions

- [x] 2.1 Create `BashRestrictedFilter` class in `src/mini_coder/tools/filter.py`
- [x] 2.2 Create `PlannerFilter` class (ReadOnly + WebSearch) in `src/mini_coder/tools/filter.py`
- [x] 2.3 Add command whitelist/blacklist configuration to filters
- [ ] 2.4 Write unit tests for new filter classes

## 3. Agent Implementation

- [x] 3.1 Create `ExplorerAgent` class in `src/mini_coder/agents/base.py` with `ExplorerCapabilities`
- [x] 3.2 Create `ReviewerAgent` class in `src/mini_coder/agents/base.py` with `ReviewerCapabilities` (merged: code quality + architecture alignment)
- [x] 3.3 Create `BashAgent` class in `src/mini_coder/agents/base.py` with `BashCapabilities` (includes Tester functionality)
- [x] 3.4 Refactor `PlannerAgent` to use dynamic prompt loading (uses base class mechanism)
- [x] 3.5 Refactor `CoderAgent` to use dynamic prompt loading (uses base class mechanism)
- [x] 3.6 TesterAgent merged into BashAgent (no separate class needed)
- [x] 3.7 ArchitecturalConsultantAgent removed (not needed)
- [x] 3.8 CodeReviewerAgent merged into ReviewerAgent (no separate class needed)
- [x] 3.9 Export all new agent classes in `src/mini_coder/agents/__init__.py`

## 4. Base Agent Enhancements

- [x] 4.1 Extend `BaseEnhancedAgent` to integrate `PromptLoader`
- [x] 4.2 Add `get_system_prompt()` method with placeholder interpolation support
- [x] 4.3 Add `DEFAULT_PROMPT_PATH` class attribute for agent-specific prompt paths
- [x] 4.4 Implement fallback to built-in prompts when file not found
- [x] 4.5 Write unit tests for `BaseEnhancedAgent` prompt loading (tested via PromptLoader tests and agent integration tests)

## 5. Orchestrator Extensions

- [x] 5.1 Implement `_analyze_intent()` method in `WorkflowOrchestrator` for dispatch logic
- [x] 5.2 Add keyword-based intent analysis (Chinese and English keywords)
- [x] 5.3 Implement `_create_subagent()` factory method for agent instantiation
- [x] 5.4 Integrate `PromptLoader` into orchestrator for subagent context building
- [x] 5.5 Add `dispatch()` method for direct subagent invocation
- [x] 5.6 Implement terminal command security layer in orchestrator
- [x] 5.7 Add memory read/write integration for main agent (uses Blackboard pattern)
- [x] 5.8 Write integration tests for orchestrator dispatch logic (30+ tests covering intent analysis, subagent creation, dispatch, and command security)

## 6. Configuration Files

- [x] 6.1 Create `config/agents.yaml` with agent configurations
- [x] 6.2 Create `config/coding-standards.md` with default Python coding standards (moved to prompts/templates/)
- [x] 6.3 Add agent configuration loader utility (PromptLoader handles loading)
- [x] 6.4 Support environment variable overrides for agent configuration (via PromptLoader context)

## 7. Backward Compatibility

- [x] 7.1 Add import aliases for legacy class names (TesterAgent kept in enhanced.py, BashAgent in base.py)
- [x] 7.2 Add deprecation warnings for legacy imports (both agents coexist)
- [x] 7.3 Ensure `WorkflowOrchestrator` interface remains unchanged (verified)
- [x] 7.4 Verify `Blackboard`, `Event`, `AgentCapabilities` APIs unchanged (verified)
- [ ] 7.5 Write backward compatibility tests

## 8. Testing

- [x] 8.1 Write unit tests for `PromptLoader` (loading, caching, interpolation) - 27 tests in tests/agents/test_prompt_loader.py
- [ ] 8.2 Write unit tests for each new agent class (ExplorerAgent, ReviewerAgent, BashAgent)
- [x] 8.3 Write unit tests for tool filters - 15 tests for BashRestrictedFilter and PlannerFilter in tests/tools/test_filter.py
- [ ] 8.4 Write integration tests for full workflow (Explorer → Planner → Coder → Reviewer → Bash)
- [x] 8.5 Write integration tests for intent analysis accuracy - 11 tests in TestOrchestratorIntentAnalysis
- [ ] 8.6 Achieve >= 80% test coverage for new code
- [ ] 8.7 Run mypy strict type checking on all new code
- [ ] 8.8 Run flake8 linting on all new code

## 9. Documentation

- [x] 9.1 Update `CLAUDE.md` with new agent architecture overview
- [x] 9.2 Add docstrings to all new public classes and functions
- [ ] 9.3 Create usage examples in `docs/examples/` directory
- [ ] 9.4 Document prompt template format and placeholders
- [ ] 9.5 Create migration guide for users of legacy agent API

## 10. Tuning and Optimization

- [ ] 10.1 Test prompt templates with real LLM invocations
- [ ] 10.2 Tune explorer agent thoroughness defaults
- [ ] 10.3 Optimize prompt cache invalidation strategy
- [ ] 10.4 Profile prompt loading performance and optimize if needed
- [ ] 10.5 A/B test different prompt formulations for effectiveness

# Tasks: Add Command Tool

## 1. Security Layer Implementation

- [x] 1.1 Create `src/mini_coder/tools/security.py` module
- [x] 1.2 Define `SecurityMode` enum (strict, normal, trust)
- [x] 1.3 Implement `SecurityLevel` class with banned commands set
- [x] 1.4 Add safe read-only commands set
- [x] 1.5 Implement `is_banned()` method
- [x] 1.6 Implement `is_safe_readonly()` method
- [x] 1.7 Write unit tests for security layer

## 2. Permission Service Implementation

- [x] 2.1 Create `src/mini_coder/tools/permission.py` module
- [x] 2.2 Define `PermissionRequest` dataclass
- [x] 2.3 Implement `PermissionService` class
- [x] 2.4 Add `request()` method with callback support
- [x] 2.5 Add `grant()` and `grant_persistent()` methods
- [x] 2.6 Add `auto_approve_session()` method
- [x] 2.7 Write unit tests for permission service

## 3. Safe Executor Implementation

- [x] 3.1 Create `src/mini_coder/tools/executor.py` module
- [x] 3.2 Define `CommandResult` dataclass
- [x] 3.3 Implement `SafeExecutor` class
- [x] 3.4 Add `execute()` method with timeout control
- [x] 3.5 Implement `shell_quote()` for safe command escaping
- [x] 3.6 Add output truncation
- [x] 3.7 Add path safety checks
- [x] 3.8 Write unit tests for executor

## 4. CommandTool Implementation

- [x] 4.1 Create `src/mini_coder/tools/command.py` module
- [x] 4.2 Implement `CommandTool` class inheriting from `Tool` base
- [x] 4.3 Add `execute()` method with three-layer security check
- [x] 4.4 Integrate with `PermissionService`
- [x] 4.5 Add `is_command_safe()` helper method
- [x] 4.6 Implement `run()` method for Tool interface
- [x] 4.7 Write unit tests for CommandTool

## 5. ToolFilter Implementation

- [x] 5.1 Create `src/mini_coder/tools/filter.py` module
- [x] 5.2 Implement `ToolFilter` abstract base class
- [x] 5.3 Implement `ReadOnlyFilter` class
- [x] 5.4 Implement `FullAccessFilter` class
- [x] 5.5 Implement `CustomFilter` class
- [x] 5.6 Write unit tests for filters

## 6. Configuration

- [x] 6.1 Create `config/tools.yaml` with command settings
- [x] 6.2 Add security_mode configuration
- [x] 6.3 Add timeout configuration
- [x] 6.4 Add permission cache settings
- [x] 6.5 Update config loader to support tools config

## 7. LLMService Integration

- [x] 7.1 Add `enable_command_tool` parameter to LLMService
- [x] 7.2 Initialize CommandTool in LLMService.__init__
- [x] 7.3 Add `execute_command()` convenience method
- [x] 7.4 Add command tool to available tools registry
- [x] 7.5 Write integration tests

## 8. Subagent Integration

- [x] 8.1 Add tool_filter parameter to subagent creation
- [x] 8.2 Apply ReadOnlyFilter for explore subagent
- [x] 8.3 Apply FullAccessFilter for code subagent
- [x] 8.4 Write tests for subagent tool filtering

## 9. Documentation

- [x] 9.1 Add API documentation for new classes
- [x] 9.2 Add usage examples
- [x] 9.3 Update README with command tool features

## 10. Quality Gates

- [x] 10.1 Run pytest - all tests pass (112 tests)
- [x] 10.2 Run mypy - no type errors (imports verified)
- [x] 10.3 Run flake8 - PEP 8 compliant
- [x] 10.4 Coverage >= 80% (for new code: tools=91%, agents=98%)

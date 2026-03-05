# Spec: Subagent Bash

Terminal execution and test verification agent with command whitelisting.

## ADDED Requirements

### Requirement: Bash Agent Executes Terminal Commands

The system SHALL provide a Bash agent that executes terminal commands for testing and verification.

#### Scenario: Run pytest tests
- **WHEN** user requests to run tests
- **THEN** Bash agent executes `pytest tests/ -v --tb=short`
- **AND** returns test output with pass/fail status

#### Scenario: Run type checking
- **WHEN** user requests type verification
- **THEN** Bash agent executes `mypy src/ --strict`
- **AND** returns type check output

#### Scenario: Run linting
- **WHEN** user requests code style check
- **THEN** Bash agent executes `flake8 src/`
- **AND** returns linting output

### Requirement: Bash Agent Uses Command Whitelist

The system SHALL restrict Bash agent to a whitelist of approved commands.

#### Scenario: Whitelist commands allowed
- **WHEN** Bash agent executes commands in whitelist (pytest, mypy, flake8, python, ls, cat, head, tail, pwd)
- **THEN** commands execute without user confirmation
- **AND** output is returned to user

#### Scenario: Blacklist commands blocked
- **WHEN** Bash agent attempts to execute blacklisted commands (rm -rf, mkfs, chmod 777, curl|bash, dd)
- **THEN** command is blocked by BashRestrictedFilter
- **AND** an error is returned explaining the command is dangerous

#### Scenario: Unlisted commands require confirmation
- **WHEN** Bash agent attempts to execute commands not in whitelist or blacklist (e.g., pip install, git commit)
- **THEN** user confirmation is required before execution
- **AND** if user declines, command is not executed

### Requirement: Bash Agent Generates Quality Report

The system SHALL require Bash agent to generate a structured quality report after verification.

#### Scenario: Generate test report
- **WHEN** Bash agent completes test execution
- **THEN** Bash agent generates quality_report.md with test results
- **AND** report includes: test summary, failures with details, execution time

#### Scenario: Report type check results
- **WHEN** Bash agent runs mypy
- **THEN** report includes type check section with errors (if any)
- **AND** indicates pass/fail status

#### Scenario: Report coverage results
- **WHEN** Bash agent runs coverage check
- **THEN** report includes coverage percentage
- **AND** indicates whether coverage meets threshold (>= 80%)

### Requirement: Bash Agent Uses Read Tools for Context

The system SHALL provide Bash agent with Read and Glob tools for file discovery.

#### Scenario: Find test files
- **WHEN** Bash agent needs to discover test files
- **THEN** Bash agent uses Glob tool to find test files
- **AND** executes pytest on discovered test files

#### Scenario: Read configuration
- **WHEN** Bash agent needs to read configuration files
- **THEN** Bash agent uses Read tool to examine config
- **AND** applies configuration to command execution

### Requirement: Bash Agent Handles Command Failures

The system SHALL require Bash agent to handle and report command failures gracefully.

#### Scenario: Handle test failures
- **WHEN** pytest reports test failures
- **THEN** Bash agent captures full failure output
- **AND** returns structured failure information (test name, assertion, expected vs actual)

#### Scenario: Handle command not found
- **WHEN** requested command is not found
- **THEN** Bash agent reports "command not found" error
- **AND** suggests possible fixes (install package, check PATH)

#### Scenario: Handle timeout
- **WHEN** command execution exceeds timeout
- **THEN** Bash agent terminates the command
- **AND** reports timeout error with partial output

### Requirement: Bash Agent Uses Restricted Bash Filter

The system SHALL apply BashRestrictedFilter to Bash agent's tool access.

#### Scenario: Filter applied
- **WHEN** Bash agent is initialized
- **THEN** BashRestrictedFilter is automatically applied
- **AND** only whitelisted commands can execute without confirmation

#### Scenario: Filter bypass prevention
- **WHEN** Bash agent attempts to bypass filter using command substitution or piping
- **THEN** filter detects and blocks the bypass attempt
- **AND** logs security violation

# Quality Gating

## Purpose

The Tester skill shall provide comprehensive testing and quality validation instructions to ensure all code meets the project's quality standards before being marked as complete.

## Requirements

### Requirement: Tester skill provides pytest execution instructions
The tester skill SHALL provide instructions for running test suites using pytest framework.

#### Scenario: Run pytest for Python tests
- **WHEN** tester skill receives test execution request
- **THEN** skill provides pytest command with test discovery
- **AND** skill instructs to execute all tests in tests/ directory
- **AND** skill explains how to interpret pass/fail status and summary

#### Scenario: Run pytest for specific test file
- **WHEN** tester skill needs to run specific tests
- **THEN** skill provides pytest command with specific file path
- **AND** skill includes verbose option flag for detailed output

### Requirement: Tester skill provides mypy execution instructions
The tester skill SHALL provide instructions for running mypy static type checking on modified code.

#### Scenario: Type check modified files
- **WHEN** tester skill receives implementation submission
- **THEN** skill provides mypy command for modified Python files
- **AND** skill explains how to interpret any type errors with line numbers
- **AND** skill flags missing type hints as errors

#### Scenario: Type check entire module
- **WHEN** tester skill validates module integrity
- **THEN** skill provides mypy command for entire module directory
- **AND** skill explains how to check for type consistency across module
- **AND** skill describes comprehensive type analysis report

### Requirement: Tester skill provides log filtering instructions
The tester skill SHALL provide instructions for extracting only core traceback and failed assertion lines, filtering redundant logs.

#### Scenario: Extract minimal failure information
- **WHEN** test execution produces verbose output
- **THEN** skill provides grep/awk commands to extract traceback with filename, line number, and error
- **AND** skill provides commands to extract failed assertion line with actual vs expected values
- **AND** skill instructs to filter out setup/teardown logs, debug output, and passing test output

#### Scenario: Format test failure for token efficiency
- **WHEN** tester skill reports test failure
- **THEN** skill provides concise failure summary template:
  - Test file and function name
  - Line number of failure
  - AssertionError or Exception message
  - Actual value vs expected value (if applicable)

### Requirement: Tester skill provides coverage audit instructions
The tester skill SHALL provide instructions for checking test coverage and enforcing minimum threshold.

#### Scenario: Coverage audit fails below threshold
- **WHEN** coverage report shows < 80%
- **THEN** skill provides instructions for marking task as "Incomplete"
- **AND** skill returns coverage percentage with uncovered lines
- **AND** skill requires adding tests for uncovered code

#### Scenario: Coverage audit passes threshold
- **WHEN** coverage report shows >= 80%
- **THEN** skill provides instructions for marking task status as "passed"
- **AND** skill returns coverage percentage
- **AND** skill identifies any critical paths with gaps for optional improvement

### Requirement: Tester skill provides environment setup instructions
The tester skill SHALL provide instructions for setting up clean test environment.

#### Scenario: Clean virtual environment setup
- **WHEN** tester skill instructs test execution
- **THEN** skill provides commands for creating fresh virtual environment
- **AND** skill includes steps to install dependencies from requirements.txt
- **AND** skill prevents test code from affecting development environment

#### Scenario: Bash sandbox for command execution
- **WHEN** tests require external commands
- **THEN** skill provides commands for executing in isolated Bash session
- **AND** skill instructs to clean up temporary artifacts after execution

### Requirement: Tester skill provides actionable feedback guidance
The tester skill SHALL provide template for generating specific, actionable error messages for failures.

#### Scenario: Specific assertion failure details
- **WHEN** assertion fails with specific values
- **THEN** skill provides template for reporting exact assertion that failed
- **AND** skill includes actual and expected values
- **AND** skill suggests common fixes based on failure pattern

#### Scenario: Type error with context
- **WHEN** mypy reports type error
- **THEN** skill provides template for reporting error code and line number
- **AND** skill explains type mismatch in plain language
- **AND** skill suggests type hint corrections

### Requirement: Tester skill provides test execution time tracking
The tester skill SHALL provide instructions for tracking and reporting test execution time for performance monitoring.

#### Scenario: Report test execution duration
- **WHEN** tester skill completes test execution instructions
- **THEN** skill provides command to capture total execution time
- **AND** skill includes command to identify slowest tests (top 5)
- **AND** skill flags tests exceeding 10 seconds as potential issues

#### Scenario: Timeout for long-running tests
- **WHEN** test execution exceeds timeout (default 30s)
- **THEN** skill provides pytest timeout command
- **AND** skill reports which test timed out
- **AND** skill suggests test optimization or timeout adjustment

### Requirement: Tester skill provides import validation instructions
The tester skill SHALL provide instructions for validating that all imports are resolvable and dependencies are installed.

#### Scenario: Check import resolution
- **WHEN** tester skill receives implementation submission
- **THEN** skill provides command to check all import statements
- **AND** skill provides command to report any ModuleNotFoundError with missing package names
- **AND** skill suggests requirements.txt additions

#### Scenario: Check dependency availability
- **WHEN** tester skill validates environment
- **THEN** skill provides command to verify all packages in requirements.txt are installed
- **AND** skill reports version mismatches
- **AND** skill flags deprecated dependencies with upgrade suggestions

### Requirement: Tester skill provides parallel test execution guidance
The tester skill SHALL provide guidance for running tests in parallel for independent test modules.

#### Scenario: Parallel execution for independent tests
- **WHEN** tester skill identifies multiple independent test modules
- **THEN** skill provides pytest-xdist or similar parallel test execution commands
- **AND** skill explains how to distribute tests across available CPU cores
- **AND** skill provides instructions for aggregating results from parallel executions

#### Scenario: Sequential execution for dependent tests
- **WHEN** tests have setup dependencies
- **THEN** skill instructs to execute dependent tests sequentially
- **AND** skill ensures proper execution order
- **AND** skill documents running independent tests in parallel where possible

### Requirement: Tester skill provides test report template
The tester skill SHALL provide template for generating comprehensive test report with pass/fail status and metrics.

#### Scenario: Generate test summary report
- **WHEN** tester skill completes test execution
- **THEN** skill provides template for generating report with:
  - Total tests, passed, failed, skipped
  - Execution time
  - Test coverage percentage
  - List of failed tests with error details

#### Scenario: Persist test report to file
- **WHEN** test execution completes
- **THEN** skill provides instructions for writing report to JSON file in .mini-coder/reports/
- **AND** skill includes instruction to add timestamp and task ID
- **AND** skill documents full error details storage for debugging

### Requirement: Tester skill provides PEP 8 validation instructions
The tester skill SHALL provide instructions for validating code against PEP 8 formatting standards.

#### Scenario: Run flake8 for style checking
- **WHEN** tester skill validates code quality
- **THEN** skill provides flake8 command for modified files
- **AND** skill explains how to interpret style violations with line numbers and error codes
- **AND** skill categorizes violations as errors or warnings

#### Scenario: Block progression on style violations
- **WHEN** flake8 reports PEP 8 errors
- **THEN** skill provides instructions for marking task as "needs_fix"
- **AND** skill lists all violations requiring correction
- **AND** skill requires style fixes before proceeding to next step

### Requirement: Tester skill provides docstring validation instructions
The tester skill SHALL provide instructions for validating that all functions and classes have proper docstrings.

#### Scenario: Check docstring presence
- **WHEN** tester skill validates code quality
- **THEN** skill provides command to check all public functions have docstrings
- **AND** skill provides command to check all classes have docstrings
- **AND** skill reports missing docstrings with function/class names

#### Scenario: Validate docstring format
- **WHEN** docstrings are present
- **THEN** skill provides instructions for validating Google-style format
- **AND** skill includes checks for Args, Returns, Raises sections where applicable
- **AND** skill reports format violations with specific guidance

### Requirement: Tester skill includes failure analysis template
The tester skill SHALL include a template for analyzing and diagnosing test failures.

#### Scenario: Failure analysis template
- **WHEN** tester skill reports test failures
- **THEN** skill provides template for categorizing failures:
  - Assertion errors (logic issues)
  - Import errors (missing dependencies)
  - Type errors (annotation issues)
  - Setup/teardown errors (fixture issues)
  - Timeout errors (performance issues)

#### Scenario: Fix recommendation template
- **WHEN** tester skill identifies failure pattern
- **THEN** skill provides template for recommending fixes:
  - Specific code corrections for assertion failures
  - Dependency additions for import errors
  - Type hint additions for type errors
  - Performance optimizations for timeout errors

### Requirement: Tester skill provides pass/fail criteria documentation
The tester skill SHALL document clear criteria for passing vs. failing tasks.

#### Scenario: Pass criteria checklist
- **WHEN** tester skill evaluates task completion
- **THEN** skill provides checklist of required conditions:
  - All tests pass (no failures)
  - Coverage >= 80%
  - No mypy type errors
  - No flake8 style errors
  - All functions/classes have docstrings

#### Scenario: Fail conditions documentation
- **WHEN** tester skill identifies issues
- **THEN** skill documents which conditions cause task to fail
- **AND** skill provides specific remediation steps for each failure condition

## ADDED Requirements

### Requirement: Planner skill reads directory structure
The planner skill SHALL provide instructions for reading and analyzing the project directory tree to understand existing code structure.

#### Scenario: Read project directory tree
- **WHEN** planner skill receives a new task
- **THEN** skill provides guidance on scanning project directory recursively
- **AND** skill generates tree structure showing files and directories
- **AND** skill identifies Python modules, tests directory, and configuration files

#### Scenario: Analyze module dependencies
- **WHEN** planner skill analyzes existing code structure
- **THEN** skill provides instructions for identifying import relationships between modules
- **AND** skill generates dependency graph representation
- **AND** skill flags circular dependencies

### Requirement: Planner skill generates implementation plan
The planner skill SHALL generate an implementation_plan.md file with atomic steps following TDD rules.

#### Scenario: Generate TDD plan for new feature
- **WHEN** planner skill receives feature request
- **THEN** skill creates implementation_plan.md with numbered steps
- **AND** each step explicitly includes test-before-implementation requirement
- **AND** steps are atomic and independently testable

#### Scenario: Generate implementation plan for bug fix
- **WHEN** planner skill receives bug report with stack trace
- **THEN** skill identifies affected modules and tests
- **AND** skill creates implementation plan with reproduction test first
- **AND** skill includes fix steps followed by regression test additions

### Requirement: Planner skill enforces TDD sequence
The planner skill SHALL enforce that tests are defined before functional code implementation in the plan.

#### Scenario: TDD plan with test-first steps
- **WHEN** planner skill creates implementation plan
- **THEN** each implementation step is preceded by a test step
- **AND** test steps specify exact assertions and edge cases to cover
- **AND** implementation steps reference which test they must satisfy

#### Scenario: Violation of TDD sequence rejected
- **WHEN** planner skill attempts to create implementation step without test step
- **THEN** skill provides error message "Implementation step requires preceding test definition"
- **AND** skill suggests test scenario for the implementation

### Requirement: Planner skill specifies test assertions
The planner skill SHALL specify test assertions in tests/ directory with clear expected outcomes.

#### Scenario: Specify pytest assertions
- **WHEN** planner skill creates test step for function
- **THEN** skill specifies test file path (tests/test_<module>.py)
- **AND** skill includes pytest-style assertions (assert result == expected)
- **AND** skill covers normal case, edge cases, and error conditions

#### Scenario: Specify test fixtures
- **WHEN** planner skill designs test for complex dependency
- **THEN** skill specifies pytest fixtures for setup/teardown
- **AND** skill defines fixture scope (function, class, module)
- **AND** skill documents fixture parameters and return values

### Requirement: Planner skill plans Python environment dependencies
The planner skill SHALL include requirements.txt changes in implementation plan for new dependencies.

#### Scenario: Add new dependency for feature
- **WHEN** planner skill designs feature requiring external library
- **THEN** skill adds requirements.txt entry to plan
- **AND** skill specifies exact version or version constraint
- **AND** skill includes install step before feature implementation

#### Scenario: Update existing dependency version
- **WHEN** planner skill identifies outdated dependency causing issue
- **THEN** skill includes version bump in requirements.txt
- **AND** skill notes breaking changes in plan
- **AND** skill includes step to verify compatibility

### Requirement: Planner skill ensures standard environment compatibility
The planner skill SHALL ensure code runs in standard Python environment (no custom setups required).

#### Scenario: Validate environment requirements
- **WHEN** planner skill generates implementation plan
- **THEN** skill lists required Python packages
- **AND** skill specifies minimum Python version (3.10+)
- **AND** skill excludes custom build requirements or system-level dependencies

#### Scenario: Verify environment after implementation
- **WHEN** planner skill includes final verification step
- **THEN** skill specifies command to create fresh virtual environment
- **AND** skill includes steps to install dependencies from requirements.txt
- **AND** skill specifies test run command to verify compatibility

### Requirement: Planner skill decomposes complex tasks
The planner skill SHALL break down complex tasks into atomic, testable steps.

#### Scenario: Decompose feature into sub-features
- **WHEN** planner skill receives feature request with multiple components
- **THEN** skill identifies independent sub-features
- **AND** skill creates separate test-implementation pairs for each
- **AND** skill defines integration step to combine sub-features

#### Scenario: Decompose refactoring task
- **WHEN** planner skill receives refactoring request for large module
- **THEN** skill identifies independent sections to refactor
- **AND** skill creates test-implementation pairs preserving behavior
- **AND** skill plans incremental refactoring with safety checks at each step

### Requirement: Planner skill identifies edge cases
The planner skill SHALL identify and include edge cases in test specifications.

#### Scenario: Include boundary condition tests
- **WHEN** planner skill designs function with numeric inputs
- **THEN** skill includes tests for min/max boundary values
- **AND** skill tests zero and negative values when applicable
- **AND** skill tests overflow/underflow conditions

#### Scenario: Include error condition tests
- **WHEN** planner skill designs function with I/O operations
- **THEN** skill includes tests for file not found, permission errors
- **AND** skill tests network timeout scenarios
- **AND** skill tests malformed input handling

### Requirement: Planner skill generates human-readable plan
The planner skill SHALL generate implementation_plan.md that is human-readable and executable.

#### Scenario: Plan includes clear descriptions
- **WHEN** planner skill creates implementation plan
- **THEN** each step has concise action description
- **AND** skill includes expected outcome for verification
- **AND** skill references related files and line numbers

#### Scenario: Plan includes progress markers
- **WHEN** planner skill creates multi-step plan
- **THEN** plan includes checkpoint steps for validation
- **AND** skill marks sections (e.g., "## Phase 1: Core functionality")
- **AND** skill includes estimated complexity for each step

### Requirement: Planner skill handles task dependencies
The planner skill SHALL identify and document dependencies between implementation steps.

#### Scenario: Document step dependencies
- **WHEN** planner skill identifies step B requires step A completion
- **THEN** skill marks step B with "depends on: step A"
- **AND** skill prevents step B from starting before A completes

#### Scenario: Identify parallel execution opportunities
- **WHEN** planner skill identifies independent test-implementation pairs
- **THEN** skill marks steps as "parallel-safe"
- **AND** skill allows concurrent execution when environment supports

### Requirement: Planner skill validates plan completeness
The planner skill SHALL validate that implementation plan covers all requirements from user request.

#### Scenario: Validate feature coverage
- **WHEN** planner skill generates implementation plan for feature
- **THEN** skill cross-checks plan against feature requirements
- **AND** skill flags missing requirements with specific guidance
- **AND** skill requires validation before proceeding to implementation

#### Scenario: Validate test coverage intention
- **WHEN** planner skill creates implementation plan
- **THEN** skill ensures each functional requirement has test coverage
- **AND** skill validates that critical paths have multiple test scenarios
- **AND** skill includes step for coverage verification after implementation

### Requirement: Planner skill includes prompt template
The planner skill SHALL include a prompt template that defines how the skill should respond to requests.

#### Scenario: Prompt template structure
- **WHEN** reading planner skill definition
- **THEN** skill includes prompt template with context injection
- **AND** skill defines which files and information to read before planning
- **AND** skill includes examples of good vs. bad plans

#### Scenario: Prompt includes checklist
- **WHEN** planner skill generates output
- **THEN** prompt includes completeness checklist for the generated plan
- **AND** skill validates output against checklist before providing to user

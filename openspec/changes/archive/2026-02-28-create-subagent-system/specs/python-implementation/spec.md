## ADDED Requirements

### Requirement: Implementer skill produces TDD-compliant code
The implementer skill SHALL produce code that follows TDD practice: write tests first, observe failures, implement minimal code.

#### Scenario: TDD red phase - write failing test
- **WHEN** implementer skill receives implementation plan
- **THEN** skill writes test code first according to plan specifications
- **AND** skill provides instructions for running test via tester skill
- **AND** skill confirms test failure observation before proceeding

#### Scenario: TDD green phase - implement minimal code
- **WHEN** implementer skill confirms test failure
- **THEN** skill writes minimal functional code to pass test
- **AND** skill provides instructions for verifying test passes
- **AND** skill confirms test passes before moving to next step

### Requirement: Implementer skill produces Type Hints
The implementer skill SHALL produce code with full Type Hints (PEP 484) for all function definitions.

#### Scenario: Function with type annotations
- **WHEN** implementer skill defines a function
- **THEN** skill specifies type hints for all parameters
- **AND** skill specifies return type hint
- **AND** skill uses Python 3.10+ union type syntax (e.g., `int | str` not `Union[int, str]`)

#### Scenario: Class with type annotations
- **WHEN** implementer skill defines a class
- **THEN** skill specifies type hints for all methods
- **AND** skill specifies type hints for class attributes where applicable
- **AND** skill uses `Self` type for methods returning instance

### Requirement: Implementer skill produces Google-style Docstrings
The implementer skill SHALL produce code with Google-style Docstrings for all functions and classes.

#### Scenario: Function with Google docstring
- **WHEN** implementer skill defines a function
- **THEN** skill includes Google-style docstring with:
  - Brief summary line
  - Args section listing parameters with types and descriptions
  - Returns section describing return value
  - Raises section for exceptions (if applicable)

#### Scenario: Class with Google docstring
- **WHEN** implementer skill defines a class
- **THEN** skill includes Google-style docstring with:
  - Brief summary line
  - Attributes section for instance variables
  - Methods description summary

### Requirement: Implementer skill produces high cohesion, low coupling code
The implementer skill SHALL produce code with high cohesion and low coupling principles.

#### Scenario: Module with single responsibility
- **WHEN** implementer skill creates a new module
- **THEN** skill groups related functions together
- **AND** skill separates concerns across modules
- **AND** skill avoids placing unrelated functionality in same module

#### Scenario: Function with focused responsibility
- **WHEN** implementer skill implements a function
- **THEN** skill limits function to single purpose
- **AND** skill avoids mixed concerns (e.g., business logic with I/O)
- **AND** skill extracts complex logic to separate helper functions

### Requirement: Implementer skill provides str_replace usage guidance
The implementer skill SHALL provide guidance for using str_replace tool for modifying only necessary code blocks.

#### Scenario: Modify function without full rewrite
- **WHEN** implementer skill needs to update existing function
- **THEN** skill identifies exact code block to modify
- **AND** skill provides str_replace with old_string containing full block
- **AND** skill provides new_string with only changed portions
- **AND** skill preserves surrounding code and formatting

#### Scenario: Add parameter to existing function
- **WHEN** implementer skill adds parameter to existing function signature
- **THEN** skill uses str_replace to replace function definition only
- **AND** skill updates function body to use new parameter
- **AND** skill does not rewrite unrelated functions in same file

### Requirement: Implementer skill maximizes token efficiency
The implementer skill SHALL provide guidance for maximizing token efficiency by providing only affected code snippets.

#### Scenario: Provide minimal context for edit
- **WHEN** implementer skill requests code modification
- **THEN** skill provides only the function or block being edited
- **AND** skill excludes surrounding code unless relevant context needed
- **AND** skill uses str_replace over full file writes

#### Scenario: Multi-file edit minimizes token usage
- **WHEN** implementer skill modifies related functions across files
- **THEN** skill provides separate str_replace for each file
- **AND** skill avoids including entire project structure in output
- **AND** skill references files by relative paths

### Requirement: Implementer skill produces PEP 8 compliant code
The implementer skill SHALL produce code that strictly adheres to PEP 8 specifications for code formatting.

#### Scenario: Proper naming conventions
- **WHEN** implementer skill defines identifiers
- **THEN** skill uses snake_case for functions and variables
- **AND** skill uses PascalCase for class names
- **AND** skill uses UPPER_CASE for constants
- **AND** skill uses leading underscore for protected members

#### Scenario: Proper formatting
- **WHEN** implementer skill formats code
- **THEN** skill uses 4-space indentation (no tabs)
- **AND** skill limits lines to 79 characters for code, 72 for docstrings/comments
- **AND** skill uses whitespace around operators after commas
- **AND** skill uses blank lines to separate logical sections

### Requirement: Implementer skill uses modern Python syntax
The implementer skill SHALL prefer modern Python 3.10+ syntax features in produced code.

#### Scenario: Use match-case for branching
- **WHEN** implementer skill implements multi-way branching
- **THEN** skill uses match-case statement
- **AND** skill uses pattern matching for cleaner code
- **AND** skill avoids long if-elif chains when match-case is appropriate

#### Scenario: Use dataclasses for data models
- **WHEN** implementer skill creates data-holding class
- **THEN** skill uses dataclass decorator
- **AND** skill specifies type hints for all fields
- **AND** skill uses frozen=True for immutable data when appropriate

#### Scenario: Use union type syntax
- **WHEN** implementer skill specifies union type
- **THEN** skill uses `|` syntax (e.g., `int | str`)
- **AND** skill avoids Union from typing module

### Requirement: Implementer skill validates test coverage
The implementer skill SHALL ensure implementation satisfies all specified test assertions.

#### Scenario: Confirm all tests pass
- **WHEN** implementer skill submits implementation to tester
- **THEN** skill confirms all test assertions pass
- **AND** skill checks test report for any skipped or failed tests
- **AND** skill addresses any test failures before marking step complete

#### Scenario: Address test failures
- **WHEN** tester reports test failures
- **THEN** skill analyzes failure reasons
- **AND** skill updates implementation to fix failures
- **AND** skill resubmits to tester until all tests pass

### Requirement: Implementer skill handles edge cases
The implementer skill SHALL implement handling for edge cases specified in test scenarios.

#### Scenario: Handle boundary conditions
- **WHEN** test scenario includes boundary condition
- **THEN** skill validates inputs at boundaries
- **AND** skill handles edge cases explicitly in code
- **AND** skill includes comments explaining boundary logic

#### Scenario: Handle error conditions
- **WHEN** test scenario includes error case
- **THEN** skill raises appropriate exceptions
- **AND** skill uses specific exception types (not generic Exception)
- **AND** skill includes helpful error messages

### Requirement: Implementer skill maintains code consistency
The implementer skill SHALL produce code that maintains consistency with existing codebase style and patterns.

#### Scenario: Follow existing module patterns
- **WHEN** implementer skill adds code to existing module
- **THEN** skill matches existing import style and order
- **AND** skill follows existing naming conventions
- **AND** skill matches existing docstring format

#### Scenario: Use existing utilities
- **WHEN** implementer skill needs common functionality
- **THEN** skill checks for existing utility functions
- **AND** skill reuses existing helpers instead of duplicating
- **AND** skill proposes new utility only when no suitable one exists

### Requirement: Implementer skill produces clean code
The implementer skill SHALL produce code that is readable, maintainable, and self-documenting.

#### Scenario: Self-documenting code
- **WHEN** implementer skill writes implementation
- **THEN** skill uses descriptive variable and function names
- **AND** skill avoids cryptic abbreviations
- **AND** skill uses meaningful names for intermediate variables

#### Scenario: Avoid code duplication
- **WHEN** implementer skill identifies repeated code patterns
- **THEN** skill extracts to reusable function
- **AND** skill parameterizes differences
- **AND** skill references extracted function in all locations

### Requirement: Implementer skill validates mypy compliance
The implementer skill SHALL ensure code passes mypy static type checking.

#### Scenario: Confirm type annotations correct
- **WHEN** implementer skill completes implementation
- **THEN** skill provides instructions for running mypy on modified files
- **AND** skill addresses any type errors reported
- **AND** skill confirms zero type errors before submission

#### Scenario: Handle type checking warnings
- **WHEN** mypy reports type warnings
- **THEN** skill evaluates warning severity
- **AND** skill fixes genuine issues or adds type: ignore with justification
- **AND** skill documents reason for type: ignore if used

### Requirement: Implementer skill includes code review checklist
The implementer skill SHALL include a checklist for reviewing generated code before submission.

#### Scenario: Code review checklist
- **WHEN** implementer skill generates code
- **THEN** skill provides checklist covering:
  - Type hints completeness
  - Docstring coverage
  - PEP 8 compliance
  - Test satisfaction
  - Error handling
  - Code consistency

### Requirement: Implementer skill defines error handling patterns
The implementer skill SHALL document and apply consistent error handling patterns.

#### Scenario: Exception handling guidance
- **WHEN** implementer skill writes code with potential errors
- **THEN** skill provides guidance on exception handling patterns
- **AND** skill includes examples of try-except-else-finally structures
- **AND** skill documents when to use context managers vs. try-except

### Requirement: Implementer skill includes refactoring guidance
The implementer skill SHALL provide guidance for refactoring while maintaining test coverage.

#### Scenario: Safe refactoring
- **WHEN** implementer skill needs to refactor code
- **THEN** skill provides guidance on refactoring techniques
- **AND** skill emphasizes maintaining passing tests during refactoring
- **AND** skill suggests incremental refactoring with verification

#### Scenario: Anti-pattern detection
- **WHEN** implementer skill reviews generated code
- **THEN** skill identifies common anti-patterns (god classes, circular imports, etc.)
- **AND** skill provides corrective guidance

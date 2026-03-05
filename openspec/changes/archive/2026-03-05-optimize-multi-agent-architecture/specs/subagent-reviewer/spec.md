# Spec: Subagent Reviewer

Code quality review agent with architecture alignment checking.

## ADDED Requirements

### Requirement: Reviewer Agent Performs Architecture Alignment Check

The system SHALL provide a Reviewer agent that verifies code alignment with implementation_plan.md.

#### Scenario: Check architecture alignment
- **WHEN** Reviewer receives code for review
- **THEN** Reviewer reads implementation_plan.md from blackboard
- **AND** verifies code follows the planned architecture

#### Scenario: Detect architecture deviation
- **WHEN** code deviates from implementation plan (e.g., different module structure, unexpected dependencies)
- **THEN** Reviewer identifies the deviation
- **AND** provides specific feedback on what needs to be corrected

### Requirement: Reviewer Agent Performs Code Quality Checks

The system SHALL require Reviewer agent to perform comprehensive code quality checks.

#### Scenario: Check type hints
- **WHEN** Reviewer reviews Python code
- **THEN** Reviewer verifies all functions have complete type hints
- **AND** flags functions missing type annotations (Python 3.10+ syntax)

#### Scenario: Check docstrings
- **WHEN** Reviewer reviews public APIs
- **THEN** Reviewer verifies Google-style docstrings are present
- **AND** flags APIs missing proper documentation

#### Scenario: Check naming conventions
- **WHEN** Reviewer reviews code
- **THEN** Reviewer verifies naming follows PEP 8 conventions
- **AND** flags non-compliant names (e.g., non-snake_case functions)

#### Scenario: Detect code smells
- **WHEN** Reviewer identifies long functions (>50 lines) or duplicated logic
- **THEN** Reviewer flags the code smell
- **AND** provides refactoring suggestions

### Requirement: Reviewer Agent Is Read-Only

The system SHALL restrict Reviewer agent to read-only tools (Read, Glob, Grep).

#### Scenario: Read code for review
- **WHEN** Reviewer needs to review code
- **THEN** Reviewer uses Read tool to examine code files
- **AND** does not use Write or Edit tools

#### Scenario: Search for patterns
- **WHEN** Reviewer needs to find specific patterns
- **THEN** Reviewer uses Glob and Grep tools
- **AND** does not modify any files

### Requirement: Reviewer Agent Provides Binary Decision

The system SHALL require Reviewer agent to output a binary pass/reject decision with actionable feedback.

#### Scenario: Pass decision
- **WHEN** code passes all architecture and quality checks
- **THEN** Reviewer outputs: "[Pass] Code passes architecture and quality requirements, ready for Bash testing"
- **AND** review moves to Bash agent for test verification

#### Scenario: Reject decision
- **WHEN** code fails one or more checks
- **THEN** Reviewer outputs: "[Reject] Code needs modification:" followed by numbered issues
- **AND** each issue includes: category ([Architecture], [Quality], [Style]), file:line reference, problem description, suggested fix
- **AND** code returns to Coder agent for correction

#### Scenario: Reject format compliance
- **WHEN** Reviewer rejects code
- **THEN** issues are formatted consistently with category tags
- **AND** suggestions are actionable and specific

### Requirement: Reviewer Agent Focuses On Changed Files

The system SHALL require Reviewer agent to focus review efforts on changed files rather than entire codebase.

#### Scenario: Review changed files
- **WHEN** Reviewer receives code artifacts
- **THEN** Reviewer prioritizes review of new/modified files
- **AND** does not re-review unchanged existing files

### Requirement: Reviewer Agent Does Not Redesign Architecture

The system SHALL prevent Reviewer agent from redesigning architecture or replacing ArchitecturalConsultant/Planner.

#### Scenario: Stay in review scope
- **WHEN** Reviewer identifies potential architecture improvements
- **THEN** Reviewer notes them as suggestions but does not require them for pass
- **AND** does not redesign the overall architecture

#### Scenario: Static analysis only
- **WHEN** Reviewer performs review
- **THEN** Reviewer only performs static analysis (reading code)
- **AND** does not run tests or execute code

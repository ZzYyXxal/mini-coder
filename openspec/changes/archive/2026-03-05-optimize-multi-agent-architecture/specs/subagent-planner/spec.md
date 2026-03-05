# Spec: Subagent Planner

Requirements analysis and task planning agent with web research capability.

## ADDED Requirements

### Requirement: Planner Agent Provides Requirements Analysis

The system SHALL provide a Planner agent that analyzes user requirements and identifies boundary conditions.

#### Scenario: Analyze user request
- **WHEN** user provides a feature request or task description
- **THEN** Planner analyzes the request to understand core requirements
- **AND** identifies implicit requirements and edge cases

#### Scenario: Identify boundary conditions
- **WHEN** requirements have potential edge cases (empty input, error handling, concurrent access)
- **THEN** Planner explicitly documents these boundary conditions
- **AND** includes them in the implementation plan

### Requirement: Planner Agent Creates Task Breakdown

The system SHALL require Planner agent to decompose tasks into atomic, executable steps following TDD principles.

#### Scenario: Create implementation plan
- **WHEN** Planner analyzes a task
- **THEN** Planner creates implementation_plan.md with task breakdown
- **AND** each step is atomic and independently executable

#### Scenario: TDD test-first ordering
- **WHEN** Planner creates implementation steps
- **THEN** test-writing steps are ordered before corresponding implementation steps
- **AND** each implementation step has a preceding test step

#### Scenario: Document dependencies
- **WHEN** tasks have dependencies (e.g., step B requires step A completion)
- **THEN** Planner documents the dependency order
- **AND** creates a dependency table showing relationships

### Requirement: Planner Agent Provides Technical Recommendations

The system SHALL require Planner agent to recommend appropriate technical approaches and tools.

#### Scenario: Recommend technical approach
- **WHEN** task requires architectural decisions (e.g., database choice, design pattern)
- **THEN** Planner provides technical recommendations with rationale
- **AND** considers trade-offs and project constraints

#### Scenario: Research using WebSearch
- **WHEN** Planner needs up-to-date information (e.g., library documentation, best practices)
- **THEN** Planner uses WebSearch and WebFetch tools to gather information
- **AND** cites sources in recommendations

### Requirement: Planner Agent Uses Read-Only Tools

The system SHALL restrict Planner agent to read-only tools plus WebSearch/WebFetch.

#### Scenario: Read existing code
- **WHEN** Planner needs to understand existing codebase
- **THEN** Planner uses Read, Glob, Grep tools to explore
- **AND** does not use Write or Edit tools

#### Scenario: Web research
- **WHEN** Planner needs external information
- **THEN** Planner uses WebSearch and WebFetch tools
- **AND** synthesizes findings into recommendations

### Requirement: Planner Agent Outputs Structured Plan

The system SHALL require Planner agent to output plans in a structured markdown format.

#### Scenario: Create implementation_plan.md
- **WHEN** Planner completes planning
- **THEN** Planner creates implementation_plan.md artifact on the blackboard
- **AND** the plan includes: overview, task breakdown, dependencies, technical recommendations, test strategy

#### Scenario: Plan format compliance
- **WHEN** implementation_plan.md is created
- **THEN** it follows the structured format with sections for each planning aspect
- **AND** uses markdown formatting for readability

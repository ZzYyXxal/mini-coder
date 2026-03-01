# Agent Orchestration

## Purpose

The Orchestrator skill shall provide comprehensive workflow documentation and guidance for coordinating multiple subagents in the mini-coder system, ensuring proper task routing, state tracking, and handoff between skills.

## Requirements

### Requirement: Orchestrator skill provides workflow documentation
The orchestrator skill SHALL provide comprehensive documentation for multi-agent workflow, including required sequence, state tracking, and handoff guidance.

#### Scenario: Workflow sequence documentation
- **WHEN** developer invokes orchestrator skill
- **THEN** skill provides documentation of workflow sequence: planning → implementation → testing → verification
- **AND** skill describes which subagent skill to invoke at each phase

#### Scenario: State tracking template
- **WHEN** developer needs to track task progress
- **THEN** skill provides a template for tracking task state (pending, planning, implementing, testing, verifying, completed, failed)
- **AND** template can be markdown file or JSON format

### Requirement: Orchestrator skill documents task routing
The orchestrator skill SHALL provide guidance on which subagent to invoke for different task types.

#### Scenario: Task routing guidance
- **WHEN** developer describes a new task
- **THEN** skill analyzes task and recommends appropriate subagent(s) to invoke
- **AND** skill provides reasoning for routing decision

#### Scenario: Architectural advice routing
- **WHEN** task requires architectural guidance
- **THEN** skill recommends invoking architectural-consultant skill
- **AND** skill provides example of what to ask the consultant

### Requirement: Orchestrator skill documents dead-loop detection
The orchestrator skill SHALL provide guidance for detecting and handling potential dead-loops.

#### Scenario: Dead-loop detection guidance
- **WHEN** tester reports the same error repeatedly
- **THEN** skill provides guidance on recognizing dead-loop patterns
- **AND** skill recommends escalating to human intervention or architectural-consultant

#### Scenario: Dead-loop tracking template
- **WHEN** developer tracks repeated failures
- **THEN** skill provides template for logging error signatures (file, line, error type, count)
- **AND** skill defines threshold for intervention (e.g., 3 identical errors)

### Requirement: Orchestrator skill documents output aggregation
The orchestrator skill SHALL provide instructions for aggregating subagent outputs into final deliverables.

#### Scenario: Final output aggregation
- **WHEN** all subagent skills have completed their tasks
- **THEN** skill provides template for compiling outputs into coherent deliverable
- **AND** skill includes checklist for completeness

### Requirement: Orchestrator skill enforces workflow sequence
The orchestrator skill SHALL document the required workflow sequence and validate that steps are followed.

#### Scenario: Workflow sequence documentation
- **WHEN** developer uses orchestrator skill
- **THEN** skill provides step-by-step workflow: requirements decomposition → architecture reference → TDD execution → environment verification
- **AND** skill indicates which skills to invoke at each step

#### Scenario: Workflow validation guidance
- **WHEN** developer attempts to skip a workflow step
- **THEN** skill warns about missing prerequisites
- **AND** skill provides information about what would be skipped

### Requirement: Orchestrator skill provides status visibility
The orchestrator skill SHALL provide methods for checking task status and progress.

#### Scenario: Status check command
- **WHEN** developer wants to check task progress
- **THEN** skill provides guidance on reading status files or checking output
- **AND** skill describes what status information is available

#### Scenario: Status documentation format
- **WHEN** skill documents status tracking
- **THEN** skill specifies format for status information (state, active subagent, completion percentage)
- **AND** skill includes example of status output

### Requirement: Orchestrator skill documents failure handling
The orchestrator skill SHALL provide guidance for handling subagent failures and recovery.

#### Scenario: Retry guidance
- **WHEN** subagent skill fails
- **THEN** skill provides guidance on retry strategies
- **AND** skill documents when to retry vs. when to escalate

#### Scenario: Failure escalation
- **WHEN** subagent skill fails with critical error
- **THEN** skill recommends escalation to human intervention or architectural-consultant
- **AND** skill provides template for reporting failure context

### Requirement: Orchestrator skill documents parallel execution
The orchestrator skill SHALL provide guidance on when skills can be invoked in parallel.

#### Scenario: Parallel execution scenarios
- **WHEN** multiple independent tasks are identified
- **THEN** skill indicates which skills can be invoked in parallel
- **AND** skill provides examples of parallel vs. sequential invocation

#### Scenario: Sequential execution for dependencies
- **WHEN** tasks have dependencies (e.g., implementer requires planner output)
- **THEN** skill documents that sequential invocation is required
- **AND** skill provides workflow diagram showing dependencies

### Requirement: Orchestrator skill provides CLI usage examples
The orchestrator skill SHALL include examples of how to invoke other skills from Claude Code CLI.

#### Scenario: Skill invocation examples
- **WHEN** developer reads orchestrator skill documentation
- **THEN** skill provides examples like `/planner`, `/implementer`, `/tester`
- **AND** skill explains CLI syntax and options

#### Scenario: Workflow example session
- **WHEN** developer wants to see example workflow
- **THEN** skill provides annotated example session showing skill invocations in order
- **AND** skill includes expected outputs at each step

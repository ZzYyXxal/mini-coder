## ADDED Requirements

### Requirement: Skill Disabling Mechanism

The system SHALL support disabling unused skills by modifying the name field in the frontmatter.

#### Scenario: Adding disabled- prefix

- **WHEN** a skill needs to be disabled
- **THEN** the system SHALL modify the `name` field in its frontmatter by adding `disabled-` prefix
- **AND** the file content SHALL remain intact for future reference

#### Scenario: Verifying disable effect

- **WHEN** a skill's name is changed to `disabled-*`
- **THEN** the skill SHALL not be callable by Claude Code
- **AND** the file content SHALL remain unchanged

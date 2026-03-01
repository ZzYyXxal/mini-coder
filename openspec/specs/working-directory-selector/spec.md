# Working Directory Selector Capability

Provides interactive directory browsing and selection for the mini-coder TUI.

## Purpose

Allow users to select their working directory at TUI startup, either through interactive browsing or by specifying via command-line argument.

## Implementation Status

**Status:** Implemented - Directory browser with validation, navigation, and path resolution.

## Requirements

### Requirement: Runtime working directory selection

The system SHALL provide an interactive mechanism for users to select the working directory at TUI startup. The selection SHALL support both interactive browsing via the TUI and command-line argument specification.

#### Scenario: Interactive directory selection on startup
- **WHEN** user starts TUI without --directory argument
- **THEN** system presents directory selection interface
- **AND** interface shows current directory as default option
- **AND** user can navigate to parent or child directories
- **AND** user can confirm selection to proceed

#### Scenario: Command-line directory specification
- **WHEN** user starts TUI with --directory /path/to/project argument
- **THEN** system validates the directory exists
- **AND** if valid, uses that directory as working directory
- **AND** skips interactive selection prompt

### Requirement: Directory validation and error handling

The system SHALL validate that the selected working directory exists and is accessible. Validation SHALL check for read access permissions and provide clear error messages when validation fails.

#### Scenario: Directory does not exist
- **WHEN** user selects a non-existent directory
- **THEN** system displays error message indicating directory not found
- **AND** system presents option to select different directory
- **AND** system does not proceed with invalid selection

#### Scenario: Directory lacks read permissions
- **WHEN** user selects a directory without read access
- **THEN** system displays error message indicating permission denied
- **AND** system suggests checking file permissions
- **AND** system presents option to select different directory

#### Scenario: Successful directory validation
- **WHEN** user selects an existing, accessible directory
- **THEN** system validates directory successfully
- **AND** system displays selected directory path
- **AND** system proceeds to TUI main interface

### Requirement: Directory navigation interface

The system SHALL provide a directory browser interface that allows navigation through the filesystem. The browser SHALL display directory listings, support navigation to parent directories, and highlight the currently selected directory.

#### Scenario: Navigate to child directory
- **WHEN** user selects a subdirectory in the listing
- **THEN** system displays contents of selected subdirectory
- **AND** current path is updated in navigation bar
- **AND** user can select the directory as working directory

#### Scenario: Navigate to parent directory
- **WHEN** user selects parent directory option
- **THEN** system displays contents of parent directory
- **AND** current path is updated in navigation bar
- **AND** parent directory option remains available (unless at root)

#### Scenario: Display directory listing
- **WHEN** system displays directory browser
- **THEN** listing shows all subdirectories (excluding hidden files by default)
- **AND** each entry shows directory name and metadata (optional)
- **AND** current directory is visually highlighted

### Requirement: Working directory persistence

The system SHALL remember the last used working directory and offer it as a default option in subsequent TUI sessions. Persistence SHALL be stored in user-specific configuration file.

#### Scenario: Remember last used directory
- **WHEN** user selects a working directory and starts TUI session
- **THEN** system saves directory path to user configuration file
- **AND** next session offers saved directory as default

#### Scenario: Restore from saved directory
- **WHEN** user starts TUI without --directory argument
- **THEN** system loads saved directory from configuration
- **AND** saved directory is pre-selected in selection interface
- **AND** user can accept saved directory or browse to new one

### Requirement: Relative path resolution

The system SHALL resolve relative paths specified via command-line arguments relative to the current working directory of the TUI process at startup. Resolution SHALL occur before validation.

#### Scenario: Relative path with single dot
- **WHEN** user specifies --directory . argument
- **THEN** system resolves to current directory at TUI startup
- **AND** validation proceeds with resolved absolute path

#### Scenario: Relative path with double dot
- **WHEN** user specifies --directory .. argument
- **THEN** system resolves to parent directory at TUI startup
- **AND** validation proceeds with resolved absolute path

#### Scenario: Relative path with subdirectory
- **WHEN** user specifies --directory ./subdirectory argument
- **THEN** system resolves to subdirectory under current directory
- **AND** validation proceeds with resolved absolute path

## Notes

- `DirectoryBrowser` class provides interactive directory navigation
- `validate_directory()` function handles existence, permissions, and provides error messages
- Path resolution supports `.`, `..`, and `./subdirectory` patterns
- Configuration persistence via YAML to `~/.mini-coder/tui.yaml`

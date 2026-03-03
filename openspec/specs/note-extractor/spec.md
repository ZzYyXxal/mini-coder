# Spec: Note Extractor

Capability for automatic extraction of structured notes from LLM responses using pattern matching.

## ADDED Requirements

### Requirement: Pattern-based extraction

The system SHALL extract notes from LLM responses using configurable regex patterns for each note category.

#### Scenario: Extract decision from response
- **WHEN** LLM response contains "决定采用 FastAPI 作为后端框架"
- **THEN** system creates a note with category "decision" and content about FastAPI

#### Scenario: Extract todo from response
- **WHEN** LLM response contains "需要添加单元测试"
- **THEN** system creates a note with category "todo" and content about adding tests

#### Scenario: Extract block from response
- **WHEN** LLM response contains "阻塞问题: 依赖未安装"
- **THEN** system creates a note with category "block" and content about the dependency issue

#### Scenario: No extraction when no patterns match
- **WHEN** LLM response contains no matching patterns
- **THEN** system extracts zero notes

### Requirement: Confidence scoring

The system SHALL assign a confidence score to each extracted note indicating extraction reliability.

#### Scenario: High confidence for exact pattern match
- **WHEN** pattern matches exactly with clear delimiters
- **THEN** confidence score SHALL be >= 0.8

#### Scenario: Lower confidence for partial match
- **WHEN** pattern matches partially or with context ambiguity
- **THEN** confidence score SHALL be between 0.5 and 0.8

### Requirement: Extraction configuration

The system SHALL allow configuration of extraction behavior including enable/disable and confidence thresholds.

#### Scenario: Disable auto-extraction
- **WHEN** config `notes.auto_extract.enabled` is false
- **THEN** system SHALL NOT extract any notes

#### Scenario: Set confidence threshold
- **WHEN** config `notes.auto_extract.confidence_threshold` is 0.9
- **THEN** only notes with confidence >= 0.9 SHALL be auto-saved

### Requirement: Extraction tagging

The system SHALL tag auto-extracted notes to distinguish them from manually created notes.

#### Scenario: Auto-extracted tag
- **WHEN** a note is auto-extracted
- **THEN** note SHALL have tag "auto-extracted"

#### Scenario: Pending confirmation tag
- **WHEN** extracted note confidence is below threshold
- **THEN** note title SHALL be prefixed with "[待确认]"

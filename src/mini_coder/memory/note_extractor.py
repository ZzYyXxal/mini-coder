"""Note extraction from LLM responses.

This module provides automatic extraction of structured notes from
LLM responses using pattern matching.

Example:
    >>> from mini_coder.memory import NoteExtractor
    >>> extractor = NoteExtractor()
    >>> notes = extractor.extract("We decided to use FastAPI for the backend")
    >>> print(notes[0].category)
    'decision'
"""

import re
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ExtractionSource(str, Enum):
    """Source of extraction."""
    RULE = "rule"
    LLM = "llm"


class ExtractedNote(BaseModel):
    """A note extracted from LLM response.

    Attributes:
        category: Note category (decision, todo, pattern, info, block).
        title: Extracted or generated title.
        content: Extracted content.
        confidence: Confidence score (0.0 to 1.0).
        source: How the note was extracted (rule or llm).
        original_text: Original text that matched.
    """

    category: str
    title: str
    content: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    source: str = ExtractionSource.RULE
    original_text: Optional[str] = None


# Regex patterns for extracting notes from LLM responses
# Patterns are ordered by specificity (more specific first)
EXTRACTION_PATTERNS: dict[str, list[tuple[str, float]]] = {
    "decision": [
        # Chinese patterns
        (r"(?:我们|最终)?决定[采用使用选]\s*(.+?)(?:作为|用于|方案)", 0.9),
        (r"选择\s*(.+?)\s*方案", 0.85),
        (r"最终方案[是为]\s*(.+)", 0.85),
        (r"(?:架构|技术)?决策[：:]\s*(.+)", 0.9),
        # English patterns
        (
            r"(?:we\s+)?decided\s+(?:to\s+)?(?:use|adopt|go\s+with)\s+"
            r"(.+?)(?:\s+for|\s+as|because|$)",
            0.9
        ),
        (r"(?:architecture|technical)?\s*decision:\s*(.+)", 0.9),
        (r"chose\s+(.+?)\s+(?:over|instead\s+of)", 0.85),
    ],
    "todo": [
        # Chinese patterns
        (r"需要[完成实现做编写添加]\s*(.+?)(?:任务)?(?:，|$)", 0.85),
        (r"待办[事项]?\s*[：:]\s*(.+)", 0.9),
        (r"下一步[是要]?\s*[：:]?\s*(.+)", 0.8),
        (r"TODO:\s*(.+)", 0.95),
        (r"FIXME:\s*(.+)", 0.9),
        # English patterns
        (r"need\s+to\s+(?:implement|add|create|write|fix)\s+(.+)", 0.85),
        (r"(?:should|must|have\s+to)\s+(?:implement|add|create)\s+(.+)", 0.8),
        (r"next\s+step:\s*(.+)", 0.85),
    ],
    "block": [
        # Chinese patterns
        (r"[遇到有]?\s*阻塞[问题]?\s*[：:]?\s*(.+)", 0.9),
        (r"无法继续\s*(.+)", 0.85),
        (r"卡在\s*(.+?)(?:，|$)", 0.85),
        (r"(?:当前)?问题[：:]\s*(.+)", 0.75),
        # English patterns
        (r"blocked\s+(?:by|on)\s*:\s*(.+)", 0.9),
        (r"blocking\s+(?:issue|problem)\s*:\s*(.+)", 0.9),
        (r"cannot\s+(?:proceed|continue)\s+(?:because|due\s+to)\s+(.+)", 0.85),
        (r"stuck\s+(?:on|with)\s+(.+)", 0.8),
    ],
    "pattern": [
        # Chinese patterns
        (r"[使用采用]\s*(.+?)\s*模式", 0.85),
        (r"代码规范[：:]\s*(.+)", 0.9),
        (r"命名规则[：:]\s*(.+)", 0.9),
        (r"最佳实践[：:]\s*(.+)", 0.85),
        # English patterns
        (r"(?:use|using|adopt)\s+(.+?)\s+pattern", 0.85),
        (r"(?:coding|code)\s+(?:standard|convention|style):\s*(.+)", 0.9),
        (r"(?:naming|variable)\s+(?:convention|rule):\s*(.+)", 0.9),
        (r"best\s+practice:\s*(.+)", 0.85),
    ],
    "info": [
        # Chinese patterns
        (r"注意[事项]?\s*[：:]\s*(.+)", 0.8),
        (r"重要信息[：:]\s*(.+)", 0.85),
        (r"提示[：:]\s*(.+)", 0.75),
        # English patterns
        (r"(?:note|important|info):\s*(.+)", 0.8),
        (r"(?:be\s+aware|remember)\s+(?:that\s+)?(.+)", 0.75),
    ],
}


class NoteExtractor:
    """Extracts structured notes from LLM responses.

    Uses pattern matching to detect decisions, todos, blocks,
    patterns, and important information in LLM responses.

    Example:
        >>> extractor = NoteExtractor()
        >>> text = "We decided to use FastAPI for better async support"
        >>> notes = extractor.extract(text)
        >>> notes[0].category
        'decision'
    """

    def __init__(
        self,
        confidence_threshold: float = 0.7,
        max_notes_per_category: int = 3
    ):
        """Initialize the extractor.

        Args:
            confidence_threshold: Minimum confidence to include a note.
            max_notes_per_category: Maximum notes to extract per category.
        """
        self.confidence_threshold = confidence_threshold
        self.max_notes_per_category = max_notes_per_category
        # Compile patterns for efficiency
        self._compiled_patterns: dict[str, list[tuple[re.Pattern, float]]] = {}
        for category, patterns in EXTRACTION_PATTERNS.items():
            self._compiled_patterns[category] = [
                (re.compile(p, re.IGNORECASE | re.MULTILINE), conf)
                for p, conf in patterns
            ]

    def extract(self, content: str) -> list[ExtractedNote]:
        """Extract notes from LLM response content.

        Args:
            content: The LLM response text to extract from.

        Returns:
            List of extracted notes with confidence scores.
        """
        if not content or not content.strip():
            return []

        extracted: list[ExtractedNote] = []
        notes_by_category: dict[str, list[ExtractedNote]] = {}

        for category, patterns in self._compiled_patterns.items():
            category_notes: list[ExtractedNote] = []

            for pattern, base_confidence in patterns:
                matches = pattern.findall(content)

                for match in matches:
                    # Handle tuple matches from groups
                    if isinstance(match, tuple):
                        match = match[0] if match[0] else match[1] if len(match) > 1 else ""

                    extracted_content = match.strip()
                    if not extracted_content or len(extracted_content) < 3:
                        continue

                    # Calculate confidence based on content quality
                    confidence = self._calculate_confidence(
                        extracted_content,
                        base_confidence
                    )

                    if confidence < self.confidence_threshold:
                        continue

                    # Generate title from content
                    title = self._generate_title(category, extracted_content)

                    note = ExtractedNote(
                        category=category,
                        title=title,
                        content=extracted_content,
                        confidence=confidence,
                        source=ExtractionSource.RULE,
                        original_text=match.strip()
                    )
                    category_notes.append(note)

            # Sort by confidence and limit per category
            category_notes.sort(key=lambda n: n.confidence, reverse=True)
            notes_by_category[category] = category_notes[:self.max_notes_per_category]

        # Flatten and sort all notes by confidence
        for category_notes in notes_by_category.values():
            extracted.extend(category_notes)

        extracted.sort(key=lambda n: n.confidence, reverse=True)
        return extracted

    def _calculate_confidence(
        self,
        content: str,
        base_confidence: float
    ) -> float:
        """Calculate confidence score for extracted content.

        Args:
            content: The extracted content.
            base_confidence: Base confidence from pattern match.

        Returns:
            Adjusted confidence score.
        """
        confidence = base_confidence

        # Boost for reasonable length (not too short, not too long)
        if 10 <= len(content) <= 100:
            confidence += 0.05
        elif len(content) > 200:
            confidence -= 0.1

        # Boost for complete sentences (ends with punctuation)
        if content[-1] in ".!?。！？":
            confidence += 0.05

        # Penalize very short extractions
        if len(content) < 5:
            confidence -= 0.2

        # Penalize if content looks like code
        if "{" in content or "}" in content or ";" in content:
            confidence -= 0.1

        return max(0.0, min(1.0, confidence))

    def _generate_title(self, category: str, content: str) -> str:
        """Generate a title for the extracted note.

        Args:
            category: The note category.
            content: The extracted content.

        Returns:
            A generated title.
        """
        # Truncate content for title
        title = content[:50]
        if len(content) > 50:
            # Find a good break point
            last_space = title.rfind(" ")
            if last_space > 20:
                title = title[:last_space]
            title += "..."

        # Add category prefix for certain types
        prefixes = {
            "todo": "TODO: ",
            "block": "BLOCK: ",
        }

        prefix = prefixes.get(category, "")
        return f"{prefix}{title}"

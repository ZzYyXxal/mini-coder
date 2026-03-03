"""Persistent storage for context memory system.

This module provides disk-based storage for session persistence
and summary management.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from .models import Session, Summary


class PersistentStore:
    """Disk-based storage for context memory.

    Provides JSON-based storage for sessions and summaries with
    optional support for vector search (Phase 2).

    Attributes:
        path: Base path for storage directory.
    """

    def __init__(self, path: str = "~/.mini-coder/memory"):
        """Initialize persistent store.

        Args:
            path: Base path for storage directory. Supports ~ expansion.
        """
        self.path = Path(path).expanduser()
        self.path.mkdir(parents=True, exist_ok=True)

        # Create subdirectories
        self._sessions_dir = self.path / "sessions"
        self._sessions_dir.mkdir(exist_ok=True)

        # Initialize optional Chroma client (Phase 2)
        self._chroma_client = None
        self._collection = None

    def save_session(self, session: Session) -> None:
        """Save session to disk.

        Args:
            session: The session to save.
        """
        session_file = self._sessions_dir / f"{session.id}.json"
        json_content = session.model_dump_json(indent=2)
        session_file.write_text(json_content, encoding="utf-8")

    def load_session(self, session_id: str) -> Optional[Session]:
        """Load session from disk.

        Args:
            session_id: The ID of the session to load.

        Returns:
            The session if found, None otherwise.
        """
        session_file = self._sessions_dir / f"{session_id}.json"
        if not session_file.exists():
            return None

        try:
            json_content = session_file.read_text(encoding="utf-8")
            return Session.model_validate_json(json_content)
        except (json.JSONDecodeError, Exception):
            return None

    def delete_session(self, session_id: str) -> bool:
        """Delete a session from disk.

        Args:
            session_id: The ID of the session to delete.

        Returns:
            True if deleted, False if not found.
        """
        session_file = self._sessions_dir / f"{session_id}.json"
        if session_file.exists():
            session_file.unlink()
            return True
        return False

    def list_sessions(self) -> list[str]:
        """List all saved session IDs.

        Returns:
            List of session IDs.
        """
        return [f.stem for f in self._sessions_dir.glob("*.json")]

    def save_summary(self, summary: Summary) -> None:
        """Save compressed summary to disk.

        Args:
            summary: The summary to save.
        """
        summaries_file = self.path / "summaries.json"

        # Load existing summaries
        summaries = []
        if summaries_file.exists():
            try:
                content = summaries_file.read_text(encoding="utf-8")
                summaries = json.loads(content)
            except (json.JSONDecodeError, Exception):
                summaries = []

        # Add new summary
        summary_dict = summary.model_dump()
        summary_dict["created_at"] = summary_dict["created_at"].isoformat()
        summaries.append(summary_dict)

        # Save back to file
        summaries_file.write_text(
            json.dumps(summaries, indent=2, default=str),
            encoding="utf-8"
        )

    def load_summaries(self) -> list[Summary]:
        """Load all summaries from disk.

        Returns:
            List of summaries.
        """
        summaries_file = self.path / "summaries.json"
        if not summaries_file.exists():
            return []

        try:
            content = summaries_file.read_text(encoding="utf-8")
            summaries_data = json.loads(content)

            summaries = []
            for item in summaries_data:
                # Parse datetime strings
                if isinstance(item.get("created_at"), str):
                    item["created_at"] = datetime.fromisoformat(item["created_at"])
                summaries.append(Summary(**item))

            return summaries
        except (json.JSONDecodeError, Exception):
            return []

    def get_latest_session(self) -> Optional[Session]:
        """Get the most recently updated session.

        Returns:
            The latest session if any, None otherwise.
        """
        sessions = self.list_sessions()
        if not sessions:
            return None

        # Load all sessions and find the most recent
        latest_session = None
        latest_time = None

        for session_id in sessions:
            session = self.load_session(session_id)
            if session:
                if latest_time is None or session.updated_at > latest_time:
                    latest_time = session.updated_at
                    latest_session = session

        return latest_session

    def cleanup_old_sessions(self, max_count: int = 100) -> int:
        """Remove old sessions to keep count under limit.

        Args:
            max_count: Maximum number of sessions to keep.

        Returns:
            Number of sessions removed.
        """
        sessions = self.list_sessions()
        if len(sessions) <= max_count:
            return 0

        # Load all sessions with their update times
        session_times = []
        for session_id in sessions:
            session = self.load_session(session_id)
            if session:
                session_times.append((session_id, session.updated_at))

        # Sort by update time (newest first)
        session_times.sort(key=lambda x: x[1], reverse=True)

        # Remove oldest sessions
        to_remove = [s[0] for s in session_times[max_count:]]
        for session_id in to_remove:
            self.delete_session(session_id)

        return len(to_remove)

    # Phase 2: Vector search methods (optional)

    def enable_vector_search(self) -> None:
        """Enable Chroma vector search (Phase 2).

        Raises:
            RuntimeError: If chromadb is not installed.
        """
        try:
            import chromadb
            chroma_path = self.path / "chroma"
            self._chroma_client = chromadb.PersistentClient(path=str(chroma_path))
            self._collection = self._chroma_client.get_or_create_collection(
                name="conversations"
            )
        except ImportError as e:
            raise RuntimeError(
                "chromadb not installed. Run: pip install chromadb"
            ) from e

    def search_similar(self, query: str, n_results: int = 5) -> list[dict]:
        """Semantic search for similar content (requires Phase 2).

        Args:
            query: The search query.
            n_results: Maximum number of results.

        Returns:
            List of matching documents.

        Raises:
            RuntimeError: If vector search is not enabled.
        """
        if not self._collection:
            raise RuntimeError(
                "Vector search not enabled. Call enable_vector_search() first."
            )

        results = self._collection.query(
            query_texts=[query],
            n_results=n_results
        )
        return results

    def __repr__(self) -> str:
        """Get string representation."""
        session_count = len(self.list_sessions())
        return f"PersistentStore(path={self.path}, sessions={session_count})"

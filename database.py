"""SQLite persistence for quiz answers and quiz state."""

from __future__ import annotations

import asyncio
import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class AnswerRecord:
    user_id: int
    username: str | None
    first_name: str | None
    answer: str
    correct: bool
    timestamp: str


class Database:
    """Small async wrapper around SQLite using worker threads for I/O."""

    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Create the database schema when it does not already exist."""
        await asyncio.to_thread(self._initialize_sync)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _initialize_sync(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True) if self.path.parent != Path(".") else None
        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS answers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL UNIQUE,
                    username TEXT,
                    first_name TEXT,
                    answer TEXT NOT NULL,
                    correct INTEGER NOT NULL CHECK (correct IN (0, 1)),
                    timestamp TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS quiz_state (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    active INTEGER NOT NULL CHECK (active IN (0, 1)),
                    correct_answer TEXT,
                    started_at TEXT,
                    ended_at TEXT
                )
                """
            )
            conn.execute(
                """
                INSERT OR IGNORE INTO quiz_state (id, active, correct_answer, started_at, ended_at)
                VALUES (1, 0, NULL, NULL, NULL)
                """
            )
            conn.commit()
        logger.info("Database initialized at %s", self.path)

    async def start_quiz(self, correct_answer: str) -> None:
        async with self._lock:
            await asyncio.to_thread(self._start_quiz_sync, correct_answer)

    def _start_quiz_sync(self, correct_answer: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute("DELETE FROM answers")
            conn.execute(
                """
                UPDATE quiz_state
                SET active = 1, correct_answer = ?, started_at = ?, ended_at = NULL
                WHERE id = 1
                """,
                (correct_answer, now),
            )
            conn.commit()

    async def end_quiz(self) -> None:
        async with self._lock:
            await asyncio.to_thread(self._end_quiz_sync)

    def _end_quiz_sync(self) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute("UPDATE quiz_state SET active = 0, ended_at = ? WHERE id = 1", (now,))
            conn.commit()

    async def reset(self) -> None:
        async with self._lock:
            await asyncio.to_thread(self._reset_sync)

    def _reset_sync(self) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM answers")
            conn.execute(
                "UPDATE quiz_state SET active = 0, correct_answer = NULL, started_at = NULL, ended_at = NULL WHERE id = 1"
            )
            conn.commit()

    async def get_state(self) -> dict[str, Any]:
        return await asyncio.to_thread(self._get_state_sync)

    def _get_state_sync(self) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute("SELECT active, correct_answer, started_at, ended_at FROM quiz_state WHERE id = 1").fetchone()
        return dict(row) if row else {"active": 0, "correct_answer": None, "started_at": None, "ended_at": None}

    async def save_answer(
        self,
        user_id: int,
        username: str | None,
        first_name: str | None,
        answer: str,
        correct: bool,
    ) -> bool:
        """Save a user's first answer. Return False when it is a duplicate."""
        async with self._lock:
            return await asyncio.to_thread(self._save_answer_sync, user_id, username, first_name, answer, correct)

    def _save_answer_sync(self, user_id: int, username: str | None, first_name: str | None, answer: str, correct: bool) -> bool:
        timestamp = datetime.now(timezone.utc).isoformat()
        try:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO answers (user_id, username, first_name, answer, correct, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (user_id, username, first_name, answer, int(correct), timestamp),
                )
                conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    async def stats(self) -> dict[str, int]:
        return await asyncio.to_thread(self._stats_sync)

    def _stats_sync(self) -> dict[str, int]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS participants, SUM(correct = 1) AS correct, SUM(correct = 0) AS wrong FROM answers"
            ).fetchone()
        return {"participants": int(row["participants"] or 0), "correct": int(row["correct"] or 0), "wrong": int(row["wrong"] or 0)}

    async def winners(self, limit: int = 3) -> list[AnswerRecord]:
        return await asyncio.to_thread(self._winners_sync, limit)

    def _winners_sync(self, limit: int) -> list[AnswerRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT user_id, username, first_name, answer, correct, timestamp
                FROM answers
                WHERE correct = 1
                ORDER BY timestamp ASC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [AnswerRecord(**{**dict(row), "correct": bool(row["correct"])}) for row in rows]

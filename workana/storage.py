from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path


class JobStore:
    CLAIM_TTL_SECONDS = 120

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    def _init_db(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS seen_jobs (
                    slug TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    url TEXT NOT NULL,
                    score REAL NOT NULL DEFAULT 0,
                    first_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    notified_at TEXT,
                    claim_at TEXT
                )
                """
            )
            columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(seen_jobs)").fetchall()
            }
            if "claim_at" not in columns:
                connection.execute("ALTER TABLE seen_jobs ADD COLUMN claim_at TEXT")
            connection.commit()

    def filter_new(self, slugs: list[str]) -> list[str]:
        if not slugs:
            return []

        placeholders = ",".join("?" for _ in slugs)
        query = f"SELECT slug FROM seen_jobs WHERE slug IN ({placeholders})"
        with self._connect() as connection:
            rows = connection.execute(query, slugs).fetchall()
        seen = {row["slug"] for row in rows}
        return [slug for slug in slugs if slug not in seen]

    def mark_seen(
        self,
        *,
        slug: str,
        title: str,
        url: str,
        score: float,
        notified: bool,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO seen_jobs (slug, title, url, score, notified_at, claim_at)
                VALUES (
                    ?, ?, ?, ?,
                    CASE WHEN ? THEN CURRENT_TIMESTAMP ELSE NULL END,
                    NULL
                )
                ON CONFLICT(slug) DO UPDATE SET
                    title = excluded.title,
                    url = excluded.url,
                    score = excluded.score,
                    notified_at = CASE
                        WHEN ? THEN COALESCE(seen_jobs.notified_at, CURRENT_TIMESTAMP)
                        ELSE seen_jobs.notified_at
                    END,
                    claim_at = CASE WHEN ? THEN NULL ELSE seen_jobs.claim_at END
                """,
                (slug, title, url, score, notified, notified, notified),
            )
            connection.commit()

    def try_claim_notify(
        self,
        *,
        slug: str,
        title: str,
        url: str,
        score: float,
    ) -> bool:
        """Atomically reserve a job for Telegram send. Cross-process safe."""
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                row = connection.execute(
                    "SELECT notified_at, claim_at FROM seen_jobs WHERE slug = ?",
                    (slug,),
                ).fetchone()
                if row is not None:
                    if row["notified_at"]:
                        connection.execute("COMMIT")
                        return False
                    if row["claim_at"] and not self._claim_is_stale(row["claim_at"]):
                        connection.execute("COMMIT")
                        return False
                    connection.execute(
                        """
                        UPDATE seen_jobs
                        SET title = ?, url = ?, score = ?, claim_at = CURRENT_TIMESTAMP
                        WHERE slug = ?
                        """,
                        (title, url, score, slug),
                    )
                else:
                    connection.execute(
                        """
                        INSERT INTO seen_jobs (slug, title, url, score, claim_at)
                        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                        """,
                        (slug, title, url, score),
                    )
                connection.execute("COMMIT")
                return True
            except Exception:
                connection.execute("ROLLBACK")
                raise

    def release_claim(self, slug: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE seen_jobs
                SET claim_at = NULL
                WHERE slug = ? AND notified_at IS NULL
                """,
                (slug,),
            )
            connection.commit()

    def count_seen(self) -> int:
        with self._connect() as connection:
            row = connection.execute("SELECT COUNT(*) AS total FROM seen_jobs").fetchone()
        return int(row["total"])

    def was_notified(self, slug: str) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT notified_at FROM seen_jobs WHERE slug = ?",
                (slug,),
            ).fetchone()
        return bool(row and row["notified_at"])

    def list_notified_slugs(self) -> list[str]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT slug FROM seen_jobs WHERE notified_at IS NOT NULL"
            ).fetchall()
        return [row["slug"] for row in rows]

    def list_slugs(self) -> list[str]:
        with self._connect() as connection:
            rows = connection.execute("SELECT slug FROM seen_jobs").fetchall()
        return [row["slug"] for row in rows]

    @classmethod
    def _claim_is_stale(cls, claim_at: str) -> bool:
        try:
            claimed = datetime.fromisoformat(claim_at)
        except ValueError:
            return True
        return datetime.utcnow() - claimed > timedelta(seconds=cls.CLAIM_TTL_SECONDS)

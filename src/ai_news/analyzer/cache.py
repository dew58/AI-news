import hashlib
import json
import logging
import sqlite3
import time
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

_DEFAULT_CACHE_DIR = Path.home() / ".ai_news_cache"
_DEFAULT_CACHE_PATH = _DEFAULT_CACHE_DIR / "analysis_cache.db"


class AnalysisCache:
    def __init__(self, db_path: Optional[str] = None):
        self._db_path = str(db_path or _DEFAULT_CACHE_PATH)
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cache_entries (
                    cache_key TEXT PRIMARY KEY,
                    response_json TEXT NOT NULL,
                    model_name TEXT NOT NULL,
                    prompt_version TEXT NOT NULL,
                    profile_version TEXT NOT NULL,
                    created_at REAL NOT NULL
                )
                """
            )
            conn.commit()

    @staticmethod
    def make_key(
        content_fingerprint: str,
        prompt_version: str,
        model_name: str,
        profile_version: str,
    ) -> str:
        raw = f"{content_fingerprint}:{prompt_version}:{model_name}:{profile_version}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def get(
        self,
        content_fingerprint: str,
        prompt_version: str,
        model_name: str,
        profile_version: str,
    ) -> Optional[Any]:
        key = self.make_key(content_fingerprint, prompt_version, model_name, profile_version)
        try:
            with sqlite3.connect(self._db_path) as conn:
                row = conn.execute(
                    "SELECT response_json FROM cache_entries WHERE cache_key = ?",
                    (key,),
                ).fetchone()
            if row:
                logger.debug("[Cache] Hit for key %s...", key[:12])
                return json.loads(row[0])
        except (sqlite3.Error, json.JSONDecodeError) as exc:
            logger.warning("[Cache] Read error: %s", exc)
        return None

    def set(
        self,
        content_fingerprint: str,
        prompt_version: str,
        model_name: str,
        profile_version: str,
        response: Any,
    ) -> None:
        key = self.make_key(content_fingerprint, prompt_version, model_name, profile_version)
        try:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO cache_entries
                        (cache_key, response_json, model_name, prompt_version, profile_version, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        key,
                        json.dumps(response),
                        model_name,
                        prompt_version,
                        profile_version,
                        time.time(),
                    ),
                )
                conn.commit()
            logger.debug("[Cache] Stored key %s...", key[:12])
        except sqlite3.Error as exc:
            logger.warning("[Cache] Write error: %s", exc)

    def clear(self) -> None:
        try:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute("DELETE FROM cache_entries")
                conn.commit()
            logger.info("[Cache] Cleared all entries.")
        except sqlite3.Error as exc:
            logger.warning("[Cache] Clear error: %s", exc)

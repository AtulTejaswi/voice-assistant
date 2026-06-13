"""
Three-tier memory system for JARVIS.

- SHORT-TERM: Rolling conversation history (last N turns)
- SEMANTIC: ChromaDB vector store for long-term facts
- EPISODIC: SQLite database for action logs
"""

import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import chromadb
import requests


class MemoryManager:
    def __init__(
        self,
        db_path: str = "",
        chroma_path: str = "",
        max_history: int = 20,
        ollama_url: str = "http://localhost:11434",
        embed_model: str = "llama3.2:3b",
    ):
        base = Path.home() / ".jarvis"
        base.mkdir(exist_ok=True)

        self._db_path = db_path or str(base / "episodic.db")
        self._chroma_path = chroma_path or str(base / "chroma")
        self._max_history = max_history
        self._ollama_url = ollama_url.rstrip("/")
        self._embed_model = embed_model
        self._lock = threading.Lock()

        # Short-term
        self._short_term: list[dict[str, str]] = []

        # Episodic (SQLite)
        self._init_sqlite()

        # Semantic (ChromaDB)
        self._chroma_client = chromadb.PersistentClient(path=self._chroma_path)
        self._collection = self._chroma_client.get_or_create_collection(
            name="jarvis_memories",
            metadata={"hnsw:space": "cosine"},
        )

    # ------------------------------------------------------------------
    # Short-term memory
    # ------------------------------------------------------------------

    def add_short_term(self, role: str, content: str):
        with self._lock:
            self._short_term.append({"role": role, "content": content})
            if len(self._short_term) > self._max_history:
                self._short_term = self._short_term[-self._max_history:]

    def get_short_term(self) -> list[dict[str, str]]:
        with self._lock:
            return list(self._short_term)

    def clear_short_term(self):
        with self._lock:
            self._short_term = []

    # ------------------------------------------------------------------
    # Semantic memory (ChromaDB)
    # ------------------------------------------------------------------

    def store_fact(self, fact: str, metadata: Optional[dict[str, Any]] = None):
        """Store a meaningful fact with embedding for later retrieval."""
        embedding = self._embed(fact)
        doc_id = f"fact_{datetime.now().timestamp()}"
        meta = {"type": "fact", "timestamp": datetime.now().isoformat()}
        if metadata:
            meta.update(metadata)

        self._collection.add(
            ids=[doc_id],
            embeddings=[embedding],
            documents=[fact],
            metadatas=[meta],
        )

    def retrieve_facts(self, query: str, n: int = 5) -> list[str]:
        """Retrieve top-N relevant facts."""
        if self._collection.count() == 0:
            return []
        embedding = self._embed(query)
        results = self._collection.query(
            query_embeddings=[embedding],
            n_results=min(n, self._collection.count()),
        )
        return results.get("documents", [[]])[0]

    def store_episodic_memory(self, command: str, result: str, metadata: Optional[dict] = None):
        """Log a command execution for later recall."""
        self.store_fact(
            f"User asked: {command} — Result: {result}",
            metadata={"type": "episode", "command": command, "result": result, **(metadata or {})},
        )

    # ------------------------------------------------------------------
    # Episodic memory (SQLite)
    # ------------------------------------------------------------------

    def _init_sqlite(self):
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS episodes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    command TEXT NOT NULL,
                    result TEXT NOT NULL,
                    metadata TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS reminders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    time TEXT NOT NULL,
                    message TEXT NOT NULL,
                    done INTEGER DEFAULT 0
                )
            """)

    def log_episode(self, command: str, result: str, metadata: Optional[dict] = None):
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "INSERT INTO episodes (timestamp, command, result, metadata) VALUES (?, ?, ?, ?)",
                (datetime.now().isoformat(), command, result, json.dumps(metadata or {})),
            )

    def query_episodes(self, limit: int = 20) -> list[dict]:
        with sqlite3.connect(self._db_path) as conn:
            rows = conn.execute(
                "SELECT timestamp, command, result FROM episodes ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
            return [
                {"timestamp": r[0], "command": r[1], "result": r[2]} for r in rows
            ]

    def add_reminder(self, time_str: str, message: str):
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "INSERT INTO reminders (time, message) VALUES (?, ?)",
                (time_str, message),
            )

    def get_pending_reminders(self) -> list[dict]:
        with sqlite3.connect(self._db_path) as conn:
            rows = conn.execute(
                "SELECT id, time, message FROM reminders WHERE done = 0 ORDER BY time"
            ).fetchall()
            return [{"id": r[0], "time": r[1], "message": r[2]} for r in rows]

    def mark_reminder_done(self, rid: int):
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("UPDATE reminders SET done = 1 WHERE id = ?", (rid,))

    # ------------------------------------------------------------------
    # Embeddings — try Ollama first, fall back to simple hash embeddings
    # ------------------------------------------------------------------

    def _embed(self, text: str) -> list[float]:
        try:
            resp = requests.post(
                f"{self._ollama_url}/api/embeddings",
                json={"model": self._embed_model, "prompt": text},
                timeout=10,
            )
            if resp.ok:
                return resp.json()["embedding"]
        except Exception:
            pass
        return self._simple_embed(text)

    @staticmethod
    def _simple_embed(text: str) -> list[float]:
        """Simple hash-based embedding — no dependencies needed."""
        import hashlib
        dim = 384
        vec = [0.0] * dim
        words = text.lower().split()
        for i, word in enumerate(words):
            h = hashlib.md5(word.encode()).digest()
            for j in range(min(len(h), dim)):
                vec[j] += (h[j] / 255.0) * (1.0 / (1.0 + i * 0.1))
        norm = sum(v * v for v in vec) ** 0.5
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec

    # ------------------------------------------------------------------
    # Context assembly for LLM prompts
    # ------------------------------------------------------------------

    def build_context(self, user_input: str) -> str:
        """Build a context string with relevant memories for LLM injection."""
        parts = []

        facts = self.retrieve_facts(user_input, n=3)
        if facts:
            parts.append("Relevant memories:\n- " + "\n- ".join(facts))

        recent = self.query_episodes(5)
        if recent:
            parts.append("Recent actions:\n- " + "\n- ".join(
                f"[{r['timestamp']}] {r['command']} → {r['result'][:60]}" for r in recent
            ))

        reminders = self.get_pending_reminders()
        if reminders:
            parts.append("Pending reminders:\n- " + "\n- ".join(
                f"At {r['time']}: {r['message']}" for r in reminders[:3]
            ))

        return "\n\n".join(parts)

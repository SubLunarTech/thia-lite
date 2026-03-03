from __future__ import annotations

"""
Thia-Lite Database Layer
=========================
Single SQLite database replacing Redis, ChromaDB, Neo4j, and TimescaleDB.
Uses sqlite-vec extension for vector similarity search.

Tables:
  kv            — Key-value store (replaces Redis)
  memories      — Vector-searchable memory documents (replaces ChromaDB)
  graph_nodes   — Knowledge graph nodes (replaces Neo4j)
  graph_edges   — Knowledge graph edges (replaces Neo4j)
  events        — Timeseries events (replaces TimescaleDB)
  conversations — Chat session history
  predictions   — Prediction tracking
  vestige_cards — Spaced repetition cards
  rules_index   — Astrology rule embeddings for RAG
"""

import json
import logging
import math
import os
import sqlite3
import struct
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ─── Vector Serialization ─────────────────────────────────────────────────────

def _serialize_vector(vec: List[float]) -> bytes:
    """Serialize a float vector to bytes for sqlite-vec."""
    return struct.pack(f"{len(vec)}f", *vec)


def _deserialize_vector(data: bytes) -> List[float]:
    """Deserialize bytes back to a float vector."""
    n = len(data) // 4
    return list(struct.unpack(f"{n}f", data))


# ─── Database Manager ─────────────────────────────────────────────────────────

class Database:
    """Unified SQLite database with vector search support."""

    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        self._conn: Optional[sqlite3.Connection] = None
        self._vec_available = False

    def connect(self) -> None:
        """Open connection and initialize schema."""
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute("PRAGMA cache_size=-64000")  # 64MB cache

        # Try loading sqlite-vec
        try:
            import sqlite_vec
            self._conn.enable_load_extension(True)
            sqlite_vec.load(self._conn)
            self._conn.enable_load_extension(False)
            self._vec_available = True
            logger.info("sqlite-vec extension loaded successfully")
        except Exception as e:
            logger.warning(f"sqlite-vec not available, vector search degraded: {e}")
            self._vec_available = False

        self._create_schema()
        logger.info(f"Database connected: {self.db_path}")

    def close(self) -> None:
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self.connect()
        return self._conn

    # ─── Schema ───────────────────────────────────────────────────────────

    def _create_schema(self) -> None:
        """Create all tables."""
        c = self.conn
        with c:
            # Key-value store (replaces Redis)
            c.execute("""
                CREATE TABLE IF NOT EXISTS kv (
                    namespace TEXT NOT NULL,
                    key       TEXT NOT NULL,
                    value     TEXT NOT NULL,
                    ttl       INTEGER DEFAULT 0,
                    updated_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
                    PRIMARY KEY (namespace, key)
                )
            """)

            # Memory documents (replaces ChromaDB)
            c.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id         TEXT PRIMARY KEY,
                    content    TEXT NOT NULL,
                    metadata   TEXT DEFAULT '{}',
                    embedding  BLOB,
                    created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
                )
            """)
            c.execute("CREATE INDEX IF NOT EXISTS idx_mem_created ON memories(created_at DESC)")

            # Knowledge graph (replaces Neo4j)
            c.execute("""
                CREATE TABLE IF NOT EXISTS graph_nodes (
                    id    TEXT PRIMARY KEY,
                    label TEXT NOT NULL,
                    type  TEXT DEFAULT 'entity',
                    props TEXT DEFAULT '{}'
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS graph_edges (
                    source TEXT NOT NULL,
                    target TEXT NOT NULL,
                    rel    TEXT NOT NULL,
                    props  TEXT DEFAULT '{}',
                    PRIMARY KEY (source, target, rel),
                    FOREIGN KEY (source) REFERENCES graph_nodes(id),
                    FOREIGN KEY (target) REFERENCES graph_nodes(id)
                )
            """)
            c.execute("CREATE INDEX IF NOT EXISTS idx_edge_src ON graph_edges(source)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_edge_tgt ON graph_edges(target)")

            # Timeseries events (replaces TimescaleDB)
            c.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id         TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    category   TEXT DEFAULT 'metrics',
                    value      REAL DEFAULT 0.0,
                    payload    TEXT DEFAULT '{}',
                    timestamp  TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
                )
            """)
            c.execute("CREATE INDEX IF NOT EXISTS idx_evt_ts ON events(timestamp DESC)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_evt_type ON events(event_type, category)")

            # Conversations
            c.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id         TEXT PRIMARY KEY,
                    title      TEXT DEFAULT 'New Chat',
                    created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
                    updated_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id              TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL,
                    role            TEXT NOT NULL,
                    content         TEXT NOT NULL,
                    tool_calls      TEXT DEFAULT '[]',
                    created_at      TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
                    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
                )
            """)
            c.execute("CREATE INDEX IF NOT EXISTS idx_msg_conv ON messages(conversation_id, created_at)")

            # Predictions
            c.execute("""
                CREATE TABLE IF NOT EXISTS predictions (
                    id         TEXT PRIMARY KEY,
                    prediction TEXT NOT NULL,
                    category   TEXT DEFAULT 'other',
                    confidence REAL DEFAULT 0.5,
                    status     TEXT DEFAULT 'pending',
                    outcome    TEXT,
                    resolve_by TEXT,
                    metadata   TEXT DEFAULT '{}',
                    created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
                    resolved_at TEXT
                )
            """)

            # Vestige spaced repetition
            c.execute("""
                CREATE TABLE IF NOT EXISTS vestige_cards (
                    id          TEXT PRIMARY KEY,
                    content     TEXT NOT NULL,
                    answer      TEXT DEFAULT '',
                    tags        TEXT DEFAULT '[]',
                    state       TEXT DEFAULT 'new',
                    interval    INTEGER DEFAULT 0,
                    ease_factor REAL DEFAULT 2.5,
                    reviews     INTEGER DEFAULT 0,
                    due_at      TEXT,
                    created_at  TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
                )
            """)

            # Ephemeris cache
            c.execute("""
                CREATE TABLE IF NOT EXISTS ephemeris_cache (
                    julian_day REAL NOT NULL,
                    planet     TEXT NOT NULL,
                    sidereal   INTEGER DEFAULT 0,
                    payload    TEXT NOT NULL,
                    computed_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
                    PRIMARY KEY (julian_day, planet, sidereal)
                )
            """)

            # Astro context snapshots (time-series planetary positions)
            c.execute("""
                CREATE TABLE IF NOT EXISTS astro_context (
                    id           TEXT PRIMARY KEY,
                    ref_type     TEXT NOT NULL,
                    ref_id       TEXT NOT NULL,
                    timestamp    TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
                    sun_sign     TEXT,
                    moon_sign    TEXT,
                    asc_sign     TEXT,
                    mercury_sign TEXT,
                    venus_sign   TEXT,
                    mars_sign    TEXT,
                    jupiter_sign TEXT,
                    saturn_sign  TEXT,
                    moon_phase   TEXT,
                    void_of_course INTEGER DEFAULT 0,
                    retrograde   TEXT DEFAULT '[]',
                    planetary_hour TEXT,
                    positions    TEXT DEFAULT '{}'
                )
            """)
            c.execute("CREATE INDEX IF NOT EXISTS idx_astro_ref ON astro_context(ref_type, ref_id)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_astro_ts ON astro_context(timestamp DESC)")

            # Virtual table for vector search (if sqlite-vec available)
            if self._vec_available:
                try:
                    c.execute("""
                        CREATE VIRTUAL TABLE IF NOT EXISTS vec_memories
                        USING vec0(
                            id TEXT PRIMARY KEY,
                            embedding float[384]
                        )
                    """)
                    c.execute("""
                        CREATE VIRTUAL TABLE IF NOT EXISTS vec_rules
                        USING vec0(
                            id TEXT PRIMARY KEY,
                            embedding float[384]
                        )
                    """)
                except Exception as e:
                    logger.warning(f"Could not create vector tables: {e}")
                    self._vec_available = False

    # ─── Key-Value Operations (Redis replacement) ─────────────────────────

    def kv_get(self, namespace: str, key: str) -> Optional[Any]:
        """Get a value from the KV store."""
        row = self.conn.execute(
            "SELECT value FROM kv WHERE namespace = ? AND key = ?",
            (namespace, key)
        ).fetchone()
        if row:
            try:
                return json.loads(row["value"])
            except (json.JSONDecodeError, TypeError):
                return row["value"]
        return None

    def kv_set(self, namespace: str, key: str, value: Any, ttl: int = 0) -> bool:
        """Set a value in the KV store."""
        try:
            serialized = json.dumps(value) if not isinstance(value, str) else value
            with self.conn:
                self.conn.execute(
                    """INSERT INTO kv (namespace, key, value, ttl, updated_at)
                       VALUES (?, ?, ?, ?, strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
                       ON CONFLICT(namespace, key) DO UPDATE SET
                         value = excluded.value, ttl = excluded.ttl,
                         updated_at = excluded.updated_at""",
                    (namespace, key, serialized, ttl)
                )
            return True
        except Exception as e:
            logger.error(f"kv_set error: {e}")
            return False

    def kv_delete(self, namespace: str, key: str) -> bool:
        """Delete a key."""
        with self.conn:
            self.conn.execute("DELETE FROM kv WHERE namespace = ? AND key = ?", (namespace, key))
        return True

    def kv_list(self, namespace: str) -> Dict[str, Any]:
        """List all keys in a namespace."""
        rows = self.conn.execute(
            "SELECT key, value FROM kv WHERE namespace = ?", (namespace,)
        ).fetchall()
        result = {}
        for row in rows:
            try:
                result[row["key"]] = json.loads(row["value"])
            except (json.JSONDecodeError, TypeError):
                result[row["key"]] = row["value"]
        return result

    # ─── Memory Operations (ChromaDB replacement) ─────────────────────────

    def memory_store(self, content: str, metadata: Dict = None,
                     embedding: List[float] = None, memory_id: str = None,
                     astro_tag: bool = True) -> str:
        """Store a memory document with optional embedding and astrological context."""
        doc_id = memory_id or f"mem_{uuid.uuid4().hex[:12]}"
        meta_json = json.dumps(metadata or {})
        emb_bytes = _serialize_vector(embedding) if embedding else None

        with self.conn:
            self.conn.execute(
                """INSERT INTO memories (id, content, metadata, embedding, created_at)
                   VALUES (?, ?, ?, ?, strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
                   ON CONFLICT(id) DO UPDATE SET
                     content = excluded.content, metadata = excluded.metadata,
                     embedding = excluded.embedding""",
                (doc_id, content, meta_json, emb_bytes)
            )

            # Add to vector index if available
            if self._vec_available and embedding:
                try:
                    self.conn.execute(
                        "INSERT OR REPLACE INTO vec_memories (id, embedding) VALUES (?, ?)",
                        (doc_id, _serialize_vector(embedding))
                    )
                except Exception as e:
                    logger.debug(f"vec insert error: {e}")

        if astro_tag:
            self._tag_with_astro("memory", doc_id)

        return doc_id

    def memory_recall(self, query_embedding: List[float] = None,
                      text_query: str = None, limit: int = 10) -> List[Dict]:
        """Recall memories by vector similarity or text search."""
        if self._vec_available and query_embedding:
            # Vector similarity search
            rows = self.conn.execute(
                """SELECT v.id, v.distance, m.content, m.metadata, m.created_at
                   FROM vec_memories v
                   JOIN memories m ON v.id = m.id
                   WHERE v.embedding MATCH ?
                   ORDER BY v.distance
                   LIMIT ?""",
                (_serialize_vector(query_embedding), limit)
            ).fetchall()
            return [
                {
                    "id": r["id"],
                    "content": r["content"],
                    "metadata": json.loads(r["metadata"]),
                    "score": r["distance"],
                    "created_at": r["created_at"],
                }
                for r in rows
            ]

        # Text search fallback
        if text_query:
            rows = self.conn.execute(
                """SELECT id, content, metadata, created_at
                   FROM memories
                   WHERE content LIKE ?
                   ORDER BY created_at DESC
                   LIMIT ?""",
                (f"%{text_query}%", limit)
            ).fetchall()
            return [
                {
                    "id": r["id"],
                    "content": r["content"],
                    "metadata": json.loads(r["metadata"]),
                    "score": 1.0,
                    "created_at": r["created_at"],
                }
                for r in rows
            ]

        return []

    # ─── Graph Operations (Neo4j replacement) ─────────────────────────────

    def graph_add_node(self, node_id: str, label: str,
                       node_type: str = "entity", props: Dict = None,
                       astro_tag: bool = True) -> bool:
        """Add a node to the knowledge graph."""
        with self.conn:
            self.conn.execute(
                """INSERT INTO graph_nodes (id, label, type, props)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET
                     label = excluded.label, type = excluded.type, props = excluded.props""",
                (node_id, label, node_type, json.dumps(props or {}))
            )
        if astro_tag:
            self._tag_with_astro("graph_node", node_id)
        return True

    def graph_add_edge(self, source: str, target: str,
                       rel: str, props: Dict = None,
                       astro_tag: bool = True) -> bool:
        """Add an edge to the knowledge graph."""
        with self.conn:
            self.conn.execute(
                """INSERT OR REPLACE INTO graph_edges (source, target, rel, props)
                   VALUES (?, ?, ?, ?)""",
                (source, target, rel, json.dumps(props or {}))
            )
        if astro_tag:
            edge_id = f"{source}_{rel}_{target}"
            self._tag_with_astro("graph_edge", edge_id)
        return True

    def graph_query_neighbors(self, node_id: str, max_depth: int = 2) -> List[Dict]:
        """Find connected nodes via recursive CTE (replaces Cypher traversal)."""
        rows = self.conn.execute(
            """WITH RECURSIVE traversal(id, label, type, depth, path) AS (
                 SELECT n.id, n.label, n.type, 0, n.id
                 FROM graph_nodes n WHERE n.id = ?
                 UNION
                 SELECT n2.id, n2.label, n2.type, t.depth + 1,
                        t.path || ' -> ' || e.rel || ' -> ' || n2.label
                 FROM traversal t
                 JOIN graph_edges e ON (e.source = t.id OR e.target = t.id)
                 JOIN graph_nodes n2 ON (n2.id = e.target OR n2.id = e.source)
                 WHERE t.depth < ? AND n2.id != t.id
                   AND instr(t.path, n2.id) = 0
               )
               SELECT DISTINCT id, label, type, depth, path
               FROM traversal WHERE depth > 0
               ORDER BY depth, label
               LIMIT 50""",
            (node_id, max_depth)
        ).fetchall()
        return [dict(r) for r in rows]

    # ─── Event/Timeseries Operations (TimescaleDB replacement) ────────────

    def store_event(self, event_type: str, value: float = 0.0,
                    category: str = "metrics", payload: Dict = None,
                    astro_tag: bool = True) -> str:
        """Store a timeseries event, optionally with astrological context."""
        event_id = f"evt_{uuid.uuid4().hex[:12]}"
        with self.conn:
            self.conn.execute(
                """INSERT INTO events (id, event_type, category, value, payload)
                   VALUES (?, ?, ?, ?, ?)""",
                (event_id, event_type, category, value, json.dumps(payload or {}))
            )
        if astro_tag:
            self._tag_with_astro("event", event_id)
        return event_id

    def query_events(self, event_type: str = None,
                     limit: int = 100, with_astro: bool = False) -> List[Dict]:
        """Query timeseries events, optionally with astrological context."""
        if event_type:
            rows = self.conn.execute(
                "SELECT * FROM events WHERE event_type = ? ORDER BY timestamp DESC LIMIT ?",
                (event_type, limit)
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM events ORDER BY timestamp DESC LIMIT ?", (limit,)
            ).fetchall()
        results = [dict(r) for r in rows]
        if with_astro:
            for r in results:
                astro = self.get_astro_context("event", r["id"])
                if astro:
                    r["astro_context"] = astro
        return results

    def _tag_with_astro(self, ref_type: str, ref_id: str) -> None:
        """Tag a record with current astrological context (planetary positions)."""
        try:
            snapshot = _get_current_astro_snapshot()
            if not snapshot:
                return
            ctx_id = f"ctx_{uuid.uuid4().hex[:12]}"
            with self.conn:
                self.conn.execute(
                    """INSERT INTO astro_context
                       (id, ref_type, ref_id, sun_sign, moon_sign, asc_sign,
                        mercury_sign, venus_sign, mars_sign, jupiter_sign, saturn_sign,
                        moon_phase, void_of_course, retrograde, planetary_hour, positions)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (ctx_id, ref_type, ref_id,
                     snapshot.get("sun_sign"), snapshot.get("moon_sign"),
                     snapshot.get("asc_sign"),
                     snapshot.get("mercury_sign"), snapshot.get("venus_sign"),
                     snapshot.get("mars_sign"), snapshot.get("jupiter_sign"),
                     snapshot.get("saturn_sign"),
                     snapshot.get("moon_phase"), snapshot.get("void_of_course", 0),
                     json.dumps(snapshot.get("retrograde", [])),
                     snapshot.get("planetary_hour", ""),
                     json.dumps(snapshot.get("positions", {})))
                )
        except Exception as e:
            logger.debug(f"Astro tagging failed: {e}")

    def get_astro_context(self, ref_type: str, ref_id: str) -> Optional[Dict]:
        """Get astrological context for a tagged record."""
        row = self.conn.execute(
            """SELECT * FROM astro_context
               WHERE ref_type = ? AND ref_id = ?
               ORDER BY timestamp DESC LIMIT 1""",
            (ref_type, ref_id)
        ).fetchone()
        if row:
            result = dict(row)
            result["retrograde"] = json.loads(result.get("retrograde", "[]"))
            result["positions"] = json.loads(result.get("positions", "{}"))
            return result
        return None

    def query_astro_timeline(self, hours: int = 24, field: str = "moon_sign") -> List[Dict]:
        """Query astro context changes over time — time-series analysis."""
        rows = self.conn.execute(
            """SELECT timestamp, sun_sign, moon_sign, moon_phase, void_of_course,
                      planetary_hour, retrograde
               FROM astro_context
               WHERE timestamp >= datetime('now', ? || ' hours')
               ORDER BY timestamp ASC""",
            (f"-{hours}",)
        ).fetchall()
        return [dict(r) for r in rows]

    # ─── Conversation Operations ──────────────────────────────────────────

    def create_conversation(self, title: str = "New Chat") -> str:
        """Create a new conversation."""
        conv_id = f"conv_{uuid.uuid4().hex[:12]}"
        with self.conn:
            self.conn.execute(
                "INSERT INTO conversations (id, title) VALUES (?, ?)",
                (conv_id, title)
            )
        return conv_id

    def add_message(self, conversation_id: str, role: str, content: str,
                    tool_calls: List[Dict] = None, astro_tag: bool = True) -> str:
        """Add a message to a conversation, auto-tagged with astro context."""
        msg_id = f"msg_{uuid.uuid4().hex[:12]}"
        with self.conn:
            self.conn.execute(
                """INSERT INTO messages (id, conversation_id, role, content, tool_calls)
                   VALUES (?, ?, ?, ?, ?)""",
                (msg_id, conversation_id, role, content, json.dumps(tool_calls or []))
            )
            self.conn.execute(
                "UPDATE conversations SET updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now') WHERE id = ?",
                (conversation_id,)
            )
        # Tag with astrological context (like thia-libre's TimescaleDB)
        if astro_tag and role == "user":
            self._tag_with_astro("message", msg_id)
        return msg_id

    def get_conversation_messages(self, conversation_id: str,
                                  limit: int = 100) -> List[Dict]:
        """Get messages for a conversation."""
        rows = self.conn.execute(
            """SELECT id, role, content, tool_calls, created_at
               FROM messages WHERE conversation_id = ?
               ORDER BY created_at ASC LIMIT ?""",
            (conversation_id, limit)
        ).fetchall()
        return [
            {
                **dict(r),
                "tool_calls": json.loads(r["tool_calls"]) if r["tool_calls"] else [],
            }
            for r in rows
        ]

    def list_conversations(self, limit: int = 50) -> List[Dict]:
        """List recent conversations."""
        rows = self.conn.execute(
            "SELECT * FROM conversations ORDER BY updated_at DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    # ─── Rules Vector Index ───────────────────────────────────────────────

    def rules_index_add(self, rule_id: str, embedding: List[float]) -> bool:
        """Add a rule embedding to the vector index."""
        if not self._vec_available:
            return False
        try:
            with self.conn:
                self.conn.execute(
                    "INSERT OR REPLACE INTO vec_rules (id, embedding) VALUES (?, ?)",
                    (rule_id, _serialize_vector(embedding))
                )
            return True
        except Exception as e:
            logger.error(f"rules_index_add error: {e}")
            return False

    def rules_search(self, query_embedding: List[float], limit: int = 8) -> List[Tuple[str, float]]:
        """Search rules by vector similarity, returns (rule_id, distance) pairs."""
        if not self._vec_available:
            return []
        rows = self.conn.execute(
            """SELECT id, distance FROM vec_rules
               WHERE embedding MATCH ?
               ORDER BY distance LIMIT ?""",
            (_serialize_vector(query_embedding), limit)
        ).fetchall()
        return [(r["id"], r["distance"]) for r in rows]

    # ─── Ephemeris Cache ──────────────────────────────────────────────────

    def ephemeris_get(self, jd: float, planet: str, sidereal: bool = False) -> Optional[Dict]:
        """Get cached ephemeris position."""
        row = self.conn.execute(
            "SELECT payload FROM ephemeris_cache WHERE julian_day = ? AND planet = ? AND sidereal = ?",
            (jd, planet, int(sidereal))
        ).fetchone()
        if row:
            return json.loads(row["payload"])
        return None

    def ephemeris_set(self, jd: float, planet: str, payload: Dict, sidereal: bool = False) -> None:
        """Cache an ephemeris position."""
        with self.conn:
            self.conn.execute(
                """INSERT OR REPLACE INTO ephemeris_cache (julian_day, planet, sidereal, payload)
                   VALUES (?, ?, ?, ?)""",
                (jd, planet, int(sidereal), json.dumps(payload))
            )

    # ─── Stats ────────────────────────────────────────────────────────────

    def get_stats(self) -> Dict[str, int]:
        """Get database statistics."""
        tables = ["kv", "memories", "graph_nodes", "graph_edges",
                  "events", "conversations", "messages", "predictions",
                  "vestige_cards", "ephemeris_cache"]
        stats = {}
        for table in tables:
            try:
                row = self.conn.execute(f"SELECT COUNT(*) as cnt FROM {table}").fetchone()
                stats[table] = row["cnt"]
            except Exception:
                stats[table] = 0
        stats["vec_available"] = self._vec_available
        return stats


# ─── Astro Snapshot Helper ────────────────────────────────────────────────────

def _get_current_astro_snapshot() -> Optional[Dict]:
    """Get current planetary positions for tagging. Lightweight, no-fail."""
    try:
        from thia_lite.llm.tool_executor import _tool_handlers
        if "get_current_transits" not in _tool_handlers:
            return None
        result = _tool_handlers["get_current_transits"]("get_current_transits", {})
        if not isinstance(result, dict):
            return None

        planets = result.get("planets", {})
        snapshot = {"positions": {}}

        sign_map = [
            "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
            "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"
        ]

        retrograde = []
        for name, data in planets.items():
            if isinstance(data, dict):
                lon = data.get("longitude", 0)
                sign = sign_map[int(lon / 30) % 12]
                snapshot["positions"][name] = {"longitude": lon, "sign": sign}
                key = f"{name.lower()}_sign"
                snapshot[key] = sign
                if data.get("retrograde"):
                    retrograde.append(name)

        snapshot["retrograde"] = retrograde
        snapshot["moon_phase"] = result.get("moon_phase", "")
        snapshot["void_of_course"] = 1 if result.get("voc") else 0
        return snapshot
    except Exception:
        return None


# ─── Global Instance ──────────────────────────────────────────────────────────

_db: Optional[Database] = None


def get_db() -> Database:
    """Get or create the global database instance."""
    global _db
    if _db is None:
        from thia_lite.config import get_settings
        settings = get_settings()
        _db = Database(settings.db_path)
        _db.connect()
    return _db

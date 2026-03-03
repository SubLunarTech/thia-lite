"""
Thia-Lite Conversation Manager
================================
Handles chat sessions with:
- Message persistence (SQLite)
- RAG injection (Lilly + Ptolemy rules)
- Entity extraction from conversations (people, dates, locations)
- Semantic memory (store/recall facts, birth data, preferences)
- Context window management
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Dict, List, Optional

from thia_lite.db import get_db
from thia_lite.llm.client import get_llm_client
from thia_lite.llm.tool_executor import ToolExecutor, SYSTEM_PROMPT

logger = logging.getLogger(__name__)


# ─── Entity Patterns ─────────────────────────────────────────────────────────

# Simple regex-based entity extraction (no NLP dependency)
DATE_PATTERN = re.compile(
    r'\b(\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{4}|'
    r'(?:January|February|March|April|May|June|July|August|September|October|November|December)'
    r'\s+\d{1,2},?\s*\d{4})\b', re.IGNORECASE
)

TIME_PATTERN = re.compile(
    r'\b(\d{1,2}:\d{2}(?::\d{2})?\s*(?:AM|PM|am|pm)?)\b'
)

COORD_PATTERN = re.compile(
    r'(-?\d{1,3}\.\d+)[,\s]+(-?\d{1,3}\.\d+)'
)

# Zodiac signs for astrological entity detection
SIGNS = [
    'aries', 'taurus', 'gemini', 'cancer', 'leo', 'virgo',
    'libra', 'scorpio', 'sagittarius', 'capricorn', 'aquarius', 'pisces'
]

PLANETS = [
    'sun', 'moon', 'mercury', 'venus', 'mars', 'jupiter',
    'saturn', 'uranus', 'neptune', 'pluto', 'north node', 'south node'
]

HOUSES = [f'{i}th house' for i in range(1, 13)]
HOUSES[0] = '1st house'
HOUSES[1] = '2nd house'
HOUSES[2] = '3rd house'

ASPECTS = [
    'conjunction', 'sextile', 'square', 'trine', 'opposition',
    'quincunx', 'semi-sextile', 'sesquiquadrate'
]


class ConversationManager:
    """Manages chat conversations with persistence, RAG, and memory."""

    def __init__(self, max_context_messages: int = 40):
        self.max_context_messages = max_context_messages
        self.current_conversation_id: Optional[str] = None
        self.executor = ToolExecutor()
        self._rules_loaded = False

    def new_conversation(self, title: str = "New Chat") -> str:
        """Start a new conversation."""
        db = get_db()
        self.current_conversation_id = db.create_conversation(title)
        return self.current_conversation_id

    def load_conversation(self, conversation_id: str) -> List[Dict]:
        """Load an existing conversation."""
        db = get_db()
        self.current_conversation_id = conversation_id
        return db.get_conversation_messages(conversation_id)

    def list_conversations(self, limit: int = 20) -> List[Dict]:
        """List recent conversations."""
        return get_db().list_conversations(limit)

    async def send_message(self, content: str) -> Dict[str, Any]:
        """
        Send a user message and get the assistant's response.
        Also:
        - Extracts entities from user message
        - Injects relevant rules (RAG)
        - Recalls relevant memories
        - Saves new entities/facts after response

        Returns:
            {
                "content": "...",
                "tool_calls_made": [...],
                "iterations": int,
                "duration_ms": int,
            }
        """
        db = get_db()
        start = time.monotonic()

        # Ensure we have a conversation
        if not self.current_conversation_id:
            title = content[:50] + "..." if len(content) > 50 else content
            self.new_conversation(title)

        # Store user message
        db.add_message(self.current_conversation_id, "user", content)

        # Extract entities from user message
        entities = extract_entities(content)
        if entities:
            self._save_entities(entities, "user", content)

        # Get conversation history for context
        history = db.get_conversation_messages(
            self.current_conversation_id,
            limit=self.max_context_messages
        )

        # Convert to LLM format
        context = []
        for msg in history[:-1]:
            entry = {"role": msg["role"], "content": msg["content"]}
            if msg.get("tool_calls"):
                entry["tool_calls"] = msg["tool_calls"]
            context.append(entry)

        # Build extra context: rules + memories
        extra_parts = []

        # RAG: get relevant astrology rules
        rules_context = self._get_relevant_rules_text(content)
        if rules_context:
            extra_parts.append(
                "=== Relevant Traditional Astrology Rules ===\n" + rules_context
            )

        # Memory: recall relevant facts
        memories = self._recall_memories(content)
        if memories:
            extra_parts.append(
                "=== Remembered Facts ===\n" + memories
            )

        extra_context = "\n\n".join(extra_parts) if extra_parts else ""

        # Execute agentic loop
        result = await self.executor.execute(
            user_message=content,
            conversation_history=context,
            extra_context=extra_context,
        )

        # Store assistant response
        db.add_message(
            self.current_conversation_id,
            "assistant",
            result["content"],
            tool_calls=result.get("tool_calls_made"),
        )

        # Extract entities from response and save
        if result["content"]:
            resp_entities = extract_entities(result["content"])
            if resp_entities:
                self._save_entities(resp_entities, "assistant", result["content"])

        # Auto-save any birth data mentioned
        self._auto_save_birth_data(content, result["content"])

        elapsed_ms = int((time.monotonic() - start) * 1000)
        result["duration_ms"] = elapsed_ms

        return result

    # ─── RAG: Rules Integration ───────────────────────────────────────────

    def _ensure_rules_loaded(self):
        """Load all rules into the database for searching (first time only)."""
        if self._rules_loaded:
            return

        db = get_db()

        # Check if rules already in DB
        existing = db.kv_get("system", "rules_loaded_version")
        if existing == "v2":
            self._rules_loaded = True
            return

        try:
            from thia_lite.rules import load_all_rules
            all_rules = load_all_rules()
            if not all_rules:
                self._rules_loaded = True
                return

            logger.info(f"Loading {len(all_rules)} rules into database...")
            for rule in all_rules:
                rule_id = rule.get("id", "")
                db.kv_set("rules", rule_id, rule)

            db.kv_set("system", "rules_loaded_version", "v2")
            self._rules_loaded = True
            logger.info(f"Loaded {len(all_rules)} rules into database")
        except Exception as e:
            logger.warning(f"Could not load rules: {e}")
            self._rules_loaded = True

    def _get_relevant_rules_text(self, query: str) -> str:
        """Search for relevant rules using text matching."""
        try:
            from thia_lite.rules import search_rules
            matches = search_rules(query, max_results=5)
            if not matches:
                return ""

            lines = []
            for rule in matches:
                source = rule.get("source", "Unknown")
                category = rule.get("category", "")
                text = rule.get("text", "")
                lines.append(f"[{source} — {category}] {text}")

            return "\n".join(lines)
        except Exception as e:
            logger.debug(f"Rule search failed: {e}")
            return ""

    # ─── Memory System ────────────────────────────────────────────────────

    def _save_entities(self, entities: Dict[str, List[str]], role: str, text: str):
        """Save extracted entities to the knowledge graph."""
        db = get_db()

        for entity_type, values in entities.items():
            for value in values:
                # Store as key-value
                key = f"{entity_type}:{value.lower()}"
                existing = db.kv_get("entities", key)
                if existing and isinstance(existing, dict):
                    # Update mention count
                    existing["mentions"] = existing.get("mentions", 0) + 1
                    existing["last_context"] = text[:200]
                    db.kv_set("entities", key, existing)
                else:
                    db.kv_set("entities", key, {
                        "type": entity_type,
                        "value": value,
                        "mentions": 1,
                        "first_context": text[:200],
                        "last_context": text[:200],
                        "conversation_id": self.current_conversation_id,
                    })

                # Store as graph node
                db.graph_add_node(
                    node_id=key,
                    node_type=entity_type,
                    properties={"name": value, "source": role},
                )

    def _recall_memories(self, query: str) -> str:
        """Recall relevant facts from past conversations."""
        db = get_db()
        memories = []

        # Check for known birth data
        birth_data = db.kv_get("user_data", "birth_info")
        if birth_data and isinstance(birth_data, dict):
            memories.append(
                f"User's birth data: "
                f"{birth_data.get('date', '?')}, "
                f"{birth_data.get('time', '?')}, "
                f"{birth_data.get('location', '?')}"
            )

        # Check for entity matches in the query
        query_lower = query.lower()
        for planet in PLANETS:
            if planet in query_lower:
                ent = db.kv_get("entities", f"planet:{planet}")
                if ent and isinstance(ent, dict):
                    memories.append(
                        f"Previously discussed {planet}: {ent.get('last_context', '')[:100]}"
                    )

        for sign in SIGNS:
            if sign in query_lower:
                ent = db.kv_get("entities", f"sign:{sign}")
                if ent and isinstance(ent, dict):
                    memories.append(
                        f"Previously discussed {sign}: {ent.get('last_context', '')[:100]}"
                    )

        # Check for remembered preferences
        prefs = db.kv_get("user_data", "preferences")
        if prefs and isinstance(prefs, dict):
            for k, v in prefs.items():
                if k.lower() in query_lower:
                    memories.append(f"User preference: {k} = {v}")

        return "\n".join(memories) if memories else ""

    def _auto_save_birth_data(self, user_msg: str, response: str):
        """Auto-detect and save birth data from conversation."""
        db = get_db()

        # Look for birth-related keywords
        birth_keywords = ['born', 'birth', 'natal', 'my chart', 'my birth']
        if not any(kw in user_msg.lower() for kw in birth_keywords):
            return

        # Extract date, time, location from user message
        dates = DATE_PATTERN.findall(user_msg)
        times = TIME_PATTERN.findall(user_msg)

        if dates:
            existing = db.kv_get("user_data", "birth_info") or {}
            if isinstance(existing, dict):
                existing["date"] = dates[0]
                if times:
                    existing["time"] = times[0]
                # Try to find location (words after "in" or "at")
                loc_match = re.search(r'\b(?:in|at)\s+([A-Z][a-zA-Z\s,]+)', user_msg)
                if loc_match:
                    existing["location"] = loc_match.group(1).strip()
                db.kv_set("user_data", "birth_info", existing)
                logger.info(f"Saved birth data: {existing}")

    # ─── Memory API (for tools) ───────────────────────────────────────────

    def remember(self, key: str, value: Any):
        """Store a fact in persistent memory."""
        get_db().kv_set("memory", key, {"value": value, "type": "fact"})

    def recall(self, key: str) -> Any:
        """Recall a fact from persistent memory."""
        data = get_db().kv_get("memory", key)
        return data.get("value") if data and isinstance(data, dict) else None

    def forget(self, key: str):
        """Remove a fact from persistent memory."""
        get_db().kv_set("memory", key, None)


# ─── Entity Extraction ───────────────────────────────────────────────────────

def extract_entities(text: str) -> Dict[str, List[str]]:
    """
    Extract astrological and temporal entities from text.

    Returns dict of entity_type -> list of values:
        {
            "planet": ["Mars", "Venus"],
            "sign": ["Aries"],
            "house": ["7th house"],
            "aspect": ["conjunction"],
            "date": ["1990-01-15"],
            "time": ["14:30"],
            "coordinates": [("40.7128", "-74.0060")],
        }
    """
    entities: Dict[str, List[str]] = {}
    text_lower = text.lower()

    # Planets
    found_planets = [p.title() for p in PLANETS if p in text_lower]
    if found_planets:
        entities["planet"] = found_planets

    # Signs
    found_signs = [s.title() for s in SIGNS if s in text_lower]
    if found_signs:
        entities["sign"] = found_signs

    # Houses
    found_houses = [h for h in HOUSES if h in text_lower]
    if found_houses:
        entities["house"] = found_houses

    # Aspects
    found_aspects = [a for a in ASPECTS if a in text_lower]
    if found_aspects:
        entities["aspect"] = found_aspects

    # Dates
    dates = DATE_PATTERN.findall(text)
    if dates:
        entities["date"] = list(set(dates))

    # Times
    times = TIME_PATTERN.findall(text)
    if times:
        entities["time"] = list(set(times))

    # Coordinates
    coords = COORD_PATTERN.findall(text)
    if coords:
        entities["coordinates"] = coords

    return entities

"""
Thia-Lite Rules Loader
========================
Loads Lilly and Ptolemy rule corpora from the JSON data files
extracted from:
  - Lilly: mlearn pipeline OCR extraction of Christian Astrology (archive.org)
  - Ptolemy: thia-libre traditional_rules.py extraction of Tetrabiblos

Used for RAG — relevant rules are injected into LLM context during conversations.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_rules_cache: Optional[Dict[str, List[Dict[str, Any]]]] = None


def _rules_dir() -> str:
    """Get the rules directory path."""
    return os.path.dirname(os.path.abspath(__file__))


def load_lilly_rules() -> List[Dict[str, Any]]:
    """Load all William Lilly rules from the JSON data file."""
    path = os.path.join(_rules_dir(), "lilly_rules_data.json")
    try:
        with open(path) as f:
            rules = json.load(f)
        logger.info(f"Loaded {len(rules)} Lilly rules from {path}")
        return rules
    except FileNotFoundError:
        logger.warning(f"Lilly rules not found at {path}")
        return []
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Lilly rules: {e}")
        return []


def load_ptolemy_rules() -> List[Dict[str, Any]]:
    """Load all Ptolemy rules from the JSON data file."""
    path = os.path.join(_rules_dir(), "ptolemy_rules_data.json")
    try:
        with open(path) as f:
            rules = json.load(f)
        logger.info(f"Loaded {len(rules)} Ptolemy rules from {path}")
        return rules
    except FileNotFoundError:
        logger.warning(f"Ptolemy rules not found at {path}")
        return []
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Ptolemy rules: {e}")
        return []


def load_all_rules() -> List[Dict[str, Any]]:
    """Load all rules from all *_data.json files in the rules directory."""
    global _rules_cache
    if _rules_cache is None:
        _rules_cache = {}
        directory = _rules_dir()
        for filename in os.listdir(directory):
            if filename.endswith("_data.json"):
                source_key = filename.replace("_rules_data.json", "").replace("_data.json", "")
                path = os.path.join(directory, filename)
                try:
                    with open(path) as f:
                        rules = json.load(f)
                        _rules_cache[source_key] = rules
                        logger.info(f"Loaded {len(rules)} rules from {path}")
                except Exception as e:
                    logger.error(f"Failed to load {path}: {e}")

    all_rules = []
    for rules in _rules_cache.values():
        all_rules.extend(rules)
    return all_rules


def get_rules_by_source(source: str) -> List[Dict[str, Any]]:
    """Get rules filtered by source (e.g., 'Lilly' or 'Ptolemy')."""
    if _rules_cache is None:
        load_all_rules()
    return _rules_cache.get(source.lower(), [])


def get_rules_by_category(category: str) -> List[Dict[str, Any]]:
    """Get rules filtered by category (e.g., 'horary', 'natal', 'mundane')."""
    return [r for r in load_all_rules() if r.get("category") == category]


def search_rules(query: str, max_results: int = 10) -> List[Dict[str, Any]]:
    """Simple text search across all rules (for use without vector DB)."""
    query_lower = query.lower()
    scored = []
    for rule in load_all_rules():
        text = rule.get("text", "").lower()
        # Simple relevance: count matching words
        score = sum(1 for word in query_lower.split() if word in text)
        if score > 0:
            scored.append((score, rule))
    scored.sort(key=lambda x: -x[0])
    return [r for _, r in scored[:max_results]]


def get_rules_stats() -> Dict[str, Any]:
    """Get statistics about the loaded rules."""
    all_rules = load_all_rules()
    sources = {}
    categories = {}
    for r in all_rules:
        s = r.get("source", "Unknown")
        c = r.get("category", "unknown")
        sources[s] = sources.get(s, 0) + 1
        categories[c] = categories.get(c, 0) + 1
    return {
        "total": len(all_rules),
        "by_source": sources,
        "by_category": categories,
    }


# ─── CLI usage ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    stats = get_rules_stats()
    print(f"Total rules: {stats['total']}")
    print("\nBy source:")
    for s, n in sorted(stats["by_source"].items(), key=lambda x: -x[1]):
        print(f"  {s}: {n}")
    print("\nBy category:")
    for c, n in sorted(stats["by_category"].items(), key=lambda x: -x[1]):
        print(f"  {c}: {n}")

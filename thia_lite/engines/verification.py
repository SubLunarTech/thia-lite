"""
Thia-Lite Verification Engine
================================
Correlates astrological predictions with real-world outcomes.
Mirrors thia-libre's prediction tracking + Bohmian mechanics correlation.

Features:
- Prediction lifecycle (create → track → resolve → score)
- Event-astrology correlation (tag events with sky data, find patterns)
- Accuracy scoring and backtesting
- Time-series analysis of prediction accuracy by planetary conditions
"""

from __future__ import annotations

import json
import logging
import math
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ─── Prediction Tracker ──────────────────────────────────────────────────────

class PredictionTracker:
    """
    Tracks astrological predictions and verifies them against outcomes.
    
    Mirrors thia-libre's prediction verification system:
    - Create predictions with astrological basis
    - Track resolution dates
    - Score accuracy
    - Analyze which astrological factors correlate with accurate predictions
    """

    def __init__(self):
        from thia_lite.db import get_db
        self._db = get_db()

    def create_prediction(
        self,
        prediction: str,
        category: str = "general",
        confidence: float = 0.5,
        resolve_by: Optional[str] = None,
        astrological_basis: Optional[Dict] = None,
        tags: Optional[List[str]] = None,
    ) -> str:
        """
        Create a new prediction with its astrological basis.
        
        Args:
            prediction: The prediction text
            category: transit, horary, election, mundane, financial, natal
            confidence: 0.0-1.0 confidence score
            resolve_by: Date by which prediction should be verifiable (ISO 8601)
            astrological_basis: Dict with the astrological factors behind prediction
            tags: Optional tags for filtering
        """
        pred_id = f"pred_{uuid.uuid4().hex[:12]}"
        metadata = {
            "astrological_basis": astrological_basis or {},
            "tags": tags or [],
        }

        # Get current sky snapshot for correlation
        try:
            from thia_lite.db import _get_current_astro_snapshot
            snapshot = _get_current_astro_snapshot()
            if snapshot:
                metadata["sky_at_prediction"] = snapshot
        except Exception:
            pass

        with self._db.conn:
            self._db.conn.execute(
                """INSERT INTO predictions
                   (id, prediction, category, confidence, status, resolve_by, metadata)
                   VALUES (?, ?, ?, ?, 'pending', ?, ?)""",
                (pred_id, prediction, category, confidence,
                 resolve_by, json.dumps(metadata))
            )

        logger.info(f"Created prediction {pred_id}: {prediction[:50]}...")
        return pred_id

    def resolve_prediction(
        self,
        prediction_id: str,
        outcome: str,
        accuracy: float = 0.0,
        notes: str = "",
    ) -> Dict[str, Any]:
        """
        Resolve a prediction with its actual outcome.
        
        Args:
            prediction_id: The prediction ID
            outcome: What actually happened
            accuracy: 0.0-1.0 how accurate the prediction was
            notes: Additional notes
        """
        # Get the prediction
        row = self._db.conn.execute(
            "SELECT * FROM predictions WHERE id = ?", (prediction_id,)
        ).fetchone()
        if not row:
            return {"error": "Prediction not found"}

        metadata = json.loads(row["metadata"])
        metadata["outcome_notes"] = notes
        metadata["accuracy_score"] = accuracy

        # Get current sky for correlation with outcome timing
        try:
            from thia_lite.db import _get_current_astro_snapshot
            snapshot = _get_current_astro_snapshot()
            if snapshot:
                metadata["sky_at_resolution"] = snapshot
        except Exception:
            pass

        status = "correct" if accuracy >= 0.5 else "incorrect"
        if accuracy >= 0.8:
            status = "highly_accurate"

        with self._db.conn:
            self._db.conn.execute(
                """UPDATE predictions
                   SET outcome = ?, status = ?, resolved_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now'),
                       metadata = ?
                   WHERE id = ?""",
                (outcome, status, json.dumps(metadata), prediction_id)
            )

        # Store as timeseries event for correlation analysis
        self._db.store_event(
            event_type="prediction_resolved",
            value=accuracy,
            category="verification",
            payload={
                "prediction_id": prediction_id,
                "status": status,
                "category": row["category"],
            }
        )

        return {
            "prediction_id": prediction_id,
            "status": status,
            "accuracy": accuracy,
            "original": row["prediction"],
            "outcome": outcome,
        }

    def get_accuracy_stats(self, category: Optional[str] = None) -> Dict[str, Any]:
        """Get prediction accuracy statistics, optionally filtered by category."""
        if category:
            rows = self._db.conn.execute(
                """SELECT status, COUNT(*) as cnt, AVG(confidence) as avg_confidence
                   FROM predictions WHERE category = ?
                   GROUP BY status""",
                (category,)
            ).fetchall()
            total = self._db.conn.execute(
                "SELECT COUNT(*) as cnt FROM predictions WHERE category = ?",
                (category,)
            ).fetchone()["cnt"]
        else:
            rows = self._db.conn.execute(
                """SELECT status, COUNT(*) as cnt, AVG(confidence) as avg_confidence
                   FROM predictions GROUP BY status"""
            ).fetchall()
            total = self._db.conn.execute(
                "SELECT COUNT(*) as cnt FROM predictions"
            ).fetchone()["cnt"]

        stats = {"total": total, "by_status": {}}
        for r in rows:
            stats["by_status"][r["status"]] = {
                "count": r["cnt"],
                "avg_confidence": round(r["avg_confidence"] or 0, 3),
            }

        # Calculate accuracy rate
        correct = sum(
            v["count"] for k, v in stats["by_status"].items()
            if k in ("correct", "highly_accurate")
        )
        resolved = sum(
            v["count"] for k, v in stats["by_status"].items()
            if k != "pending"
        )
        stats["accuracy_rate"] = round(correct / resolved, 3) if resolved > 0 else 0.0
        stats["resolved"] = resolved
        stats["pending"] = stats["by_status"].get("pending", {}).get("count", 0)

        return stats

    def get_pending_predictions(self) -> List[Dict]:
        """Get predictions that are due for resolution."""
        rows = self._db.conn.execute(
            """SELECT * FROM predictions
               WHERE status = 'pending'
               AND (resolve_by IS NULL OR resolve_by <= strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
               ORDER BY created_at DESC"""
        ).fetchall()
        return [dict(r) for r in rows]


# ─── Event Correlator ────────────────────────────────────────────────────────

class EventCorrelator:
    """
    Correlates real-world events with astrological conditions.
    
    Mirrors thia-libre's Bohmian mechanics correlation analysis:
    - Log real-world events with timestamps
    - Auto-tag with planetary positions
    - Find patterns (e.g., "events of type X occur more often when Mars is in Aries")
    - Statistical correlation analysis
    """

    def __init__(self):
        from thia_lite.db import get_db
        self._db = get_db()

    def log_event(
        self,
        event_type: str,
        description: str,
        magnitude: float = 1.0,
        category: str = "observation",
        tags: Optional[List[str]] = None,
    ) -> str:
        """
        Log a real-world event for astrological correlation.
        
        Examples:
          - log_event("market_move", "BTC dropped 15%", magnitude=15.0, category="financial")
          - log_event("personal", "Got promoted at work", magnitude=8.0, category="career")
          - log_event("mundane", "Earthquake in Turkey", magnitude=7.5, category="natural")
        """
        event_id = self._db.store_event(
            event_type=event_type,
            value=magnitude,
            category=category,
            payload={
                "description": description,
                "tags": tags or [],
            },
            astro_tag=True,  # Auto-tag with planetary positions
        )
        return event_id

    def find_correlations(
        self,
        event_type: str,
        field: str = "moon_sign",
        min_events: int = 3,
    ) -> Dict[str, Any]:
        """
        Find astrological correlations for a type of event.
        
        Analyzes which planetary conditions appear more often
        when events of this type occur vs. the baseline.
        """
        # Get all events of this type with their astro context
        events = self._db.query_events(event_type=event_type, limit=1000, with_astro=True)
        events_with_astro = [e for e in events if "astro_context" in e]

        if len(events_with_astro) < min_events:
            return {
                "event_type": event_type,
                "total_events": len(events),
                "events_with_astro": len(events_with_astro),
                "message": f"Need at least {min_events} events with astro context for correlation",
            }

        # Count field values across events
        field_counts: Dict[str, int] = {}
        for e in events_with_astro:
            val = e["astro_context"].get(field)
            if val:
                field_counts[val] = field_counts.get(val, 0) + 1

        # Calculate percentages
        total = len(events_with_astro)
        correlations = []
        for val, count in sorted(field_counts.items(), key=lambda x: -x[1]):
            pct = count / total * 100
            # Expected baseline is ~8.3% for signs (1/12)
            expected = 100 / 12 if field.endswith("_sign") else 100 / len(field_counts)
            lift = pct / expected if expected > 0 else 1.0
            correlations.append({
                "value": val,
                "count": count,
                "percentage": round(pct, 1),
                "expected_pct": round(expected, 1),
                "lift": round(lift, 2),  # >1.0 means over-represented
            })

        return {
            "event_type": event_type,
            "field": field,
            "total_events": total,
            "correlations": correlations,
            "strongest": correlations[0] if correlations else None,
        }

    def analyze_retrograde_correlation(self, event_type: str) -> Dict[str, Any]:
        """Check if events correlate with retrograde periods."""
        events = self._db.query_events(event_type=event_type, limit=1000, with_astro=True)
        events_with_astro = [e for e in events if "astro_context" in e]

        retro_counts: Dict[str, int] = {}
        retro_events = 0
        for e in events_with_astro:
            retros = e["astro_context"].get("retrograde", [])
            if isinstance(retros, str):
                retros = json.loads(retros)
            if retros:
                retro_events += 1
                for planet in retros:
                    retro_counts[planet] = retro_counts.get(planet, 0) + 1

        total = len(events_with_astro)
        return {
            "event_type": event_type,
            "total_events": total,
            "events_during_retrograde": retro_events,
            "retrograde_rate": round(retro_events / total * 100, 1) if total > 0 else 0,
            "by_planet": {
                planet: {"count": count, "rate": round(count / total * 100, 1)}
                for planet, count in sorted(retro_counts.items(), key=lambda x: -x[1])
            } if total > 0 else {},
        }

    def compare_events(
        self, event_type_a: str, event_type_b: str, field: str = "moon_sign"
    ) -> Dict[str, Any]:
        """Compare astrological conditions between two event types."""
        corr_a = self.find_correlations(event_type_a, field=field, min_events=1)
        corr_b = self.find_correlations(event_type_b, field=field, min_events=1)

        return {
            "field": field,
            "event_a": {"type": event_type_a, **corr_a},
            "event_b": {"type": event_type_b, **corr_b},
        }


# ─── Backtesting Engine ──────────────────────────────────────────────────────

class BacktestEngine:
    """
    Backtest astrological rules against historical events.
    
    Tests whether specific astrological conditions (e.g., "Saturn square Moon")
    historically correlate with specific event types.
    """

    def __init__(self):
        from thia_lite.db import get_db
        self._db = get_db()

    def test_rule(
        self,
        rule_condition: str,
        event_type: str,
        field: str = "moon_sign",
        expected_value: str = "",
    ) -> Dict[str, Any]:
        """
        Test whether a condition correlates with events.
        
        Args:
            rule_condition: Description of the astrological condition
            event_type: Type of event to check
            field: Astro context field to test
            expected_value: Expected value of the field
        """
        events = self._db.query_events(event_type=event_type, limit=1000, with_astro=True)
        events_with_astro = [e for e in events if "astro_context" in e]

        matching = [
            e for e in events_with_astro
            if e["astro_context"].get(field) == expected_value
        ]

        total = len(events_with_astro)
        matches = len(matching)

        return {
            "rule": rule_condition,
            "event_type": event_type,
            "field": field,
            "expected": expected_value,
            "total_events": total,
            "matching_events": matches,
            "hit_rate": round(matches / total * 100, 1) if total > 0 else 0,
            "expected_rate": round(100 / 12, 1),  # baseline for signs
            "is_significant": matches / total > 1.5 / 12 if total > 0 else False,
        }


# ─── Tool Registration ───────────────────────────────────────────────────────

def register_verification_tools():
    """Register verification/correlation tools for the LLM."""
    from thia_lite.llm.tool_executor import register_tool

    _tracker = PredictionTracker()
    _correlator = EventCorrelator()
    _backtester = BacktestEngine()

    def verification_dispatch(tool_name: str, args: Dict[str, Any]) -> Any:
        if tool_name == "create_prediction":
            return _tracker.create_prediction(
                prediction=args["prediction"],
                category=args.get("category", "general"),
                confidence=args.get("confidence", 0.5),
                resolve_by=args.get("resolve_by"),
                astrological_basis=args.get("astrological_basis"),
                tags=args.get("tags"),
            )

        elif tool_name == "resolve_prediction":
            return _tracker.resolve_prediction(
                prediction_id=args["prediction_id"],
                outcome=args["outcome"],
                accuracy=args.get("accuracy", 0.0),
                notes=args.get("notes", ""),
            )

        elif tool_name == "prediction_stats":
            return _tracker.get_accuracy_stats(category=args.get("category"))

        elif tool_name == "pending_predictions":
            return _tracker.get_pending_predictions()

        elif tool_name == "log_real_event":
            return _correlator.log_event(
                event_type=args["event_type"],
                description=args["description"],
                magnitude=args.get("magnitude", 1.0),
                category=args.get("category", "observation"),
                tags=args.get("tags"),
            )

        elif tool_name == "find_astro_correlations":
            return _correlator.find_correlations(
                event_type=args["event_type"],
                field=args.get("field", "moon_sign"),
                min_events=args.get("min_events", 3),
            )

        elif tool_name == "check_retrograde_correlation":
            return _correlator.analyze_retrograde_correlation(
                event_type=args["event_type"]
            )

        elif tool_name == "backtest_rule":
            return _backtester.test_rule(
                rule_condition=args["rule_condition"],
                event_type=args["event_type"],
                field=args.get("field", "moon_sign"),
                expected_value=args.get("expected_value", ""),
            )

        return {"error": f"Unknown verification tool: {tool_name}"}

    register_tool("create_prediction",
        "Create a tracked astrological prediction. The system records the current sky and will track accuracy when resolved.",
        {"type": "object", "properties": {
            "prediction": {"type": "string", "description": "The prediction text"},
            "category": {"type": "string", "enum": ["transit", "horary", "election", "mundane", "financial", "natal"]},
            "confidence": {"type": "number", "description": "0.0-1.0 confidence"},
            "resolve_by": {"type": "string", "description": "Resolution deadline (ISO 8601)"},
            "astrological_basis": {"type": "object", "description": "The astrological factors behind the prediction"},
            "tags": {"type": "array", "items": {"type": "string"}},
        }, "required": ["prediction"]},
        verification_dispatch)

    register_tool("resolve_prediction",
        "Resolve a prediction with the actual outcome and accuracy score.",
        {"type": "object", "properties": {
            "prediction_id": {"type": "string"},
            "outcome": {"type": "string", "description": "What actually happened"},
            "accuracy": {"type": "number", "description": "0.0-1.0 accuracy score"},
            "notes": {"type": "string"},
        }, "required": ["prediction_id", "outcome"]},
        verification_dispatch)

    register_tool("prediction_stats",
        "Get prediction accuracy statistics. Shows how well your astrological predictions have performed.",
        {"type": "object", "properties": {
            "category": {"type": "string", "description": "Filter by category"},
        }},
        verification_dispatch)

    register_tool("pending_predictions",
        "Get predictions that are due for resolution.",
        {"type": "object", "properties": {}},
        verification_dispatch)

    register_tool("log_real_event",
        "Log a real-world event for astrological correlation. The system automatically captures the current planetary positions.",
        {"type": "object", "properties": {
            "event_type": {"type": "string", "description": "Event category (market_move, personal, mundane, weather, etc.)"},
            "description": {"type": "string", "description": "What happened"},
            "magnitude": {"type": "number", "description": "Event magnitude/importance (1-10)"},
            "category": {"type": "string", "description": "Sub-category"},
            "tags": {"type": "array", "items": {"type": "string"}},
        }, "required": ["event_type", "description"]},
        verification_dispatch)

    register_tool("find_astro_correlations",
        "Analyze correlations between a type of real-world event and astrological conditions. For example, find if 'market_move' events happen more often when Moon is in certain signs.",
        {"type": "object", "properties": {
            "event_type": {"type": "string", "description": "Event type to analyze"},
            "field": {"type": "string", "description": "Astro field to check (moon_sign, sun_sign, etc.)"},
            "min_events": {"type": "integer", "description": "Minimum events required"},
        }, "required": ["event_type"]},
        verification_dispatch)

    register_tool("check_retrograde_correlation",
        "Check if events of a given type correlate with retrograde periods.",
        {"type": "object", "properties": {
            "event_type": {"type": "string"},
        }, "required": ["event_type"]},
        verification_dispatch)

    register_tool("backtest_rule",
        "Backtest an astrological rule against logged events. Tests whether a specific condition historically correlates with specific events.",
        {"type": "object", "properties": {
            "rule_condition": {"type": "string", "description": "The astrological rule to test"},
            "event_type": {"type": "string", "description": "Event type to check against"},
            "field": {"type": "string", "description": "Astro context field"},
            "expected_value": {"type": "string", "description": "Expected field value"},
        }, "required": ["rule_condition", "event_type"]},
        verification_dispatch)

    logger.info("Registered verification/correlation tools")

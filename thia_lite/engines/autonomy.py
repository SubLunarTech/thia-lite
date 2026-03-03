"""
Thia-Lite Autonomy Engine
===========================
Lightweight autonomy capabilities matching thia-libre's systems:

- Research Loop: autonomous multi-step investigation
- Background Scanner: periodic transit/aspect monitoring
- Anticipation: proactive alerts for upcoming astrological events
- Task Planner: break complex questions into sub-tasks

All designed to run within 8GB RAM on a single process.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


# ─── Research Loop ────────────────────────────────────────────────────────────

@dataclass
class ResearchStep:
    """One step in a research investigation."""
    tool: str
    args: Dict[str, Any]
    result: Any = None
    reasoning: str = ""


@dataclass
class ResearchPlan:
    """A multi-step research plan."""
    question: str
    steps: List[ResearchStep] = field(default_factory=list)
    findings: List[str] = field(default_factory=list)
    status: str = "planned"  # planned, running, complete, failed
    created_at: float = field(default_factory=time.time)


class ResearchEngine:
    """
    Autonomous research loop.
    
    Given a complex question, decomposes it into sub-queries,
    executes tools iteratively, synthesizes findings, and asks
    follow-up questions until the investigation is complete.
    
    Mirrors thia-libre's Agentic Coordinator.
    """

    def __init__(self, max_steps: int = 15):
        self.max_steps = max_steps
        self._plans: Dict[str, ResearchPlan] = {}

    async def investigate(
        self,
        question: str,
        executor: Any,  # ToolExecutor
        on_step: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """
        Run an autonomous research investigation.
        
        The LLM plans the research, executes tools, reviews results,
        and iterates until it has enough information to answer.
        """
        plan = ResearchPlan(question=question)
        plan.status = "running"

        # Ask LLM to plan the research
        planning_prompt = f"""You are conducting a research investigation. 
Question: {question}

Plan your research by listing the tools you need to call and in what order.
Think step by step about what information you need and which tools will provide it.
Then execute the plan by calling tools one at a time.

After each tool result, evaluate whether you have enough information to answer,
or if you need additional tool calls. Synthesize all findings into a comprehensive answer."""

        result = await executor.execute(
            user_message=planning_prompt,
            extra_context="MODE: Research Investigation. Be thorough and systematic.",
        )

        plan.status = "complete"
        plan.findings.append(result.get("content", ""))

        return {
            "question": question,
            "answer": result.get("content", ""),
            "tools_used": result.get("tool_calls_made", []),
            "iterations": result.get("iterations", 0),
            "duration_ms": result.get("duration_ms", 0),
        }


# ─── Background Scanner ──────────────────────────────────────────────────────

@dataclass
class ScanResult:
    """Result from a background scan."""
    event_type: str
    description: str
    severity: str  # info, notice, alert
    timestamp: float = field(default_factory=time.time)
    data: Dict[str, Any] = field(default_factory=dict)


class BackgroundScanner:
    """
    Periodic background scanning for astrological events.
    
    Mirrors thia-libre's Gestalt Event Router + Anticipation Engine:
    - Scans for VoC Moon periods
    - Detects exact aspects forming today
    - Alerts on retrogrades starting/ending
    - Watches for eclipses and lunations
    """

    def __init__(self):
        self._scan_interval = 3600  # 1 hour
        self._running = False
        self._last_scan: Optional[float] = None
        self._alerts: List[ScanResult] = []
        self._watchers: List[Callable] = []

    def on_alert(self, callback: Callable[[ScanResult], None]):
        """Register callback for scan alerts."""
        self._watchers.append(callback)

    async def scan_now(self) -> List[ScanResult]:
        """Run an immediate scan for notable astrological events."""
        from thia_lite.llm.tool_executor import _tool_handlers

        results = []
        now = datetime.utcnow()

        # 1. Check Moon void-of-course
        if "is_moon_void_of_course" in _tool_handlers:
            try:
                voc = _tool_handlers["is_moon_void_of_course"](
                    "is_moon_void_of_course", {}
                )
                if isinstance(voc, dict) and voc.get("is_void"):
                    results.append(ScanResult(
                        event_type="voc_moon",
                        description=f"Moon is void of course until {voc.get('void_ends', '?')}",
                        severity="notice",
                        data=voc,
                    ))
            except Exception as e:
                logger.debug(f"VoC scan failed: {e}")

        # 2. Check current transits
        if "get_current_transits" in _tool_handlers:
            try:
                transits = _tool_handlers["get_current_transits"](
                    "get_current_transits", {}
                )
                if isinstance(transits, dict):
                    # Look for exact aspects (orb < 1°)
                    aspects = transits.get("aspects", [])
                    for asp in aspects:
                        orb = asp.get("orb", 99)
                        if isinstance(orb, (int, float)) and abs(orb) < 1.0:
                            results.append(ScanResult(
                                event_type="exact_aspect",
                                description=f"Exact {asp.get('aspect','?')}: {asp.get('planet1','?')} - {asp.get('planet2','?')} (orb: {orb:.2f}°)",
                                severity="alert",
                                data=asp,
                            ))
            except Exception as e:
                logger.debug(f"Transit scan failed: {e}")

        # 3. Check planetary hours
        if "get_planetary_hour" in _tool_handlers:
            try:
                hour = _tool_handlers["get_planetary_hour"](
                    "get_planetary_hour", {}
                )
                if isinstance(hour, dict):
                    results.append(ScanResult(
                        event_type="planetary_hour",
                        description=f"Current planetary hour: {hour.get('planet', '?')}",
                        severity="info",
                        data=hour,
                    ))
            except Exception as e:
                logger.debug(f"Hour scan failed: {e}")

        # Store results
        self._alerts.extend(results)
        self._last_scan = time.time()

        # Notify watchers
        for alert in results:
            for watcher in self._watchers:
                try:
                    watcher(alert)
                except Exception:
                    pass

        return results

    async def start(self):
        """Start periodic background scanning."""
        self._running = True
        logger.info("Background scanner started")
        while self._running:
            try:
                await self.scan_now()
            except Exception as e:
                logger.error(f"Background scan error: {e}")
            await asyncio.sleep(self._scan_interval)

    def stop(self):
        """Stop background scanning."""
        self._running = False

    def get_recent_alerts(self, count: int = 10) -> List[ScanResult]:
        """Get the most recent alerts."""
        return self._alerts[-count:]


# ─── Task Planner ─────────────────────────────────────────────────────────────

@dataclass
class SubTask:
    """A sub-task in a complex operation."""
    description: str
    tool: Optional[str] = None
    args: Optional[Dict[str, Any]] = None
    status: str = "pending"  # pending, running, complete, failed
    result: Any = None
    depends_on: List[int] = field(default_factory=list)


class TaskPlanner:
    """
    Breaks complex questions into sub-tasks with dependencies.
    
    Mirrors thia-libre's Agentic Coordinator task decomposition.
    """

    # Common astrological task patterns
    PATTERNS = {
        "natal_chart": {
            "triggers": ["natal chart", "birth chart", "my chart"],
            "tasks": [
                SubTask("Get or confirm birth data", tool="get_birth_data"),
                SubTask("Calculate natal chart", tool="calculate_natal_chart"),
                SubTask("Analyze dignities", tool="get_planet_dignities"),
                SubTask("Check current transits to natal", tool="get_current_transits"),
            ],
        },
        "compatibility": {
            "triggers": ["compatibility", "synastry", "relationship"],
            "tasks": [
                SubTask("Get first person's birth data"),
                SubTask("Get second person's birth data"),
                SubTask("Calculate both natal charts"),
                SubTask("Analyze inter-aspects"),
                SubTask("Search rules for relationship indicators", tool="astrology_rules_rag_search"),
            ],
        },
        "electional": {
            "triggers": ["best time", "auspicious", "when should", "electional"],
            "tasks": [
                SubTask("Clarify the activity type"),
                SubTask("Scan for electional windows", tool="find_electional_window"),
                SubTask("Check VoC Moon during windows", tool="is_moon_void_of_course"),
                SubTask("Search rules for electional principles", tool="astrology_rules_rag_search"),
            ],
        },
        "forecast": {
            "triggers": ["forecast", "prediction", "what's ahead", "upcoming"],
            "tasks": [
                SubTask("Get birth data", tool="get_birth_data"),
                SubTask("Calculate current transits", tool="get_current_transits"),
                SubTask("Check upcoming retrogrades"),
                SubTask("Analyze profections or solar return"),
                SubTask("Search rules for transit interpretations", tool="astrology_rules_rag_search"),
            ],
        },
    }

    def identify_pattern(self, query: str) -> Optional[str]:
        """Identify which task pattern matches the query."""
        query_lower = query.lower()
        for pattern_name, pattern in self.PATTERNS.items():
            if any(trigger in query_lower for trigger in pattern["triggers"]):
                return pattern_name
        return None

    def create_plan(self, query: str) -> Optional[List[SubTask]]:
        """Create a task plan for the given query."""
        pattern_name = self.identify_pattern(query)
        if pattern_name and pattern_name in self.PATTERNS:
            import copy
            return copy.deepcopy(self.PATTERNS[pattern_name]["tasks"])
        return None


# ─── Anticipation Engine ─────────────────────────────────────────────────────

class AnticipationEngine:
    """
    Proactive event anticipation.
    
    Monitors upcoming astrological events and generates alerts
    before they happen. Mirrors thia-libre's Anticipation Engine.
    """

    def __init__(self):
        self._forecasts: List[Dict[str, Any]] = []

    async def forecast_next_week(self, latitude: float = 0, longitude: float = 0) -> List[Dict[str, Any]]:
        """Generate a forecast of notable events for the next 7 days."""
        from thia_lite.llm.tool_executor import _tool_handlers

        events = []
        now = datetime.utcnow()

        # Check each day
        for day_offset in range(7):
            target = now + timedelta(days=day_offset)
            date_str = target.strftime("%Y-%m-%d")

            # Planetary hours for the day
            if "get_planetary_hour" in _tool_handlers:
                try:
                    hour = _tool_handlers["get_planetary_hour"](
                        "get_planetary_hour",
                        {"date": date_str, "latitude": latitude, "longitude": longitude}
                    )
                    if isinstance(hour, dict):
                        events.append({
                            "date": date_str,
                            "type": "planetary_day",
                            "description": f"Day ruler: {hour.get('day_ruler', '?')}",
                        })
                except Exception:
                    pass

        self._forecasts = events
        return events

    def get_forecasts(self) -> List[Dict[str, Any]]:
        """Get cached forecasts."""
        return self._forecasts


# ─── Register Autonomy Tools ────────────────────────────────────────────────

def register_autonomy_tools():
    """Register autonomy-related tools that the LLM can call."""
    from thia_lite.llm.tool_executor import register_tool

    _scanner = BackgroundScanner()
    _research = ResearchEngine()
    _planner = TaskPlanner()

    def autonomy_dispatch(tool_name: str, args: Dict[str, Any]) -> Any:
        if tool_name == "scan_current_sky":
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(asyncio.run, _scanner.scan_now())
                    results = future.result()
            else:
                results = asyncio.run(_scanner.scan_now())
            return {
                "alerts": [
                    {
                        "type": r.event_type,
                        "description": r.description,
                        "severity": r.severity,
                    }
                    for r in results
                ],
                "total": len(results),
            }

        elif tool_name == "get_recent_alerts":
            alerts = _scanner.get_recent_alerts(args.get("count", 10))
            return {
                "alerts": [
                    {"type": a.event_type, "description": a.description, "severity": a.severity}
                    for a in alerts
                ]
            }

        elif tool_name == "plan_investigation":
            plan = _planner.create_plan(args.get("query", ""))
            if plan:
                return {
                    "plan": [
                        {"step": i+1, "description": t.description, "tool": t.tool}
                        for i, t in enumerate(plan)
                    ]
                }
            return {"plan": None, "message": "No standard pattern found — will investigate freely"}

        elif tool_name == "search_web":
            try:
                from duckduckgo_search import DDGS
                with DDGS() as ddgs:
                    results = list(ddgs.text(args["query"], max_results=args.get("max_results", 5)))
                    return {"query": args["query"], "results": results}
            except ImportError:
                return {"error": "duckduckgo-search package not installed. Run: pip install duckduckgo-search"}
            except Exception as e:
                return {"error": f"Search failed: {e}"}

        elif tool_name == "get_polymarket_markets":
            import httpx
            params = {}
            for k in ["active", "closed", "order", "query", "limit", "startDate_min", "startDate_max", "endDate_min", "endDate_max", "ascending"]:
                if args.get(k) is not None:
                    if k in ["active", "closed"]:
                        params[k] = "true" if args.get(k) else "false"
                    else:
                        params[k] = str(args.get(k))
            
            if not params or (len(params) == 1 and "limit" in params):
                params.update({"active": "true", "closed": "false", "order": "volume24hr", "ascending": "false"})
            
            try:
                response = httpx.get("https://gamma-api.polymarket.com/markets", params=params, timeout=10.0)
                markets = response.json() if response.status_code == 200 else []
                limit = int(args.get("limit", 20) or 20)
                return {"markets": markets[:limit], "count": len(markets), "params_used": params, "source": "polymarket"}
            except Exception as e:
                return {"error": f"Polymarket API error: {e}"}

        elif tool_name == "get_prediction_odds":
            import httpx
            slug = str(args.get("slug", "")).lower()
            try:
                response = httpx.get("https://gamma-api.polymarket.com/markets", params={"active": "true", "closed": "false", "limit": 100}, timeout=10.0)
                markets = response.json() if response.status_code == 200 else []
                for m in markets:
                    if slug and slug in str(m.get("slug", "")).lower():
                        return {"market": m, "source": "polymarket"}
                return {"market": markets[0] if markets else None, "source": "polymarket"}
            except Exception as e:
                return {"error": f"Polymarket API error: {e}"}

        return {"error": f"Unknown autonomy tool: {tool_name}"}

    register_tool(
        "scan_current_sky",
        "Scan the current sky for notable astrological events: VoC Moon, exact aspects, planetary hours. Returns active alerts.",
        {"type": "object", "properties": {}},
        autonomy_dispatch,
    )

    register_tool(
        "get_recent_alerts",
        "Get recent astrological alerts from the background scanner.",
        {
            "type": "object",
            "properties": {
                "count": {"type": "integer", "description": "Number of recent alerts (default: 10)"},
            },
        },
        autonomy_dispatch,
    )

    register_tool(
        "plan_investigation",
        "Create a structured research plan for a complex astrological question. Returns a step-by-step plan with recommended tools.",
        {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The complex question to investigate"},
            },
            "required": ["query"],
        },
        autonomy_dispatch,
    )

    register_tool(
        "search_web",
        "Search the web using DuckDuckGo to find real-time news, information about people, or events to correlate with astrology.",
        {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "max_results": {"type": "integer", "description": "Max results to return (default: 5)"},
            },
            "required": ["query"],
        },
        autonomy_dispatch,
    )

    register_tool(
        "get_polymarket_markets",
        "Get Polymarket prediction markets with flexible filtering and sorting. Returns current active real-money markets on future events.",
        {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Maximum number of markets to return (default: 20)"},
                "query": {"type": "string", "description": "Search text for tracking a topic on polymarket"},
            },
        },
        autonomy_dispatch,
    )

    register_tool(
        "get_prediction_odds",
        "Get the current prediction odds and statistics for a specific Polymarket event by its identifier or slug.",
        {
            "type": "object",
            "properties": {
                "slug": {"type": "string", "description": "The URL slug or partial keyword for the polymarket market"},
            },
            "required": ["slug"],
        },
        autonomy_dispatch,
    )

    logger.info("Registered autonomy tools (scanner, planner, web search, polymarket)")

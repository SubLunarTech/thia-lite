#!/usr/bin/env python3
"""
THIA Libre — Recursive Language Model (RLM) Engine
====================================================
Implements the RLM paradigm from Zhang, Kraska & Khattab (2025):
"Recursive Language Models" (arXiv:2512.24601)

Architecture (Algorithm 1 from the paper):
  1. User prompt P stored as a variable in a sandboxed REPL
  2. LLM receives ONLY metadata about P (length, prefix, type hints)
  3. LLM writes Python code to examine/decompose/transform P
  4. Code can call sub_rlm(sub_prompt) to recursively invoke the LLM
  5. Results accumulate in REPL variables
  6. Loop terminates when the variable `Final` is set

Uses the same LLM provider as the MCP client (via llm_simple.complete()).
"""

from __future__ import annotations

import asyncio
import io
import logging
import os
import re
import time
from contextlib import redirect_stdout
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger("thia.rlm")

# Configuration
RLM_MAX_ITERATIONS = int(os.getenv("RLM_MAX_ITERATIONS", "15"))
RLM_MAX_RECURSION_DEPTH = int(os.getenv("RLM_MAX_RECURSION_DEPTH", "5"))
RLM_MAX_OUTPUT_CHARS = int(os.getenv("RLM_MAX_OUTPUT_CHARS", "50000"))


# ═══════════════════════════════════════════════════════════════════════════════
# REPL SANDBOX
# ═══════════════════════════════════════════════════════════════════════════════

# Restricted builtins — no file I/O, no imports, no os access
_SAFE_BUILTINS = {
    "abs": abs, "all": all, "any": any, "bool": bool, "chr": chr,
    "dict": dict, "enumerate": enumerate, "filter": filter, "float": float,
    "format": format, "frozenset": frozenset, "hasattr": hasattr,
    "hash": hash, "int": int, "isinstance": isinstance, "issubclass": issubclass,
    "iter": iter, "len": len, "list": list, "map": map, "max": max,
    "min": min, "next": next, "ord": ord, "pow": pow, "print": print,
    "range": range, "repr": repr, "reversed": reversed, "round": round,
    "set": set, "slice": slice, "sorted": sorted, "str": str, "sum": sum,
    "tuple": tuple, "type": type, "zip": zip,
    "True": True, "False": False, "None": None,
}


def _summarize_value(v: Any, max_len: int = 120) -> str:
    """Summarize a variable value for metadata display."""
    s = repr(v)
    if len(s) > max_len:
        length_info = f"len={len(v)}" if hasattr(v, "__len__") else "?"
        return f"{type(v).__name__}({length_info}) = {s[:max_len]}..."
    return s


class RLMSandbox:
    """Sandboxed REPL environment for RLM code execution.

    The user prompt is stored as `PROMPT` in the namespace.
    The LLM sets `Final` to signal completion.
    `sub_rlm(prompt)` enables recursive self-invocation.
    """

    def __init__(self, prompt: str, llm_fn, depth: int = 0, max_depth: int = 5):
        self.prompt = prompt
        self.depth = depth
        self.max_depth = max_depth
        self._llm_fn = llm_fn  # async function for LLM completion

        self._namespace: Dict[str, Any] = {
            "__builtins__": _SAFE_BUILTINS,
            "PROMPT": prompt,
            "PROMPT_LENGTH": len(prompt),
            "PROMPT_LINES": prompt.count("\n") + 1,
            "Final": None,
            "sub_rlm": self._sub_rlm_sync,
            "notes": {},
        }
        self._sub_rlm_results: List[Dict] = []
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def set_loop(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop

    def _sub_rlm_sync(self, sub_prompt: str, max_iter: int = 10) -> str:
        """Synchronous sub_rlm wrapper (called from exec'd code)."""
        if self.depth >= self.max_depth:
            return f"[RLM] Max recursion depth ({self.max_depth}) reached."

        if self._loop and self._loop.is_running():
            future = asyncio.run_coroutine_threadsafe(
                rlm_complete(
                    sub_prompt, self._llm_fn,
                    depth=self.depth + 1,
                    max_depth=self.max_depth,
                    max_iterations=max_iter,
                ),
                self._loop
            )
            result = future.result(timeout=60)
        else:
            result = asyncio.run(
                rlm_complete(
                    sub_prompt, self._llm_fn,
                    depth=self.depth + 1,
                    max_depth=self.max_depth,
                    max_iterations=max_iter,
                )
            )
        self._sub_rlm_results.append(result)
        return result.get("response", "")

    def execute(self, code: str) -> str:
        """Execute code in the sandbox, return captured stdout."""
        buf = io.StringIO()
        try:
            with redirect_stdout(buf):
                exec(code, self._namespace)
        except Exception as e:
            buf.write(f"\n[EXEC ERROR] {type(e).__name__}: {e}")
        output = buf.getvalue()
        if len(output) > RLM_MAX_OUTPUT_CHARS:
            output = output[:RLM_MAX_OUTPUT_CHARS] + f"\n... [truncated, {len(output)} total chars]"
        return output

    @property
    def final(self) -> Optional[str]:
        val = self._namespace.get("Final")
        return str(val) if val is not None else None

    def get_metadata(self) -> str:
        """Produce REPL state metadata for the LLM (NOT the full prompt)."""
        prefix = self.prompt[:200]
        suffix = self.prompt[-100:] if len(self.prompt) > 200 else ""
        user_vars = {
            k: _summarize_value(v)
            for k, v in self._namespace.items()
            if k not in ("__builtins__", "sub_rlm", "PROMPT") and not k.startswith("_")
        }
        meta = (
            f"REPL State:\n"
            f"- PROMPT_LENGTH: {len(self.prompt)} chars, {self.prompt.count(chr(10)) + 1} lines\n"
            f"- PROMPT prefix (first 200 chars): {repr(prefix)}"
        )
        if suffix:
            meta += f"\n- PROMPT suffix (last 100 chars): {repr(suffix)}"
        meta += f"\n- Variables: {user_vars}"
        meta += f"\n- Recursion depth: {self.depth}/{self.max_depth}"
        return meta


# ═══════════════════════════════════════════════════════════════════════════════
# SYSTEM PROMPT
# ═══════════════════════════════════════════════════════════════════════════════

RLM_SYSTEM_PROMPT = """You are an RLM (Recursive Language Model). You process inputs by writing Python code in a REPL environment.

ENVIRONMENT:
- `PROMPT` — the user's input (may be very long; do NOT try to read all at once)
- `PROMPT_LENGTH`, `PROMPT_LINES` — size metadata
- `notes` — dict for storing intermediate results
- `sub_rlm(sub_prompt)` — recursively call yourself on a sub-prompt, returns response string
- Set `Final = "your answer"` when done

RULES:
1. Respond ONLY with Python code inside ```python ... ``` blocks
2. Examine PROMPT via slicing: PROMPT[:500], PROMPT[start:end]
3. Use sub_rlm() to process sub-sections that need LLM understanding
4. Build answers incrementally in variables, then set Final
5. Use print() for observations (you'll see stdout summary next turn)
6. For long inputs, split into chunks and process with sub_rlm()

EXAMPLE:
```python
# Examine structure
print(f"Length: {PROMPT_LENGTH}, Lines: {PROMPT_LINES}")
print(PROMPT[:500])
```

Then:
```python
chunks = [PROMPT[i:i+2000] for i in range(0, PROMPT_LENGTH, 2000)]
notes["summaries"] = [sub_rlm(f"Summarize:\\n{c}") for c in chunks[:5]]
Final = " | ".join(notes["summaries"])
```"""


# ═══════════════════════════════════════════════════════════════════════════════
# RLM CORE LOOP — Algorithm 1 from Zhang et al. (2025)
# ═══════════════════════════════════════════════════════════════════════════════

def _extract_code(text: str) -> Optional[str]:
    """Extract Python code from markdown-fenced LLM output."""
    matches = re.findall(r"```python\s*\n(.*?)```", text, re.DOTALL)
    if matches:
        return "\n".join(matches)
    matches = re.findall(r"```\s*\n(.*?)```", text, re.DOTALL)
    if matches:
        return "\n".join(matches)
    return None


async def rlm_complete(
    prompt: str,
    llm_fn,
    depth: int = 0,
    max_depth: int = RLM_MAX_RECURSION_DEPTH,
    max_iterations: int = RLM_MAX_ITERATIONS,
) -> Dict[str, Any]:
    """Execute the RLM loop (Algorithm 1 from Zhang et al. 2025).

    Args:
        prompt: The user prompt to process
        llm_fn: Async callable(prompt, system_prompt) -> str
        depth: Current recursion depth
        max_depth: Maximum recursion depth
        max_iterations: Maximum REPL iterations
    """
    sandbox = RLMSandbox(prompt, llm_fn, depth=depth, max_depth=max_depth)
    try:
        sandbox.set_loop(asyncio.get_running_loop())
    except RuntimeError:
        pass

    trajectory: List[Dict[str, Any]] = []
    start_time = time.time()

    for iteration in range(max_iterations):
        meta = sandbox.get_metadata()

        if iteration == 0:
            llm_prompt = (
                f"Process this user request using the RLM paradigm.\n"
                f"The input is stored in PROMPT. You see only metadata:\n\n"
                f"{meta}\n\n"
                f"Write Python code to begin examining and processing PROMPT."
            )
        else:
            prev = trajectory[-1].get("stdout", "")
            preview = prev[:500]
            llm_prompt = (
                f"Continue. Current REPL state:\n\n{meta}\n\n"
                f"Previous output ({len(prev)} chars):\n{preview}\n\n"
                f"Write next code block. Set Final when done."
            )

        llm_response = await llm_fn(llm_prompt, RLM_SYSTEM_PROMPT)
        code = _extract_code(llm_response)

        if not code:
            # LLM didn't produce code — treat response as direct answer
            if iteration > 0 or "Final" in llm_response:
                sandbox.execute(f'Final = """{llm_response[:5000]}"""')
            trajectory.append({
                "iteration": iteration, "code": None, "stdout": "",
                "note": "No code block in LLM response",
            })
            if sandbox.final:
                break
            continue

        stdout = sandbox.execute(code)
        trajectory.append({
            "iteration": iteration,
            "code": code[:2000],
            "stdout": stdout[:2000],
            "final_set": sandbox.final is not None,
        })

        logger.info(
            f"RLM iter={iteration} depth={depth} "
            f"stdout_len={len(stdout)} final={'YES' if sandbox.final else 'no'}"
        )

        if sandbox.final is not None:
            break

    return {
        "response": sandbox.final or "(RLM did not produce a final answer)",
        "iterations": len(trajectory),
        "recursion_depth": depth,
        "max_depth": max_depth,
        "elapsed_seconds": round(time.time() - start_time, 2),
        "sub_rlm_calls": len(sandbox._sub_rlm_results),
        "trajectory": trajectory,
        "method": "rlm_repl",
        "paper": "Zhang, Kraska & Khattab (2025) arXiv:2512.24601",
    }


@dataclass
class RLMResult:
    """Result container matching other intelligence engine patterns."""
    response: str = ""
    iterations: int = 0
    recursion_depth: int = 0
    sub_rlm_calls: int = 0
    elapsed_seconds: float = 0.0
    trajectory: List[Dict] = field(default_factory=list)


class RecursiveLanguageModel:
    """RLM intelligence engine for the consensus daemon.

    Integrates with the existing llm_simple.complete() backend,
    which uses the same provider as the MCP client.
    """

    def __init__(self):
        self._call_count = 0

    async def _llm_fn(self, prompt: str, system_prompt: str) -> str:
        """Call the universal LLMClient."""
        try:
            from thia_lite.llm.client import get_llm_client
            client = get_llm_client()
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ]
            result = await client.chat(messages=messages, temperature=0.0)
            return result.get("content", "")
        except Exception as e:
            logger.error(f"RLM LLM call failed: {e}")
            return f"[LLM ERROR] {e}"

    async def process(self, prompt: str, max_iterations: int = None,
                      max_depth: int = None) -> RLMResult:
        """Run the RLM REPL loop on the given prompt."""
        self._call_count += 1
        result = await rlm_complete(
            prompt=prompt,
            llm_fn=self._llm_fn,
            max_iterations=max_iterations or RLM_MAX_ITERATIONS,
            max_depth=max_depth or RLM_MAX_RECURSION_DEPTH,
        )
        return RLMResult(
            response=result["response"],
            iterations=result["iterations"],
            recursion_depth=result["recursion_depth"],
            sub_rlm_calls=result["sub_rlm_calls"],
            elapsed_seconds=result["elapsed_seconds"],
            trajectory=result["trajectory"],
        )

"""agent.py - Deductive Logic Agent (yêu cầu 4.4).

Tác tử suy diễn logic hoạt động hoàn toàn trên trạng thái công khai
(PublicState) từ GameEngine, sử dụng encoder.py và solver.py.

Nguyên tắc cốt lõi:
  * Không bao giờ đoán (chỉ chọn verdict bị ép logic: KB_t |= C_i hoặc KB_t |= -C_i).
  * Không đọc nhãn ẩn hay clue chưa lật (chỉ check_uniqueness nhận full_clues).
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from encoder import ClueError, all_cells, build_kb, referenced_cells, var
from solver import solve

if TYPE_CHECKING:
    from engine import GameEngine, PublicState

VALID_VERDICTS = ("CRIMINAL", "INNOCENT")


def _clue_id(clue: dict, idx: int | None = None) -> str:
    cid = clue.get("id")
    if cid is not None:
        return str(cid)
    return f"clue_{idx}" if idx is not None else "clue"


def _new_stats() -> dict[str, Any]:
    return {
        "sat_calls": 0,
        "decisions": 0,
        "propagations": 0,
        "backtracks": 0,
        "runtime_ms": 0.0,
    }


def _add_stats(acc: dict[str, Any], solver_stats: dict[str, Any]) -> None:
    acc["sat_calls"] += 1
    acc["decisions"] += solver_stats["decisions"]
    acc["propagations"] += solver_stats["propagations"]
    acc["backtracks"] += solver_stats["backtracks"]
    acc["runtime_ms"] += solver_stats["runtime_ms"]


def _probe_cell(
    clauses: list[list[int]],
    num_vars: int,
    cell: str,
    n: int,
    stats_acc: dict[str, Any] | None = None,
    totals_acc: dict[str, Any] | None = None,
    queries_out: list[dict[str, str]] | None = None,
) -> str:
    x = var(cell, n)
    for assumption, query_label, forced_status in (
        (-x, f"KB ∧ ¬C{x}", "CRIMINAL"),
        (x, f"KB ∧ C{x}", "INNOCENT"),
    ):
        res = solve(clauses, num_vars, [assumption])
        if stats_acc is not None:
            _add_stats(stats_acc, res["stats"])
        if totals_acc is not None:
            _add_stats(totals_acc, res["stats"])
        if queries_out is not None:
            queries_out.append({"cell": cell, "query": query_label, "result": res["status"]})
        if res["status"] == "UNSAT":
            return forced_status
    return "UNKNOWN"


def classify_cell(state: PublicState, cell: str) -> str:
    n = state.size
    num_vars = n ** 2
    var(cell, n)
    clauses, _ = build_kb(state.revealed_clues, state.known, n)
    if solve(clauses, num_vars)["status"] == "UNSAT":
        return "INCONSISTENT"
    return _probe_cell(clauses, num_vars, cell, n)


def classify(state: PublicState) -> dict[str, str]:
    n = state.size
    num_vars = n ** 2
    unknown_cells = [c for c in all_cells(n) if c not in state.known]
    if not unknown_cells:
        return {}

    clauses, _ = build_kb(state.revealed_clues, state.known, n)
    if solve(clauses, num_vars)["status"] == "UNSAT":
        return {c: "INCONSISTENT" for c in unknown_cells}
    return {c: _probe_cell(clauses, num_vars, c, n) for c in unknown_cells}


def check_verdict(state: PublicState, cell: str, verdict: str) -> str:
    if verdict not in VALID_VERDICTS:
        return "INVALID"
    try:
        var(cell, state.size)
    except ClueError:
        return "INVALID"

    if cell in state.known:
        return "ALREADY_KNOWN"

    entailed = classify_cell(state, cell)
    if entailed == "INCONSISTENT":
        return "INVALID"
    if entailed == "UNKNOWN":
        return "NOT_PROVABLE"
    if entailed == verdict:
        return "ACCEPTED"
    return "CONTRADICTED"


def _relevant_clue_ids(state: PublicState, cell: str, verdict: str) -> list[str]:
    n = state.size
    num_vars = n ** 2
    x = var(cell, n)
    negated = [-x] if verdict == "CRIMINAL" else [x]

    necessary: list[str] = []
    for idx, clue in enumerate(state.revealed_clues):
        reduced = state.revealed_clues[:idx] + state.revealed_clues[idx + 1:]
        clauses, _ = build_kb(reduced, state.known, n)
        if solve(clauses, num_vars, negated)["status"] == "SAT":
            necessary.append(_clue_id(clue, idx))
    if necessary:
        return necessary

    return [
        _clue_id(clue, idx)
        for idx, clue in enumerate(state.revealed_clues)
        if cell in referenced_cells(clue, n)
    ]


def hint(state: PublicState) -> dict[str, Any] | None:
    n = state.size
    num_vars = n ** 2
    clauses, _ = build_kb(state.revealed_clues, state.known, n)
    if solve(clauses, num_vars)["status"] == "UNSAT":
        return None

    for cell in all_cells(n):
        if cell in state.known:
            continue
        entailed = _probe_cell(clauses, num_vars, cell, n)
        if entailed in VALID_VERDICTS:
            return {
                "cell": cell,
                "verdict": entailed,
                "clue_ids": _relevant_clue_ids(state, cell, entailed),
            }
    return None


def _finish_auto_solve(
    status: str,
    trace: list[dict[str, Any]],
    totals: dict[str, Any],
    kb_stats: dict[str, int],
    start_time: float,
) -> dict[str, Any]:
    totals["steps"] = len(trace)
    totals["primary_vars"] = kb_stats["primary_vars"]
    totals["aux_vars"] = kb_stats["aux_vars"]
    totals["clauses"] = kb_stats["clauses"]
    totals["runtime_ms"] = (time.perf_counter() - start_time) * 1000.0
    return {"status": status, "trace": trace, "totals": totals}


def auto_solve(engine: GameEngine) -> dict[str, Any]:
    """Tự động giải toàn bộ puzzle qua vòng lặp suy diễn không đoán."""
    start_time = time.perf_counter()
    trace: list[dict[str, Any]] = []
    totals = _new_stats()
    step = 0

    while True:
        state = engine.public_state()
        n = state.size
        num_vars = n ** 2
        clauses, kb_stats = build_kb(state.revealed_clues, state.known, n)

        base = solve(clauses, num_vars)
        _add_stats(totals, base["stats"])
        if base["status"] == "UNSAT":
            return _finish_auto_solve("INCONSISTENT", trace, totals, kb_stats, start_time)

        if state.solved or len(state.known) == num_vars:
            return _finish_auto_solve("SOLVED", trace, totals, kb_stats, start_time)

        step_stats = _new_stats()
        _add_stats(step_stats, base["stats"])
        queries: list[dict[str, str]] = []
        found: tuple[str, str] | None = None

        for cell in all_cells(n):
            if cell in state.known:
                continue
            entailed = _probe_cell(
                clauses,
                num_vars,
                cell,
                n,
                stats_acc=step_stats,
                totals_acc=totals,
                queries_out=queries,
            )
            if entailed in VALID_VERDICTS:
                found = (cell, entailed)
                break

        if found is None:
            return _finish_auto_solve("STUCK", trace, totals, kb_stats, start_time)

        cell, verdict = found
        prev_known_len = len(state.known)
        active_clues = [_clue_id(c, idx) for idx, c in enumerate(state.revealed_clues)]
        reply = engine.submit_verdict(cell, verdict)
        if reply.get("status") != "ACCEPTED":
            terminal = "INCONSISTENT" if reply.get("status") == "INVALID" else "STUCK"
            return _finish_auto_solve(terminal, trace, totals, kb_stats, start_time)

        step += 1
        revealed = reply.get("revealed_clue")
        revealed_id = _clue_id(revealed) if revealed is not None else None
        trace.append({
            "step": step,
            "active_clues": active_clues,
            "kb_clauses": kb_stats["clauses"],
            "queries": queries,
            "verdict": {"cell": cell, "status": verdict},
            "revealed_clue": revealed_id,
            "solver_stats": step_stats,
        })

        next_state = engine.public_state()
        if len(next_state.known) <= prev_known_len and not next_state.solved:
            return _finish_auto_solve("STUCK", trace, totals, kb_stats, start_time)


def analyze_uniqueness(clues: list[dict], n: int) -> dict[str, Any]:
    clauses, kb_stats = build_kb(clues, {}, n)
    num_vars = n ** 2

    first = solve(clauses, num_vars)
    if first["status"] == "UNSAT":
        return {
            "unique": False,
            "status": "UNSAT",
            "models": [],
            "kb_stats": kb_stats,
            "solver_stats": [first["stats"]],
        }

    m1 = first["assignment"]
    blocking_clause = [-v if m1[v] else v for v in range(1, num_vars + 1)]
    second = solve(clauses + [blocking_clause], num_vars)

    if second["status"] == "UNSAT":
        return {
            "unique": True,
            "status": "UNIQUE",
            "models": [m1],
            "kb_stats": kb_stats,
            "solver_stats": [first["stats"], second["stats"]],
        }

    return {
        "unique": False,
        "status": "MULTIPLE",
        "models": [m1, second["assignment"]],
        "kb_stats": kb_stats,
        "solver_stats": [first["stats"], second["stats"]],
    }


def check_uniqueness(clues: list[dict], n: int) -> bool:
    return analyze_uniqueness(clues, n)["unique"]

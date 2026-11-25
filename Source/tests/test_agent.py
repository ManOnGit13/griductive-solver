"""Kiểm thử đơn vị cho agent.py (4.4 Deductive Logic Agent & checker).

Chạy trong thư mục Source/:
    python -m unittest discover -s tests -v
"""

from dataclasses import dataclass
import copy
import json
import os
import sys
import unittest

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SRC)

import agent  # noqa: E402
from encoder import (ClueError, all_cells, as_bool, build_kb, check_clue,  # noqa: E402
                     evaluate, var)
from solver import solve  # noqa: E402


@dataclass
class MockPublicState:
    size: int
    characters: list
    known: dict
    revealed_clues: list
    clues_by_cell: dict
    solved: bool


class MockGameEngine:
    """Engine giả lập theo hợp đồng mục 6 của INTERFACES.md để kiểm thử Agent."""

    def __init__(self, puzzle: dict, alias_state: bool = False):
        self._puzzle = copy.deepcopy(puzzle)
        self.size = self._puzzle["size"]
        self._alias_state = alias_state
        self._chars_by_cell = {c["cell"]: c for c in self._puzzle["characters"]}
        for ch in self._puzzle["characters"]:
            check_clue(ch["clue"], self.size)
        self.restart()

    def restart(self) -> None:
        self._known = {}
        self._revealed_clues = []
        self._clues_by_cell = {}
        for cell in self._puzzle.get("initially_revealed", []):
            ch = self._chars_by_cell[cell]
            self._known[cell] = as_bool(ch["status"])
            self._revealed_clues.append(ch["clue"])
            self._clues_by_cell[cell] = ch["clue"]

    def public_state(self) -> MockPublicState:
        public_chars = [
            {"cell": c["cell"], "name": c["name"], "profession": c["profession"]}
            for c in self._puzzle["characters"]
        ]
        solved = len(self._known) == self.size ** 2
        if self._alias_state:
            return MockPublicState(
                size=self.size,
                characters=public_chars,
                known=self._known,
                revealed_clues=self._revealed_clues,
                clues_by_cell=self._clues_by_cell,
                solved=solved,
            )
        return MockPublicState(
            size=self.size,
            characters=public_chars,
            known=dict(self._known),
            revealed_clues=copy.deepcopy(self._revealed_clues),
            clues_by_cell=copy.deepcopy(self._clues_by_cell),
            solved=solved,
        )

    def submit_verdict(self, cell: str, verdict: str) -> dict:
        if verdict not in ("CRIMINAL", "INNOCENT") or cell not in self._chars_by_cell:
            return {"status": "INVALID", "cell": cell, "revealed_clue": None, "message": "Invalid input"}
        if cell in self._known:
            return {"status": "ALREADY_KNOWN", "cell": cell, "revealed_clue": None, "message": "Already known"}

        c = agent.classify_cell(self.public_state(), cell)
        if c == "INCONSISTENT":
            return {"status": "INVALID", "cell": cell, "revealed_clue": None, "message": "Inconsistent puzzle"}
        if c == "UNKNOWN":
            return {"status": "NOT_PROVABLE", "cell": cell, "revealed_clue": None, "message": "Not provable"}
        if c != verdict:
            return {"status": "CONTRADICTED", "cell": cell, "revealed_clue": None, "message": "Contradicted"}

        ch = self._chars_by_cell[cell]
        self._known[cell] = (verdict == "CRIMINAL")
        self._revealed_clues.append(ch["clue"])
        self._clues_by_cell[cell] = ch["clue"]
        return {
            "status": "ACCEPTED",
            "cell": cell,
            "revealed_clue": copy.deepcopy(ch["clue"]),
            "message": "Accepted",
        }

    def full_clues(self) -> list:
        return [copy.deepcopy(c["clue"]) for c in self._puzzle["characters"]]

    def ground_truth(self) -> dict:
        return {c: as_bool(ch["status"]) for c, ch in self._chars_by_cell.items()}


class StrictNoLeakProxy:
    """Proxy chỉ cho phép Agent gọi public_state() và submit_verdict()."""

    def __init__(self, inner: MockGameEngine):
        self._inner = inner

    def public_state(self) -> MockPublicState:
        return self._inner.public_state()

    def submit_verdict(self, cell: str, verdict: str) -> dict:
        return self._inner.submit_verdict(cell, verdict)

    def __getattr__(self, name: str):
        raise AssertionError(f"Agent must not access hidden engine member: {name}")


def make_state(size=3, known=None, revealed_clues=None, solved=False):
    known = {} if known is None else known
    revealed_clues = [] if revealed_clues is None else revealed_clues
    chars = [{"cell": c, "name": c, "profession": "Role"} for c in all_cells(size)]
    return MockPublicState(
        size=size,
        characters=chars,
        known=known,
        revealed_clues=revealed_clues,
        clues_by_cell={},
        solved=solved,
    )


def make_puzzle(size, specs, initially_revealed):
    """Tạo puzzle JSON từ dict {cell: (status, clue_body)}."""
    chars = []
    for cell in all_cells(size):
        status, clue_body = specs[cell]
        clue = dict(clue_body)
        clue.setdefault("id", f"clue_{cell}")
        chars.append({
            "cell": cell,
            "name": f"Name_{cell}",
            "profession": "Tester",
            "status": status,
            "clue": clue,
        })
    return {
        "id": "synthetic-test",
        "size": size,
        "initially_revealed": list(initially_revealed),
        "characters": chars,
    }


class AgentClassificationTests(unittest.TestCase):
    def test_classify_cell_all_four_outcomes(self):
        state = make_state(
            size=3,
            known={"B2": False},
            revealed_clues=[
                {"id": "c1", "type": "FACT", "cell": "A1", "status": "CRIMINAL"},
                {"id": "c2", "type": "SAME", "a": "B1", "b": "C1"},
            ],
        )
        self.assertEqual(agent.classify_cell(state, "A1"), "CRIMINAL")
        self.assertEqual(agent.classify_cell(state, "B2"), "INNOCENT")
        self.assertEqual(agent.classify_cell(state, "B1"), "UNKNOWN")
        self.assertEqual(agent.classify_cell(state, "C1"), "UNKNOWN")

        bad_state = make_state(
            size=3,
            known={"B2": False},
            revealed_clues=[
                {"id": "c1", "type": "FACT", "cell": "B2", "status": "CRIMINAL"},
            ],
        )
        self.assertEqual(agent.classify_cell(bad_state, "A1"), "INCONSISTENT")
        self.assertEqual(agent.classify_cell(bad_state, "B2"), "INCONSISTENT")

    def test_classify_cell_supports_string_known_and_validates_cell(self):
        state = make_state(
            size=3,
            known={"A1": "CRIMINAL"},
            revealed_clues=[{"id": "c1", "type": "DIFFERENT", "a": "A1", "b": "B1"}],
        )
        self.assertEqual(agent.classify_cell(state, "B1"), "INNOCENT")
        with self.assertRaises(ClueError):
            agent.classify_cell(state, "Z9")

    def test_classify_returns_all_unknown_cells_in_row_major_order(self):
        state = make_state(
            size=3,
            known={"B2": False},
            revealed_clues=[
                {"id": "c_b2", "type": "EXACTLY", "k": 0, "region": {"kind": "explicit", "cells": ["A1", "C1", "C2"]}},
                {"id": "c_ext", "type": "FACT", "cell": "A3", "status": "CRIMINAL"},
            ],
        )
        res = agent.classify(state)
        expected_order = [c for c in all_cells(3) if c != "B2"]
        self.assertEqual(list(res.keys()), expected_order)
        for cell in expected_order:
            self.assertEqual(res[cell], agent.classify_cell(state, cell))
        self.assertEqual(res["A1"], "INNOCENT")
        self.assertEqual(res["C1"], "INNOCENT")
        self.assertEqual(res["C2"], "INNOCENT")
        self.assertEqual(res["A3"], "CRIMINAL")
        self.assertEqual(res["B1"], "UNKNOWN")

        full_known = make_state(size=2, known={c: False for c in all_cells(2)})
        self.assertEqual(agent.classify(full_known), {})

        inconsistent = make_state(
            size=2,
            known={"A1": True},
            revealed_clues=[{"id": "c", "type": "NO", "region": {"kind": "row", "row": 1}}],
        )
        self.assertEqual(agent.classify(inconsistent), {"B1": "INCONSISTENT", "A2": "INCONSISTENT", "B2": "INCONSISTENT"})

    def test_check_verdict_all_statuses(self):
        state = make_state(
            size=3,
            known={"B2": False},
            revealed_clues=[{"id": "c1", "type": "FACT", "cell": "A1", "status": "CRIMINAL"}],
        )
        self.assertEqual(agent.check_verdict(state, "A1", "CRIMINAL"), "ACCEPTED")
        self.assertEqual(agent.check_verdict(state, "A1", "INNOCENT"), "CONTRADICTED")
        self.assertEqual(agent.check_verdict(state, "C3", "CRIMINAL"), "NOT_PROVABLE")
        self.assertEqual(agent.check_verdict(state, "B2", "INNOCENT"), "ALREADY_KNOWN")
        self.assertEqual(agent.check_verdict(state, "Z9", "CRIMINAL"), "INVALID")
        self.assertEqual(agent.check_verdict(state, "A1", "MAYBE"), "INVALID")

        bad_state = make_state(
            size=2,
            known={"A1": True},
            revealed_clues=[{"id": "c1", "type": "FACT", "cell": "A1", "status": "INNOCENT"}],
        )
        self.assertEqual(agent.check_verdict(bad_state, "B1", "CRIMINAL"), "INVALID")


class AgentHintTests(unittest.TestCase):
    def test_hint_row_major_and_relevant_clues(self):
        state = make_state(
            size=3,
            known={"B2": False},
            revealed_clues=[
                {"id": "clue_B2", "type": "NO", "region": {"kind": "explicit", "cells": ["A1", "C1", "C2"]}},
            ],
        )
        h = agent.hint(state)
        self.assertEqual(h, {"cell": "A1", "verdict": "INNOCENT", "clue_ids": ["clue_B2"]})

    def test_hint_multi_clue_chain_excludes_unrelated_clues(self):
        state = make_state(
            size=3,
            known={"A1": False},
            revealed_clues=[
                {"id": "clue_A1", "type": "EXACTLY", "k": 1, "region": {"kind": "row", "row": 1}},
                {"id": "clue_C2", "type": "FACT", "cell": "C1", "status": "INNOCENT"},
                {"id": "clue_C3", "type": "SAME", "a": "A3", "b": "B3"},
            ],
        )
        h = agent.hint(state)
        self.assertIsNotNone(h)
        self.assertEqual(h["cell"], "B1")
        self.assertEqual(h["verdict"], "CRIMINAL")
        self.assertEqual(set(h["clue_ids"]), {"clue_A1", "clue_C2"})

    def test_hint_redundant_clues_and_terminal_cases(self):
        redundant = make_state(
            size=3,
            known={"B2": True},
            revealed_clues=[
                {"id": "c_direct", "type": "FACT", "cell": "A1", "status": "CRIMINAL"},
                {"id": "c_same", "type": "SAME", "a": "A1", "b": "B2"},
            ],
        )
        h = agent.hint(redundant)
        self.assertIsNotNone(h)
        self.assertEqual(h["cell"], "A1")
        self.assertEqual(h["verdict"], "CRIMINAL")
        self.assertTrue(h["clue_ids"])
        self.assertTrue(set(h["clue_ids"]).issubset({"c_direct", "c_same"}))

        ambiguous = make_state(size=2, known={}, revealed_clues=[{"id": "c1", "type": "SAME", "a": "A1", "b": "B1"}])
        self.assertIsNone(agent.hint(ambiguous))

        done = make_state(size=2, known={c: False for c in all_cells(2)}, revealed_clues=[], solved=True)
        self.assertIsNone(agent.hint(done))

        inconsistent = make_state(
            size=2,
            known={"A1": True},
            revealed_clues=[{"id": "c_bad", "type": "FACT", "cell": "A1", "status": "INNOCENT"}],
        )
        self.assertIsNone(agent.hint(inconsistent))


class AgentAutoSolveAndUniquenessTests(unittest.TestCase):
    def test_auto_solve_and_uniqueness_on_all_puzzles(self):
        puzzles_dir = os.path.join(SRC, "puzzles")
        files = sorted(f for f in os.listdir(puzzles_dir) if f.endswith(".json"))
        self.assertGreaterEqual(len(files), 6)

        for fname in files:
            with open(os.path.join(puzzles_dir, fname), encoding="utf-8") as f:
                puzzle = json.load(f)

            n = puzzle["size"]
            chars = {c["cell"]: c for c in puzzle["characters"]}
            engine = MockGameEngine(puzzle)
            proxy = StrictNoLeakProxy(engine)

            full_clues = engine.full_clues()
            self.assertTrue(agent.check_uniqueness(full_clues, n), fname)
            uniq_info = agent.analyze_uniqueness(full_clues, n)
            self.assertEqual(uniq_info["status"], "UNIQUE", fname)
            self.assertEqual(len(uniq_info["models"]), 1, fname)

            result = agent.auto_solve(proxy)
            self.assertEqual(result["status"], "SOLVED", fname)
            final_state = engine.public_state()
            self.assertTrue(final_state.solved, fname)
            self.assertEqual(final_state.known, engine.ground_truth(), fname)

            trace = result["trace"]
            expected_steps = n * n - len(puzzle["initially_revealed"])
            self.assertEqual(len(trace), expected_steps, fname)

            sim_known = {c: as_bool(chars[c]["status"]) for c in puzzle["initially_revealed"]}
            sim_clues = [chars[c]["clue"] for c in puzzle["initially_revealed"]]
            for idx, entry in enumerate(trace, start=1):
                self.assertEqual(entry["step"], idx, fname)
                self.assertEqual(entry["active_clues"], [c["id"] for c in sim_clues], fname)
                kb_before, kb_stats = build_kb(sim_clues, sim_known, n)
                self.assertEqual(entry["kb_clauses"], kb_stats["clauses"], fname)
                self.assertTrue(entry["queries"], fname)

                vcell = entry["verdict"]["cell"]
                vstatus = entry["verdict"]["status"]
                self.assertEqual(vstatus == "CRIMINAL", engine.ground_truth()[vcell], fname)
                x = var(vcell, n)
                self.assertEqual(solve(kb_before, n * n)["status"], "SAT", fname)
                refuted = [-x] if vstatus == "CRIMINAL" else [x]
                self.assertEqual(solve(kb_before, n * n, refuted)["status"], "UNSAT", fname)
                self.assertEqual(entry["revealed_clue"], f"clue_{vcell}", fname)
                self.assertEqual(
                    set(entry["solver_stats"].keys()),
                    {"sat_calls", "decisions", "propagations", "backtracks", "runtime_ms"},
                    fname,
                )

                sim_known[vcell] = (vstatus == "CRIMINAL")
                sim_clues.append(chars[vcell]["clue"])

            totals = result["totals"]
            self.assertEqual(totals["steps"], expected_steps, fname)
            self.assertEqual(totals["primary_vars"], n * n, fname)
            self.assertEqual(totals["aux_vars"], 0, fname)
            self.assertGreater(totals["clauses"], 0, fname)
            self.assertGreaterEqual(totals["sat_calls"], sum(s["solver_stats"]["sat_calls"] for s in trace), fname)
            self.assertGreaterEqual(totals["runtime_ms"], 0.0, fname)

    def test_auto_solve_with_aliased_public_state_preserves_trace_active_clues(self):
        with open(os.path.join(SRC, "puzzles", "sample_3x3.json"), encoding="utf-8") as f:
            puzzle = json.load(f)
        engine = MockGameEngine(puzzle, alias_state=True)
        res = agent.auto_solve(StrictNoLeakProxy(engine))
        self.assertEqual(res["status"], "SOLVED")
        self.assertEqual(res["trace"][0]["active_clues"], ["clue_B2"])
        self.assertEqual(res["trace"][0]["revealed_clue"], "clue_A1")

    def test_auto_solve_stuck_never_guesses(self):
        puzzle = make_puzzle(
            2,
            {
                "A1": ("INNOCENT", {"type": "FACT", "cell": "B1", "status": "INNOCENT"}),
                "B1": ("INNOCENT", {"type": "FACT", "cell": "A1", "status": "INNOCENT"}),
                "A2": ("CRIMINAL", {"type": "SAME", "a": "A2", "b": "B2"}),
                "B2": ("CRIMINAL", {"type": "FACT", "cell": "A2", "status": "CRIMINAL"}),
            },
            initially_revealed=["A2"],
        )
        engine = MockGameEngine(puzzle)
        res = agent.auto_solve(StrictNoLeakProxy(engine))
        self.assertEqual(res["status"], "STUCK")
        self.assertEqual(len(res["trace"]), 1)
        self.assertEqual(res["trace"][0]["verdict"], {"cell": "B2", "status": "CRIMINAL"})
        self.assertEqual(set(engine.public_state().known.keys()), {"A2", "B2"})
        self.assertFalse(engine.public_state().solved)

    def test_auto_solve_inconsistent_initial_and_mid_game(self):
        p_init_bad = make_puzzle(
            2,
            {
                "A1": ("CRIMINAL", {"type": "NO", "region": {"kind": "row", "row": 1}}),
                "B1": ("INNOCENT", {"type": "FACT", "cell": "A1", "status": "CRIMINAL"}),
                "A2": ("INNOCENT", {"type": "FACT", "cell": "A2", "status": "INNOCENT"}),
                "B2": ("INNOCENT", {"type": "FACT", "cell": "B2", "status": "INNOCENT"}),
            },
            initially_revealed=["A1"],
        )
        res1 = agent.auto_solve(StrictNoLeakProxy(MockGameEngine(p_init_bad)))
        self.assertEqual(res1["status"], "INCONSISTENT")
        self.assertEqual(res1["trace"], [])

        p_mid_bad = make_puzzle(
            2,
            {
                "A1": ("CRIMINAL", {"type": "FACT", "cell": "B1", "status": "INNOCENT"}),
                "B1": ("INNOCENT", {"type": "FACT", "cell": "A1", "status": "INNOCENT"}),
                "A2": ("INNOCENT", {"type": "FACT", "cell": "A2", "status": "INNOCENT"}),
                "B2": ("INNOCENT", {"type": "FACT", "cell": "B2", "status": "INNOCENT"}),
            },
            initially_revealed=["A1"],
        )
        res2 = agent.auto_solve(StrictNoLeakProxy(MockGameEngine(p_mid_bad)))
        self.assertEqual(res2["status"], "INCONSISTENT")
        self.assertEqual(len(res2["trace"]), 1)
        self.assertEqual(res2["trace"][0]["verdict"], {"cell": "B1", "status": "INNOCENT"})

    def test_auto_solve_already_solved_and_no_loop_on_broken_engine(self):
        with open(os.path.join(SRC, "puzzles", "sample_3x3.json"), encoding="utf-8") as f:
            puzzle = json.load(f)
        puzzle["initially_revealed"] = all_cells(3)
        res = agent.auto_solve(StrictNoLeakProxy(MockGameEngine(puzzle)))
        self.assertEqual(res["status"], "SOLVED")
        self.assertEqual(res["trace"], [])

        class BrokenEngine:
            def __init__(self):
                self._st = make_state(
                    size=2,
                    known={},
                    revealed_clues=[{"id": "c1", "type": "FACT", "cell": "A1", "status": "CRIMINAL"}],
                )

            def public_state(self):
                return self._st

            def submit_verdict(self, cell, verdict):
                return {"status": "ACCEPTED", "cell": cell, "revealed_clue": None, "message": "oops"}

        broken_res = agent.auto_solve(BrokenEngine())
        self.assertEqual(broken_res["status"], "STUCK")
        self.assertEqual(len(broken_res["trace"]), 1)

    def test_uniqueness_multiple_and_unsat_and_immutability(self):
        with open(os.path.join(SRC, "puzzles", "sample_3x3.json"), encoding="utf-8") as f:
            puzzle = json.load(f)
        clues = [c["clue"] for c in puzzle["characters"]]
        clues_snap = copy.deepcopy(clues)

        self.assertTrue(agent.check_uniqueness(clues, 3))
        self.assertEqual(clues, clues_snap)

        multi_clues = [
            {"id": "c1", "type": "FACT", "cell": "A1", "status": "CRIMINAL"},
            {"id": "c2", "type": "SAME", "a": "A2", "b": "B2"},
        ]
        self.assertFalse(agent.check_uniqueness(multi_clues, 2))
        info = agent.analyze_uniqueness(multi_clues, 2)
        self.assertEqual(info["status"], "MULTIPLE")
        self.assertEqual(len(info["models"]), 2)
        m1, m2 = info["models"]
        self.assertNotEqual(m1, m2)
        for m in (m1, m2):
            world = {c: m[var(c, 2)] for c in all_cells(2)}
            self.assertTrue(all(evaluate(cl, world, 2) for cl in multi_clues))

        unsat_clues = [
            {"id": "c1", "type": "FACT", "cell": "A1", "status": "CRIMINAL"},
            {"id": "c2", "type": "FACT", "cell": "A1", "status": "INNOCENT"},
        ]
        self.assertFalse(agent.check_uniqueness(unsat_clues, 2))
        unsat_info = agent.analyze_uniqueness(unsat_clues, 2)
        self.assertEqual(unsat_info["status"], "UNSAT")
        self.assertEqual(unsat_info["models"], [])


if __name__ == "__main__":
    unittest.main()

"""Regression checks for no-guess play and the GUI backend contracts."""

from copy import deepcopy
from itertools import product
from pathlib import Path
import random
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import agent
from engine import GameEngine, PublicState
from solver import solve

PUZZLES = Path(__file__).resolve().parents[1] / "puzzles"


class SolverTests(unittest.TestCase):
    def test_dpll_matches_exhaustive_models_and_preserves_inputs(self):
        rng = random.Random(42)
        for _ in range(200):
            clauses = [[rng.choice((-1, 1)) * rng.randint(1, 4)
                        for _ in range(rng.randrange(4))] for _ in range(rng.randrange(12))]
            assumptions = [rng.choice((-1, 1)) * rng.randint(1, 4)]
            original = deepcopy(clauses)
            models = [dict(enumerate(bits, 1)) for bits in product((False, True), repeat=4)
                      if all(any(bits[abs(x) - 1] == (x > 0) for x in c)
                             for c in clauses + [[x] for x in assumptions])]
            result = solve(clauses, 4, assumptions)
            self.assertEqual(result["status"], "SAT" if models else "UNSAT")
            if models:
                self.assertIn(result["assignment"], models)
            self.assertEqual(clauses, original)
            repeat = solve(clauses, 4, assumptions)
            self.assertEqual(result["assignment"], repeat["assignment"])
        self.assertEqual(solve([], 2)["assignment"], {1: True, 2: True})
        self.assertEqual(solve([[]], 2)["status"], "UNSAT")


class GameTests(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(str(PUZZLES / "sample_3x3.json"))

    def test_public_state_is_detached_and_does_not_leak_hidden_fields(self):
        state = self.engine.public_state()
        for person in state.characters:
            self.assertEqual(set(person), {"cell", "name", "profession"})
        self.assertEqual(set(state.clues_by_cell), set(state.known))
        self.assertEqual(len(state.revealed_clues), len(state.known))
        state.characters[0]["name"] = "tampered"
        state.clues_by_cell["B2"]["region"]["cells"].clear()
        state.known.clear()
        fresh = self.engine.public_state()
        self.assertNotEqual(fresh.characters[0]["name"], "tampered")
        self.assertEqual(len(fresh.clues_by_cell["B2"]["region"]["cells"]), 3)
        self.assertTrue(fresh.known)

    def test_rejections_leave_public_state_unchanged(self):
        initial = self.engine.public_state()
        self.assertEqual(self.engine.submit_verdict("B1", "CRIMINAL")["status"], "NOT_PROVABLE")
        self.assertEqual(self.engine.submit_verdict("A1", "CRIMINAL")["status"], "CONTRADICTED")
        self.assertEqual(self.engine.submit_verdict("B2", "INNOCENT")["status"], "ALREADY_KNOWN")
        self.assertEqual(self.engine.submit_verdict("Z9", "INNOCENT")["status"], "INVALID")
        self.assertEqual(self.engine.public_state(), initial)

    def test_hint_does_not_reveal_and_step_opens_one_card(self):
        initial = self.engine.public_state()
        hint = agent.hint(initial)
        self.assertEqual(hint["cell"], "A1")
        self.assertEqual(self.engine.public_state(), initial)
        result = agent.step(self.engine)
        self.assertEqual(len(self.engine.public_state().known), len(initial.known) + 1)
        self.assertEqual(result["trace"][0]["verdict"]["status"], "INNOCENT")
        self.assertTrue(result["trace"][0]["queries"])
        self.engine.restart()
        self.assertEqual(self.engine.public_state(), initial)

    def test_all_puzzles_solve_without_reading_full_clues(self):
        for path in sorted(PUZZLES.glob("*.json")):
            with self.subTest(puzzle=path.name):
                engine = GameEngine(str(path))
                with patch.object(engine, "full_clues", side_effect=AssertionError("Hidden access")):
                    result = agent.auto_solve(engine)
                self.assertEqual(result["status"], "SOLVED")
                self.assertTrue(engine.public_state().solved)
                # Upstream auto_solve performs a final KB check after the last reveal.
                self.assertEqual(result["totals"]["sat_calls"], 1 + sum(
                    e["solver_stats"]["sat_calls"] for e in result["trace"]))

    def test_stuck_inconsistent_and_uniqueness(self):
        state = PublicState(1, [{"cell": "A1", "name": "A", "profession": "B"}], {}, [], {}, False)
        self.assertEqual(agent.classify_cell(state, "A1"), "UNKNOWN")
        self.assertIsNone(agent.hint(state))
        state.revealed_clues = [{"id": "x", "type": "FACT", "cell": "A1", "status": "CRIMINAL"},
                                {"id": "y", "type": "FACT", "cell": "A1", "status": "INNOCENT"}]
        self.assertEqual(agent.classify_cell(state, "A1"), "INCONSISTENT")
        self.assertFalse(agent.check_uniqueness([], 1))
        self.assertTrue(agent.check_uniqueness(state.revealed_clues[:1], 1))
        self.assertFalse(agent.check_uniqueness(state.revealed_clues, 1))


if __name__ == "__main__":
    unittest.main()

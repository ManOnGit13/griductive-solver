"""Kiểm thử đơn vị cho solver.py (4.3 DPLL SAT Solver).

Chạy trong thư mục Source/:
    python -m unittest discover -s tests -v
"""

import copy
import itertools
import os
import sys
import unittest

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SRC)

from encoder import encode_clue  # noqa: E402
from solver import solve  # noqa: E402


def satisfies(clauses, assignment, assumptions=()):
    """Kiểm tra phép gán có thỏa mãn mọi mệnh đề và assumptions hay không."""
    for clause in clauses:
        if not any(assignment[abs(lit)] == (lit > 0) for lit in clause):
            return False
    for lit in assumptions:
        if assignment[abs(lit)] != (lit > 0):
            return False
    return True


def brute_force_sat(clauses, num_vars, assumptions=()):
    """Kiểm tra vét cạn xem công thức có nghiệm hay không (dùng để đối chứng)."""
    for bits in itertools.product((False, True), repeat=num_vars):
        assignment = {v: bits[v - 1] for v in range(1, num_vars + 1)}
        if satisfies(clauses, assignment, assumptions):
            return True
    return False


class SolverTests(unittest.TestCase):
    def assert_valid_result_schema(self, res, num_vars):
        self.assertIn(res["status"], ("SAT", "UNSAT"))
        stats = res["stats"]
        self.assertEqual(set(stats.keys()), {"decisions", "propagations", "backtracks", "runtime_ms"})
        self.assertIsInstance(stats["decisions"], int)
        self.assertIsInstance(stats["propagations"], int)
        self.assertIsInstance(stats["backtracks"], int)
        self.assertGreaterEqual(stats["decisions"], 0)
        self.assertGreaterEqual(stats["propagations"], 0)
        self.assertGreaterEqual(stats["backtracks"], 0)
        self.assertGreaterEqual(stats["runtime_ms"], 0.0)
        if res["status"] == "SAT":
            self.assertEqual(set(res["assignment"].keys()), set(range(1, num_vars + 1)))
            for v in res["assignment"].values():
                self.assertIsInstance(v, bool)
        else:
            self.assertIsNone(res["assignment"])

    def test_empty_formula_and_empty_clause(self):
        res_empty = solve([], 3)
        self.assert_valid_result_schema(res_empty, 3)
        self.assertEqual(res_empty["status"], "SAT")
        self.assertEqual(res_empty["assignment"], {1: True, 2: True, 3: True})

        res_zero = solve([], 0)
        self.assert_valid_result_schema(res_zero, 0)
        self.assertEqual(res_zero["status"], "SAT")
        self.assertEqual(res_zero["assignment"], {})

        res_unsat = solve([[]], 3)
        self.assert_valid_result_schema(res_unsat, 3)
        self.assertEqual(res_unsat["status"], "UNSAT")

        res_mixed_unsat = solve([[1, 2], []], 2)
        self.assertEqual(res_mixed_unsat["status"], "UNSAT")

    def test_unit_propagation_chain_and_conflict(self):
        clauses = [[1], [-1, 2], [-2, 3], [-3, -4]]
        res = solve(clauses, 4)
        self.assert_valid_result_schema(res, 4)
        self.assertEqual(res["status"], "SAT")
        self.assertEqual(res["assignment"], {1: True, 2: True, 3: True, 4: False})
        self.assertEqual(res["stats"]["decisions"], 0)
        self.assertEqual(res["stats"]["backtracks"], 0)
        self.assertEqual(res["stats"]["propagations"], 4)

        conflict = solve([[1], [-1, 2], [-1, -2]], 2)
        self.assert_valid_result_schema(conflict, 2)
        self.assertEqual(conflict["status"], "UNSAT")
        self.assertEqual(conflict["stats"]["decisions"], 0)

    def test_deterministic_variable_selection_and_backtracking(self):
        res = solve([[1, 2]], 2)
        self.assertEqual(res["status"], "SAT")
        self.assertEqual(res["assignment"], {1: True, 2: True})
        self.assertEqual(res["stats"]["decisions"], 2)
        self.assertEqual(res["stats"]["backtracks"], 0)

        res2 = solve([[-1, 2]], 2)
        self.assertEqual(res2["assignment"], {1: True, 2: True})
        self.assertEqual(res2["stats"]["decisions"], 1)
        self.assertEqual(res2["stats"]["propagations"], 1)

        res_bt = solve([[-1, 2], [-1, -2], [1, 2]], 2)
        self.assert_valid_result_schema(res_bt, 2)
        self.assertEqual(res_bt["status"], "SAT")
        self.assertEqual(res_bt["assignment"], {1: False, 2: True})
        self.assertGreaterEqual(res_bt["stats"]["backtracks"], 1)

    def test_pigeonhole_3_2_requires_branching_and_backtracking(self):
        clauses = [
            [1, 2], [3, 4], [5, 6],
            [-1, -3], [-1, -5], [-3, -5],
            [-2, -4], [-2, -6], [-4, -6],
        ]
        res = solve(clauses, 6)
        self.assert_valid_result_schema(res, 6)
        self.assertEqual(res["status"], "UNSAT")
        self.assertGreater(res["stats"]["decisions"], 0)
        self.assertGreater(res["stats"]["backtracks"], 0)

    def test_duplicate_and_tautological_clauses(self):
        clauses = [[1, 1], [2, -2], [-1, -2]]
        res = solve(clauses, 2)
        self.assert_valid_result_schema(res, 2)
        self.assertEqual(res["status"], "SAT")
        self.assertTrue(satisfies(clauses, res["assignment"]))

        res_unsat = solve([[1, 1], [-1]], 1)
        self.assertEqual(res_unsat["status"], "UNSAT")

    def test_assumptions_handling(self):
        kb = [[1, 2], [-1, 2]]
        self.assertEqual(solve(kb, 2)["status"], "SAT")
        self.assertEqual(solve(kb, 2, [-2])["status"], "UNSAT")
        self.assertEqual(solve(kb, 2, [1])["status"], "SAT")
        self.assertEqual(solve(kb, 2, [-1])["status"], "SAT")

        self.assertEqual(solve(kb, 2, [1, -1])["status"], "UNSAT")
        dup = solve(kb, 2, [1, 1])
        self.assertEqual(dup["status"], "SAT")
        self.assertTrue(satisfies(kb, dup["assignment"], [1, 1]))

        self.assertEqual(solve([[1]], 1, [-1])["status"], "UNSAT")

    def test_does_not_mutate_inputs(self):
        clauses = [[1, 2], [-1, 3], [-2, -3]]
        assumptions = [-1]
        clauses_snap = copy.deepcopy(clauses)
        assumptions_snap = list(assumptions)

        res = solve(clauses, 3, assumptions)
        self.assertEqual(res["status"], "SAT")
        self.assertEqual(clauses, clauses_snap)
        self.assertEqual(assumptions, assumptions_snap)

    def test_invalid_inputs_raise_value_error(self):
        bad_clauses = [
            [[0]],
            [[4]],
            [[-4]],
            [["1"]],
        ]
        for clauses in bad_clauses:
            with self.assertRaises(ValueError, msg=str(clauses)):
                solve(clauses, 3)

        for bad_assump in ([0], [4], [-4], ["2"]):
            with self.assertRaises(ValueError, msg=str(bad_assump)):
                solve([[1, 2]], 3, bad_assump)

    def test_matches_brute_force_on_encoded_formulas(self):
        clauses = (
            encode_clue({"type": "EXACTLY", "k": 2, "region": {"kind": "row", "row": 1}}, 3)
            + encode_clue({"type": "PARITY", "parity": "ODD", "region": {"kind": "col", "col": "A"}}, 3)
            + encode_clue({"type": "DIFFERENT", "a": "B1", "b": "B2"}, 3)
        )
        for assump in ([], [1], [-1], [5], [1, 5], [-1, -2, -3]):
            res = solve(clauses, 9, assump)
            expected_sat = brute_force_sat(clauses, 9, assump)
            self.assertEqual(res["status"], "SAT" if expected_sat else "UNSAT", assump)
            if expected_sat:
                self.assertTrue(satisfies(clauses, res["assignment"], assump))


if __name__ == "__main__":
    unittest.main()

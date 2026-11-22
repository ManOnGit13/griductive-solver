"""Kiểm thử cho encoder.py.  Chạy trong thư mục Source/:   python -m unittest discover -s tests -v"""

import itertools
import json
import os
import sys
import unittest

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SRC)

from encoder import (ClueError, all_cells, build_kb, encode_clue, evaluate,  # noqa: E402
                     region, var)


def worlds(n):
    """Mọi phép gán đầy đủ {ô: bool} của lưới n x n."""
    cells = all_cells(n)
    for bits in itertools.product((False, True), repeat=len(cells)):
        yield dict(zip(cells, bits))


def cnf_true(clauses, world, n):
    """CNF đúng khi mọi mệnh đề đều có ít nhất một literal đúng."""
    return all(any(world[all_cells(n)[abs(x) - 1]] == (x > 0) for x in c) for c in clauses)


class EncoderTests(unittest.TestCase):
    def test_variable_map(self):
        self.assertEqual([var(c, 3) for c in ("A1", "B1", "C1", "A2", "C3")], [1, 2, 3, 4, 9])

    def test_regions(self):
        self.assertEqual(region({"kind": "neighbors", "of": "A1"}, 3), ["B1", "A2", "B2"])
        self.assertEqual(len(region({"kind": "neighbors", "of": "B2"}, 3)), 8)
        self.assertEqual(region({"kind": "corners"}, 3), ["A1", "C1", "A3", "C3"])
        self.assertEqual(len(region({"kind": "boundary"}, 4)), 12)
        self.assertEqual(region({"kind": "between", "a": "A1", "b": "D1"}, 4), ["B1", "C1"])

    def test_examples_from_report(self):
        self.assertEqual(encode_clue({"type": "SAME", "a": "A1", "b": "B1"}, 3), [[-1, 2], [1, -2]])
        self.assertEqual(encode_clue({"type": "EXACTLY", "k": 1, "region": {"kind": "row", "row": 1}}, 3),
                         [[1, 2, 3], [-1, -2], [-1, -3], [-2, -3]])

    def test_invalid_clues(self):
        bad = [
            {"type": "FACT", "cell": "D1", "status": "CRIMINAL"},
            {"type": "FACT", "cell": "A1", "status": "MAYBE"},
            {"type": "SAME", "a": "A1", "b": "A1"},
            {"type": "EXACTLY", "k": 4, "region": {"kind": "row", "row": 1}},
            {"type": "AT_MOST", "k": 1, "region": {"kind": "row", "row": 9}},
            {"type": "PARITY", "parity": "PRIME", "region": {"kind": "corners"}},
            {"type": "AT_LEAST", "k": 1, "region": {"kind": "between", "a": "A1", "b": "B2"}},
            {"type": "TELEPORT"},
        ]
        for clue in bad:
            with self.assertRaises(ClueError, msg=str(clue)):
                encode_clue(clue, 3)

    def test_cnf_matches_evaluator_on_all_512_assignments(self):
        # CNF của mỗi clue phải cho kết quả giống evaluate trên cả 512 phép gán của lưới 3x3
        n = 3
        clues = [
            {"type": "FACT", "cell": "B2", "status": "CRIMINAL"},
            {"type": "FACT", "cell": "C3", "status": "INNOCENT"},
            {"type": "SAME", "a": "A1", "b": "C3"},
            {"type": "DIFFERENT", "a": "A1", "b": "B1"},
            {"type": "PARITY", "parity": "ODD", "region": {"kind": "col", "col": "A"}},
            {"type": "PARITY", "parity": "EVEN", "region": {"kind": "boundary"}},
        ]
        for t in ("EXACTLY", "AT_LEAST", "AT_MOST"):
            clues += [{"type": t, "k": k, "region": {"kind": "neighbors", "of": "B2"}} for k in range(9)]
            clues += [{"type": t, "k": k, "region": {"kind": "corners"}} for k in range(5)]
        all_worlds = list(worlds(n))
        for clue in clues:
            cnf = encode_clue(clue, n)
            for w in all_worlds:
                self.assertEqual(cnf_true(cnf, w, n), evaluate(clue, w, n), clue)

    def test_build_kb(self):
        clauses, stats = build_kb([{"type": "SAME", "a": "A1", "b": "B1"}], {"C3": True, "B2": False}, 3)
        self.assertEqual(clauses, [[-1, 2], [1, -2], [-5], [9]])
        self.assertEqual(stats, {"primary_vars": 9, "aux_vars": 0, "clauses": 4, "clues": 1, "units": 2})


class SamplePuzzleTest(unittest.TestCase):
    def test_unique_and_solvable_without_guessing(self):
        with open(os.path.join(SRC, "puzzles", "sample_3x3.json"), encoding="utf-8") as f:
            p = json.load(f)
        n, chars = p["size"], {c["cell"]: c for c in p["characters"]}
        solution = {c: ch["status"] == "CRIMINAL" for c, ch in chars.items()}

        def models(clues, known):
            cnf, _ = build_kb(clues, known, n)
            return [w for w in worlds(n) if cnf_true(cnf, w, n)]

        # Toàn bộ clue phải cho đúng 1 nghiệm
        self.assertEqual(models([ch["clue"] for ch in chars.values()], {}), [solution])

        # Mô phỏng vòng suy luận: mỗi bước phải có ít nhất 1 ô bị ép (không phải đoán)

        known = {c: solution[c] for c in p["initially_revealed"]}
        while len(known) < n * n:
            ms = models([chars[c]["clue"] for c in known], known)
            forced = {c: ms[0][c] for c in all_cells(n) if c not in known and len({m[c] for m in ms}) == 1}
            self.assertTrue(forced, f"stuck at {known}")
            known.update(forced)
        self.assertEqual(known, solution)


if __name__ == "__main__":
    unittest.main()

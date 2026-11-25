"""Kiểm thử bổ sung các trường hợp biên cho encoder.py.

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

from encoder import (ClueError, all_cells, as_bool, build_kb, cell_of,  # noqa: E402
                     describe_clue, encode_clue, evaluate, parse_cell,
                     referenced_cells, region, var)


class EncoderEdgeCaseTests(unittest.TestCase):
    def test_cell_of_parse_cell_and_as_bool(self):
        self.assertEqual(cell_of(5, 3), "B2")
        self.assertEqual(cell_of(-5, 3), "B2")
        self.assertEqual(parse_cell("C2", 3), (1, 2))
        self.assertIs(as_bool(True), True)
        self.assertIs(as_bool(False), False)
        self.assertIs(as_bool("CRIMINAL"), True)
        self.assertIs(as_bool("INNOCENT"), False)

        for bad_cell in ("a1", "A0", "A", "1A", "", None, 12):
            with self.assertRaises(ClueError, msg=repr(bad_cell)):
                parse_cell(bad_cell, 3)

        for bad_status in ("UNKNOWN", "criminal", None, 1):
            with self.assertRaises(ClueError, msg=repr(bad_status)):
                as_bool(bad_status)

    def test_region_edge_cases(self):
        self.assertEqual(region({"kind": "between", "a": "D1", "b": "A1"}, 4), ["B1", "C1"])
        self.assertEqual(region({"kind": "between", "a": "B4", "b": "B1"}, 4), ["B2", "B3"])
        with self.assertRaises(ClueError):
            region({"kind": "between", "a": "A1", "b": "B1"}, 4)

        self.assertEqual(region({"kind": "col", "col": "b"}, 3), ["B1", "B2", "B3"])
        for bad_reg in (
            "row",
            {"kind": "row", "row": True},
            {"kind": "row", "row": 0},
            {"kind": "col", "col": None},
            {"kind": "col", "col": "AB"},
            {"kind": "explicit", "cells": []},
            {"kind": "explicit", "cells": ["A1", "A1"]},
        ):
            with self.assertRaises(ClueError, msg=repr(bad_reg)):
                region(bad_reg, 3)

    def test_check_clue_rejects_bool_k_and_non_dict(self):
        for bad in (
            None,
            [],
            {"type": "EXACTLY", "k": True, "region": {"kind": "row", "row": 1}},
            {"type": "AT_LEAST", "k": -1, "region": {"kind": "row", "row": 1}},
            {"type": "FACT", "cell": "A1", "status": True},
        ):
            with self.assertRaises(ClueError, msg=repr(bad)):
                encode_clue(bad, 3)

    def test_parity_max_8_cells_on_4x4(self):
        reg = {"kind": "neighbors", "of": "B2"}
        reg_cells = region(reg, 4)
        self.assertEqual(len(reg_cells), 8)
        clue = {"type": "PARITY", "parity": "ODD", "region": reg}
        cnf = encode_clue(clue, 4)
        self.assertEqual(len(cnf), 128)

        base = {c: False for c in all_cells(4)}
        for bits in itertools.product((False, True), repeat=8):
            world = dict(base)
            for cell, val in zip(reg_cells, bits):
                world[cell] = val
            cnf_sat = all(any(world[cell_of(lit, 4)] == (lit > 0) for lit in cl) for cl in cnf)
            self.assertEqual(cnf_sat, evaluate(clue, world, 4))

    def test_build_kb_immutability_and_sorting_and_gui_helpers(self):
        clues = [{"id": "c1", "type": "DIFFERENT", "a": "A1", "b": "B1"}]
        known = {"C3": True, "A1": "INNOCENT"}
        clues_snap = copy.deepcopy(clues)
        known_snap = dict(known)

        clauses, stats = build_kb(clues, known, 3)
        self.assertEqual(clues, clues_snap)
        self.assertEqual(known, known_snap)
        self.assertEqual(clauses[-2:], [[-1], [9]])
        self.assertEqual(stats, {"primary_vars": 9, "aux_vars": 0, "clauses": 4, "clues": 1, "units": 2})

        all_samples = [
            ({"type": "FACT", "cell": "A1", "status": "CRIMINAL"}, ["A1"]),
            ({"type": "SAME", "a": "A1", "b": "B2"}, ["A1", "B2"]),
            ({"type": "DIFFERENT", "a": "B1", "b": "C1"}, ["B1", "C1"]),
            ({"type": "NO", "region": {"kind": "corners"}}, ["A1", "C1", "A3", "C3"]),
            ({"type": "AT_LEAST", "k": 2, "region": {"kind": "boundary"}}, region({"kind": "boundary"}, 3)),
            ({"type": "AT_MOST", "k": 1, "region": {"kind": "between", "a": "A1", "b": "C1"}}, ["B1"]),
            ({"type": "PARITY", "parity": "EVEN", "region": {"kind": "col", "col": "B"}}, ["B1", "B2", "B3"]),
        ]
        for clue, expected_cells in all_samples:
            self.assertEqual(referenced_cells(clue, 3), expected_cells)
            text = describe_clue(clue, 3)
            self.assertTrue(isinstance(text, str) and text.endswith("."))


if __name__ == "__main__":
    unittest.main()

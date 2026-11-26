"""Own the hidden puzzle; expose detached public snapshots to GUI and agent."""

from copy import deepcopy
from dataclasses import dataclass
import json

import encoder


@dataclass
class PublicState:
    size: int
    characters: list[dict]
    known: dict[str, bool]
    revealed_clues: list[dict]
    clues_by_cell: dict[str, dict]
    solved: bool


class GameEngine:
    def __init__(self, path: str):
        with open(path, encoding="utf-8") as handle:
            puzzle = json.load(handle)
        n = puzzle.get("size")
        if type(n) is not int or not 1 <= n <= len(encoder.COLS):
            raise ValueError("Puzzle size must be an integer from 1 to 10")
        characters = puzzle.get("characters")
        if not isinstance(characters, list) or len(characters) != n * n:
            raise ValueError("Puzzle must contain exactly N x N characters")
        self._cards = {}
        clue_ids = set()
        for card in characters:
            cell = card["cell"]
            encoder.parse_cell(cell, n)
            if cell in self._cards or cell not in encoder.all_cells(n):
                raise ValueError(f"Duplicate or noncanonical cell: {cell}")
            for field in ("name", "profession"):
                if not isinstance(card.get(field), str) or not card[field].strip():
                    raise ValueError(f"{cell}: missing {field}")
            encoder.as_bool(card["status"])
            encoder.check_clue(card["clue"], n)
            clue_id = card["clue"].get("id")
            if not isinstance(clue_id, str) or not clue_id or clue_id in clue_ids:
                raise ValueError(f"{cell}: clue id must be a unique nonempty string")
            clue_ids.add(clue_id)
            self._cards[cell] = card
        initial = puzzle.get("initially_revealed", [])
        if not isinstance(initial, list) or any(c not in self._cards for c in initial):
            raise ValueError("Invalid initially_revealed cells")
        if len(set(initial)) != len(initial):
            raise ValueError("Duplicate initially_revealed cells")
        assignment = {c: encoder.as_bool(card["status"]) for c, card in self._cards.items()}
        if not all(encoder.evaluate(card["clue"], assignment, n) for card in characters):
            raise ValueError("A clue contradicts the puzzle's supplied solution")
        self._size = n
        self._initial = list(initial)
        self.restart()

    def restart(self):
        self._known = {c: encoder.as_bool(self._cards[c]["status"]) for c in self._initial}
        self._clues = {c: deepcopy(self._cards[c]["clue"]) for c in self._initial}

    def public_state(self):
        return PublicState(
            self._size,
            [{k: self._cards[c][k] for k in ("cell", "name", "profession")}
             for c in encoder.all_cells(self._size)],
            self._known.copy(), deepcopy(list(self._clues.values())),
            deepcopy(self._clues), len(self._known) == self._size ** 2,
        )

    def submit_verdict(self, cell, verdict):
        import agent  # Local import keeps the public-state dependency acyclic.

        def response(status, message, clue=None):
            return {"status": status, "cell": cell, "revealed_clue": deepcopy(clue),
                    "message": message}

        if cell not in self._cards or verdict not in ("CRIMINAL", "INNOCENT"):
            return response("INVALID", "Ô hoặc verdict không hợp lệ.")
        if cell in self._known:
            return response("ALREADY_KNOWN", "Nhân vật này đã được xác định.")
        classification = agent.classify_cell(self.public_state(), cell)
        if classification == "INCONSISTENT":
            return response("INVALID", "INCONSISTENT: dữ kiện công khai mâu thuẫn.")
        if classification == "UNKNOWN":
            return response("NOT_PROVABLE", "Chưa đủ dữ kiện để chứng minh verdict này.")
        if classification != verdict:
            return response("CONTRADICTED", "Dữ kiện chứng minh verdict ngược lại.")
        if encoder.as_bool(verdict) != encoder.as_bool(self._cards[cell]["status"]):
            return response("INVALID", "Puzzle lỗi: verdict chứng minh được khác đáp án.")
        self._known[cell] = encoder.as_bool(verdict)
        self._clues[cell] = deepcopy(self._cards[cell]["clue"])
        return response("ACCEPTED", f"Đã chứng minh {cell}: {verdict}. Clue mới được mở.",
                        self._clues[cell])

    def full_clues(self):
        """For offline uniqueness checks / experiments only; never used by GUI."""
        return deepcopy([self._cards[c]["clue"] for c in encoder.all_cells(self._size)])

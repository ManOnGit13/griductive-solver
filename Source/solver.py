"""solver.py - DPLL SAT Solver (yêu cầu 4.3).

Hợp đồng (theo INTERFACES.md, mục 5):
    solve(clauses, num_vars, assumptions=[]) -> {
        "status": "SAT" | "UNSAT",
        "assignment": {1: True, 2: False, ...} | None,   # SAT: gán đủ 1..num_vars
        "stats": {"decisions", "propagations", "backtracks", "runtime_ms"},
    }

- Không sửa list `clauses` truyền vào.
- `assumptions` là các literal bị ép đúng tạm thời (như thêm unit clause).
- clauses == [] -> SAT; có mệnh đề rỗng [] -> UNSAT.
- Chọn biến tất định: biến chưa gán có số nhỏ nhất, thử True trước.
- Có unit propagation, phát hiện xung đột, đệ quy + quay lui.
"""

from __future__ import annotations

import time


class _DPLL:
    """Trạng thái một lần giải. Dùng trail để hoàn tác gán khi quay lui."""

    def __init__(self, clauses, num_vars):
        # Sao chép nông sang tuple để không đụng vào dữ liệu của người gọi.
        self.clauses = [tuple(c) for c in clauses]
        self.num_vars = num_vars
        self.assign = {}          # var -> bool
        self.trail = []           # thứ tự các biến đã gán
        self.decisions = 0
        self.propagations = 0
        self.backtracks = 0

    # ---- gán / hoàn tác ----
    def _set(self, lit):
        v = abs(lit)
        self.assign[v] = lit > 0
        self.trail.append(v)

    def _undo(self, mark):
        while len(self.trail) > mark:
            del self.assign[self.trail.pop()]

    def _value(self, lit):
        """True / False nếu literal đã có giá trị, None nếu chưa gán."""
        val = self.assign.get(abs(lit))
        if val is None:
            return None
        return val if lit > 0 else not val

    # ---- unit propagation + phát hiện xung đột ----
    def _propagate(self):
        """Lặp đến khi không còn mệnh đề đơn vị. Trả False nếu có xung đột."""
        changed = True
        while changed:
            changed = False
            for clause in self.clauses:
                satisfied = False
                unassigned = None
                n_unassigned = 0
                for lit in clause:
                    val = self._value(lit)
                    if val is True:
                        satisfied = True
                        break
                    if val is None:
                        n_unassigned += 1
                        unassigned = lit
                if satisfied:
                    continue
                if n_unassigned == 0:
                    return False                      # xung đột: mệnh đề bị falsified
                if n_unassigned == 1:
                    self._set(unassigned)             # mệnh đề đơn vị -> ép
                    self.propagations += 1
                    changed = True
        return True

    # ---- chọn biến tất định ----
    def _pick_var(self):
        for v in range(1, self.num_vars + 1):
            if v not in self.assign:
                return v
        return None

    # ---- đệ quy ----
    def dpll(self):
        if not self._propagate():
            return False
        v = self._pick_var()
        if v is None:
            return True            # đã gán đủ, không xung đột -> mọi mệnh đề đúng
        for value in (True, False):                   # thử True trước
            self.decisions += 1
            mark = len(self.trail)
            self._set(v if value else -v)
            if self.dpll():
                return True
            self._undo(mark)
            self.backtracks += 1
        return False


def _validate(clauses, num_vars, assumptions):
    for clause in clauses:
        for lit in clause:
            if not isinstance(lit, int) or lit == 0 or abs(lit) > num_vars:
                raise ValueError(f"Literal không hợp lệ {lit!r} (num_vars={num_vars})")
    for lit in assumptions:
        if not isinstance(lit, int) or lit == 0 or abs(lit) > num_vars:
            raise ValueError(f"Assumption không hợp lệ {lit!r} (num_vars={num_vars})")


def solve(clauses: list[list[int]], num_vars: int, assumptions: list[int] = []) -> dict:
    """Giải CNF bằng DPLL. Xem docstring module để biết hợp đồng."""
    t0 = time.perf_counter()
    _validate(clauses, num_vars, assumptions)
    s = _DPLL(clauses, num_vars)

    ok = True
    # Assumptions: gán trước như unit clause; hai assumption đối nhau -> UNSAT.
    for lit in assumptions:
        val = s._value(lit)
        if val is False:
            ok = False
            break
        if val is None:
            s._set(lit)
    if ok:
        ok = s.dpll()

    stats = {
        "decisions": s.decisions,
        "propagations": s.propagations,
        "backtracks": s.backtracks,
        "runtime_ms": (time.perf_counter() - t0) * 1000.0,
    }
    if not ok:
        return {"status": "UNSAT", "assignment": None, "stats": stats}
    return {
        "status": "SAT",
        "assignment": {v: s.assign[v] for v in range(1, num_vars + 1)},
        "stats": stats,
    }


if __name__ == "__main__":
    # Ví dụ trong đề (mục 3.4): KB = (CA v CB) ^ (-CA v CB), A=1, B=2
    kb = [[1, 2], [-1, 2]]
    assert solve(kb, 2)["status"] == "SAT"
    assert solve(kb, 2, [-2])["status"] == "UNSAT"     # KB |= C_B
    assert solve(kb, 2, [1])["status"] == "SAT"
    assert solve(kb, 2, [-1])["status"] == "SAT"       # A là UNKNOWN
    assert solve([], 3)["status"] == "SAT"
    assert solve([[]], 3)["status"] == "UNSAT"
    assert solve([[1]], 1, [1, -1])["status"] == "UNSAT"
    before = [[1, 2], [-1, 2]]
    solve(before, 2)
    assert before == [[1, 2], [-1, 2]]                 # không sửa input
    print("OK", solve(kb, 2))
"""Griductive - Bộ mã hóa CNF (mục 4.2 của đề), phiên bản gọn.

Ý tưởng chính:
  * Mỗi ô có đúng một biến chính, đánh số theo từng hàng (row-major):
        A1=1, B1=2, C1=3, A2=4, ...      var = (hàng-1)*N + chỉ_số_cột + 1
    Literal +v nghĩa là "tội phạm", -v nghĩa là "vô tội". KHÔNG dùng biến phụ.
  * Mỗi clue được dịch thành một danh sách mệnh đề (mỗi mệnh đề là list số nguyên,
    giống định dạng DIMACS).
  * Clue đếm dùng mã hóa tổ hợp trực tiếp (itertools.combinations).
  * KB_t = CNF(các clue đã lật) + unit clause của các verdict đã chứng minh.

Định dạng clue (dict):
    {"id": "c1", "type": "FACT",      "cell": "B2", "status": "CRIMINAL"}
    {"id": "c2", "type": "SAME",      "a": "A1", "b": "B1"}
    {"id": "c3", "type": "DIFFERENT", "a": "A1", "b": "B1"}
    {"id": "c4", "type": "EXACTLY",   "k": 1, "region": {...}}     (tương tự AT_LEAST, AT_MOST)
    {"id": "c5", "type": "NO",        "region": {...}}             (viết tắt của EXACTLY k=0)
    {"id": "c6", "type": "PARITY",    "parity": "ODD", "region": {...}}   (phần mở rộng)

Định dạng vùng (dict):
    {"kind": "row", "row": 2}            {"kind": "col", "col": "B"}
    {"kind": "neighbors", "of": "B2"}    {"kind": "explicit", "cells": ["A1", "C3"]}
    mở rộng: {"kind": "corners"}  {"kind": "boundary"}  {"kind": "between", "a": "A1", "b": "A3"}
"""

from itertools import combinations, product

COLS = "ABCDEFGHIJ"
COUNT_TYPES = ("EXACTLY", "AT_LEAST", "AT_MOST")
PARITY_MAX_CELLS = 8   # giới hạn số ô cho PARITY (2^7 = 128 mệnh đề) để tránh treo trên lưới 5x5


class ClueError(ValueError):
    """Lỗi khi clue, vùng hoặc trạng thái không hợp lệ."""


# 1. Ô, biến và chuẩn hóa trạng thái
def parse_cell(cell, n):
    """'C2' -> (chỉ_số_hàng, chỉ_số_cột) = (1, 2), cả hai đếm từ 0."""
    if not isinstance(cell, str) or len(cell) < 2 or not cell[1:].isdigit():
        raise ClueError(f"Bad cell id: {cell!r}")
    r, c = int(cell[1:]) - 1, COLS.find(cell[0])   # chỉ nhận chữ in hoa: "B2"
    if not (0 <= r < n and 0 <= c < n):
        raise ClueError(f"Cell {cell!r} is outside the {n}x{n} board")
    return r, c


def cell_name(r, c):
    """(hàng, cột) đếm từ 0 -> tên ô, ví dụ (1, 2) -> 'C2'."""
    return f"{COLS[c]}{r + 1}"


def all_cells(n):
    """Tất cả các ô theo thứ tự hàng: A1, B1, ..., A2, ..."""
    return [cell_name(r, c) for r in range(n) for c in range(n)]


def var(cell, n):
    """Tên ô -> số hiệu biến chính (1..n*n)."""
    r, c = parse_cell(cell, n)
    return r * n + c + 1


def cell_of(v, n):
    """Số hiệu biến (hoặc literal) -> tên ô."""
    v = abs(v) - 1
    return cell_name(v // n, v % n)


def as_bool(status):
    """Chuẩn hóa trạng thái: True/'CRIMINAL' -> True, False/'INNOCENT' -> False."""
    if isinstance(status, bool):
        return status
    if status == "CRIMINAL":
        return True
    if status == "INNOCENT":
        return False
    raise ClueError(f"Status must be bool, 'CRIMINAL' or 'INNOCENT', got {status!r}")


# 2. Vùng -> danh sách ô (sắp theo thứ tự hàng, không trùng, không rỗng)
def region(spec, n):
    if not isinstance(spec, dict):
        raise ClueError(f"Region must be a dict, got {spec!r}")
    kind = spec.get("kind")
    if kind == "row":                                   # cả một hàng
        row = spec.get("row")
        if not isinstance(row, int) or isinstance(row, bool) or not 1 <= row <= n:
            raise ClueError(f"Bad row: {row!r}")
        cells = [cell_name(row - 1, c) for c in range(n)]
    elif kind == "col":                                 # cả một cột
        c = COLS.find(str(spec.get("col", "")).upper())
        if not 0 <= c < n or len(str(spec.get("col"))) != 1:
            raise ClueError(f"Bad column: {spec.get('col')!r}")
        cells = [cell_name(r, c) for r in range(n)]
    elif kind == "neighbors":                           # tối đa 8 ô xung quanh, không tính chính nó
        r0, c0 = parse_cell(spec.get("of"), n)
        cells = [cell_name(r, c)
                 for r in range(r0 - 1, r0 + 2) for c in range(c0 - 1, c0 + 2)
                 if 0 <= r < n and 0 <= c < n and (r, c) != (r0, c0)]
    elif kind == "explicit":                            # danh sách ô chỉ định
        raw = spec.get("cells")
        if not isinstance(raw, list):
            raise ClueError("Explicit region needs a list 'cells'")
        cells = [cell_name(*parse_cell(x, n)) for x in raw]
        if len(set(cells)) != len(cells):
            raise ClueError("Explicit region has duplicate cells")
    # ---- PHẦN MỞ RỘNG 1: vùng nâng cao ----
    elif kind == "corners":                             # 4 ô góc
        cells = [cell_name(r, c) for r in (0, n - 1) for c in (0, n - 1)]
    elif kind == "boundary":                            # các ô nằm trên viền
        cells = [cell_name(r, c) for r in range(n) for c in range(n)
                 if r in (0, n - 1) or c in (0, n - 1)]
    elif kind == "between":                             # các ô nằm giữa a và b (cùng hàng hoặc cột)
        (ra, ca), (rb, cb) = parse_cell(spec.get("a"), n), parse_cell(spec.get("b"), n)
        if ra == rb:
            cells = [cell_name(ra, c) for c in range(min(ca, cb) + 1, max(ca, cb))]
        elif ca == cb:
            cells = [cell_name(r, ca) for r in range(min(ra, rb) + 1, max(ra, rb))]
        else:
            raise ClueError("'between' needs two cells on the same row or column")
    else:
        raise ClueError(f"Unknown region kind: {kind!r}")

    if not cells:
        raise ClueError(f"Region {spec} is empty")
    return sorted(set(cells), key=lambda x: var(x, n))


# 3. Các khối CNF cơ bản (mã hóa tổ hợp trực tiếp, không dùng biến phụ)
def at_most(lits, k):
    """Nhiều nhất k literal đúng  <=>  không có nhóm k+1 literal nào cùng đúng."""
    return [[-x for x in group] for group in combinations(lits, k + 1)]


def at_least(lits, k):
    """Ít nhất k literal đúng  <=>  không có nhóm n-k+1 literal nào cùng sai."""
    if k <= 0:
        return []
    return [list(group) for group in combinations(lits, len(lits) - k + 1)]


def parity(lits, odd):
    """Cấm mọi phép gán có tính chẵn/lẻ sai (sinh ra 2^(n-1) mệnh đề).

    Với mỗi phép gán sai, thêm một mệnh đề chỉ sai đúng tại phép gán đó.
    """
    clauses = []
    for bits in product((0, 1), repeat=len(lits)):
        if sum(bits) % 2 != (1 if odd else 0):
            clauses.append([-x if b else x for x, b in zip(lits, bits)])
    return clauses


# 4. Clue -> CNF
def check_clue(clue, n):
    """Kiểm tra clue hợp lệ; nếu sai thì ném ClueError kèm id của clue."""
    if not isinstance(clue, dict):
        raise ClueError(f"Clue must be a dict, got {clue!r}")
    t = clue.get("type")
    try:
        if t == "FACT":
            parse_cell(clue.get("cell"), n)
            if clue.get("status") not in ("CRIMINAL", "INNOCENT"):
                raise ClueError("status must be CRIMINAL or INNOCENT")
        elif t in ("SAME", "DIFFERENT"):
            if var(clue.get("a"), n) == var(clue.get("b"), n):
                raise ClueError("a and b must be different cells")
        elif t == "NO":
            region(clue.get("region"), n)
        elif t in COUNT_TYPES:
            k, size = clue.get("k"), len(region(clue.get("region"), n))
            if not isinstance(k, int) or isinstance(k, bool) or not 0 <= k <= size:
                raise ClueError(f"k must be an integer with 0 <= k <= {size}")
        elif t == "PARITY":
            size = len(region(clue.get("region"), n))
            if size > PARITY_MAX_CELLS:
                raise ClueError(f"PARITY region has {size} cells (max {PARITY_MAX_CELLS})")
            if clue.get("parity") not in ("ODD", "EVEN"):
                raise ClueError("parity must be ODD or EVEN")
        else:
            raise ClueError(f"Unknown clue type: {t!r}")
    except ClueError as e:
        raise ClueError(f"[{clue.get('id')}] {e}") from None


def encode_clue(clue, n):
    """Dịch MỘT clue thành danh sách mệnh đề."""
    check_clue(clue, n)
    t = clue["type"]
    if t == "FACT":                              # C   hoặc  -C
        x = var(clue["cell"], n)
        return [[x]] if clue["status"] == "CRIMINAL" else [[-x]]
    if t == "SAME":                              # a <-> b  =  (-a v b) & (a v -b)
        a, b = var(clue["a"], n), var(clue["b"], n)
        return [[-a, b], [a, -b]]
    if t == "DIFFERENT":                         # a xor b  =  (a v b) & (-a v -b)
        a, b = var(clue["a"], n), var(clue["b"], n)
        return [[a, b], [-a, -b]]
    lits = [var(c, n) for c in region(clue["region"], n)]
    if t == "NO":                                # NO(R) = EXACTLY(0, R)
        return at_most(lits, 0)
    if t == "AT_MOST":
        return at_most(lits, clue["k"])
    if t == "AT_LEAST":
        return at_least(lits, clue["k"])
    if t == "EXACTLY":                           # EXACTLY = AT_LEAST và AT_MOST
        return at_least(lits, clue["k"]) + at_most(lits, clue["k"])
    return parity(lits, clue["parity"] == "ODD")  # PHẦN MỞ RỘNG 2: PARITY (chẵn/lẻ)


# 5. Cơ sở tri thức KB_t
def build_kb(revealed_clues, known, n):
    """KB_t = CNF(các clue đã lật) + unit clause của các verdict đã chứng minh.

    revealed_clues : list các clue (dict) - CHỈ truyền clue đã lật
    known          : {ô: True/False hoặc 'CRIMINAL'/'INNOCENT'}, verdict đã chứng minh
    trả về         : (clauses, stats)
        clauses = list[list[int]], các biến là 1..n*n
        stats   = {"primary_vars", "aux_vars", "clauses", "clues", "units"}
    """
    clauses = []
    for clue in revealed_clues:
        clauses += encode_clue(clue, n)
    for cell in sorted(known, key=lambda c: var(c, n)):   # thêm unit clause theo thứ tự biến
        x = var(cell, n)
        clauses.append([x] if as_bool(known[cell]) else [-x])
    stats = {"primary_vars": n * n, "aux_vars": 0, "clauses": len(clauses),
             "clues": len(revealed_clues), "units": len(known)}
    return clauses, stats


# 6. Bộ đánh giá ngữ nghĩa trực tiếp & tiện ích cho GUI
def evaluate(clue, assignment, n):
    """Clue có đúng với một phép gán đầy đủ {ô: True/False hoặc 'CRIMINAL'/'INNOCENT'} không?"""
    check_clue(clue, n)
    val = {c: as_bool(v) for c, v in assignment.items()}
    t = clue["type"]
    if t == "FACT":
        return val[clue["cell"]] == (clue["status"] == "CRIMINAL")
    if t == "SAME":
        return val[clue["a"]] == val[clue["b"]]
    if t == "DIFFERENT":
        return val[clue["a"]] != val[clue["b"]]
    count = sum(val[c] for c in region(clue["region"], n))   # số tội phạm trong vùng
    if t == "NO":
        return count == 0
    if t == "EXACTLY":
        return count == clue["k"]
    if t == "AT_LEAST":
        return count >= clue["k"]
    if t == "AT_MOST":
        return count <= clue["k"]
    return count % 2 == (1 if clue["parity"] == "ODD" else 0)


def referenced_cells(clue, n):
    """Các ô mà clue nhắc tới hoặc đếm (GUI dùng để tô sáng)."""
    check_clue(clue, n)
    if clue["type"] == "FACT":
        return [clue["cell"]]
    if clue["type"] in ("SAME", "DIFFERENT"):
        return [clue["a"], clue["b"]]
    return region(clue["region"], n)


def describe_clue(clue, n):
    """Tạo câu tiếng Anh ngắn gọn cho clue để GUI hiển thị trên thẻ đã lật."""
    check_clue(clue, n)
    t = clue["type"]
    if t == "FACT":
        return f"{clue['cell']} is {'a criminal' if clue['status'] == 'CRIMINAL' else 'innocent'}."
    if t == "SAME":
        return f"{clue['a']} and {clue['b']} have the same status."
    if t == "DIFFERENT":
        return f"{clue['a']} and {clue['b']} have different statuses."
    r = clue["region"]
    kind = r["kind"]
    where = {
        "row": f"row {r.get('row')}",
        "col": f"column {str(r.get('col', '')).upper()}",
        "neighbors": f"neighbors of {r.get('of')}",
        "explicit": "{" + ", ".join(r.get("cells", [])) + "}",
        "corners": "the corners",
        "boundary": "the boundary",
        "between": f"cells between {r.get('a')} and {r.get('b')}",
    }[kind]
    if t == "NO" or (t == "EXACTLY" and clue["k"] == 0):
        return f"No criminals in {where}."
    if t == "PARITY":
        return f"An {clue['parity'].lower()} number of criminals in {where}."
    prefix = {"EXACTLY": "Exactly", "AT_LEAST": "At least", "AT_MOST": "At most"}[t]
    k = clue["k"]
    return f"{prefix} {k} {'criminal' if k == 1 else 'criminals'} in {where}."

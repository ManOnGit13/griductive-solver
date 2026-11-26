"""Vietnamese presentation labels; backend values and puzzle data stay unchanged."""

import encoder

VERDICTS = {"INNOCENT": "Vô tội", "CRIMINAL": "Tội phạm", "UNKNOWN": "Chưa xác định"}
EMPTY_TRACE = "Chưa có bước suy luận. Bấm “Giải một bước” hoặc “Tự động giải” để bắt đầu."


def clue_text(clue, n):
    encoder.check_clue(clue, n)
    kind = clue["type"]
    if kind == "FACT":
        status = "CRIMINAL" if encoder.as_bool(clue["status"]) else "INNOCENT"
        return f"{clue['cell']} là {VERDICTS[status].lower()}."
    if kind in ("SAME", "DIFFERENT"):
        relation = "cùng" if kind == "SAME" else "khác"
        return f"{clue['a']} và {clue['b']} {relation} trạng thái."
    region = clue["region"]
    where = {
        "row": f"hàng {region.get('row')}",
        "col": f"cột {region.get('col')}",
        "neighbors": f"các ô lân cận {region.get('of')}",
        "explicit": "các ô " + ", ".join(region.get("cells", [])),
        "corners": "các ô góc", "boundary": "các ô biên",
        "between": f"các ô nằm giữa {region.get('a')} và {region.get('b')}",
    }[region["kind"]]
    if kind == "PARITY":
        parity = "lẻ" if clue["parity"] == "ODD" else "chẵn"
        return f"Số tội phạm trong {where} là số {parity}."
    if kind == "NO" or (kind == "EXACTLY" and clue["k"] == 0):
        return f"Không có tội phạm trong {where}."
    prefix = {"EXACTLY": "Đúng", "AT_LEAST": "Ít nhất", "AT_MOST": "Nhiều nhất"}[kind]
    return f"{prefix} {clue['k']} tội phạm trong {where}."


def feedback_text(message):
    text = message.split(" • ", 1)[-1]
    for code, label in VERDICTS.items():
        text = text.replace(code, label)
    for old, new in (("INCONSISTENT:", "Dữ kiện không hợp lệ:"),
                     ("Clue", "Manh mối"), ("clue", "manh mối"),
                     ("Puzzle", "Bàn chơi"), ("puzzle", "bàn chơi"),
                     ("verdict", "lựa chọn")):
        text = text.replace(old, new)
    return text

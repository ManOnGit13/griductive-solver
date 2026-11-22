

## 1. Encoder làm gì?

Encoder là bộ phiên dịch: nhận các clue dạng JSON, xuất ra CNF (danh sách các danh sách số nguyên) cho bộ giải DPLL.

$$KB_t = \text{CNF}(\text{các clue đã lật}) \land \text{unit clause của các verdict đã chứng minh}$$

| Yêu cầu đề (4.2) | Hàm trong `encoder.py` |
|---|---|
| Gán biến tất định | `var(cell, n)`, `cell_of(v, n)`, `all_cells(n)` |
| Kiểm tra clue & vùng | `check_clue(clue, n)`, `region(spec, n)` → ném `ClueError` |
| Chuyển clue sang CNF | `encode_clue(clue, n)` (hỗ trợ cả `NO` = `EXACTLY(0, R)`) |
| Verdict → unit clause, xây KB_t | `build_kb(revealed_clues, known, n)` (nhận được cả `bool` và `"CRIMINAL"`/`"INNOCENT"`) |
| Báo số biến / mệnh đề | `stats` do `build_kb` trả về |
| Bộ đánh giá trực tiếp | `evaluate(clue, assignment, n)` |
| ≥ 2 extension | Ext 1: vùng `corners`, `boundary`, `between` · Ext 2: clue `PARITY` (≤ 8 ô) |
| Tiện ích cho GUI | `referenced_cells(clue, n)` (tô sáng ô), `describe_clue(clue, n)` (hiển thị câu chữ) |

## 2. Biến mệnh đề

Mỗi ô $i$ có một biến $C_i$: `True` = Criminal, `False` = Innocent. Đánh số theo hàng:

$$\text{var} = (\text{hàng} - 1)\cdot N + \text{cột} + 1 \quad (A = 0, B = 1, \dots)$$

| | A | B | C |
|---|---|---|---|
| **1** | 1 | 2 | 3 |
| **2** | 4 | 5 | 6 |
| **3** | 7 | 8 | 9 |

Literal `+5` = "B2 là Criminal", `-5` = "B2 là Innocent". **Không dùng biến phụ**, nên tổng số biến luôn là $N^2$.

## 3. Vùng

| kind | Ví dụ | Loại |
|---|---|---|
| `row` | `{"kind":"row","row":2}` | core |
| `col` | `{"kind":"col","col":"B"}` | core |
| `neighbors` | `{"kind":"neighbors","of":"B2"}` (tối đa 8 ô, không tính chính nó) | core |
| `explicit` | `{"kind":"explicit","cells":["A1","C3"]}` | core |
| `corners` | `{"kind":"corners"}` – 4 ô góc | **Ext 1** |
| `boundary` | `{"kind":"boundary"}` – các ô viền | **Ext 1** |
| `between` | `{"kind":"between","a":"A1","b":"A3"}` – các ô nằm giữa a và b (cùng hàng hoặc cột) | **Ext 1** |

Kết quả luôn là danh sách ô không trùng, sắp theo thứ tự biến, không rỗng (rỗng thì báo lỗi).

## 4. Dẫn xuất CNF (dùng cho báo cáo)

Ký hiệu: $a, b$ là biến của 2 ô; $R = \{x_1..x_n\}$ là các biến trong vùng.

**FACT:** `CRIMINAL` → $C_p$ ; `INNOCENT` → $\neg C_p$.

**SAME (clue 2 ngôi):**
$$a \leftrightarrow b \equiv (a \rightarrow b) \land (b \rightarrow a) \equiv (\neg a \lor b) \land (a \lor \neg b)$$
`SAME(A1, B1)` → `[[-1, 2], [1, -2]]`

**DIFFERENT:**
$$a \oplus b \equiv (a \lor b) \land \neg(a \land b) \equiv (a \lor b) \land (\neg a \lor \neg b)$$

**AT_MOST(k, R):** không có nhóm $k+1$ ô nào cùng là Criminal:
$$\bigwedge_{S \subseteq R,\ |S| = k+1} \ \bigvee_{x \in S} \neg x \qquad (\tbinom{n}{k+1} \text{ mệnh đề})$$

**AT_LEAST(k, R):** ít nhất $k$ Criminal ⇔ nhiều nhất $n-k$ Innocent ⇔ không có nhóm $n-k+1$ ô nào cùng Innocent:
$$\bigwedge_{S \subseteq R,\ |S| = n-k+1} \ \bigvee_{x \in S} x$$

**EXACTLY(k, R)** = AT_LEAST ∧ AT_MOST. **`NO(R)`** tương đương `EXACTLY(0, R)`.

**Ví dụ clue đếm:** `EXACTLY(1, row 1)` trên lưới 3×3, với $R = \{1, 2, 3\}$:
- AT_LEAST 1 (nhóm cỡ 3): $(C_1 \lor C_2 \lor C_3)$
- AT_MOST 1 (nhóm cỡ 2): $(\neg C_1 \lor \neg C_2)(\neg C_1 \lor \neg C_3)(\neg C_2 \lor \neg C_3)$
- Kết quả: `[[1, 2, 3], [-1, -2], [-1, -3], [-2, -3]]`

**PARITY (Ext 2):** với mỗi phép gán $(b_1..b_n)$ có tính chẵn lẻ **sai**, thêm một mệnh đề chỉ sai đúng tại phép gán đó: $\bigvee_i (b_i\ ?\ \neg x_i : x_i)$. Tổng cộng $2^{n-1}$ mệnh đề (giới hạn cho vùng $\le 8$ ô, tức tối đa 128 mệnh đề, để tránh nổ tổ hợp trên vùng `boundary` của lưới 5×5).

> [!NOTE]
> Cách liệt kê tổ hợp được đề cho phép vì vùng nhỏ: vùng 8 ô chỉ sinh tối đa $\binom{8}{4} = 70$ mệnh đề. Không cần biến phụ nên dễ dẫn xuất và dễ debug.

## 5. `build_kb`

```python
from encoder import build_kb
clauses, stats = build_kb(revealed_clues, {"B2": False}, 3)   # hoặc {"B2": "INNOCENT"}
# clauses = [[...], ...]   biến 1..9
# stats   = {"primary_vars": 9, "aux_vars": 0, "clauses": 4, "clues": 1, "units": 1}
```

Các bước: mã hóa từng clue theo thứ tự truyền vào, rồi thêm unit clause cho mỗi verdict đã biết (sắp theo thứ tự biến). Hàm này **chỉ mã hóa những gì được truyền vào**, nên Agent chỉ được truyền clue đã lật.

## 6. Bộ đánh giá trực tiếp

`evaluate(clue, assignment, n)` không dùng CNF, chỉ đếm bằng Python: `count == k`, `>= k`, `<= k`, `count % 2`, `a == b`… Dùng để kiểm chứng encoder và kiểm tra lời giải.

## 7. Kiểm thử

```powershell
cd Source
python -m unittest discover -s tests -v
```

Test chính: với mỗi clue, duyệt **toàn bộ 512 phép gán** của lưới 3×3 và kiểm tra CNF đúng ⇔ `evaluate` đúng. Ngoài ra có test kiểm tra puzzle mẫu có đúng 1 nghiệm và giải được hết mà không đoán.


# Griductive Solver – Source

Python 3.10+, chỉ dùng thư viện chuẩn và Tkinter/ttk.

## Chạy GUI

Từ thư mục `Source`:

```powershell
python main.py
```

Ứng dụng tự mở bàn 3×3. Chọn **Kích thước** 3×3, 4×4 hoặc 5×5 để bắt đầu
bàn tương ứng; người chơi không cần chuẩn bị hoặc nạp JSON. **Ván mới** chọn
bàn khác trong bộ có sẵn cùng kích thước (nếu có). Hiện có 3 bàn 3×3,
2 bàn 4×4 và 1 bàn 5×5; chưa có bộ sinh puzzle vô hạn.
Có thể chạy `main.py` bằng đường dẫn tuyệt đối từ thư mục khác.
Kiểm tra Tkinter bằng `python -m tkinter` nếu gặp lỗi môi trường.

### Bàn chơi và bảng suy luận

Giao diện desktop tham khảo bố cục và màu sắc từ
[Griductive của Knotwise Games](https://knotwise.games/games/griductive): nền tối ấm,
thẻ bo góc, avatar nhân vật, đồng hồ và hộp thoại verdict. Avatar được vẽ bằng
Tkinter Canvas từ tên công khai, không tải tài nguyên hoặc kết nối dịch vụ của website.
UI và logic game chạy hoàn toàn offline.

- Chọn **Kích thước** để đổi bàn; **Ván mới** chọn bàn khác, **Chơi lại** đặt lại bàn hiện tại.
- Bấm thẻ chưa mở và chọn **Vô tội** hoặc **Tội phạm**. **Hủy** hoặc `Esc` đóng hộp thoại.
- Bấm thẻ đã mở để xem **Manh mối** và tô sáng các ô liên quan; **Bỏ tô sáng** xóa vùng đang chọn.
- **Đánh dấu thẻ** bật chế độ ghi chú. Tắt để tiếp tục chọn trạng thái nhân vật.
- **Gợi ý** chỉ đề xuất nước đi; **Giải một bước** thực hiện một nước đi;
  **Tự động giải** chạy đến khi kết thúc, **Dừng giải** hoặc `Esc` dừng sau bước hiện tại.
- **Xem suy luận / Ẩn suy luận** bật/tắt panel có hai tab **Manh mối** và **Các bước giải**.
  Chọn một bước để xem kết luận, truy vấn SAT, manh mối sử dụng và manh mối mới.
- **Xem thống kê** mở bảng riêng; **Xem nhật ký / Ẩn nhật ký** bật/tắt nhật ký thao tác.
- Nút gợi ý và giải được vô hiệu hóa khi bàn đã hoàn thành. Chơi lại/Ván mới vẫn sử dụng được.
- Thống kê và nhật ký mặc định ẩn. Phản hồi thao tác tự ẩn sau 4,5 giây.
- Nhãn trạng thái, manh mối và thông báo dùng tiếng Việt. Tên và nghề nghiệp giữ theo dữ liệu puzzle.
- Mã trạng thái backend và nội dung trace gốc giữ nguyên; chỉ bản trình bày được đổi nhãn.

Font được quản lý tập trung trong `ui_fonts.py`: ưu tiên Segoe UI cho tiếng Việt,
Consolas cho truy vấn; tự chọn font thay thế có sẵn khi thiếu font ưu tiên.
Các font Canvas được giữ trong suốt vòng đời UI, chữ nhỏ tối thiểu 9 pt.
Thẻ căn kích thước theo DPI, đo chiều cao dòng để tránh manh mối đè nhãn trạng thái.

GUI chỉ đọc `PublicState`, không đọc file puzzle hoặc gọi `full_clues()`.
Engine giữ dữ liệu ẩn và kiểm tra verdict bằng agent trước khi mở clue.
Đã đồng bộ `origin/main` tại commit `0d2ece1`: dùng `solver.py`, `agent.py`
và bộ kiểm thử từ GitHub. Bổ sung `agent.step(engine)` cho UI giải từng bước,
tái sử dụng cùng phép kiểm chứng của agent upstream. Không thay đổi encoder,
solver hoặc dữ liệu puzzle có sẵn. Hint dùng danh sách clue liên quan từ agent.

Giao diện chính không có khối thông tin nhân vật hoặc thống kê lặp lại dưới bàn.
Phản hồi thao tác hiện tạm thời trong 4,5 giây; nhật ký đầy đủ ở tab Suy luận.
Thống kê KB và các chỉ số trong cửa sổ **Xem thống kê** cộng dồn các lần **Giải một bước / Tự động giải**,
chỉ gồm SAT calls tìm verdict, không gồm phần engine kiểm chứng lại, Hint và thao tác
verdict thủ công. Runtime của GUI là tổng thời gian bên trong SAT solver, không phải thời gian
hoạt ảnh hay toàn bộ thời gian tương tác.
API `agent.auto_solve` của GitHub trả runtime toàn lượt giải; không so sánh trực tiếp
con số đó với tổng SAT runtime trong GUI.

## Kiểm thử

```powershell
cd Source
python -m unittest discover -s tests -v
```

Các kiểm thử GUI tạo cửa sổ Tk ẩn và cần desktop session. Để chỉ chạy backend:

```powershell
python -m unittest discover -s tests -p test_encoder.py -v
python -m unittest discover -s tests -p test_game.py -v
```

Docs: `../docs/ENCODER_GIAI_THICH.md`, `../docs/INTERFACES.md`.

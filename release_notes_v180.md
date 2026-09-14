## Train ĐỒNG LOẠT TẤT CẢ cửa sổ — không trần (thường 10/PC)

Mỗi cửa số game = 1 thread thao tác CÙNG LÚC (không xoay vòng 2s/cửa sổ như v1.7). An toàn nhờ PM mode: không active cửa sổ, không chiếm chuột vật lý, trạng thái đọc thuần memory. Cửa sổ 11+ vẫn train đủ (thanh bar GUI hiển thị 10 slot — chỉ là hiển thị).

## Trạng thái Helper / Giảm tải / MobileMod: THUẦN MEMORY — không ảnh, không active

- Cờ byte đọc qua ReadProcessMemory (majority vote) — mặc định TIN HOÀN TOÀN, không bao giờ chụp ảnh khi train
- Bật/tắt = **PM CLICK vào 4 nút HUD** hiệu chuẩn 1 lần (tab Log → 📷 Camera): ◎ Mobile · ◎ Helper · ◎ Vào GT · ◎ Thoát GT
- **MobileMod phải BẬT trước** khi bật Helper/Giảm tải — tool tự kiểm tra & bấm
- Đọc cờ không được (file flags thiếu/hỏng, offset heap cũ sau restart game) → hoãn cửa sổ + log NGUYÊN NHÂN, vòng sau quay lại — không bao giờ kẹt vô hạn
- Checkbox mới "Tin cờ memory hoàn toàn": bỏ chọn = về chế độ cũ (đối chiếu flag↔ảnh 1 lần/cửa sổ)

## GUI Camera làm lại

- Modal đúng bằng kích thước & vị trí cửa sổ chính (khit tuyệt đối, hết lệch frame)
- Bỏ 2 ảnh preview, chỉ còn 2 nút chụp (ảnh chỉ dùng cho chế độ cũ) + bảng tọa độ 4 nút HUD căn giữa
- Không còn "mất modal vĩnh viễn": đóng overlay bằng X / bấm hụt vùng quá nhỏ / lỗi lưu file — modal luôn quay lại; nhấn 📷 Camera 2 lần không đè 2-3 modal

## Watchdog & chống kẹt

- PgUp/Dừng: tắt Giảm tải TẤT CẢ cửa sổ đang bật (trước chỉ tắt 1)
- Bạn bấm Dừng giữa lúc watchdog đang mở lại cửa sổ → không bị tính là "3 lần hỏng" (hết blacklist oan 10 phút)
- 1 cửa sổ chết → chỉ hủy lượt đi của NÓ; các cửa sổ lành vẫn chạy tiếp
- Đợi watchdog: thoát đúng khi watchdog xong (hết chờ nhầm 10 phút)

## Sửa lỗi lớn tìm bằng audit 6 chiều (8 agent + 37 findings × 2 skeptic)

- Worker song song lấy hình học cửa sổ… của người khác → click sai tọa độ (blocker)
- `reset_stop()` trong mỗi lượt đi nuốt lệnh Dừng PgUp của toàn tool (blocker)
- Lệnh Tk gọi từ thread nền (treo/segfault tiềm ẩn) → counter log an toàn
- Race: pymem handle, FlagReader, per-window lock, MOUSE_BLOCK — đều đã khóa đúng chỗ
- Cấu hình cũ (`mu_goto_cfg.json`) không còn bị reset về mặc định sau khởi động lại tool; file cfg hỏng → cảnh báo trước khi ghi đè
- Chế độ vật lý (pm_mode=0) quay về chạy TUẦN TỰ — chuột thật không đánh nhau
- hwnd 64-bit bị cắt sign-extension khi so sánh focus → khai báo restype chuẩn

**Tải**: `MU-Goto.exe` — 1 file duy nhất, Run as administrator.
**Nâng cấp từ v1.7**: hiệu chuẩn lại 2 nút mới trong 📷 Camera (◎ Mobile, ◎ Thoát GT).

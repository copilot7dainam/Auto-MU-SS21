## Chế độ PostMessage (mặc định — tắt được trong tab Log → 📷 Camera)

Nghiên cứu thực chiến trên EpicMU S21 (server có NexusGuard): DLL-inject bị chặn hoàn toàn → chuyển sang **PostMessage thẳng vào hwnd game**:

- **Click chuột + lệnh chat (/move, /reset, /add…)** gửi khi cửa sổ game nằm **background/chồng lên nhau** — nhân vật vẫn đi, lệnh vẫn chạy. **Không chiếm chuột thật, không cần active cửa sổ** — bạn dùng máy bình thường trong lúc tool chạy nhiều game.
- Phím Home/Ctrl+F **không** gửi PM được (client poll DirectInput — đã chứng minh) → tool **click vào NÚT HUD** của Helper/Giảm tải; hiệu chuẩn 1 lần bằng 2 nút **"◎ Nút Helper / ◎ Nút Giảm tải"** trong modal Camera.
- Muốn về kiểu cũ (mouse_event + chặn chuột): bỏ chọn "Chế độ PostMessage".

## Trạng thái Helper/Giảm tải đọc BẰNG MEMORY — không cần nhìn màn hình

Cờ byte tìm bằng scan vi phân, lưu `mu_goto_flags.json` (Helper·GiamTai·MobileMod), đọc **majority-vote** qua ReadProcessMemory:
- Cửa sổ game minimize/bị che vẫn biết chính xác Helper/Giảm tải đã bật chưa — thay cho verify ảnh (phải kéo từng cửa sổ lên đỉnh)
- **Sanity one-shot**: lần đầu dùng cờ mỗi PID, đối chiếu với ảnh 1 lần — lệch (offset heap cũ sau restart game) → tự quay về verify ảnh
- Không có file cờ → mọi thứ chạy như v1.6

## Watchdog LI tách độc lập — chu kỳ 5 phút

- Thread riêng `mu-watchdog`, không còn nằm trong train/sync
- Cửa sổ game đã bind bị **ĐÓNG** → **dừng mọi thao tác khác trong ≤2s** (dừng tại ranh giới lệnh), mở lại cửa sổ đó trước, xong mới cho chạy tiếp
- Giới hạn: 3 lần thử / 3 phút mỗi cửa sổ — hỏng → nghỉ 10 phút, vòng sau quay lại, không kẹt chuỗi
- PgUp/nút dừng của người dùng → watchdog không tự bật lại train

## Chống kẹt bổ sung
- 1 lượt đi tới spot tối đa **3 phút** → bỏ qua, chuyển cửa sổ khác, lượt sau thử lại (không đếm vào spot-fail)
- Lượt đi bị watchdog chen → không tính là fail của nhân vật

**Tải**: `MU-Goto.exe` — 1 file duy nhất, Run as administrator.
**Lần đầu**: mở game vào world → Camera → hiệu chuẩn 2 nút HUD → dùng.

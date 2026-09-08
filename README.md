# Auto-MU-SS21 — Tự động hóa nhân vật MU Online (Season 21)

Bộ công cụ tự động hóa nhân vật **MU Online Season 21** (đã test với client
**epicmu.net / EpicMU Part2 IGCN**): auto-move tới tọa độ bất kỳ bằng click giả
lập + A*, chuỗi Train **đa cửa sổ** tự động theo level từng nhân vật, tự Reset
stat, nhận diện trạng thái game **bằng hình ảnh**, và giải mã bản đồ `.att` làm
lưới walkable 256×256.

> ⚠️ **Cảnh báo**: đọc memory và điều khiển click client game có thể vi phạm điều
> khoản dịch vụ của server. Tự chịu trách nhiệm khi sử dụng. Chạy quyền
> **Administrator** + game ở chế độ **WINDOWED**.

---

## 1. Cài đặt & chạy

### Cách 1 — file exe (khuyên dùng, không cần cài Python)

Tải **`MU-Goto.exe`** ở mục Releases — **1 file duy nhất**, bỏ vào thư mục bất
kỳ, **right-click → Run as administrator**. Trong exe đã nhúng sẵn:

- Lưới bản đồ walkable 85 map + ma trận calib isometric + danh sách spot.
- **Toàn bộ ảnh template đã chụp** (Helper / Giảm tải / Chế độ đơn giản A).

Lần chạy đầu, tool tự giải phóng các file thiếu ra **cạnh exe** — **không cần
chụp lại ảnh**. File bạn tự chụp/sửa sau đó luôn được giữ nguyên (không ghi đè).
Mở được UI kể cả khi chưa bật game.

### Cách 2 — chạy từ source

```bash
pip install pymem customtkinter numpy pillow opencv-python pyinstaller
python mu_goto.py
```

Build exe từ source:

```bash
pyinstaller --onefile --windowed --name MU-Goto --collect-all customtkinter ^
  --add-data "att_samples/_grid_cache;att_samples/_grid_cache" ^
  --add-data "mu_goto_calib.json;." --add-data "mu_goto_spots.json;." ^
  --add-data "mu_goto_helper.png;." --add-data "mu_goto_lt.png;." --add-data "mu_goto_simple_A.png;." ^
  --hidden-import pymem --hidden-import cv2 --hidden-import numpy --hidden-import PIL mu_goto.py
```

---

## 2. Giao diện MU GOTO

Cửa sổ **cố định 460×430**, phong cách macOS. Hàng đầu: nút **▶ Train** (bằng
chiều cao header tab) + 3 tab **Điều khiển / Cấu hình / Log**.

### Tab "Điều khiển"
- **▶ Train** — bật/tắt chuỗi train tự động (nhấn lần 1 chạy, nhấn lần 2 dừng).
  Xanh dương khi nghỉ → **xanh lá** khi đang chạy.
- **↺ Reset** — hẹn lịch reset stat: chỉ chạy khi nhân vật đạt **Lv 400**.
  Nút **đỏ** khi đang chờ/đang chạy; nhấn lần 2 để hủy.
  **Chuột phải** vào nút → bảng nhập 5 điểm cộng (str/agi/vit/ene/cmd).
- **📷 Chụp ảnh** — modal giữa cửa sổ, xem trước ảnh đã chụp:
  - **Helper** — icon khi Helper đang bật.
  - **Giảm tải** — icon/nút khi Giảm tải đang bật.
  - **Chế độ đơn giản — ảnh A** — ảnh chỉ báo chế độ đơn giản ĐÃ BẬT.
  - **Điểm B** — phủ màn hình trong suốt, **bấm 1 điểm** đúng nút bật đơn giản
    trong game → tool lưu tọa độ (tương đối client) vào config.
- **Thanh tiến trình** — mỗi cửa sổ game là **1 bar** bo tròn (mỏng hơn khi >5
  cửa sổ): fill **xanh lá** theo level, **đỏ khi đủ Lv 400**; tên / Lv / tọa độ
  nằm **bên trong** bar. Tự thêm/xóa bar khi mở/đóng game.

### Tab "Cấu hình"
Lưới 5 dòng train, mỗi dòng 4 cột đều 87px cách nhau 10px:
`Map` (dropdown /move) · `Spot` · `Min` · `Max` + nút `+` lưu tọa độ hiện tại.

### Tab "Log"
Log chạy **trong ứng dụng** (không xuất file): kéo con lăn chuột để xem log cũ.
Đường đi **không** in từng điểm — chỉ báo **DEN NOI** khi tới nơi.

Toàn bộ lựa chọn tự lưu và khôi phục lần sau mở tool.

---

## 3. Train đa cửa sổ (kịch bản đầy đủ)

Tool **quét liên tục** các cửa sổ game, **mỗi cửa sổ cách nhau 2s**; mỗi nhân
vật chạy chuỗi riêng theo **Lv của chính nó**:

```
Đủ Lv Max dòng → Tắt Giảm tải (verify icon MẤT, tối đa 10 lần bấm)
→ Kiểm tra Chế độ đơn giản (chỉ SAU khi đã thoát Giảm tải)
→ /move + đi tới bãi mới → Home bật Helper (verify icon) → Bật Giảm tải (verify icon)
→ quay lại quét cửa sổ khác...
→ Đủ Lv 400 → Tắt Giảm tải → đơn giản → Reset stat → về Lv 1 → chạy lại dòng 1
```

- **Không thao tác chuột thừa**: ghé cửa sổ mà nhân vật đang đứng đúng bãi +
  Giảm tải đang bật → chỉ đọc Lv rồi đi, **không click gì**.
- Ctrl+F và Home đều là **toggle** → tool **kiểm tra trạng thái bằng hình ảnh
  TRƯỚC khi bấm**, bấm tối đa 1 lần mỗi lượt kiểm tra, nghỉ tối đa 10 lần →
  không bao giờ bật/tắt nhầm.
- **PgUp** = dừng mọi thứ ngay lập tức.

## 4. Ba lớp kiểm tra trạng thái

| Lớp | Cách hoạt động |
|-----|----------------|
| **Helper** | Tới đích → chờ 1s → nhấn Home → 1s → tìm icon Helper → chưa thấy → nhấn lại → lặp (PgUp thoát) |
| **Giảm tải** | ON: không thấy icon → Ctrl+F → 1s → thấy → dừng. OFF: thấy icon → Ctrl+F → 1s → mất → dừng. Tối đa 10 lần |
| **Chế độ đơn giản** (tùy chọn) | Không thấy **ảnh A** → **click điểm B** đã cấu hình → 1s → kiểm tra lại → lặp. Chạy ngay sau khi thoát Giảm tải thành công |

- Phạm vi quét ảnh: **chỉ vùng client của cửa sổ game đang thao tác** (không
  phải toàn màn hình), ngưỡng khớp 0.90 (chống khớp nhầm nút Pause cùng màu).
- Lệnh chat (/move, /reset, /add…): **copy clipboard + Ctrl+V** (nhanh & chính
  xác hơn gõ từng ký tự), Enter mở chat → dán → Enter.
- Phím gửi bằng `keybd_event` **scan code thật** + xác minh đúng foreground
  window — cách duy nhất hoạt động với client MU này.

## 5. Cơ chế di chuyển

1. Gửi `/move <map>` → **chờ 3s** → click điểm cố định **(400,300)** ép game
   cập nhật tọa độ memory → đọc tới khi **ổn định**.
2. Xác nhận warp bằng **cả map đúng lẫn vị trí thay đổi** (chống "đến nơi" giả).
3. A* trên lưới walkable. **Mỗi click chỉ cách tâm nhân vật tối đa 5 unit**.
4. **Stuck**: 3s → giữ chuột phải 1s → 6s → giữ phải lần 2 → 9s → tính lại
   đường. Tổng stuck >5 lần / 30s chưa tới điểm / 60s chưa tới đích → nghỉ 3s →
   `/move` lại từ đầu.
5. Trước `/move`: nếu còn thấy nút Giảm tải → tắt trước.

## 6. Reset stat

- Bấm nút Reset = **hẹn giờ**: chỉ chạy khi Lv 400 (nhấn lần 2 để hủy).
- Đạt Lv 400 trong lúc Train = **tự động** chạy chuỗi, xong quay lại dòng 1.
- Chuỗi: `/reset` (chờ 5s) → `/addagi auto 32000` **trước**, rồi
  `/addstr|ene|vit|cmd auto 32000` → các lệnh `/add... <điểm>` theo cấu hình.

## 7. Quyền chuột & an toàn

- Khi tool chiếm chuột (di chuyển), **mọi click vật lý của người dùng bị chặn**
  bằng low-level hook (click do tool phát vẫn hoạt động). Thả ngay khi dừng.
- Bàn phím không bị chặn → **PgUp** luôn dừng được tool giữa chừng.
- Click: `SetCursorPos + mouse_event` (input toàn cục — SendInput/PostMessage
  đã thử và không hoạt động với client này).

---

## 8. Test toàn bộ map (`mu_goto_test.py`)

Mô phỏng pathfinding trên mọi map có sẵn, **100 lần/map**: chọn ngẫu nhiên tọa
độ hiện tại & đích (0–255), tính đường A* y hệt `mu_goto.py`. Tổng cộng
85 × 100 = 8500 lần test.

## 9. Dữ liệu bản đồ (grid)

`mu_path.load_grid(map_num)` đọc grid walkable từ
`att_samples/_grid_cache/World<map>.json`. Chưa có cache → lần đầu gọi
`node gfxdec_src/att_dec.js` giải mã `EncTerrain<map>.att`.

**Trạng thái (2026-09):** đã có grid **85 map** (1–147 trừ các map thiếu dữ
liệu); **62 map chưa giải được** do `att_dec.js` lỗi `algo2 unsupported 6`.

## 10. Kiến trúc tóm tắt

| Tầng | File chính |
|------|-----------|
| Giao diện / điều khiển | `mu_goto.py` (UI + train chain đa cửa sổ + verify ảnh) |
| Core pathfinding | `mu_path.py` (A*, `load_grid`, `make_safe`, `nearest_walkable`) |
| Giải mã & gallery | `gfxdec_src/att_dec.js`, `mu_att_html.py`, `mu_epic_gallery.py` |
| Công cụ memory | `mu_find.py`, `mu_reader.py`, `mu_scanner.py`, `mu_ptrscan.py` |
| Dữ liệu | `att_samples/_grid_cache/World*.json`, `mu_goto_calib.json` |

Xem `README_ATT.md` để biết chi tiết giải mã `.att`.

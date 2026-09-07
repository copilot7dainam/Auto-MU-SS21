# Auto-MU-SS21 — Tự động hóa nhân vật MU Online (Season 21)

Bộ công cụ tự động hóa nhân vật **MU Online Season 21** (đã test với client
**epicmu.net / EpicMU Part2 IGCN**): auto-move tới tọa độ bất kỳ bằng click giả
lập + A*, chuỗi Train tự động theo level, tự Reset stat, và giải mã bản đồ
`.att` làm lưới walkable 256×256.

> ⚠️ **Cảnh báo**: đọc memory và điều khiển click client game có thể vi phạm điều
> khoản dịch vụ của server. Tự chịu trách nhiệm khi sử dụng. Chạy quyền
> **Administrator** + game ở chế độ **WINDOWED**.

---

## 1. Cài đặt & chạy

```bash
pip install pymem customtkinter numpy pillow opencv-python
python mu_goto.py
```

Hoặc tạo shortcut Desktop tới `pythonw.exe mu_goto.py` (đã có sẵn trong repo
này: `MU GOTO.lnk`). Game phải mở ở chế độ cửa sổ (windowed), chạy quyền Admin.

File dữ liệu đi kèm (tự tạo/tự nhớ, không cần chỉnh tay):

| File | Nội dung |
|------|----------|
| `mu_goto_calib.json` | Ma trận isometric world↔pixel (do `mu_calib.py` đo) |
| `mu_goto_spots.json` | Các tọa độ train đã lưu theo từng map |
| `mu_goto_cfg.json` | 5 dòng Train + điểm cộng Reset (cài đặt UI, chỉ máy bạn) |
| `mu_goto_helper.png` | Template ảnh nút Helper (chụp bằng nút 📷) |
| `mu_goto_lt.png` | Template ảnh nút Giảm tải |
| `mu_goto_chat.png` | Template ảnh ô chat |

---

## 2. Giao diện MU GOTO

Cửa sổ **cố định 460×430**, phong cách macOS, 2 tab chuyển bằng nút đầu window:

### Tab "Điều khiển"
- **▶ Train** — bật/tắt chuỗi train tự động (nhấn lần 1 chạy, nhấn lần 2 dừng).
  Nút xanh dương khi nghỉ → **xanh lá** khi đang chạy.
- **↺ Reset** — hẹn lịch reset stat: chỉ chạy khi nhân vật đạt **Lv 400**.
  Nút **đỏ** khi đang chờ/đang chạy; nhấn lần 2 để hủy.
  **Chuột phải** vào nút → bảng nhập 5 điểm cộng (str/agi/vit/ene/cmd).
- **📷 Chụp ảnh** — chọn 1 trong 3 icon (Helper / Giảm tải / Ô chat) → phủ màn
  hình trong suốt → kéo chuột khoanh vùng icon trên game → lưu template để tool
  nhận diện bằng hình ảnh. Làm 1 lần, dùng mãi mãi.
- **Thanh tiến trình** — mỗi cửa sổ game đang mở là **1 bar** (hình dạng như nút
  Train, bo góc): nền xám, fill **xanh lá** theo level (Lv 1 = 0%, Lv 400 =
  100%), **chuyển đỏ khi đủ Lv 400**. Bên trong bar hiển thị
  `Tên · Lv — Map (x, y)` của nhân vật tương ứng. Tool tự phát hiện cửa sổ
  mới mở / đã đóng để thêm / xóa bar.

### Tab "Cấu hình"
- **Lưới 5 dòng train**, mỗi dòng 4 ô bằng nhau (87px, cách nhau 10px):
  `Map` (dropdown lệnh /move, kèm số tọa độ đã lưu màu đỏ) · `Spot` (dropdown
  tọa độ đã lưu) · `Min` · `Max` (level tối thiểu/tối đa của bãi) · nút `+`
  lưu tọa độ hiện tại vào map đang chọn.
- **Log đường đi**: liệt kê từng điểm A* (đen = chưa tới, xanh = đã tới, đỏ =
  đích cuối). Không thanh cuộn — lăn chuột để kéo.

Toàn bộ lựa chọn (map/spot/min/max, điểm reset) được **tự lưu** và khôi phục
lần sau mở tool.

---

## 3. Chuỗi Train tự động (kịch bản đầy đủ)

```
Tới bãi train → Home (bật Helper, verify bằng icon) → Bật Giảm tải (verify icon)
→ Đủ Lv Max của dòng → Tắt Giảm tải (verify icon mất) → Sang bãi kế tiếp
→ ... → Đủ Lv 400 → Tắt Giảm tải → Reset stat → Về Lv 1 → chạy lại từ dòng 1
```

- Duyệt lần lượt 5 dòng: `Lv < Min` → chờ; `Min ≤ Lv ≤ Max` → di chuyển tới
  spot và train; `Lv > Max` → bỏ qua dòng.
- Đang train mà bị đẩy lệch khỏi spot quá **5 unit** → tự đi quay lại.
- Space (thực ra là **PgUp**) = dừng mọi thứ ngay lập tức.

## 4. Cơ chế di chuyển

1. Gửi `/move <map>` → **chờ 3s** → click điểm cố định **(400,300)** trong
   client để ép game cập nhật tọa độ memory → đọc tới khi **ổn định**.
2. Xác nhận warp thành công bằng **cả map đúng lẫn vị trí thay đổi** (chống đọc
   tọa độ cũ → báo "đến nơi" giả).
3. A* trên lưới walkable → đi từng waypoint. **Mỗi click chỉ cách tâm nhân vật
   tối đa 5 unit** (chống click văng nhầm đường).
4. **Stuck (tọa độ đứng yên)**: 3s → giữ chuột phải 1s → 6s → giữ phải lần 2 →
   9s → tính lại đường từ vị trí hiện tại. Tổng stuck >5 lần → nghỉ 3s →
   `/move` lại từ đầu.
5. **30s chưa tới điểm kế tiếp** hoặc **60s chưa tới đích** → nghỉ 3s →
   `/move` lại từ đầu.
6. Trước khi `/move`: nếu còn thấy **nút Giảm tải** trên màn hình → tắt nó
   trước (Ctrl+F verify icon biến mất).
7. Trước khi gõ **mọi lệnh chat** (/move, /reset, /add...): Enter mở ô chat →
   **phải thấy template ô chat** mới được gõ; không thấy → Esc → Enter → kiểm
   tra lại (tối đa 5 vòng).
8. **Home**: chỉ nhấn **1 lần khi tới đúng tọa độ đích** (±1.5 unit).

## 5. Reset stat

- Bấm nút Reset = **hẹn giờ**: chờ tới Lv 400 mới chạy (không chạy ngay).
- Đạt Lv 400 trong lúc Train = **tự động** chạy chuỗi, xong Train quay lại
  dòng 1 (nhân vật về Lv 1).
- Chuỗi lệnh: `/reset` (chờ 5s) → `/addstr|agi|vit|ene|cmd <điểm>` theo cấu
  hình (chuột phải nút Reset để sửa, mặc định 500) → 5 lệnh
  `/add... auto 32000`, mỗi lệnh cách 1s.

## 6. Quyền chuột & an toàn

- Khi tool đang chiếm chuột (di chuyển), **mọi thao tác chuột vật lý của người
  dùng bị chặn** bằng low-level hook (click do tool phát vẫn hoạt động) — tránh
  bấm nhầm làm lệch đường. Thả chuột ngay khi dừng.
- Bàn phím không bị chặn → **PgUp** luôn dừng được tool giữa chừng.
- Cơ chế click: `SetCursorPos + mouse_event` (input toàn cục — cách duy nhất
  hoạt động với client MU này; SendInput/PostMessage đã thử và bị lỗi).

---

## 7. Test toàn bộ map (`mu_goto_test.py`)

Mô phỏng pathfinding trên mọi map có sẵn, **100 lần/map**: chọn ngẫu nhiên tọa
độ hiện tại & đích (0–255), tính đường A* y hệt `mu_goto.py` (snap
`nearest_walkable` + safe-margin, thử lại grid gốc nếu bị kẹt). Cửa sổ hiển
thị: map hiện tại, lần thử, % tiến trình, số lần thành/thất bại, log từng map,
nút Dừng. Tổng cộng 85 × 100 = 8500 lần test.

## 8. Dữ liệu bản đồ (grid)

`mu_path.load_grid(map_num)` đọc grid walkable từ
`att_samples/_grid_cache/World<map>.json`. Chưa có cache → lần đầu gọi
`node gfxdec_src/att_dec.js` giải mã `EncTerrain<map>.att`.

**Trạng thái (2026-09):** đã có grid **85 map** (1–147 trừ các map thiếu dữ
liệu); **62 map chưa giải được** do `att_dec.js` lỗi `algo2 unsupported 6`
với cipher-6.

## 9. Kiến trúc tóm tắt

| Tầng | File chính |
|------|-----------|
| Giao diện / điều khiển | `mu_goto.py` (toàn bộ UI + train chain + verify ảnh) |
| Core pathfinding | `mu_path.py` (A*, `load_grid`, `make_safe`, `replan`, `nearest_walkable`) |
| Giải mã & gallery | `gfxdec_src/att_dec.js`, `mu_att_html.py`, `mu_epic_gallery.py` |
| Công cụ memory | `mu_find.py`, `mu_reader.py`, `mu_scanner.py`, `mu_ptrscan.py` |
| Dữ liệu | `att_samples/_grid_cache/World*.json`, `mu_goto_calib.json` |

Xem `README_ATT.md` để biết chi tiết giải mã `.att`.

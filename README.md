# Auto-MU-SS21 — Tự động hóa nhân vật MU Online (Season 21)

Bộ công cụ tự động hóa nhân vật **MU Online Season 21** (đã test với client
**epicmu.net**): auto-move tới tọa độ bất kỳ bằng click giả lập + A*, giải mã
bản đồ `.att`, và tìm đường A* trên lưới walkable 256×256.

> ⚠️ **Cảnh báo**: đọc memory và điều khiển click client game có thể vi phạm điều
> khoản dịch vụ của server. Tự chịu trách nhiệm khi sử dụng. Chạy quyền
> **Administrator** + game ở chế độ **WINDOWED 800×600**.

---

## 1. Cài đặt

```bash
pip install -r requirements.txt   # nếu có
# cần node.exe để giải mã .att lần đầu (đã có cache sẵn, thường không cần)
```

Chạy app chính:

```bash
python mu_goto.py
```

---

## 2. Dữ liệu bản đồ (grid)

`mu_path.load_grid(map_num)` đọc grid walkable từ:

```
att_samples/_grid_cache/World<map>.json   # {"index","isExt","grid":[65536 int]}
```

Nếu chưa có cache, lần đầu sẽ gọi `node gfxdec_src/att_dec.js` giải mã
`att_samples/World<map>/EncTerrain<map>.att` → JSON.

**Trạng thái hiện tại (2026-09-05):**
- Đã có sẵn grid của **85 map** trong `_grid_cache/` (và `World<map>/grid.json`):
  map 1–147, trừ các map chưa có dữ liệu giải mã.
- **62 map chưa có grid** (không có dữ liệu ở bất kỳ nguồn nào):
  `6, 13–18, 20–24, 26–30, 33, 36, 37, 44–46, 48–51, 53–56, 61, 67, 76–79,
  84–91, 93, 97, 98, 100, 102, 104–110, 112, 125–128`.
- `att_dec.js` hiện lỗi `algo2 unsupported 6` với cipher-6 → chưa giải được các
  map trên (cần sửa decoder).

---

## 3. Test toàn bộ map (`mu_goto_test.py`)

Mô phỏng pathfinding trên mọi map có sẵn, **100 lần/map**:

- Với mỗi lần: chọn ngẫu nhiên tọa độ hiện tại & đích (0–255), tính đường A* y
  hệt `mu_goto.py` (snap `nearest_walkable` + safe-margin, thử lại grid gốc nếu
  bị kẹt).
- Thành công = tìm được đường (≥2 điểm). Thất bại = ngược lại (thường do random
  trúng 2 điểm bị tường kẹt hoàn toàn).
- Cửa sổ hiển thị: map hiện tại, lần thử, thanh % tiến trình, số lần thành
  công/thất bại, và log từng map. Có nút **Dừng**.

```bash
python mu_goto_test.py
```

Tổng cộng 85 × 100 = 8500 lần test.

---

## 4. Kiến trúc tóm tắt

| Tầng | File chính |
|------|-----------|
| Giao diện / điều khiển | `mu_goto.py`, `mu_gui.py`, `mu_calib.py` |
| Core pathfinding | `mu_path.py` (A*, `load_grid`, `make_safe`, `replan`, `nearest_walkable`) |
| Giải mã & gallery | `gfxdec_src/att_dec.js`, `mu_att_html.py`, `mu_epic_gallery.py` |
| Công cụ memory | `mu_find.py`, `mu_reader.py`, `mu_scanner.py`, `mu_ptrscan.py` |
| Dữ liệu | `att_samples/_grid_cache/World*.json`, `mu_goto_calib.json` |

Xem `README_ATT.md` để biết chi tiết giải mã `.att`.

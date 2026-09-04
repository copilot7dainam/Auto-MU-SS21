# Auto MU SS21 — Bộ công cụ MU Online Season 21 (EpicMU)

Bộ script Python điều khiển nhân vật MU Online (epicmu.net, client Season 21)
**tự động di chuyển đến tọa độ bất kỳ**, vòng qua tường/nước nhờ đọc bản đồ
`.att` và tìm đường A*. Kèm theo tool hiệu chuẩn (calibration) và tool đọc tọa
độ real-time.

---

## 1. Tổng quan các file

| File | Vai trò |
|------|---------|
| `mu_goto.py` | **App chính** — nhập Map # + tọa độ đích, tự click đưa nhân vật tới nơi. Tích hợp A*. |
| `mu_path.py` | Module A* trên lưới walkable 256×256 lấy từ file `.att` (đã giải mã). |
| `mu_calib.py` | Tool hiệu chuẩn: quét 360° để fit ma trận `world = A × screen_px` (MU isometric). |
| `mu_goto_calib.json` | Kết quả calibration (ma trận A + nghịch đảo). Do `mu_calib.py` sinh ra. |
| `README_ATT.md` | Giải thích chi tiết cách giải mã file `.att` (FileCryptor/ModulusCryptor + BUX mask). |
| `att_samples/` | Thư mục chứa file `.att` thô + bản đồ đã giải (`_grid_cache/*.json`) + ảnh PNG xem trước. |
| `gfxdec_src/` | Source Node.js giải mã `.att` (dùng bởi `mu_path.py` khi chưa có cache). |

---

## 2. Cơ chế hoạt động — MU là isometric

Điểm quan trọng nhất: **MU dùng bản đồ isometric**. Click theo 1 hướng trên màn
hình → nhân vật đi **chéo** trong world. Nên 1 pixel ≠ 1 hệ số k; phải dùng
**ma trận 2×2**:

```
worldX = a00 * dx_px + a01 * dy_px
worldY = a10 * dx_px + a11 * dy_px
```

Nghịch đảo để tính ngược: từ delta world (đích − hiện tại) ra delta pixel cần
click. Ma trận này được đo bằng `mu_calib.py` (xem §4).

Camera luôn bám nhân vật → nhân vật luôn ở **trung tâm cửa sổ**. Với cửa sổ
800×600: tọa độ pixel trung tâm = `(L + W/2, T + H/2)`. Mọi click đều tính offset
so với tâm này.

---

## 3. Luồng hoạt động của `mu_goto.py`

```
Nhập Map # + (X,Y đích)
        │
        ▼
load_grid(map) ──► lưới walkable 256×256 (từ cache .att hoặc giải mã)
        │
        ▼
A* (hiện tại → đích) ──► danh sách waypoint (tile) ──► tọa độ world
        │  (nếu đích là tường → snap tile walkable gần nhất)
        ▼
Vòng lặp di chuyển (cadence-click):
  - đọc tọa độ hiện tại từ memory (0xB80AF60 / 0xB80AF64)
  - chọn waypoint A* phía trước, giữ 1 điểm "aim" ~4 unit trước mặt
  - chuyển delta world → delta pixel qua ma trận A⁻¹
  - click trái (SetCursorPos + mouse_event) tại tâm + offset
  - click nhịp 0.30s / hoặc khi đi được 1.5u / hoặc bị kẹt 2s
  - tới waypoint → chuyển waypoint kế (log đổi xanh)
  - tới đích (cách <1.5u) → "DEN NOI"
```

### Chi tiết từng phần

- **Đọc tọa độ**: `pymem` đọc 4 byte float tại `CUR_X=0xB80AF60`, `CUR_Y=0xB80AF64`
  (địa chỉ tuyệt đối, client không bật ASLR). Cần quyền **Admin + SeDebugPrivilege**.
- **Click chuột**: `SetCursorPos` + `mouse_event(LEFTDOWN/LEFTUP)`, sau đó trả con
  trỏ về vị trí cũ (chỉ chiếm vài chục ms, không "cướp" chuột lâu). Đã thử
  `PostMessage/SendMessage` nhưng **epicmu bỏ qua** (game đọc `GetCursorPos`/raw
  input), nên chỉ click chuột thật mới hiệu quả.
- **Di chuyển mượt**: click theo nhịp cố định + lookahead (luôn nhắm 1 điểm phía
  trước), tránh khựng giật. Ngưỡng dead-zone của MU (~click <30–70px bị bỏ qua)
  nên waypoint A* đủ xa nhau là an toàn.
- **Snap tường**: nếu (X,Y) nhập vào là ô không đi được, `nearest_walkable` tìm
  tile walkable gần nhất và báo trong log.

---

## 4. Hiệu chuẩn (`mu_calib.py`)

Chỉ chạy **1 lần** (hoặc khi đổi độ phân giải/máy). Sinh `mu_goto_calib.json`.

Cơ chế:
1. Bạn **tự click** vào trung tâm nhân vật → lấy gốc pixel.
2. Quét 360° (mặc định 24 tia, mỗi 15°). Mỗi tia **tăng dần** pixel
   (10,20,30…250px) cho đến khi nhân vật bắt đầu đi (world delta ≥ 1 unit).
3. Ghi lại cặp `(offset_px, world_delta)`.
4. Fit ma trận A bằng least-squares: `world = A × screen_offset`.
5. Lưu A, nghịch đảo, và sai số fit vào JSON.

```powershell
python mu_calib.py --rays 24 --maxpx 250
```

Nếu bỏ qua bước này, `mu_goto.py` dùng ma trận fallback
`A=((0.01494,0.02190),(0.01728,-0.02415))` (đo thực tế trước đó).

---

## 5. Bản đồ `.att` & A* (`mu_path.py` + `README_ATT.md`)

- Mỗi map = lưới **256×256 tile**, 1 tile = 1 game-unit.
- File `EncTerrainN.att` mã hóa; `mu_path.py` gọi `node att_dec.js` giải mã →
  JSON grid. Kết quả cache tại `att_samples/_grid_cache/WorldN.json` (lần sau
  không cần node).
- Bit chặn: `NoMove(0x0004) | NoGround(0x0008) | Water(0x0010)` → không đi được.
- `astar(walk, start, goal)` trả danh sách waypoint 8 hướng (heapq).
- `coord_to_tile` / `tile_to_coord`: world ↔ tile (làm tròn).

Test nhanh pathfinding không cần game:
```powershell
python mu_path.py 1 10 10 177 180
```

---

## 6. Cách chạy

### Chuẩn bị (1 lần)
```powershell
# PowerShell quyền Admin
cd C:\Users\Admin\Auto-MU-SS21
pip install pymem
# cần Node.js 22+ nếu map chưa có cache _grid_cache
```

### Dùng auto-move
1. Mở game **WINDOWED** (800×600), nhân vật đứng Lorencia.
2. `python mu_goto.py`
3. Map # = `1`, nhập Target X / Y, nhấn **OK - Di toi**.
4. Theo dõi log: waypoint đổi xanh khi tới, "DEN NOI" khi kết thúc.

### Đọc tọa độ real-time (tool cũ)
`python mu_gui.py` — bảng mỗi cửa sổ game 1 dòng X/Y/Z.

---

## 7. Yêu cầu & lưu ý

- Windows 10/11, Python 3.x, **chạy quyền Administrator**.
- `pip install pymem`; Tkinter (có sẵn trong Python chuẩn).
- Node.js 22+ chỉ cần khi **đầu tiên** giải mã 1 map chưa có cache.
- Offset `0xB80AF60` đúng với client epicmu S21 tại thời điểm viết. Nếu server
  cập nhật client, dùng `mu_find.py` tìm lại địa chỉ.
- Đọc memory / điều khiển click client game có thể vi phạm điều khoản dịch vụ
  của server. **Tự chịu trách nhiệm** khi sử dụng.

---

## 8. Cấu trúc thư mục

```
Auto-MU-SS21/
├─ mu_goto.py          # auto-move chính (A*)
├─ mu_path.py          # module A* / load .att
├─ mu_calib.py         # hiệu chuẩn ma trận isometric
├─ mu_goto_calib.json  # kết quả calibration
├─ mu_gui.py           # monitor tọa độ real-time
├─ mu_find.py / mu_reader.py / mu_scanner.py / mu_ptrscan.py  # tool tìm offset
├─ README.md           # file này
├─ README_ATT.md       # giải mã .att chi tiết
├─ att_samples/        # .att thô + cache grid JSON + PNG xem trước
└─ gfxdec_src/         # source Node.js giải mã .att
```

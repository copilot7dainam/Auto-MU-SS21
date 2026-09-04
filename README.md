# Auto-MU-SS21 — Tự động hóa nhân vật MU Online (Season 21)

Bộ công cụ tự động hóa nhân vật **MU Online Season 21** (đã test với client
**epicmu.net**). Gồm 3 nhóm chức năng chính:

1. **Auto-move** — đưa nhân vật tới tọa độ bất kỳ bằng click giả lập + A*.
2. **Bản đồ / Pathfinding** — giải mã file `.att` và tìm đường A* trên lưới 256×256.
3. **Công cụ chẩn đoán memory** — đọc tọa độ real-time, quét memory tìm offset,
   hiệu chuẩn ma trận isometric.

> ⚠️ **Cảnh báo pháp lý**: đọc memory và điều khiển click client game có thể vi phạm
> điều khoản dịch vụ của server. Tự chịu trách nhiệm khi sử dụng. Cần chạy quyền
> **Administrator** + game ở chế độ **WINDOWED 800×600**.

---

## 1. Tổng quan kiến trúc

```
┌─────────────────────────────────────────────────────────────────────┐
│                        LỚP GIAO DIỆN / ĐIỀU KHIỂN                    │
│   mu_goto.py (app chính)        mu_gui.py (monitor tọa độ)           │
│   mu_calib.py (hiệu chuẩn)                                        │
├─────────────────────────────────────────────────────────────────────┤
│                        LỚP LOGIC / CORE                             │
│   mu_path.py  (A*, load grid, make_safe, replan, nearest_walkable)  │
│   mu_att_html.py / mu_epic_gallery.py / mu_att_view.py  (gallery)  │
├─────────────────────────────────────────────────────────────────────┤
│                        LỚP CÔNG CỤ memory                          │
│   mu_find.py  mu_reader.py  mu_scanner.py  mu_ptrscan.py            │
│   mu_debug_click.py                                                │
├─────────────────────────────────────────────────────────────────────┤
│                        LỚP DỮ LIỆU / GIẢI MÃ                       │
│   gfxdec_src/ (Node.js: att_dec.js, batch.ts, run.ts, terrain/, crypto/)│
│   att_samples/WorldN/EncTerrainN.att  →  _grid_cache/WorldN.json   │
│   mu_goto_calib.json  (ma trận hiệu chuẩn)                          │
└─────────────────────────────────────────────────────────────────────┘
```

**Luồng dữ liệu cốt lõi** (auto-move):

```
att_samples/WorldN/EncTerrainN.att
        │  (lần đầu) node att_dec.js giải mã
        ▼
att_samples/_grid_cache/WorldN.json   ←─── cache grid walkable 256×256
        │  mu_path.load_grid()
        ▼
A* (mu_path.astar)  ──► waypoint (tile) ──► tọa độ world
        │
        ▼
mu_goto.goto(): vòng lặp đọc memory → tính delta → click giả lập
        │
        ▼
main.exe (game) di chuyển nhân vật
        │
        └──► (loop) đọc lại tọa độ từ memory (0xB80AF60 / 0xB80AF64)
```

---

## 2. Danh mục đầy đủ chức năng (từng file)

| File | Nhóm | Chức năng chính | Cách chạy |
|------|------|-----------------|-----------|
| `mu_goto.py` | Auto-move | **App chính.** GUI chọn map + nhập (X,Y) → A* + click giả lập đưa nhân vật tới nơi. Xử lý kẹt, gửi phím khi đến. | `python mu_goto.py` |
| `mu_path.py` | Pathfinding | Module A* trên lưới walkable 256×256. | `python mu_path.py <map> <sx> <sy> <tx> <ty>` |
| `mu_calib.py` | Hiệu chuẩn | Quét 360° fit ma trận `world = A × screen_px` (isometric) → `mu_goto_calib.json`. | `python mu_calib.py --rays 24` |
| `mu_gui.py` | Monitor | Bảng theo dõi X/Y/Z real-time của mọi cửa sổ game (Treeview). ⚠️ đang lỗi offset (xem §7). | `python mu_gui.py` |
| `mu_find.py` | Memory scan | Quét float toàn module theo workflow Cheat Engine: `scan` / `watch` / `rec`. | `python mu_find.py` |
| `mu_reader.py` | Memory read | Đọc X/Y/Z theo địa chỉ tuyệt đối hoặc pointer chain. | `python mu_reader.py` |
| `mu_scanner.py` | Memory scan | Quét float theo target, in địa chỉ khớp (dạng one-shot). | `python mu_scanner.py` |
| `mu_ptrscan.py` | Memory scan | Pointer scan (numpy) tìm chain `base→…→target`; kiểm tra ASLR qua PE header. | `python mu_ptrscan.py` |
| `mu_debug_click.py` | Test | Kiểm tra click có tới được game không (so sánh pos trước/sau). | `python mu_debug_click.py` |
| `mu_att_view.py` | Gallery | Đọc 1 file `.att` (bản rõ) → xuất PNG walkable + thống kê %. | `python mu_att_view.py <file.att>` |
| `mu_att_html.py` | Gallery | Sinh `att_gallery.html` duyệt **76 map `.att` rõ** (OpenMU TerrainN). | `python mu_att_html.py` |
| `mu_epic_gallery.py` | Gallery | Sinh `epic_gallery.html` duyệt **89 map S21** (đã giải mã), phóng to, đổi tên map trên web. | `python mu_epic_gallery.py` |
| `gfxdec_src/att_dec.js` | Giải mã | JS thuần giải mã `EncTerrain*.att` (TEA/ThreeWay/RC6 + BUX mask). | `node att_dec.js file.att` |
| `gfxdec_src/batch.ts` | Giải mã | Giải mã TẤT CẢ `.att` trong `att_samples/World*` → PNG. | `node --experimental-transform-types batch.ts` |
| `gfxdec_src/run.ts` | Giải mã | Test 1 file (hardcode World10). | `node --experimental-transform-types run.ts` |
| `gfxdec_src/terrain/formats/ATTReader.ts` | Giải mã | Entry chính (port từ xulek): phát hiện loại mã hóa + parse. | — |
| `gfxdec_src/crypto/*` | Giải mã | Các cipher: `file-cryptor`, `modulus-cryptor`, `tea`, `threeway`, `rc6`, `rc5`, `cast5`, `mars`, `idea`, `gost`. | — |
| `README_ATT.md` | Tài liệu | Giải thích sâu cách giải mã `.att` (FileCryptor/ModulusCryptor + BUX). | — |

---

## 3. Chi tiết từng module & mọi hàm

### 3.1. `mu_goto.py` — Auto-move (app chính)

Giao diện Tkinter (`main()`), chạy vòng lặp di chuyển trong thread nền (`goto()`).

**Các hàm chính**
- `enable_debug()` — cấp `SeDebugPrivilege` để `ReadProcessMemory` vào process game.
- `find_window()` — liệt kê `EnumWindows`, trả về `(L, T, W, H)` của cửa sổ `main.exe`.
- `rd_pos(pm)` — đọc float X/Y tại `0xB80AF60` / `0xB80AF64` (4 byte little-endian).
- `click_at(sx, sy, right=False)` — `SetCursorPos` + `mouse_event(LEFTDOWN/UP)`. Tool
  **giữ quyền chuột** suốt quá trình (không trả về vị trí cũ); nhấn **Space** để dừng.
- `focus_game()` — `SetForegroundWindow` vào game để phím gửi tới đúng cửa sổ.
- `send_home()` — gửi **Home** (Helper) qua `keybd_event`.
- `send_ctrl_f()` — gửi **Ctrl+F** (Giảm tải) qua `keybd_event`.
- `send_keys_on_arrive(do_home, do_ctrl_f)` — gửi Home rồi Ctrl+F theo tick người dùng.
- `check_stop_key()` — phát hiện phím **Space** (`GetAsyncKeyState` bit cao).
- `reset_stop()` — xóa cờ dừng giữa 2 lần chạy.
- `load_matrix()` — đọc `world_per_px` từ calib; nghịch đảo thành `inv`. Nếu file sai
  key → fallback `((0.01494,0.02190),(0.01728,-0.02415))`.

**Giao diện (`main()`)**
- Dropdown **Map** tự động lấy từ các thư mục `WorldN/` hiện có, hiển thị tên
  (`Lorencia (1)`…) qua `MAP_NAMES`.
- Ô nhập **Target X / Y**.
- Dòng **Hiện tại** cập nhật mỗi 1s (poll live).
- Danh sách **waypoint** (màu: đen=chưa tới, xanh=lên tới, đỏ=đích cuối).
- 2 tick **Helper (Home)** / **Giảm tải (Ctrl+F)** gửi khi đến nơi (mặc định tắt cả 2).
- Nút **OK - Di tới** (chạy thread) và **STOP**.

**Vòng lặp di chuyển (`goto()`)**
1. Click tâm màn hình ép game cập nhật tọa độ → đọc pos hiện tại.
2. `load_grid(map, keep_points=[start, goal])` → lưới walkable (có cache JSON).
3. `nearest_walkable` snap đích/tọa độ nếu rơi vào ô chặn.
4. `astar` → danh sách waypoint tile → tọa độ world.
5. Cadence-click: đọc pos → chọn waypoint phía trước, giữ 1 điểm "aim" ~4 unit trước
   mặt → `delta world → delta pixel` qua `A⁻¹` → click tại tâm + offset.
6. Ngưỡng: `ARRIVE=1.5u` coi như đến nơi; `REACH_WP=2.5u` chuyển waypoint kế.
7. Nhịp click: mỗi `0.1s` hoặc khi đi được `MOV_AHEAD=6u`; `MIN_GAP=0.10s`.
8. Đến nơi → log **"DEN NOI"** + gửi phím (nếu tick).

**Xử lý kẹt (stuck)** — phát hiện nếu 2s (`STUCK_T`) tọa độ không đổi:
| Bậc | Điều kiện | Hành động |
|-----|-----------|-----------|
| 1–6 | `stuck_count ≤ 6` | Tăng khoảng cách click gấp **2,3,4,5,6** (cap = toàn cửa sổ), đồng thời `replan` vòng qua tọa độ kẹt (block bán kính 4 tile). |
| 7+ | hết 6 bậc vẫn kẹt | **Phương án 2**: lui lại `BACK_N=6` điểm trên đường cũ, rồi `replan` tìm đường vòng. Nếu vẫn không được → thử grid gốc (`safe_margin=0`). |
| Thoát | `moved > 0.1` | Nhân vật thực sự di chuyển → reset về mặc định. |

Nếu `astar` trả đường <2 điểm do bị safe-margin loại, code tự thử lại trên **grid gốc**
(`safe_margin=0`) trước khi báo "không tìm được đường".

### 3.2. `mu_path.py` — Pathfinding / giải mã grid

- `load_grid(map_num, force=False, safe_margin=1, keep_points=None)` — trả
  `(grid2d, is_ext)` với `grid[y][x]=bool walkable`. Ưu tiên cache JSON, nếu thiếu gọi
  `node att_dec.js` giải mã lần đầu. `safe_margin` loại bỏ ô cách vật cản < N tile;
  `keep_points` giữ start/goal luôn walkable.
- `make_safe(walk, margin=1, keep=None)` — lọc grid, bỏ ô sát tường để đường không dính
  vật cản khi click thực tế.
- `astar(walk, start, goal)` — A* 8 hướng trên lưới 256×256, heapq, heuristic
  **octile** (admissible → đường ngắn nhất). Trả list `(x,y)` tile hoặc `None`.
- `replan(walk, start, goal, blocked=None, radius=3)` — block tạm vùng quanh `blocked`
  (tọa độ kẹt) ép đường vòng; đảm bảo start/goal vẫn walkable.
- `coord_to_tile(x, y)` — world → tile (`round` + `% 256`).
- `nearest_walkable(walk, tx, ty, max_r=30)` — tile walkable gần nhất (khi đích là tường).
- `tile_to_coord(tx, ty)` — tile → tọa độ world (float).
- `_decode_att(map_num)` — gọi `node att_dec.js` giải mã 1 map → `_grid_cache/WorldN.json`.
- `__main__` — test nhanh: `python mu_path.py <map> <sx> <sy> <tx> <ty>`.

**Bit chặn**: `NoMove(0x0004) | NoGround(0x0008) | Water(0x0010)` → không đi được.

### 3.3. `mu_calib.py` — Hiệu chuẩn ma trận isometric

Chỉ chạy **1 lần** (hoặc khi đổi độ phân giải/máy). Sinh `mu_goto_calib.json`.

- `wait_for_user_click()` — overlay fullscreen, bạn **tự click** vào trung tâm nhân vật
  → lấy gốc pixel.
- `wait_arrival(pm, prev0, t_click, timeout)` — đo nhân vật có thực sự đi không.
- `probe(pm, cx, cy, L,T,W,H, angle, off, right, timeout)` — click 1 hướng/số px, trả
  `(world_dx, world_dy, moved?)`.
- `solve_A(pairs)` — least-squares fit ma trận 2×2 `world = A × screen_offset`.
- `main()` — argparse: `--rays 24 --maxpx 250 --step 10 --gap 1.0 --wait 2.0
  --timeout 12.0 --button left`. Quét 360° (mỗi tia tăng dần 10,20,…px đến khi nhân vật
  đi ≥1 unit), ghi `(offset_px, world_delta)`, fit A, lưu `world_per_px` + `px_per_world`
  + sai số fit `resid`.

> Lưu ý: file này ghi key `world_per_px` (format mới) — nếu chạy lại sẽ **ghi đè và
> được `mu_goto.load_matrix()` sử dụng**. Xem §7 về file calib bundled đang lỗi format.

### 3.4. `mu_gui.py` — Monitor tọa độ real-time

- `enable_debug_privilege()` — cấp `SeDebugPrivilege` (cần Admin để đọc tiêu đề cửa sổ
  IL cao và mở handle game).
- `enum_window_titles()` — `{pid: tieu_de_dai_nhat}` qua `EnumWindows` + `GetWindowTextW`.
- `list_games()` — chỉ lấy cửa sổ visible thuộc process `main.exe`.
- `rd_float(pm, off)` — đọc float tại `0x400000 + off`.
- `class Monitor` (Tkinter Treeview):
  - `get_pm(pid)` — cache `Pymem` theo PID.
  - `tick()` — mỗi `0.25s` cập nhật X/Y/Z; mỗi `1.5s` quét lại danh sách cửa sổ.
  - `refresh_games()` — thêm/xóa dòng theo PID, cập nhật tiêu đề khi đổi (sau đăng nhập).
  - `destroy()` — đóng các handle Pymem.

⚠️ **Đang lỗi offset** (xem §7): đọc `0xB40AF60 + 0x400000 = 0xF40AF60` → tọa độ rác.

### 3.5. Công cụ memory (tìm lại offset khi server cập nhật client)

| Tool | Hàm chính | Workflow |
|------|-----------|----------|
| `mu_scanner.py` | `read_region`, `scan_floats_near` | Quét one-shot theo target → in địa chỉ khớp (nhanh, cơ bản). |
| `mu_find.py` | `full_scan`, `narrow_scan`, `watch`, `rec` | Full scan → Next scan (narrow) → Watch (tìm địa chỉ thay đổi khi đi) → Rec (quan sát). Giống Cheat Engine. |
| `mu_reader.py` | `resolve`, `rd_ptr` | Đọc X/Y/Z liên tục theo địa chỉ tuyệt đối (`ABSOLUTE_ADDR=0xb80af60`) hoặc pointer chain (`CHAR_STRUCT_CHAIN`). |
| `mu_ptrscan.py` | `read_module`, `pe_is_aslr`, BFS `preimages` | Đọc PE header kiểm tra ASLR; nếu không ASLR → offset tĩnh; nếu ASLR → BFS ngược tìm chain `base→deref→…→target` (numpy). |
| `mu_debug_click.py` | `find_window`, `rd_pos` | Click trái lệch tâm 150px → so sánh pos trước/sau để biết click có hiệu lực. |

> Offset `0xB80AF60` chỉ đúng với epicmu S21 tại thời điểm viết; client khác/season khác
> dùng `mu_find.py` / `mu_ptrscan.py` tìm lại.

### 3.6. Giải mã bản đồ (`gfxdec_src/`) — chi tiết ở `README_ATT.md`

- `att_dec.js` — JS thuần, `readATT(buf)` trả `{version, index, isExt, grid}`. Pipeline:
  ModulusCryptor (RC6→ThreeWay, ~80% map extended) hoặc FileCryptor (rolling XOR, ~20%
  map standard), rồi **BUX mask** `[0xFC,0xCF,0xAB]`. Dùng làm module cho `mu_path`.
- `run.ts` — test 1 file (hardcode `World10/EncTerrain10.att`).
- `batch.ts` — giải mã tất cả `att_samples/World*/EncTerrain*.att` → `*.att.png`
  (dùng `zlib` viết PNG, không cần thư viện ngoài).
- `terrain/formats/ATTReader.ts` + `crypto/*.ts` — port nguyên gốc từ
  [xulek/muonline-bmd-viewer](https://github.com/xulek/muonline-bmd-viewer).
  Cần **Node.js 22+**: `node --experimental-transform-types batch.ts`.

### 3.7. Gallery & xem bản đồ

- `mu_att_view.py` — `parse` (bỏ 3 byte header), `classify` (bitmask OpenMU), `to_png`
  (PIL hoặc fallback PPM), `stats` (%), `decrypt_enc` (thử XOR 3-byte, chỉ đúng bản rõ).
  Chạy không tham số để xem danh sách mẫu.
- `mu_att_html.py` — sinh `att_samples/att_gallery.html` duyệt **76 map `.att` rõ**
  (OpenMU `TerrainN`), nhóm theo vùng, hover xem tọa độ tile `(x,y)`.
- `mu_epic_gallery.py` — sinh `att_samples/epic_gallery.html` duyệt **89 map S21** (sau
  khi loại trùng lặp md5). Tính năng:
  - **Click ảnh** → phóng to modal (90% viewport).
  - **Hover** → tọa độ tile; **Click** trên ảnh phóng to → chọn/chép tọa độ (Copy chuột /
    Copy đã chọn).
  - **Đổi tên map**: click dòng tên (xám) → `prompt` → lưu `localStorage` (`mu_map_names`,
    không mất khi tải lại; xóa trắng = revert). Tên tùy chỉnh cũng hiện trên tiêu đề modal.

---

## 4. Cơ chế hoạt động sâu

### 4.1. MU là isometric — tại sao cần ma trận 2×2

Click 1 hướng trên màn hình → nhân vật đi **chéo** trong world. 1 pixel ≠ 1 hệ số k.
Do đó dùng ma trận biến đổi tuyến tính:

```
worldX = a00·dx_px + a01·dy_px
worldY = a10·dx_px + a11·dy_px
```

Nghịch đảo A để tính ngược: từ **delta world** (đích − hiện tại) ra **delta pixel** cần click.

- Camera luôn bám nhân vật → nhân vật ở **trung tâm cửa sổ**.
- Với cửa sổ 800×600: tâm pixel = `(L + W/2, T + H/2)`. Mọi click tính offset so với tâm.
- Ma trận A đo bằng `mu_calib.py` (xem §3.3) hoặc lấy fallback cố định
  `((0.01494,0.02190),(0.01728,-0.02415))` khi chưa có file calib hợp lệ.

### 4.2. Đọc tọa độ & click

- `pymem` đọc 4 byte float tại offset tuyệt đối (client epicmu S21 không bật ASLR).
  Cần quyền **Admin + SeDebugPrivilege** (`enable_debug()`).
- Click: `SetCursorPos` + `mouse_event(LEFTDOWN/LEFTUP)`. `PostMessage/SendMessage` bị
  epicmu bỏ qua (game đọc `GetCursorPos`/raw input) → chỉ click chuột thật mới hiệu quả.
- Tool giữ quyền chuột suốt quá trình; nhấn **Space** để dừng và trả quyền.
- Dead-zone của MU (click <30–70px thường bị bỏ) → waypoint A* đủ xa nhau là an toàn.

---

## 5. Bảng tên map S21 (`MAP_NAMES`)

Dropdown `mu_goto.py` và gallery dùng bảng tên chuẩn (nguồn: MapList Webzen):

| ID | Tên | ID | Tên | ID | Tên |
|----|-----|----|-----|----|-----|
| 1 | Lorencia | 2 | Dungeon | 3 | Devias |
| 4 | Noria | 5 | Lost Tower | 7 | Arena |
| 8 | Atlans | 9 | Tarkan | 10 | Devil Square |
| 11 | Icarus | 12 | Blood Castle | 19 | Chaos Catsle |
| 25 | Kalima2 | 31 | Valley of Loren 2 | 32 | Land of Trials |
| 34 | Aida | 35 | Crywolf 3 | 38 | Kanturu Ruins |
| 39 | Kanturu 1 (Remain) | 40 | Kanturu 2 (Refinery Tower) | 42 | Barracks of Balgass |
| 43 | Balgass Refuge | 47 | Illusion Temple 1 | 52 | Elbeland |
| 57 | Swamp of Calmness | 58 | Raklion | 59 | Hatchery (Raklion Boss) |
| 64 | Vulcanus | 65 | Duel Arena | 69 | Double Goer |
| 80 | Loren Market | 81 | Karutan 1 | 82 | Karutan 2 |
| 92 | Acheron | 94 | Null | 95 | Debenter |
| 96 | Debenter | 99 | Illusion Temple League | 101 | Urk Mountain |
| 103 | Event | 111 | Nars | 113 | Ferea |
| 114 | Nixie Lake | 117 | Deep Dungeon 1 | 118 | Deep Dungeon 2 |
| 119 | Deep Dungeon 3 | 120 | Deep Dungeon 4 | 121 | Deep Dungeon 5 |
| 122 | Test Area | 124 | Kubera Mine | 129 | Atlans Abyss |
| 130 | Atlans Abyss 2 | 131 | Atlans Abyss 3 | 132 | Scotch Canyon |
| 133 | Redsmoke Icarus | 134 | Arenil Temple | 135 | Gray Aida |
| 136 | Old Kethotum | 137 | Old Kethotum | 138 | Kanturu Underground |
| 139 | Ignis Vulcanus | 140 | Battle Boss | 141 | Bloody Tarkan |
| 142 | Tormenta Island | 143 | Twisted Karutan | 144 | Kardamahal Underground Temple |
| 145 | Swamp of Despair | 146 | Aquilas Santuary | 147 | Forgotten Ralkion |

> Tổng 69 map có tên. Các map chưa đặt tên (World41, 60, 62, 63, 66, 68, 70–75, 83,
> 115, 116, 123…) không nằm trong bảng, khi chạy tool sẽ hiện số World và xếp cuối danh sách.
> Tên được cập nhật từ `Test.htm` (đổi tên trực tiếp trên gallery).

---

## 6. Cài đặt & cách chạy

### Chuẩn bị (1 lần)
```powershell
# PowerShell quyền Admin
cd C:\Users\Administrator\Auto-MU-SS21
pip install pymem numpy
# Node.js 22+ chỉ cần khi ĐẦU TIÊN giải mã 1 map chưa có cache
```

### Auto-move
1. Mở game **WINDOWED** (800×600), nhân vật đứng Lorencia.
2. `python mu_goto.py`
3. Chọn Map (tên) + nhập Target X / Y → **OK - Di toi**.
4. Theo dõi log: waypoint đổi xanh khi tới, "DEN NOI" khi kết thúc. **Space** = dừng.

### Đọc tọa độ real-time
`python mu_gui.py` — bảng mỗi cửa sổ game 1 dòng X/Y/Z (⚠️ xem §7).

### Test pathfinding (không cần game)
```powershell
python mu_path.py 1 10 10 177 180
```

### Hiệu chuẩn lại ma trận (khi đổi máy/độ phân giải)
```powershell
python mu_calib.py --rays 24 --maxpx 250
```

---

## 7. Lỗi đã biết & giải pháp

| Vấn đề | Mô tả | Trạng thái / Sửa |
|--------|-------|------------|
| Calib JSON bundled sai format | `mu_goto_calib.json` đi kèm dùng key `matrix`/`inverse`, trong khi `load_matrix()` đọc `world_per_px` → KeyError → luôn dùng ma trận fallback cứng. | **Đã tự sửa**: chạy `python mu_calib.py` 1 lần sẽ ghi đè file với key `world_per_px` và được sử dụng. File bundled cũ chỉ là điểm khởi đầu. |
| `mu_gui.py` đọc tọa độ rác | Dùng `X_OFFSET=0xB40AF60` + `read_bytes(0x400000+off)` = `0xF40AF60` (sai). Phải là `0xB80AF60` tuyệt đối. | **Chưa sửa code**. Sửa 1 dòng: `X_OFFSET=0xB80AF60` (và Y/Z +4/+8), bỏ `+0x400000` trong `rd_float`. Hoặc dùng `mu_reader.py`/`mu_debug_click.py` thay thế để đọc pos. |
| `coord_to_tile` modulo | `% N` wrap âm thầm nếu world coord <0 hoặc >255. | Ít gặp (Lorencia 0–255). |
| `mu_goto.py.bak` | File backup thừa (12KB). | Nên xóa/ignore. |
| README cũ ghi "trả con trỏ về vị trí cũ" | Code thực tế giữ chuột (chỉ Space mới trả). | Tài liệu đã cập nhật ở §3.1/§4.2. |

---

## 8. Giải mã toàn bộ map (`grid.json`)

Mỗi `att_samples/WorldN/` chứa file `.att` mã hóa. Script giải mã toàn bộ
thành JSON lưới 256×256 (tile → thuộc tính 16-bit), lưu tại 2 nơi:

- `att_samples/_grid_cache/WorldN.json` — `mu_path.load_grid` đọc trực tiếp.
- `att_samples/WorldN/grid.json` — bản sao để xem/lưu từng World.

### Pipeline

1. `decode_all_maps.py` (Python) — gọi `mu_path.load_grid(force=True)` cho mỗi
   `WorldN`. Dùng engine giải mã JS (`gfxdec_src/att_dec.js`). **Chỉ giải được
   các map dùng 3 thuật toán Modulus là TEA(0)/ThreeWay(1)/RC6(4)** hoặc
   FileCryptor. Kết quả ~11/86 map.
2. `gfxdec_src/batch_json.ts` (TypeScript) — dùng **engine TS đầy đủ**
   (`terrain/formats/ATTReader.ts`) hỗ trợ cả 8 thuật toán Modulus
   (CAST5/RC5/MARS/IDEA/GOST). Chạy:

   ```powershell
   cd gfxdec_src
   node --experimental-transform-types batch_json.ts
   ```

   Kết quả: **85/86 World** được giải (bản cập nhật gần nhất).

### Cách chọn file `.att`

`batch_json.ts` ưu tiên: `EncTerrainN_.att` → `EncTerrainN.att` → `EncTerrain.att`.
(Vài map như World7 chỉ giải được từ bản `EncTerrain7_.att`.)

### Trường hợp đặc biệt / chưa giải được

- **World67**: file `EncTerrain67.att` dùng lược đồ mã hóa **không thuộc**
  FileCryptor cũng như ModulusCryptor (8 thuật toán đều thử đều ra rác). Đây là
  định dạng mới hơn chưa có engine tương ứng trong repo này → **chưa có grid**.
  `mu_goto.py` sẽ báo lỗi rõ ràng ("Loi load map 67: ...") nếu bạn chọn map này,
  không crash.
- Một số map có nhiều biến thể `.att` (vd World1 có `EncTerrain1/11/12/_Server_64k`);
  picker chỉ lấy 1 file ưu tiên, đủ để pathfinding.

### Khi thêm map mới

Copy `WorldN/` chứa `.att` vào `att_samples/`, chạy `batch_json.ts` lại. Nếu map
mới cũng lỗi giống World67 → cần bổ sung engine giải mã tương ứng (tham khảo repo
[xulek/muonline-bmd-viewer](https://github.com/xulek/muonline-bmd-viewer) hoặc
GFxDec S21).

---

## 8. Cấu trúc thư mục

```
Auto-MU-SS21/
├─ mu_goto.py            # auto-move chính (GUI + A* + click loop + stuck handling)
├─ mu_path.py            # module A* / load .att / make_safe / replan
├─ mu_calib.py           # hiệu chuẩn ma trận isometric → mu_goto_calib.json
├─ mu_goto_calib.json    # kết quả calibration (bundled đang lỗi format, xem §7)
├─ mu_gui.py             # monitor tọa độ real-time (đang lỗi offset, xem §7)
├─ mu_find.py            # scan/watch/rec (workflow Cheat Engine)
├─ mu_reader.py          # đọc X/Y/Z (absolute hoặc pointer chain)
├─ mu_scanner.py         # quét float one-shot
├─ mu_ptrscan.py         # pointer scan + kiểm tra ASLR
├─ mu_debug_click.py     # test click tới game không
├─ mu_att_view.py        # viewer 1 file .att → PNG + thống kê
├─ mu_att_html.py        # gallery 76 map .att rõ → att_gallery.html
├─ mu_epic_gallery.py    # gallery 89 map S21 → epic_gallery.html (phóng to, đổi tên)
├─ README.md             # file này
├─ README_ATT.md         # giải mã .att chi tiết
├─ mu_goto.py.bak        # backup thừa (nên xóa)
├─ att_samples/          # .att thô + cache grid JSON + PNG xem trước
│   ├─ WorldN/EncTerrainN.att(.png)
│   ├─ *.att / *.att.png (76 map rõ OpenMU)
│   ├─ _grid_cache/WorldN.json   # (hiện có World1.json; map khác giải mã on-demand)
│   ├─ att_gallery.html
│   └─ epic_gallery.html
└─ gfxdec_src/           # source Node.js giải mã .att (port xulek/muonline-bmd-viewer)
    ├─ att_dec.js        # JS thuần (TEA/ThreeWay/RC6 + BUX)
    ├─ batch.ts / run.ts
    ├─ terrain/formats/ATTReader.ts
    ├─ crypto/           # file-cryptor, modulus-cryptor, tea, threeway, rc6, rc5,
    │                     #   cast5, mars, idea, gost
    └─ utils/Logger.ts   # logger rỗng (để chạy TS)
```

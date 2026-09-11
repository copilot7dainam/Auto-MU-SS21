# Auto-MU-SS21 — Tự động hóa nhân vật MU Online (Season 21)

Bộ công cụ tự động hóa nhân vật **MU Online Season 21** (đã test với client
**epicmu.net / EpicMU Part2 IGCN**): auto-login **đa tài khoản** bằng nhận diện
hình ảnh, auto-move tới tọa độ bất kỳ bằng click giả lập + A*, chuỗi Train
**đa cửa sổ** tự động theo level từng nhân vật, tự Reset stat, và giải mã bản đồ
`.att` làm lưới walkable 256×256.

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

### Tự nâng cấp từ tool MU-Login cũ

Lần chạy đầu, tab **LI** tự đọc `config.json` của MU-Login cũ (nếu có, nằm cạnh
app hoặc `~/mu_login`): launcher path, tiêu đề cửa sổ, tọa độ, tài khoản —
**không phải cài lại**. Key đã tồn tại không bao giờ bị ghi đè.

---

## 2. Giao diện

Cửa sổ **cố định 280×520**, phong cách macOS. Hàng đầu: nút **▶ Train** + 4 tab
**RR / Spot / Log / LI**. Mọi lựa chọn tự lưu, khôi phục lần sau mở tool.

### Tab "RR" — Điều khiển
- **▶ Train** — bật/tắt chuỗi train tự động (nhấn lần 1 chạy, nhấn lần 2 dừng).
  Xanh dương khi nghỉ → **xanh lá** khi đang chạy.
- Reset stat **tự động** khi train chạm Lv 400 (không còn nút hẹn — cấu hình
  điểm cộng ở nút **➕ Add Point** trong tab Log).
- **Thanh tiến trình** — **lưới 10 hàng cố định**, mỗi nhân vật **1 hàng duy
  nhất không bao giờ đổi chỗ**: slot gắn theo **tên nhân vật** (relogin sinh
  hwnd mới vẫn về đúng hàng cũ), không phụ thuộc thứ tự Z-order cửa sổ. Bar bo
  tròn cao đúng 1/10 grid; fill **xanh lá** theo level, **đỏ khi đủ Lv 400**;
  tên + Lv nằm **bên trong** bar. **Chấm trạng thái vẽ trong bar, đè trên
  đầu thanh tiến trình**: **đỏ** = cửa sổ đang được duyệt/thao tác, **xanh** =
  cửa sổ sống chưa duyệt. Hàng trống giữ chỗ (không giãn hàng khác). Nền **xanh
  lá nhạt** = cửa sổ đang bind với một tài khoản LI.

### Tab "Spot" — Cấu hình chuỗi train
- **1 grid choán toàn tab**, hàng đầu = dropdown **Account**: chọn "(Chung)" hoặc
  từng username (khai báo ở tab LI) → **5 dòng train riêng theo từng account**.
- Mỗi dòng: `Map` (dropdown lệnh /move) · `Spot` (dropdown tọa độ đã lưu) ở
  hàng trên, `Min` · `Max` (level vào bãi) ở hàng dưới. Grid tự lưu mọi sửa đổi.
- Tên nhân vật trong title cửa sổ khớp `char_name` tài khoản nào → train tự áp
  đúng 5 dòng của tài khoản đó.

### Tab "Log"
- 2 listbox cuộn độc lập trong ứng dụng (không xuất file): **lịch sử reset**
  trên, **log tiến trình** dưới. Kéo con lăn chuột để xem log cũ.
- Lịch sử reset ghi gọn: `Tên reset ( avg X phút / N lần )`.
- Đường đi **không** in từng điểm — chỉ báo **DEN NOI** khi tới nơi.
- **➕ Add Point** — modal danh sách lệnh `/add`, **kéo hàng ⋮⋮ để đổi thứ tự
  chạy** (thả chuột là lưu ngay); checkbox `auto` + ô điểm từng stat; nút **Lưu**
  đóng dialog. Chuỗi reset chạy đúng thứ tự hiển thị ở đây.
- **📷 Camera** — modal chọn ảnh cần chụp, xem trước ảnh đã lưu:
  - **Helper** — icon khi Helper đang bật.
  - **Giảm tải** — icon khi Giảm tải đang bật.
  - **Chế độ đơn giản — ảnh A** — ảnh chỉ báo chế độ đơn giản ĐÃ BẬT.
  - **Điểm B** — phủ màn hình trong suốt, **bấm 1 điểm** đúng nút bật đơn giản
    trong game → tool lưu tọa độ (tương đối client) vào config.

### Tab "LI" — Auto-login
- **➕ Account** — modal nhập đầy đủ tài khoản **trùng kích thước + vị trí cửa sổ
  chính**: Username, Mật khẩu (ẩn), Tên nhân vật, Server 1–5, checkbox Kích hoạt.
  Enter = Lưu, Esc = Hủy, chống trùng username.
- **Danh sách tài khoản** — mỗi dòng **chỉ hiện Username** (chấm xanh = enabled,
  xám = tắt). **Bấm vào username** → mở modal sửa / xóa (🗑).
- **⚙ Config** — modal cùng size cửa sổ chính:
  - `Launcher path` (+ nút **Chon** file), `Title launcher` / `Title game` (regex).
  - 📷 **Play / Credit / Connect** — chụp template 3 nút (kéo vùng trên ảnh chụp
    launcher/game, scale 2× cho dễ chọn).
  - ◎ **Login, S1–S5, P1–P4** — lấy tọa độ: tool chụp cửa sổ game, hiện fullscreen,
    **bấm 1 điểm** trên ảnh → lưu tọa độ tương đối. (P1–P4 = 4 bước sau Connect.)
  - **Luu** — ghi toàn bộ vào `mu_goto_li.json`.
- **▶ Chay login** — chạy lần lượt từng tài khoản enabled.

## 3. Luồng auto-login (tab LI)

```
Launcher: đã tồn tại (ke ca minimize) → maximize + active → bấm Play → minimize
          chưa tồn tại                → mới mở exe duy nhất 1 lần
→ chờ của số game MOI → chờ ảnh Credit (load xong)
→ bam Login → bam Server N → GO TUNG PHIM user / Tab / pass / Enter (khong clipboard — MU cache mat khau Vinh Vien)
→ tim anh Connect → bam → bam P1..P4 (bo qua neu chua cau hinh)
→ DOI TITLE = [Char:..] xac nhan da vo WORLD → Ctrl+F bat Giam tai (verify icon)
```

- **Deadline 5 phút/toàn luồng**: qua giờ hoặc PgUp → **dong cửa sổ game → làm
  lại từ đầu**, không giới hạn số lần thử.
- **Mọi click đều xác minh**: active đúng cửa sổ, đưa chuột tới điểm, poll tới 8s
  cho đến khi cửa sổ đích thực sự nằm dưới con trỏ mới bấm — chống click rơi vào
  lúc game đang chuyển màn hình.
- **Watchdog relogin**: cửa sổ game đã bind với tài khoản mà biến mất (rơi
  mạng/đóng nhầm) → tool **tự đăng nhập lại** — cả khi đang Train (dừng train
  tạm thời, thread riêng) lẫn khi nghỉ. Fail ≥3 lần → nghỉ 60s rồi thử lại.
- Login tranh chấp với Train được chặn bằng cờ `LI_BUSY` — không bao giờ hai
  luồng cùng bấm bàn phím một lúc.

## 4. Train đa cửa sổ (kịch bản đầy đủ)

Tool **quét liên tục** các cửa sổ game, **mỗi cửa sổ cách nhau 2s**; mỗi nhân
vật chạy chuỗi riêng theo **Lv của chính nó** + cấu hình riêng theo account:

```
Đủ Lv Max dòng → Tắt Giảm tải (verify icon MẤT, tối đa 10 lần bấm)
→ Kiểm tra Chế độ đơn giản (chỉ SAU khi đã thoát Giảm tải)
→ /move + đi tới bãi mới → Home bật Helper (verify icon) → Bật Giảm tải (verify icon)
→ quay lại quét cửa sổ khác...
→ Đủ Lv 400 → Tắt Giảm tải → đơn giản → Reset stat → về Lv 1 → chạy lại dòng 1
```

- **Không thao tác chuột thừa**: ghé cửa sổ mà nhân vật đang đứng đúng bãi +
  Giảm tải đang bật → chỉ đọc Lv rồi đi, **không click gì** — nhưng có chốt
  chống "đúng spot giả": tọa độ đọc từ memory **chỉ cập nhật khi có thao tác
  trong client**, nên tool đồng thời **so map hiện tại với map của bãi** (sai
  map = bắt buộc về lại bãi, không cần click), và **tối đa 5 lượt fast-path
  liên tiếp** rồi buộc click điểm (400,300) + đọc `pos_stable` xác minh lại —
  nhân vật bị lôi/chết về thị trấn không thể bị tưởng nhầm còn đứng tại bãi.
- Ctrl+F và Home đều là **toggle** → tool **kiểm tra trạng thái bằng hình ảnh
  TRƯỚC khi bấm**, bấm tối đa 1 lần mỗi lượt kiểm tra, nghỉ tối đa 10 lần →
  không bao giờ bật/tắt nhầm.
- **PgUp** = dừng mọi thứ ngay lập tức.

## 5. Ba lớp kiểm tra trạng thái

| Lớp | Cách hoạt động |
|-----|----------------|
| **Helper** | Tới đích → chờ 1s → nhấn Home → 1s → tìm icon Helper → chưa thấy → nhấn lại → lặp (PgUp thoát). Không verify được ảnh → bấm Home 1 lần (best effort) |
| **Giảm tải** | ON: không thấy icon → Ctrl+F → 1s → thấy → dừng. OFF: thấy icon → Ctrl+F → 1s → mất → dừng. Tối đa 10 lần |
| **Chế độ đơn giản** (tùy chọn) | Không thấy **ảnh A** → **click điểm B** đã cấu hình → 1s → kiểm tra lại → lặp. Chỉ chạy **sau khi đã thoát Giảm tải thành công** |

**Nguyên tắc "không chắc thì không đi tiếp":**
- Ảnh chụp để so khớp luôn **kéo đúng cửa sổ thao tác lên đỉnh trước khi chụp**
  — chống trường hợp cửa sổ game khác đè lên làm nhận diện sai.
- Giảm tải **chưa thoát được** (10 lần bấm / không verify được ảnh) → tool
  **dừng chuỗi ở cửa sổ đó**, hoãn sang lượt duyệt sau; **không** /move,
  **không** reset, **không** chạy bước kế tiếp.
- Mỗi click xác minh **cửa sổ dưới con trỏ đúng là cửa sổ đang làm việc**
  (WindowFromPoint + BringWindowToTop) — chống thao tác nhầm cửa sổ khi nhiều
  game chồng nhau. **Kéo lên đỉnh 3 lần vẫn bị che → THẢ click** (bỏ qua bước,
  vòng sau thử lại) — bấm nhầm cửa sổ khác tốn hại hơn mất 1 bước.
- Mỗi lệnh chat đi qua **5 lớp guard focus** (trước Enter, sau Enter, trước dán,
  Enter gửi…) — mất focus ở bất kỳ bước nào = **không coi là đã gửi**, thử lại
  tối đa 3 vòng, mỗi vòng Esc dọn ô chat dở dang.
- Toạ độ khớp ảnh được quy chiếu **window-relative** (trừ offset title bar) →
  click trúng tâm nút, không lệch.

- Phạm vi quét ảnh: **chỉ vùng client của cửa sổ game đang thao tác** (không
  phải toàn màn hình), ngưỡng khớp 0.90 (chống khớp nhầm nút Pause cùng màu).
- Lệnh chat (/move, /reset, /add…): **copy clipboard + Ctrl+V** (nhanh & chính
  xác hơn gõ từng ký tự), Enter mở chat → dán → Enter.
- Phím gửi bằng `keybd_event` **scan code thật** + xác minh đúng foreground
  window — cách duy nhất hoạt động với client MU này.

## 6. Cơ chế di chuyển

1. Gửi `/move <map>` → **chờ 3s** → click điểm cố định **(400,300)** ép game
   cập nhật tọa độ memory → đọc tới khi **ổn định**.
2. Xác nhận warp bằng **cả map đúng lẫn vị trí thay đổi** (chống "đến nơi" giả).
3. A* trên lưới walkable. **Mỗi click chỉ cách tâm nhân vật tối đa 5 unit**.
4. **Stuck**: 3s → giữ chuột phải 1s → 6s → giữ phải lần 2 → 9s → tính lại
   đường. Tổng stuck >5 lần / 30s chưa tới điểm / 60s chưa tới đích → nghỉ 3s →
   `/move` lại từ đầu.
5. Trước `/move`: nếu còn thấy nút Giảm tải → tắt trước.

## 7. Reset stat

- Đạt Lv 400 trong lúc Train = **tự động** chạy chuỗi, xong quay lại dòng 1.
  Không còn nút hẹn Reset.
- Chuỗi: `/reset` (chờ 5s) → từng lệnh `/add...` **cách nhau 1s**, thứ tự chạy
  = đúng thứ tự danh sách trong modal **➕ Add Point** (kéo ⋮⋮ để đổi). Mặc định:
  5 dòng `/addstr|agi|vit|ene|cmd 500` rồi 5 dòng `auto 32000`.
- **Lệnh không gửi được = chuỗi dừng ngay** và **không ghi lịch sử** — không
  bao giờ báo "reset xong" giả khi /reset đã chạy mà thiếu lệnh /add.

## 8. Quyền chuột & an toàn

- Khi tool chiếm chuột (di chuyển), **mọi click vật lý của người dùng bị chặn**
  bằng low-level hook (click do tool phát vẫn hoạt động). Thả ngay khi dừng.
- Bàn phím không bị chặn → **PgUp** luôn dừng được tool giữa chừng.
- Click: `SetCursorPos + mouse_event` (input toàn cục — SendInput/PostMessage
  đã thử và không hoạt động với client này).

---

## 9. File config (cạnh exe)

| File | Nội dung |
|------|----------|
| `mu_goto_cfg.json` | 5 dòng "(Chung)" + `add_lines` (danh sách & thứ tự lệnh /add, sửa bằng kéo thả ở ➕ Add Point) |
| `mu_goto_li.json` | Tài khoản LI + launcher + template + tọa độ Login/S1-5/P1-4 |
| `mu_goto_spots.json` | Danh sách tọa độ /move đã lưu theo map |
| `rows_map` (trong cfg) | 5 dòng train **riêng từng account** |
| `li_templates/*.png` | Ảnh Play / Credit / Connect |

## 10. Test toàn bộ map (`mu_goto_test.py`)

Mô phỏng pathfinding trên mọi map có sẵn, **100 lần/map**: chọn ngẫu nhiên tọa
độ hiện tại & đích (0–255), tính đường A* y hệt `mu_goto.py`. Tổng cộng
85 × 100 = 8500 lần test.

## 11. Dữ liệu bản đồ (grid)

`mu_path.load_grid(map_num)` đọc grid walkable từ
`att_samples/_grid_cache/World<map>.json`. Chưa có cache → lần đầu gọi
`node gfxdec_src/att_dec.js` giải mã `EncTerrain<map>.att`.

**Trạng thái (2026-09):** đã có grid **85 map** (1–147 trừ các map thiếu dữ
liệu); **62 map chưa giải được** do `att_dec.js` lỗi `algo2 unsupported 6`.

> **Bắt buộc phải nhúng `att_samples/map_index.json`** khi build exe — file này
> ánh xạ MapID → tên file grid (54/85 map có tên không theo quy ước
> `WorldN_Grid.json`). Thiếu nó, exe không `load_grid` được.

## 12. Kiến trúc tóm tắt

| Tầng | File chính |
|------|-----------|
| Giao diện / điều khiển / auto-login | `mu_goto.py` (UI + train chain + verify ảnh + LI) |
| Core pathfinding | `mu_path.py` (A*, `load_grid`, `make_safe`, `nearest_walkable`) |
| Giải mã & gallery | `gfxdec_src/att_dec.js`, `mu_att_html.py`, `mu_epic_gallery.py` |
| Công cụ memory | `mu_find.py`, `mu_reader.py`, `mu_scanner.py`, `mu_ptrscan.py` |
| Dữ liệu | `att_samples/_grid_cache/World*.json`, `mu_goto_calib.json` |

Xem `README_ATT.md` để biết chi tiết giải mã `.att`.

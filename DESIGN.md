# DESIGN — PM Mode: thao tác nền + trạng thái bằng memory (v1.7.0)

## Bối cảnh nghiên cứu (đã chứng minh bằng test thật trên EpicMU S21 / NexusGuard)

1. **DLL inject CHẾT**: NexusGuard phát hiện remote thread (LoadLibrary=NULL,
   game bị đóng ngay). Mọi kỹ thuật inject (stub, classic, wow-powershell)
   đều fail → BỎ.
2. **PostMessage nền HOẠT ĐỘNG** với:
   - CLICK chuột: client đọc tọa độ từ lParam của message → PM CLICK
     (300,300) làm nhân vật đi khi game ở background ✓ (test thật)
   - Ô CHAT: Enter mở → gõ → Enter, toàn bộ qua message queue ✓ (test thật,
     user xác nhận "các lệnh chat thực hiện rất tốt")
3. **PostMessage KHÔNG hoạt động** với phím nóng Home / Ctrl+F / F2:
   client POLL GetAsyncKeyState/DirectInput — không đọc queue. → Phím nóng
   phải thay bằng PM CLICK vào NÚT HUD tương ứng (cần hiệu chuẩn tọa độ nút).
4. **Trạng thái Helper/GiamTai/MobileMod đọc được từ HEAP** bằng cờ byte:
   offset đã quét thành công bằng scan vi phân (HookProbe/helper_watch.py),
   file `mu_goto_flags.json` (copy từ helper_watch_offsets.json).
   Đọc bằng ReadProcessMemory thuần — không cần active/cửa sổ nhìn thấy.
   Majority vote: ON khi >½ số byte đọc được của nhóm = 1 (chống byte giặc).
   Lưu ý: offset HEAP có thể đổi khi restart process → tool cảnh báo khi
   flag đọc ra None/loạn, fallback về ảnh.

## Kiến trúc mới — "PM mode" (config `pm_mode`, mặc định 1)

| Chức năng | Cũ (physical) | Mới (PM mode) |
|---|---|---|
| Click di chuyển | SetCursorPos+mouse_event, cần foreground + WindowFromPoint + MOUSE_BLOCK | `pm_click(hwnd, client_x, y)` — nền, đa cửa sổ, không chiếm chuột |
| Lệnh chat | clipboard + Ctrl+V + 5 lớp guard focus | `pm_chat(hwnd, cmd)` = Enter→type→Enter bằng message |
| Home/Ctrl+F | keybd_event scan | pm_click vào NÚT HUD hiệu chuẩn (`hud_helper`, `hud_lt` trong cfg, tọa độ client) |
| Verify Helper/GiamTai | cv2 matchTemplate ảnh (cần window trên đỉnh) | cờ memory majority vote (`mu_state`) |
| Chuột người dùng | hook WH_MOUSE_LL chặn khi chạy | KHÔNG CẦN chặn nữa ở pm_mode (tool không đụng chuột thật) |

## Interface ĐÔNG CỨNG (2 module mới — agent làm, MUỐN SỬA PHẢI SỬA Ở ĐÂY TRƯỚC)

### mu_pm.py — PostMessage input layer (stdlib ctypes thuần)
```python
WM_* constants
def key_params(vk) -> (lparam_down, lparam_up)   # scan MapVirtualKeyW, ext bit24
def pm_move(hwnd, cx, cy)                        # WM_MOUSEMOVE
def pm_click(hwnd, cx, cy, right=False) -> bool  # MOVE→DOWN→60ms→UP; toa do CLIENT
def pm_keydown(hwnd, vk) / pm_keyup(hwnd, vk) / pm_tap(hwnd, vk, hold=0.05)
def pm_hold(hwnd, vk) / pm_release(hwnd, vk)     # giu chuot phai stuck: pm_hold(0x02)
def pm_type_char(hwnd, ch)                       # VK path neu state==0, nguoc WM_CHAR
def pm_text(hwnd, text, gap=0.02)
def pm_chat(hwnd, cmd, open_delay=0.35) -> bool  # Enter → text → Enter (KHONG Esc)
def pm_ctrl_f(hwnd)                              # Ctrl down, F tap, Ctrl up  (tho ng;
                                                 #  khong hieu luc voi client poll — giu
                                                 #  cho client khac, van send van duoc)
def screen_to_client(hwnd, sx, sy) -> (cx, cy) | None
```
KHONG import mu_goto. Test: selftest trong `if __name__` (assert key_params
Home == 0x1470001, scan 0x47 ext bit24; screen_to_client vs window rect).

### mu_state.py — doc co trang thai tu memory
```python
FLAGS_FILE = mu_goto_flags.json  cạnh file  {name: ["0xAABBCCDD", ...]}
class FlagReader:                      # 1 instance/process game (pid)
    def __init__(self, pid): ...       # pymem lazy + auto-reconnect
    def read(self, name) -> bool | None  # majority vote; None = khong doc duoc
    def close(self)
def vote(vals) -> bool | None          # ham module-level (reusable, co test)
```
Test: `if __name__`: vote([1,1,0]) True; vote([1,0]) False; vote all None→None.

### mu_goto.py integration (TÔI làm sau khi 2 module xong — KHÔNG giao agent)
- `PM_MODE = [1]` doc tu cfg `pm_mode`; `HUD_BTNS = {"helper": (x,y), "lt": (x,y)}`
  trong mu_goto_cfg.json, nut chup trong 📷 Camera modal → dung
  li_capture_coord_via_cursor() hien co (doi ten = thu toa do client khi
  game dang duoc kich hoat 1 lan cuoi) — them 2 item "hud_helper", "hud_lt".
- `click_at`: neu PM_MODE + hwnd → chuyen sang pm_click (screen→client);
  giu nguyen duong physical khi pm_mode=0.
- `send_chat_command`: neu PM_MODE → pm_chat(hwnd, cmd) (khong clipboard,
  khong guard focus, van tra False khi hwnd chet).
- `send_home_verified` / `send_ctrl_f_on/off`: neu PM_MODE + co flag reader
  → vong lap: doc flag; sai → pm_click nut HUD; verify lai 1s; toi da 10.
  Thieu file flag / thieu hud coord → fallback duong cu (anh + phim that).
- `run_visit`: LT_ON.get → flag reader; fast-path giu nguyen logic map-check.
- MOUSE_BLOCK: van install (pm_mode=0 con dung); goto() chi tang count khi
  khong PM_MODE.
- train_chain van tuan tu (2s/cua so) — PM mode da khong chiem chuot nen
  song song hoa toan bo la buoc ke tieu (v1.8), CHUA lam bay gio.
- LI login flow: GIU NGUYEN physical (man login khong co flag/ HUD nut),
  rieng click P1..P4/Server co the thu pm qua li_click_rel — CHAM: giu cu.

## File dau vao
- `mu_goto_flags.json` ← copy tu HookProbe/helper_watch_offsets.json
  (Helper 7, GiamTai 20 — NGUOI DUNG se tinh clean sau audit, tool phai
  chay duoc voi so byte bat ky).

## Rủi ro đã biết
- Heap offset doi theo LAN CHAY GAME → state.py phai bao None khi doc ra
  gia tri-la-la → mu_goto tu fallback anh. (Pointer chain = bai rieng.)
- NexusGuard có thể soi window message? Chưa thấy bằng chứng; chat/click
  PM đã chạy OK thực tế nhiều phút.
- pm_type: ky tu dac biet (Tieng Viet) — khong can, lenh chat ASCII het.

## Trạng thái công việc
- [x] DESIGN.md này
- [x] mu_pm.py        (agent + bo sung pm_mouse_hold)
- [x] mu_state.py     (agent + khop ten mem Giam Tai/GiamTai)
- [x] copy flags json + nhung vao spec/seed
- [x] mu_goto.py integration + build exe (v1.7.0-pm) — Desktop

## Ghi chu tich hop thuc te (khac it voi k hoach)
- them SANITY ONE-SHOT trong state_read: lan dau dung flags cua moi pid, doi
  chieu GiamTai(flag) voi icon(anh) 1 lan → khop=trust flags, lech=vo hieu
  flags pid do (offset heap cu sau restart), bao ve khoi doc rac.
- _goto_once: PM mode bo focus_game(); goto()/right_hold_1s()/MOUSE_BLOCK chi
  chan chuot vat ly khi KHONG PM.
- send_chat_command: PM path = pm_chat Enter→gõ→Enter (3 lan thu), khong
  clipboard/focus. LI li_click_rel cung co PM path (quy window→client).
- GUI: modal Camera co checkbox PM mode + trang thai flags + 2 nut hieu chuan
  "◎ Nút Helper / ◎ Nút Giảm tải" (chup diem tren anh → luu toa do CLIENT).
- LI dang nhap: GIU nguyen nhieu buoc lien (chua PM hoa toan bo LI flow).

## Viec con lai (v1.9+)
- ~~Train SONG SONG 1-thread/cua-so~~ ✓ v1.8 (thread-local WINCTX/RUN, watchdog tach).
- ~~4 nut HUD hieu chuan~~ ✓ (Mobile/Helper/Vào GT/Thoát GT — MobileMod bat BUOC truoc Helper/GiamTai).
- PM hoa toan bo LI login flow (nut Login/Server/P1-4 + typing login).
- pointer chain cho offset heap (chong restart game mat flag) — hook_probe
  mu_state dang doc absolute heap addr.
- kiem thu: mo game → Camera → hieu chuan 4 nut HUD → Train → log flag +
  nhan vat tu di chuyen o TAT CA cua so DONG THOI.

## v1.8 — POM mode thuan memory + train SONG SONG (audit 6 chieu + 37 findings)
- YEU CAU: TAT CA cua so = N thread cung luc (thuong 10/PC, khong tran co dinh); kiem tra Helper/GiamTai/MobileMod
  THUAN MEMORY (khong anh, khong active cua so); bat/tat = PM CLICK toa do
  nut HUD da hieu chuan; MobileMod phai BAT truoc Helper/GiamTai.
- FLAG_TRUST=1 MAC DINH: khong bao gio chup anh khi train. Fail do flag
  (thieu/hong json, offset heap da cu) → hoan cua so + log nguyen nhan
  (WATCHDOG tab LI: thread rieng 5', cua so CHET → PAUSE toan bo, mo lai
  ≤3 lan/3', nghi 10' → vong sau).
- FLAG_TRUST=0 (= nut "che do cu" trong code): sanity flag↔anh one-shot/pid;
  lech → VE verify anh + phim that (duong vat ly van con, pm_mode=0).
- Audit-fix quan trong: rect refresh theo win_hwnd() (tung worker), MOVE_ABORT
  = SET hwnd (chi cua so chet bi huy luot di, 5 cua lanh di tiep), _goto_once
  BO reset_stop() (nuot PgUp da thread), capture_icon/early-return PHAI goi
  on_done (modal khong con an Vinh Vien), proc_box.size() → _LOG_LINES (Tk
  lenh tu thread la = treo), races: for_win_lock/state_reader/get_pm_for +
  MOUSE_BLOCK deu co lock; PgUp → tat Giam tai MOI cua so; pm_mode=0 → train
  TUAN TU (click vat ly khong tranh duoc); GetForegroundWindow/GetModuleHandleW
  khai bao restype (HWND 64-bit khong bi sign-extend).

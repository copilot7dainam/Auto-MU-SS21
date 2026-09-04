"""
MU GOTO - Di chuyen den toa do mong muon bang click gia lap.

Cach hoat dong don gian:
  1. Doc toa do hien tai cua nhan vat tu memory.
  2. Ban nhap toa do dich (X, Y).
  3. Tool tinh delta world = dich - hien tai, chuyen sang delta pixel
     qua ma tran calib (MU isometric), roi LEFT-CLICK tai vi tri do.
  4. Cho nhan vat di, doc lai toa do, lap lai den khi den noi.

Yeu cau: pip install pymem ; chay QUYEN ADMIN. Game WINDOWED.
Ma tran calib lay tu mu_goto_calib.json (do mu_calib.py tao).

Su dung: python mu_goto.py
"""
import sys, os, time, math, json, ctypes, ctypes.wintypes as wt, threading
import tkinter as tk
import pymem, pymem.process
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mu_path

PROCESS_NAME = "main.exe"
CUR_X = 0xB80AF60
CUR_Y = 0xB80AF64
CALIB_FILE = "mu_goto_calib.json"

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
user32.SetProcessDPIAware()

# Nguong: den gan dich hon muc nay thi coi nhu den noi (don vi world)
ARRIVE = 1.5


def enable_debug():
    try:
        advapi32 = ctypes.windll.advapi32
        h = wt.HANDLE()
        if not advapi32.OpenProcessToken(kernel32.GetCurrentProcess(), 0x20 | 0x8, ctypes.byref(h)):
            return
        class LUID(ctypes.Structure):
            _fields_ = [("LowPart", ctypes.c_ulong), ("HighPart", ctypes.c_long)]
        luid = LUID()
        if not advapi32.LookupPrivilegeValueW(None, "SeDebugPrivilege", ctypes.byref(luid)):
            return
        class LAA(ctypes.Structure):
            _fields_ = [("Luid", LUID), ("Attributes", ctypes.c_ulong)]
        class TP(ctypes.Structure):
            _fields_ = [("PrivilegeCount", ctypes.c_ulong), ("Privileges", LAA * 1)]
        tp = TP()
        tp.PrivilegeCount = 1
        tp.Privileges[0].Luid = luid
        tp.Privileges[0].Attributes = 0x2
        advapi32.AdjustTokenPrivileges(h, False, ctypes.byref(tp), 0, None, None)
    except Exception:
        pass


def find_window():
    targets = set()
    for p in pymem.process.list_processes():
        try:
            name = p.szExeFile.decode("utf-8", "ignore")
        except Exception:
            continue
        if name.lower() == PROCESS_NAME.lower():
            targets.add(p.th32ProcessID)
    found = {}
    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def cb(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        pid = wt.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value in targets:
            r = wt.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(r))
            found[pid.value] = (r.left, r.top, r.right - r.left, r.bottom - r.top)
        return True
    user32.EnumWindows(cb, 0)
    if not found:
        raise RuntimeError("Khong tim thay cua so main.exe")
    return list(found.values())[0]


def rd_pos(pm):
    try:
        import struct
        x = struct.unpack("<f", pm.read_bytes(CUR_X, 4))[0]
        y = struct.unpack("<f", pm.read_bytes(CUR_Y, 4))[0]
        return x, y
    except Exception:
        return None, None


def click_at(sx, sy, right=False, hwnd=None):
    """Click vao vi tri man hinh (sx,sy) bang SetCursorPos + mouse_event.
    Tool GIU TOAN QUYEN chuot trong suot qua trinh di chuyen (khong tra ve
    vi tri cu). Chi SetCursorPos + click, khong recover con tro."""
    sx, sy = int(sx), int(sy)
    user32.SetCursorPos(sx, sy)
    time.sleep(0.02)
    down = 0x0008 if right else 0x0002   # RIGHTDOWN / LEFT DOWN
    up = 0x0010 if right else 0x0004      # RIGHTUP / LEFT UP
    user32.mouse_event(down, 0, 0, 0, 0)
    time.sleep(0.04)
    user32.mouse_event(up, 0, 0, 0, 0)


def focus_game():
    """Dem cua so game len foreground de cac phim gui toi dung game
    (khong phai cua so Tkinter cua tool)."""
    procs = pymem.process.list_processes()
    target_pids = {p.th32ProcessID for p in procs
                   if p.szExeFile.decode('utf-8', 'ignore').lower() == PROCESS_NAME.lower()}
    GW = [None]
    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def finder(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        pid = wt.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value in target_pids:
            GW[0] = hwnd
        return True
    user32.EnumWindows(finder, 0)
    if GW[0]:
        # buoc flash truoc (Windows yeu cau app tu flash moi SetForeground duoc)
        user32.ShowWindow(GW[0], 9)  # SW_RESTORE
        user32.SetForegroundWindow(GW[0])
        time.sleep(0.10)
        return GW[0]
    return None


def send_home():
    """Gui phim Home (Helper). Dung keybd_event cung ho mouse_event."""
    VK_HOME = 0x24
    focus_game()
    time.sleep(0.10)
    user32.keybd_event(VK_HOME, 0, 0, 0)       # keydown
    time.sleep(0.05)
    user32.keybd_event(VK_HOME, 0, 0x0002, 0)  # keyup


def send_ctrl_f():
    """Gui phim Ctrl+F (Giam tai). Dung keybd_event."""
    VK_CONTROL = 0x11
    VK_F = 0x46
    focus_game()
    time.sleep(0.10)
    user32.keybd_event(VK_CONTROL, 0, 0, 0)    # Ctrl down
    time.sleep(0.05)
    user32.keybd_event(VK_F, 0, 0, 0)          # F down
    time.sleep(0.05)
    user32.keybd_event(VK_F, 0, 0x0002, 0)     # F up
    time.sleep(0.05)
    user32.keybd_event(VK_CONTROL, 0, 0x0002, 0)  # Ctrl up


def send_keys_on_arrive(do_home, do_ctrl_f):
    """Sau khi den noi: gui Home va/hoac Ctrl+F tuy theo tick cua nguoi dung.
    Thu tu: Home truoc (cho 1s), roi Ctrl+F (cho them 2s)."""
    if do_home:
        time.sleep(1.0)
        send_home()
        log_arrive("  Da gui Home (Helper)")
    if do_ctrl_f:
        time.sleep(2.0)
        send_ctrl_f()
        log_arrive("  Da gui Ctrl+F (Giam tai)")


def log_arrive(msg):
    """Ghi log an toan tu thread nen (goi tu ben trong vong lap)."""
    try:
        root.after(0, lambda: _log_add(msg, False))
    except Exception:
        pass


# --- Dung tool bang phim Space (polling toan cuc) ---
STOP_REQUESTED = [False]
VK_SPACE = 0x20


def check_stop_key():
    """Tra ve True neu phim Space dang duoc nhan (GetAsyncKeyState toan cuc).
    Goi trong vong lap di chuyen de phat hien Space -> dung + tra quyen chuot."""
    # bit cao nhat (0x8000) = phim dang duoc giu
    return bool(user32.GetAsyncKeyState(VK_SPACE) & 0x8000)


def reset_stop():
    STOP_REQUESTED[0] = False


def load_matrix():
    """Load ma tran world_per_px tu calib. Tra ve (A, inv)."""
    try:
        a = json.load(open(CALIB_FILE))["world_per_px"]
        A = ((a[0], a[1]), (a[2], a[3]))
    except Exception:
        # fallback tu lan do thuc te
        A = ((0.01494, 0.02190), (0.01728, -0.02415))
    a00, a01 = A[0]; a10, a11 = A[1]
    det = a00 * a11 - a01 * a10
    if abs(det) < 1e-9:
        inv = ((1, 0), (0, 1))
    else:
        inv = ((a11 / det, -a01 / det), (-a10 / det, a00 / det))
    return A, inv


def main():
    enable_debug()
    pm = pymem.Pymem(PROCESS_NAME)
    L, T, W, H = find_window()
    cx_screen, cy_screen = L + W // 2, T + H // 2
    A, inv = load_matrix()
    print(f"[calib] A={A}")
    print(f"[calib] inv={inv}")
    print(f"[window] {W}x{H} tai ({L},{T}); tam nhan vat=({cx_screen},{cy_screen})")

    # Focus cua so game
    procs = pymem.process.list_processes()
    target_pids = {p.th32ProcessID for p in procs
                   if p.szExeFile.decode('utf-8', 'ignore').lower() == PROCESS_NAME.lower()}
    GW = [None]
    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def finder(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        pid = wt.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value in target_pids:
            GW[0] = hwnd
        return True
    user32.EnumWindows(finder, 0)
    if GW[0]:
        user32.SetForegroundWindow(GW[0])

    running = [False]
    root = tk.Tk()
    root.title("MU GOTO - den toa do")
    root.geometry("360x560")
    tk.Label(root, text="Map #:").grid(row=0, column=0, padx=8, pady=6)
    tk.Label(root, text="Target X:").grid(row=1, column=0, padx=8, pady=6)
    tk.Label(root, text="Target Y:").grid(row=2, column=0, padx=8, pady=6)
    em = tk.Entry(root); em.grid(row=0, column=1); em.insert(0, "1")
    ex = tk.Entry(root); ex.grid(row=1, column=1)
    ey = tk.Entry(root); ey.grid(row=2, column=1)
    cur = tk.Label(root, text="Hien tai: (?, ?)", anchor="w")
    cur.grid(row=3, column=0, columnspan=2, sticky="ew", padx=8, pady=4)
    status = tk.Label(root, text="San sang", anchor="w", justify="left")
    status.grid(row=4, column=0, columnspan=2, sticky="ew", padx=8, pady=6)

    # --- Cap nhat toa do hien tai cua nhan vat NGAY KHI APP KHOI DONG ---
    # Poll moi 200ms, hien thi vao label "Hien tai" de nguoi dung biet vi tri.
    LIVE_POS = [None, None]
    def poll_live():
        try:
            x, y = rd_pos(pm)
            if x is not None:
                LIVE_POS[0], LIVE_POS[1] = x, y
                cur.config(text=f"Hien tai: ({x:.1f}, {y:.1f})")
        except Exception:
            pass
        root.after(200, poll_live)
    root.after(200, poll_live)

    # Danh sach cac diem tren duong di (toi da 10 dong)
    tk.Label(root, text="Cac diem (den=xanh, cuoi=do, toi da 10 dong):").grid(
        row=5, column=0, columnspan=2, sticky="w", padx=8)
    logbox = tk.Listbox(root, height=10, width=44)
    logbox.grid(row=6, column=0, columnspan=2, padx=8, pady=4)

    # Tick chon gui phim khi den noi
    tk.Label(root, text="Gui phim khi den noi:").grid(
        row=7, column=0, columnspan=2, sticky="w", padx=8)
    do_home = tk.BooleanVar(value=False)
    do_ctrl_f = tk.BooleanVar(value=False)
    tk.Checkbutton(root, text="Helper (Nhan Home)", variable=do_home).grid(
        row=8, column=0, sticky="w", padx=8)
    tk.Checkbutton(root, text="Giam tai (Ctrl+F)", variable=do_ctrl_f).grid(
        row=8, column=1, sticky="w", padx=8)

    def set_status(m):
        root.after(0, lambda: status.config(text=m))

    def log_add(text, done=False, color=None):
        root.after(0, lambda: _log_add(text, done, color))
    def _log_add(text, done, color):
        # Gioi han toi da 10 dong: xoa dong cu nhat neu vuot
        if logbox.size() >= 10:
            logbox.delete(0)
        idx = logbox.size()
        logbox.insert(tk.END, text)
        if color:
            logbox.itemconfig(idx, fg=color)
        elif done:
            logbox.itemconfig(idx, fg="green")
        logbox.see(tk.END)

    def goto():
        if running[0]:
            return
        try:
            m = int(em.get()); tx = float(ex.get()); ty = float(ey.get())
        except ValueError:
            set_status("Map/X/Y phai la so."); return
        # Tham so da chon sau khi test: 0.1s / 6 unit
        click_interval = 0.1
        mov_ahead = 6.0
        running[0] = True
        set_status(f"Load map {m}...")
        # Uu tien toa do da duoc poll truc tiep tu khi app khoi dong (LIVE_POS)
        if LIVE_POS[0] is not None:
            x0, y0 = LIVE_POS[0], LIVE_POS[1]
        else:
            x0, y0 = rd_pos(pm)
        if x0 is None:
            set_status("Mat ket noi game. Admin + game mo."); running[0] = False; return
        # Tinh tile start/goal truoc de giu nguyen walkable (khong bi margin loai)
        s0 = mu_path.coord_to_tile(x0, y0)
        g0 = mu_path.coord_to_tile(tx, ty)
        try:
            walk, is_ext = mu_path.load_grid(m, keep_points=[s0, g0])
        except Exception as e:
            set_status(f"Loi load map {m}: {e}")
            running[0] = False; return
        set_status(f"Di toi map{m} ({tx:.0f},{ty:.0f}) bang A*...")
        sx, sy = mu_path.nearest_walkable(walk, *s0) or s0
        gx, gy = mu_path.nearest_walkable(walk, *g0) or g0
        # neu dich la tuong, thong bao toa do thuc se la tile walkable gan nhat
        if (gx, gy) != g0:
            log_add(f"  Dich ({tx:.0f},{ty:.0f}) la tuong -> snap ({gx},{gy})")
        path = mu_path.astar(walk, (sx, sy), (gx, gy))
        if not path or len(path) < 2:
            # thu lai tren grid goc (khong margin) neu bi co lap boi safe margin
            log_add("  Thu lai tren grid goc (bo margin)...")
            try:
                walk0, _ = mu_path.load_grid(m, safe_margin=0, keep_points=[s0, g0])
            except Exception:
                walk0 = walk
            sx0, sy0 = mu_path.nearest_walkable(walk0, *s0) or s0
            gx0, gy0 = mu_path.nearest_walkable(walk0, *g0) or g0
            path = mu_path.astar(walk0, (sx0, sy0), (gx0, gy0))
            if not path or len(path) < 2:
                set_status(f"Khong tim duoc duong toi ({tx:.0f},{ty:.0f}). Co the bi ket boi tuong.")
                running[0] = False; return
            walk = walk0  # su dung grid goc de di (khong dam bao cach tuong)
        # chuyen waypoint tile -> toa do world (tam tile)
        wps = [mu_path.tile_to_coord(*p) for p in path]
        n_wp = len(wps)

        # --- Hien thi tung diem len log (toi da 10 dong) ---
        # Diem moi xuat hien mau DEN; khi den thi TO XANH; diem cuoi TO DO.
        wp_lines = {}   # wp_index -> line_index trong logbox
        def reveal_wp(i, color):
            def _do():
                if logbox.size() >= 10:
                    logbox.delete(0)
                    for k in list(wp_lines.keys()):
                        wp_lines[k] -= 1
                        if wp_lines[k] < 0:
                            del wp_lines[k]
                idx = logbox.size()
                tag = " (DICH CUOI)" if i == n_wp - 1 else ""
                logbox.insert(tk.END, f"  Diem {i+1}/{n_wp}: ({wps[i][0]:.0f},{wps[i][1]:.0f}){tag}")
                if color:
                    logbox.itemconfig(idx, fg=color)
                wp_lines[i] = idx
                logbox.see(tk.END)
            root.after(0, _do)
        def mark_done(i):
            def _do():
                if i in wp_lines and 0 <= wp_lines[i] < logbox.size():
                    logbox.itemconfig(wp_lines[i], fg="green")
            root.after(0, _do)

        # Bat dau: hien diem dau tien (mau den)
        reveal_wp(0, None)
        wp_idx = [0]

        # --- Tham so thuat toan: cadence click de di muot ---
        AHEAD = 4.0        # luon giu diem dich phia truoc ~4 unit theo huong toi dich
        CLICK_INTERVAL = click_interval   # Thoi gian giua 2 lan click (s) - tu UI
        MOV_AHEAD = mov_ahead             # Khoang cach di duoc moi click lai (unit) - tu UI
        MIN_GAP = 0.10
        STUCK_T = 2.0
        REACH_WP = 2.5     # den gan waypoint nay thi chuyen waypoint ke tiep
        MIN_AIM = 1.0      # neu aim cach nhan vat < 1 unit -> bo qua click (tranh click giua man hinh)
        START_AHEAD = 1.5  # AHEAD nho hon o lan click dau de khong vang xa duong di
        POLL = 0.03

        last_click_pos = (x0, y0)
        last_click_t = -10.0
        last_move_t = time.time()
        last_pos = (x0, y0)
        step_no = [0]
        reset_stop()  # xoa co STOP tu lan chay truoc
        try:
            while running[0] and not STOP_REQUESTED[0]:
                if check_stop_key():
                    STOP_REQUESTED[0] = True
                    break
                x, y = rd_pos(pm)
                if x is None:
                    set_status("Mat ket noi game."); break
                root.after(0, lambda v=(x, y): cur.config(
                    text=f"Hien tai: ({v[0]:.1f}, {v[1]:.1f})"))
                now = time.time()
                moved = math.hypot(x - last_pos[0], y - last_pos[1])
                if moved > 0.1:
                    last_move_t = now
                    last_pos = (x, y)

                # --- Phat hien KET (stuck): 2s toa do khong doi -> ve duong moi ---
                if now - last_move_t > STUCK_T:
                    cur_tile = mu_path.coord_to_tile(x, y)
                    log_add(f"  BI KET tai ({x:.1f},{y:.1f}) -> tim duong vong...")
                    # Block tam thoi vung hien tai, bat buoc di vong qua
                    new_path = mu_path.replan(walk, cur_tile,
                                              mu_path.coord_to_tile(tx, ty),
                                              blocked=cur_tile, radius=3)
                    if new_path and len(new_path) >= 2:
                        wps[:] = [mu_path.tile_to_coord(*p) for p in new_path]
                        n_wp = len(wps)
                        wp_idx[0] = 0
                        # Xoa log diem cu, hien duong moi tu dau
                        logbox.delete(0, tk.END)
                        wp_lines.clear()
                        reveal_wp(0, None)
                        log_add(f"  Duong moi: {n_wp} diem (tranh ({x:.0f},{y:.0f}))")
                        set_status(f"Da ve duong vong ({n_wp} diem)")
                    else:
                        log_add("  Khong tim duoc duong vong, thu grid goc...")
                        try:
                            walk0, _ = mu_path.load_grid(m, safe_margin=0, keep_points=[cur_tile, mu_path.coord_to_tile(tx, ty)])
                            new_path = mu_path.replan(walk0, cur_tile,
                                                      mu_path.coord_to_tile(tx, ty),
                                                      blocked=cur_tile, radius=3)
                        except Exception:
                            new_path = None
                        if new_path and len(new_path) >= 2:
                            wps[:] = [mu_path.tile_to_coord(*p) for p in new_path]
                            n_wp = len(wps)
                            wp_idx[0] = 0
                            logbox.delete(0, tk.END)
                            wp_lines.clear()
                            reveal_wp(0, None)
                            walk = walk0
                            log_add(f"  Duong moi (grid goc): {n_wp} diem")
                            set_status(f"Da ve duong vong (grid goc, {n_wp} diem)")
                        else:
                            log_add("  Van kem: tiep tuc cho hoac nhan Space de dung.")
                    last_move_t = now  # reset de tranh replan lien tuc
                    last_pos = (x, y)

                # chuyen sang waypoint A* ke tiep neu da den waypoint hien tai
                while (wp_idx[0] < len(wps) - 1 and
                       math.hypot(wps[wp_idx[0]][0] - x, wps[wp_idx[0]][1] - y) < REACH_WP):
                    reached = wp_idx[0]
                    wp_idx[0] += 1
                    # To xanh diem vua den, roi hien diem ke tiep (den / do neu la diem cuoi)
                    mark_done(reached)
                    nxt = wp_idx[0]
                    reveal_wp(nxt, "red" if nxt == n_wp - 1 else None)

                tx_seg, ty_seg = wps[wp_idx[0]]
                dist_goal = math.hypot(tx - x, ty - y)
                if dist_goal < ARRIVE:
                    # Diem cuoi phai la mau DO (reveal neu chua, hoac to do neu da co)
                    if n_wp - 1 not in wp_lines:
                        reveal_wp(n_wp - 1, "red")
                    else:
                        li = wp_lines[n_wp - 1]

                        def _red(li=li):
                            if 0 <= li < logbox.size():
                                logbox.itemconfig(li, fg="red")
                        root.after(0, _red)
                    log_add(f"  DEN NOI ({x:.1f},{y:.1f})", done=True)
                    set_status(f"DEN NOI ({x:.1f},{y:.1f})")
                    # Gui phim theo tick cua nguoi dung (Home / Ctrl+F)
                    try:
                        if do_home.get() or do_ctrl_f.get():
                            log_add("  Den noi: gui phim theo lua chon...")
                            send_keys_on_arrive(do_home.get(), do_ctrl_f.get())
                        else:
                            log_add("  Den noi: khong tick gui phim nao.")
                    except Exception as e:
                        log_add(f"  Loi gui phim: {e}")
                    break
                # den waypoint cuoi -> dich chinh la tx,ty
                if wp_idx[0] >= len(wps) - 1:
                    tx_seg, ty_seg = tx, ty

                # diem dich phia truoc tren duong thang toi waypoint, cach AHEAD
                # (lan click dau dung START_AHEAD nho hon de khong vang xa duong di)
                ahead_now = START_AHEAD if step_no[0] == 0 else AHEAD
                dseg = math.hypot(tx_seg - x, ty_seg - y)
                if dseg <= ahead_now:
                    aim_x, aim_y = tx_seg, ty_seg
                else:
                    k = ahead_now / dseg
                    aim_x = x + (tx_seg - x) * k
                    aim_y = y + (ty_seg - y) * k

                # neu aim gan nhan vat qua muc (da den waypoint, sap chuyen diem)
                # -> bo qua click de tranh click chet giua man hinh, cho chuyen WP
                if dseg < MIN_AIM:
                    time.sleep(POLL)
                    continue

                moved_since = math.hypot(x - last_click_pos[0], y - last_click_pos[1])
                stuck = (now - last_move_t > STUCK_T)
                if (now - last_click_t >= CLICK_INTERVAL or moved_since >= MOV_AHEAD
                        or stuck) and now - last_click_t >= MIN_GAP:
                    dx_px = inv[0][0] * (aim_x - x) + inv[0][1] * (aim_y - y)
                    dy_px = inv[1][0] * (aim_x - x) + inv[1][1] * (aim_y - y)
                    click_x = max(L + 10, min(L + W - 10, cx_screen + dx_px))
                    click_y = max(T + 10, min(T + H - 10, cy_screen + dy_px))
                    step_no[0] += 1
                    click_at(click_x, click_y, right=False)
                    last_click_pos = (x, y)
                    last_click_t = now
                time.sleep(POLL)
            if STOP_REQUESTED[0]:
                # Nhan Space -> dung va tra quyen dieu khien chuot
                running[0] = False
                set_status("DA DUNG (Space) - da tra quyen chuot.")
                log_add("  Stopped by Space: da ngung chiem chuot.")
            elif running[0]:
                set_status("Da dung.")
        except Exception as e:
            set_status(f"Loi: {e}")
        finally:
            running[0] = False

    def stop():
        running[0] = False
        set_status("Da dung.")

    tk.Button(root, text="OK - Di toi", command=lambda: threading.Thread(target=goto, daemon=True).start()).grid(row=9, column=0, pady=8)
    tk.Button(root, text="STOP", command=stop).grid(row=9, column=1, pady=8)
    root.mainloop()


if __name__ == "__main__":
    main()

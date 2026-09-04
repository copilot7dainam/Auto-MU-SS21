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
import sys, os, time, math, json, ctypes, ctypes.wintypes as wt
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
    Day la cach DA CHUNG MINH hoat dong voi epicmu (game doc toa do chuot that).
    De KHONG chiem chuot lau: luu vi tri chuot that, click xong tra lai ngay."""
    orig = wt.POINT()
    user32.GetCursorPos(ctypes.byref(orig))
    sx, sy = int(sx), int(sy)
    user32.SetCursorPos(sx, sy)
    time.sleep(0.02)
    down = 0x0008 if right else 0x0002   # RIGHTDOWN / LEFT DOWN
    up = 0x0010 if right else 0x0004      # RIGHTUP / LEFT UP
    user32.mouse_event(down, 0, 0, 0, 0)
    time.sleep(0.04)
    user32.mouse_event(up, 0, 0, 0, 0)
    # tra chuot ve vi tri cu (chi chiem vai chuc ms)
    user32.SetCursorPos(orig.x, orig.y)


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
    root.geometry("360x520")
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

    # Bang log duong di
    tk.Label(root, text="Duong di (xanh = da den):").grid(
        row=5, column=0, columnspan=2, sticky="w", padx=8)
    logbox = tk.Listbox(root, height=12, width=44)
    logbox.grid(row=6, column=0, columnspan=2, padx=8, pady=4)

    def set_status(m):
        root.after(0, lambda: status.config(text=m))

    def log_add(text, done=False):
        root.after(0, lambda: _log_add(text, done))
    def _log_add(text, done):
        logbox.insert(tk.END, text)
        if done:
            logbox.itemconfig(tk.END, fg="green")
        logbox.see(tk.END)

    def goto():
        if running[0]:
            return
        try:
            m = int(em.get()); tx = float(ex.get()); ty = float(ey.get())
        except ValueError:
            set_status("Map/X/Y phai la so."); return
        running[0] = True
        set_status(f"Load map {m}...")
        try:
            walk, is_ext = mu_path.load_grid(m)
        except Exception as e:
            set_status(f"Loi load map {m}: {e}")
            running[0] = False; return
        set_status(f"Di toi map{m} ({tx:.0f},{ty:.0f}) bang A*...")
        x0, y0 = rd_pos(pm)
        if x0 is None:
            set_status("Mat ket noi game. Admin + game mo."); running[0] = False; return

        # --- A* tu vi tri hien tai toi dich, lay duong di waypoint ---
        s0 = mu_path.coord_to_tile(x0, y0)
        g0 = mu_path.coord_to_tile(tx, ty)
        sx, sy = mu_path.nearest_walkable(walk, *s0) or s0
        gx, gy = mu_path.nearest_walkable(walk, *g0) or g0
        # neu dich la tuong, thong bao toa do thuc se la tile walkable gan nhat
        if (gx, gy) != g0:
            log_add(f"  Dich ({tx:.0f},{ty:.0f}) la tuong -> snap ({gx},{gy})")
        path = mu_path.astar(walk, (sx, sy), (gx, gy))
        if not path or len(path) < 2:
            set_status(f"Khong tim duoc duong toi ({tx:.0f},{ty:.0f}). Co the bi ket boi tuong.")
            running[0] = False; return
        # chuyen waypoint tile -> toa do world (tam tile)
        wps = [mu_path.tile_to_coord(*p) for p in path]
        log_add(f"  A* tim thay {len(wps)} waypoint tu ({sx},{sy})->({gx},{gy})")
        wp_idx = [0]

        # --- Tham so thuat toan: cadence click de di muot ---
        AHEAD = 4.0        # luon giu diem dich phia truoc ~4 unit theo huong toi dich
        CLICK_INTERVAL = 0.30
        MOV_AHEAD = 1.5
        MIN_GAP = 0.10
        STUCK_T = 2.0
        REACH_WP = 2.5     # den gan waypoint nay thi chuyen waypoint ke tiep
        POLL = 0.03

        last_click_pos = (x0, y0)
        last_click_t = -10.0
        last_move_t = time.time()
        last_pos = (x0, y0)
        step_no = [0]
        try:
            while running[0]:
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

                # chuyen sang waypoint A* ke tiep neu da den waypoint hien tai
                while (wp_idx[0] < len(wps) - 1 and
                       math.hypot(wps[wp_idx[0]][0] - x, wps[wp_idx[0]][1] - y) < REACH_WP):
                    wp_idx[0] += 1
                    log_add(f"  WP {wp_idx[0]+1}/{len(wps)} ({wps[wp_idx[0]][0]:.0f},"
                            f"{wps[wp_idx[0]][1]:.0f})", done=True)

                tx_seg, ty_seg = wps[wp_idx[0]]
                dist_goal = math.hypot(tx - x, ty - y)
                if dist_goal < ARRIVE:
                    log_add(f"  DEN NOI ({x:.1f},{y:.1f})", done=True)
                    set_status(f"DEN NOI ({x:.1f},{y:.1f})")
                    break
                # den waypoint cuoi -> dich chinh la tx,ty
                if wp_idx[0] >= len(wps) - 1:
                    tx_seg, ty_seg = tx, ty

                # diem dich phia truoc tren duong thang toi waypoint, cach AHEAD
                dseg = math.hypot(tx_seg - x, ty_seg - y)
                if dseg <= AHEAD:
                    aim_x, aim_y = tx_seg, ty_seg
                else:
                    k = AHEAD / dseg
                    aim_x = x + (tx_seg - x) * k
                    aim_y = y + (ty_seg - y) * k

                moved_since = math.hypot(x - last_click_pos[0], y - last_click_pos[1])
                stuck = (now - last_move_t > STUCK_T)
                if (now - last_click_t >= CLICK_INTERVAL or moved_since >= MOV_AHEAD
                        or stuck) and now - last_click_t >= MIN_GAP:
                    dx_px = inv[0][0] * (aim_x - x) + inv[0][1] * (aim_y - y)
                    dy_px = inv[1][0] * (aim_x - x) + inv[1][1] * (aim_y - y)
                    click_x = max(L + 10, min(L + W - 10, cx_screen + dx_px))
                    click_y = max(T + 10, min(T + H - 10, cy_screen + dy_px))
                    step_no[0] += 1
                    tag = " (stuck)" if stuck else ""
                    log_add(f"  [{step_no[0]}] -> ({aim_x:.1f},{aim_y:.1f}) "
                            f"click({int(click_x)},{int(click_y)}){tag}")
                    click_at(click_x, click_y, right=False)
                    last_click_pos = (x, y)
                    last_click_t = now
                time.sleep(POLL)
            if running[0]:
                set_status("Da dung.")
        except Exception as e:
            set_status(f"Loi: {e}")
        finally:
            running[0] = False

    def stop():
        running[0] = False
        set_status("Da dung.")

    import threading
    tk.Button(root, text="OK - Di toi", command=lambda: threading.Thread(target=goto, daemon=True).start()).grid(row=7, column=0, pady=8)
    tk.Button(root, text="STOP", command=stop).grid(row=7, column=1, pady=8)
    root.mainloop()


if __name__ == "__main__":
    main()

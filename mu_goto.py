"""
MU GOTO - Nhap X,Y -> OK -> nhan vat di toi (bang cach click chuot gia lap).

CACH HOAT DONG:
  Nhan vat luon o GIUA man hinh (camera follow). Khi ta RIGHT-CLICK vao 1 diem
  tren man hinh, client tu tinh duong di (A*) den toa do game tai diem do.
  Ta chi can click vao vi tri man hinh tuong ung voi (X,Y) dich.

  Vi tri click = center + k * (target - current)
    voi k = he so pixel / game-unit (tu dong hieu chinh qua cac lan click).

Yeu cau: pip install pymem ; chay QUYEN ADMIN. Game o che do WINDOWED.

Su dung: python mu_goto.py
"""
import sys, os, time, math, json, ctypes, ctypes.wintypes as wt
import tkinter as tk
import pymem, pymem.process
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mu_path

PROCESS_NAME = "main.exe"
BASE = 0x400000
CUR_X = 0xB80AF60
CUR_Y = 0xB80AF64
CONFIG_FILE = "mu_goto.json"
CALIB_FILE = "mu_goto_calib.json"

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
adv = ctypes.wintypes  # placeholder, not used
user32.SetProcessDPIAware()

# He so mac dinh: pixel tren man hinh cho moi 1 don vi game.
# Do thuc te: click lech 150px -> nhan vat di ~2.83 unit => k ~ 53.
DEFAULT_K = 50.0


def enable_debug():
    try:
        import ctypes
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


def click_at(sx, sy, right=False):
    """Click bang mouse_event + SetCursorPos (da chung minh hoat dong voi epicmu).
    Mac dinh LEFT (epicmu move = left click)."""
    sx, sy = int(sx), int(sy)
    # Di chuyen chuot that den toa do truoc khi press (game mot so client can dieu nay)
    user32.SetCursorPos(sx, sy)
    time.sleep(0.02)
    down = 0x0008 if right else 0x0002   # RIGHTDOWN / LEFT DOWN
    up = 0x0010 if right else 0x0004     # RIGHTUP / LEFT UP
    user32.mouse_event(down, 0, 0, 0, 0)
    time.sleep(0.04)
    user32.mouse_event(up, 0, 0, 0, 0)


def load_k():
    try:
        return json.load(open(CALIB_FILE))["k"]
    except Exception:
        return DEFAULT_K


def save_k(k):
    json.dump({"k": k}, open(CALIB_FILE, "w"))


def main():
    enable_debug()
    pm = pymem.Pymem(PROCESS_NAME)
    L, T, W, H = find_window()
    cx_screen, cy_screen = L + W // 2, T + H // 2   # vi tri nhan vat (giua man hinh)
    k = [load_k()]

    # Focus cua so game (debug chung minh can thiet)
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
    root.title("MU GOTO - A* pathfinding")
    root.geometry("360x280")
    tk.Label(root, text="Map #:").grid(row=0, column=0, padx=8, pady=6)
    tk.Label(root, text="Target X:").grid(row=1, column=0, padx=8, pady=6)
    tk.Label(root, text="Target Y:").grid(row=2, column=0, padx=8, pady=6)
    em = tk.Entry(root); em.grid(row=0, column=1)
    em.insert(0, "1")
    ex = tk.Entry(root); ex.grid(row=1, column=1)
    ey = tk.Entry(root); ey.grid(row=2, column=1)
    status = tk.Label(root, text="San sang", anchor="w", justify="left")
    status.grid(row=4, column=0, columnspan=2, sticky="ew", padx=8, pady=8)

    def set_status(msg):
        root.after(0, lambda: status.config(text=msg))

    def goto():
        if running[0]:
            return
        try:
            m = int(em.get()); tx = float(ex.get()); ty = float(ey.get())
        except ValueError:
            set_status("Map/X/Y phai la so.")
            return
        running[0] = True
        set_status(f"Load map {m}...")
        try:
            walk, _ = mu_path.load_grid(m)
        except Exception as e:
            set_status(f"Loi load map {m}: {e}")
            running[0] = False
            return
        set_status(f"Di toi map{m} ({tx:.0f},{ty:.0f}) bang A*...")
        try:
            for step in range(400):
                if not running[0]:
                    break
                x, y = rd_pos(pm)
                if x is None:
                    set_status("Mat ket noi game. Kiem tra Admin + game mo.")
                    break
                # tile hien tai va dich
                sx, sy = mu_path.coord_to_tile(x, y)
                gx, gy = mu_path.coord_to_tile(tx, ty)
                dist_goal = math.hypot(tx - x, ty - y)
                if dist_goal < 2.0:
                    set_status(f"DEN NOI ({x:.1f},{y:.1f})")
                    break
                path = mu_path.astar(walk, (sx, sy), (gx, gy))
                if not path or len(path) < 2:
                    set_status(f"Khong tim duoc duong toi ({tx:.0f},{ty:.0f}). Co the la tuong.")
                    break
                # buoc ke tiep: chon waypoint cach hien tai ~ 3-5 unit de click
                nxt = None
                for wp in path[1:]:
                    d = math.hypot(wp[0]-sx, wp[1]-sy)
                    if d >= 2:
                        nxt = wp; break
                if nxt is None:
                    nxt = path[1]
                wx, wy = mu_path.tile_to_coord(*nxt)
                dx, dy = wx - x, wy - y
                click_x = cx_screen + k[0] * dx
                click_y = cy_screen + k[0] * dy
                click_x = max(L + 10, min(L + W - 10, click_x))
                click_y = max(T + 10, min(T + H - 10, click_y))
                prev = (x, y)
                click_at(click_x, click_y, right=False)
                time.sleep(1.0)
                nx, ny = rd_pos(pm)
                if nx is None:
                    continue
                moved = math.hypot(nx - prev[0], ny - prev[1])
                if moved > 0.3:
                    pix = math.hypot(click_x - cx_screen, click_y - cy_screen)
                    if moved > 0.1:
                        new_k = pix / moved
                        k[0] = 0.7 * k[0] + 0.3 * new_k
                        save_k(k[0])
                set_status(f"wp={len(path)} cur=({nx:.1f},{ny:.1f}) goal={dist_goal:.1f} k={k[0]:.1f}")
            if running[0]:
                set_status("Het buoc (400). Co the bi chan/vat can.")
        except Exception as e:
            set_status(f"Loi: {e}")
        finally:
            running[0] = False

    def stop():
        running[0] = False
        set_status("Da dung.")

    import threading
    tk.Button(root, text="OK - Di toi", command=lambda: threading.Thread(target=goto, daemon=True).start()).grid(row=2, column=0, pady=8)
    tk.Button(root, text="STOP", command=stop).grid(row=2, column=1, pady=8)
    root.mainloop()


if __name__ == "__main__":
    main()

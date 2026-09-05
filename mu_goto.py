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
ERR_LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mu_goto_errors.log")


def log_err(msg):
    """Ghi log loi ra file (de debug cac map khong dung duoc)."""
    try:
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(ERR_LOG, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {msg}\n")
    except Exception:
        pass

# Ten map S21 theo World ID doc tu memory (offset duoi). Dung de hien thi ten
# map thuc te nhan vat dang dung. Bang nay lay tu Map ID.txt, da xac nhan voi
# EpicMU Part2/IGCN S21. Danh sach ten chinh cua grid nam trong map_index.json.
WORLD_ID_NAMES = {
    0:"Lorencia",1:"Dungeon",2:"Devias",3:"Noria",4:"Lost Tower",
    6:"Arena",7:"Atlans",8:"Tarkan",10:"Icarus",33:"Aida",
    34:"Crywolf (Crywolf Fortress)",37:"Kanturu Relics",
    38:"Kanturu Event (Remain)",51:"Elbeland",56:"Swamp of Calmness",
    57:"Raklion",80:"Karutan 1",81:"Karutan 2",91:"Acheron",
    99:"Illusion Temple League",112:"Ferea",113:"Nixie Lake",
    116:"Deep Dungeon 1",117:"Deep Dungeon 2",118:"Deep Dungeon 3",
    119:"Deep Dungeon 4",120:"Deep Dungeon 5",122:"Swamp Of Darkness",
    123:"Kubera Mine",128:"Atlans Abyss 1",129:"Atlans Abyss 2",
    130:"Atlans Abyss 3",131:"Scorched Canyon",132:"Red Smoke Icarus",
    133:"Arnil Temple",134:"Ashen Aida",135:"Old Kethotum",
    136:"Blade Kehotum",137:"Kanturu Underground",138:"Ignis Vulcanus",
    140:"Bloody Tarkan",141:"Tormenta Island",142:"Twisted Karutan",
    143:"Kardamahal Underground",144:"Swamp of Despair",
    145:"Aquilas Sanctuary",146:"Forgotten Raklion",
}
# (Ten map moi cap nhat tu map_overrides.json: 51,122,123,128,132,133,134,136)
# Offset World ID trong main.exe (EpicMU Part2 / IGCN S21, base + offset).
OFF_MAP = 0x19D85DC


def rd_map(pm):
    """Doc World ID map hien tai tu memory. Tra ve int hoac None."""
    try:
        # pm.process_base la MODULEINFO (struct), lay lpBaseOfDll moi la dia chi base.
        base = int(pm.process_base.lpBaseOfDll)
        return pm.read_int(base + OFF_MAP)
    except Exception:
        return None


# Trang thai map hien tai (cap nhat moi 1s boi poll_live).
LIVE_MAP = [None]


def live_map_name():
    mid = LIVE_MAP[0]
    if mid is None:
        return "?"
    return WORLD_ID_NAMES.get(mid, f"Map {mid}")


def fmt_live(x, y):
    return f"{live_map_name()} ({int(x)}, {int(y)})"

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
    # --- Danh sach map tu map_index.json (ten + file grid tuong ung) ---
    avail_maps = []   # list of (id, name)  id = MapID 0-based
    for m in mu_path.MAP_INDEX:
        avail_maps.append((m["id"], m.get("name", "")))
    if not avail_maps:
        avail_maps = [(0, "")]

    # Sap xep: map co ten len truoc (World tang dan), khong ten nam cuoi.
    avail_maps.sort(key=lambda t: (0, t[0]) if t[1] else (1, t[0]))

    # Hien thi ten map: ("Lorencia (1)", 1) hoac so neu chua dat ten.
    def map_label(t):
        nm, mid = t[1], t[0]
        return f"{nm} ({mid})" if nm else str(mid)
    map_disp = [map_label(t) for t in avail_maps]

    def stop():
        running[0] = False
        set_status("Da dung.")

    # ===== THIET KE LAI UI (don gian, hien dai, can giua deu) =====
    import tkinter.ttk as ttk
    root = tk.Tk()
    root.title("MU GOTO - Auto Move")
    root.geometry("380x540")
    root.resizable(False, False)
    root.columnconfigure(0, weight=1)
    sel_map_id = tk.IntVar(value=avail_maps[0][0])
    try:
        ttk.Style().theme_use("clam")
    except Exception:
        pass
    PAD = 8

    # --- Hang 1: Map dropdown (hien 5 dong) ---
    top = ttk.Frame(root); top.grid(row=0, column=0, padx=PAD, pady=(PAD, 2), sticky="ew")
    top.columnconfigure(0, weight=0); top.columnconfigure(1, weight=1)
    def _on_map_sel(*_):
        i = map_disp.index(sel_map_disp.get())
        sel_map_id.set(avail_maps[i][0])
    sel_map_disp = tk.StringVar(value=map_disp[0])
    sel_map_disp.trace_add("write", _on_map_sel)
    map_menu = ttk.OptionMenu(top, sel_map_disp, map_disp[0], *map_disp)
    map_menu.configure(width=22, height=5)   # hien toi da 5 dong
    map_menu["menu"].configure(tearoff=0)
    map_menu.grid(row=0, column=0, sticky="w")

    # --- Hang 2: Ten map + toa do + nut + (luu train spot) ---
    curf = ttk.Frame(root); curf.grid(row=1, column=0, padx=PAD, pady=2, sticky="ew")
    cur = ttk.Label(curf, text="? (?, ?)", anchor="w")
    cur.pack(side="left", fill="x", expand=True)
    btn_add = ttk.Button(curf, text="+", width=3, command=lambda: save_spot())
    btn_add.pack(side="left", padx=(6, 0))

    status = ttk.Label(root, text="San sang", anchor="center")
    status.grid(row=2, column=0, padx=PAD, pady=4, sticky="ew")

    # --- Cap nhat toa do hien tai NGAY KHI APP KHOI DONG (1s/lan) ---
    LIVE_POS = [None, None]
    def poll_live():
        try:
            x, y = rd_pos(pm)
            if x is not None:
                LIVE_POS[0], LIVE_POS[1] = x, y
                mid = rd_map(pm)
                LIVE_MAP[0] = mid
                cur.config(text=fmt_live(x, y))
        except Exception:
            pass
        root.after(1000, poll_live)
    root.after(1000, poll_live)

    # --- Danh sach diem tren duong di (toi da 10 dong, co scrollbar) ---
    ttk.Label(root, text="Cac diem tren duong di (den=xanh, cuoi=do):").grid(
        row=3, column=0, padx=PAD, pady=(6, 2), sticky="w")
    lf = ttk.Frame(root); lf.grid(row=4, column=0, padx=PAD, pady=2, sticky="nsew")
    root.rowconfigure(4, weight=1)
    logbox = tk.Listbox(lf, height=10, width=42, relief="flat",
                        highlightthickness=1, borderwidth=1)
    logbox.pack(side="left", fill="both", expand=True)
    scroll = ttk.Scrollbar(lf, orient="vertical", command=logbox.yview)
    scroll.pack(side="right", fill="y")
    logbox.config(yscrollcommand=scroll.set)

    # --- Danh sach train spot (toi da 5 dong, co scrollbar) ---
    ttk.Label(root, text="Train spot (luu bang +):").grid(
        row=5, column=0, padx=PAD, pady=(6, 2), sticky="w")
    sf = ttk.Frame(root); sf.grid(row=6, column=0, padx=PAD, pady=2, sticky="nsew")
    spotbox = tk.Listbox(sf, height=5, width=42, relief="flat",
                         highlightthickness=1, borderwidth=1)
    spotbox.pack(side="left", fill="both", expand=True)
    sscroll = ttk.Scrollbar(sf, orient="vertical", command=spotbox.yview)
    sscroll.pack(side="right", fill="y")
    spotbox.config(yscrollcommand=sscroll.set)
    SPOTS = []   # [(mid, name, x, y)]
    SELECTED_SPOT = [None]   # (mid, x, y) duoc chon lam dich

    def save_spot():
        mid = LIVE_MAP[0]
        if mid is None or LIVE_POS[0] is None:
            set_status("Chua doc duoc vi tri nhan vat")
            return
        x, y = int(LIVE_POS[0]), int(LIVE_POS[1])
        nm = live_map_name()
        SPOTS.append((mid, nm, x, y))
        spotbox.insert(tk.END, f"{nm} ({x}, {y})")
        spotbox.see(tk.END)
        log_add(f"  Da luu train spot: {nm} ({x}, {y})")

    def on_spot_select(evt):
        sel = spotbox.curselection()
        if not sel:
            return
        idx = sel[0]
        if 0 <= idx < len(SPOTS):
            mid, nm, x, y = SPOTS[idx]
            SELECTED_SPOT[0] = (mid, x, y)
            set_status(f"Chon dich: {nm} ({x}, {y})")
    spotbox.bind("<<ListboxSelect>>", on_spot_select)

    # --- Tick chon gui phim khi den noi (can giua, deu) ---
    cf = ttk.Frame(root); cf.grid(row=7, column=0, padx=PAD, pady=4, sticky="ew")
    cf.columnconfigure(0, weight=1); cf.columnconfigure(1, weight=1)
    do_home = tk.BooleanVar(value=False)
    do_ctrl_f = tk.BooleanVar(value=False)
    ttk.Checkbutton(cf, text="Helper (Home)", variable=do_home).grid(
        row=0, column=0, padx=4, sticky="e")
    ttk.Checkbutton(cf, text="Giam tai (Ctrl+F)", variable=do_ctrl_f).grid(
        row=0, column=1, padx=4, sticky="w")

    # --- Nut OK / STOP (can giua, cung kich thuoc) ---
    bf = ttk.Frame(root); bf.grid(row=8, column=0, padx=PAD, pady=(4, PAD), sticky="ew")
    bf.columnconfigure(0, weight=1); bf.columnconfigure(1, weight=1); bf.columnconfigure(2, weight=1)
    ttk.Button(bf, text="OK - Di toi", command=lambda: threading.Thread(target=goto, daemon=True).start()).grid(
        row=0, column=0, padx=4, sticky="ew")
    ttk.Button(bf, text="Tinh toan", command=lambda: threading.Thread(target=calculate, daemon=True).start()).grid(
        row=0, column=1, padx=4, sticky="ew")
    ttk.Button(bf, text="STOP", command=stop).grid(
        row=0, column=2, padx=4, sticky="ew")

    def set_status(m):
        root.after(0, lambda: status.config(text=m))

    def log_add(text, done=False, color=None):
        root.after(0, lambda: _log_add(text, done, color))
    def _log_add(text, done, color):
        # Khong gioi han so dong: thanh cuon (scrollbar) de xem tiep.
        idx = logbox.size()
        logbox.insert(tk.END, text)
        if color:
            logbox.itemconfig(idx, fg=color)
        elif done:
            logbox.itemconfig(idx, fg="green")
        logbox.see(tk.END)

    def get_target():
        """Tra ve (map_id, tx, ty) tu spot duoc chon, hoac vi tri live hien tai."""
        if SELECTED_SPOT[0]:
            return SELECTED_SPOT[0]
        if LIVE_MAP[0] is not None and LIVE_POS[0] is not None:
            return (LIVE_MAP[0], int(LIVE_POS[0]), int(LIVE_POS[1]))
        raise ValueError("Chua chon spot va chua doc duoc vi tri")

    def goto():
        if running[0]:
            return
        try:
            m, tx, ty = get_target()
        except ValueError:
            set_status("Chon 1 train spot hoac dam bao nhan vat dang o map."); return
        # Tham so da chon sau khi test: 0.1s / 6 unit
        click_interval = 0.1
        mov_ahead = 6.0
        running[0] = True
        set_status("Click tam man hinh de cap nhat toa do...")
        # Click vao TRUNG TAM man hinh (tam nhan vat) de ep game cap nhat toa do,
        # sau do moi doc toa do that va tinh duong di.
        click_at(cx_screen, cy_screen, right=False)
        time.sleep(1.0)
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
            log_err(f"[goto] Loi load map {m}: {e}")
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
                log_err(f"[goto] Map {m}: khong tim duoc duong den ({tx:.0f},{ty:.0f})")
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
                # Khong gioi han so dong (co scrollbar). Moi diem 1 dong duy nhat.
                if i in wp_lines and 0 <= wp_lines[i] < logbox.size():
                    return  # diem da hien thi roi (tranh trung lap sau khi ve lai duong)
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
        # Khoang cach click (pixel tu tam) - khi bi kem vat can se tang gấp 2,3,4,5,6.
        BASE_CD = 40.0
        FACTORS = [2, 3, 4, 5, 6]          # tang gấp 2 roi 3,4,5,6
        click_dist = BASE_CD
        max_dist = min(W, H)               # khong vuot qua ca cua so game
        stuck_active = [False]             # flag KEM keo dai den khi nhan vat thuc su di chuyen
        stuck_count = 0
        escalate_t = [-10.0]               # thoi diem tang muc do kem gan nhat
        plan2 = [False]                    # True = da chuyen phuong an 2 (di nguoc duong cu)
        BACK_N = 6                         # so diem lui lai khi phuong an 2
        passed = [(x0, y0)]                # cac diem da di qua (de lui nguoc)

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
                    text=fmt_live(v[0], v[1])))
                now = time.time()
                moved = math.hypot(x - last_pos[0], y - last_pos[1])
                if moved > 0.1:
                    last_move_t = now
                    last_pos = (x, y)
                    # nhan vat thuc su di chuyen -> thoat kem, reset ve mac dinh
                    if stuck_active[0]:
                        stuck_active[0] = False
                        click_dist = BASE_CD
                        stuck_count = 0
                        plan2[0] = False
                        log_add("  Da thoat kem, tiep tuc di binh thuong.")

                # --- Phat hien KET (stuck): 2s toa do khong doi -> bat co kem ---
                if now - last_move_t > STUCK_T:
                    if not stuck_active[0]:
                        stuck_active[0] = True
                        stuck_count = 0
                        escalate_t[0] = now
                        log_add(f"  BI KET tai ({x:.1f},{y:.1f}): bat co xu ly kem.")
                    cur_tile = mu_path.coord_to_tile(x, y)
                    goal_tile = mu_path.coord_to_tile(tx, ty)
                    # Moi STUCK_T giay se tang 1 muc (x2,3,4,5,6) hoac chuyen phuong an 2.
                    if now - escalate_t[0] >= STUCK_T:
                        escalate_t[0] = now
                        stuck_count += 1
                        if not plan2[0] and stuck_count <= len(FACTORS):
                            # PHUONG AN 1: tang gap 2,3,4,5,6 khoang cach click (toi da ca cua so)
                            factor = FACTORS[stuck_count - 1]
                            click_dist = min(BASE_CD * factor, max_dist)
                            log_add(f"  KEM #{stuck_count}: tang click_dist x{factor} = {click_dist:.0f}px")
                            fb = max(0, wp_idx[0] - 1)
                            start_tile = mu_path.coord_to_tile(*wps[fb])
                            # Block vung quanh vi tri kem, bat buoc di vong qua
                            new_path = mu_path.replan(walk, start_tile, goal_tile,
                                                      blocked=cur_tile, radius=4)
                            if new_path and len(new_path) >= 2:
                                wps[:] = [mu_path.tile_to_coord(*p) for p in new_path]
                                n_wp = len(wps); wp_idx[0] = 0
                                logbox.delete(0, tk.END); wp_lines.clear(); reveal_wp(0, None)
                                log_add(f"  Duong vong tu diem {fb+1}: {n_wp} diem (tranh {cur_tile})")
                                set_status(f"Da ve duong vong ({n_wp} diem)")
                            else:
                                log_add("  Khong tim duoc, thu grid goc...")
                                try:
                                    walk0, _ = mu_path.load_grid(m, safe_margin=0, keep_points=[start_tile, goal_tile])
                                    new_path = mu_path.replan(walk0, start_tile, goal_tile,
                                                              blocked=cur_tile, radius=4)
                                except Exception:
                                    new_path = None
                                if new_path and len(new_path) >= 2:
                                    wps[:] = [mu_path.tile_to_coord(*p) for p in new_path]
                                    n_wp = len(wps); wp_idx[0] = 0
                                    logbox.delete(0, tk.END); wp_lines.clear(); reveal_wp(0, None)
                                    walk = walk0
                                    log_add(f"  Duong vong (grid goc): {n_wp} diem")
                                    set_status(f"Da ve duong vong (grid goc, {n_wp} diem)")
                                else:
                                    log_add("  Van kem: tiep tuc thu hoac nhan Space de dung.")
                        else:
                            # PHUONG AN 2: di nguoc lai duong cu da di, roi tim duong vong
                            plan2[0] = True
                            rev = list(reversed(passed))
                            back_pts = rev[1:1 + BACK_N]   # cac diem da di (bo vi tri hien tai)
                            if back_pts:
                                back_tiles = [mu_path.coord_to_tile(*p) for p in back_pts]
                                far_tile = back_tiles[-1]
                                detour = mu_path.replan(walk, far_tile, goal_tile,
                                                        blocked=cur_tile, radius=4)
                                if detour and len(detour) >= 2:
                                    full = back_tiles + detour[1:]
                                    wps[:] = [mu_path.tile_to_coord(*p) for p in full]
                                    n_wp = len(wps); wp_idx[0] = 0
                                    logbox.delete(0, tk.END); wp_lines.clear(); reveal_wp(0, None)
                                    log_add(f"  PHUONG AN 2: lui {len(back_tiles)} diem + duong vong {len(detour)} diem")
                                    set_status(f"Phuong an 2: lui {len(back_tiles)} diem roi vong")
                                else:
                                    log_add("  PHUONG AN 2: thu grid goc...")
                                    try:
                                        walk0, _ = mu_path.load_grid(m, safe_margin=0, keep_points=[far_tile, goal_tile])
                                        detour = mu_path.replan(walk0, far_tile, goal_tile,
                                                                blocked=cur_tile, radius=4)
                                    except Exception:
                                        detour = None
                                    if detour and len(detour) >= 2:
                                        full = back_tiles + detour[1:]
                                        wps[:] = [mu_path.tile_to_coord(*p) for p in full]
                                        n_wp = len(wps); wp_idx[0] = 0
                                        logbox.delete(0, tk.END); wp_lines.clear(); reveal_wp(0, None)
                                        walk = walk0
                                        log_add(f"  PHUONG AN 2 (grid goc): lui {len(back_tiles)} + vong {len(detour)}")
                                        set_status("Phuong an 2 (grid goc)")
                                    else:
                                        log_add("  PHUONG AN 2 that bai: cho hoac nhan Space.")
                            else:
                                log_add("  Khong co duong cu de lui: nhan Space de dung.")

                # chuyen sang waypoint A* ke tiep neu da den waypoint hien tai
                while (wp_idx[0] < len(wps) - 1 and
                       math.hypot(wps[wp_idx[0]][0] - x, wps[wp_idx[0]][1] - y) < REACH_WP):
                    reached = wp_idx[0]
                    wp_idx[0] += 1
                    # To xanh diem vua den, roi hien diem ke tiep (den / do neu la diem cuoi)
                    mark_done(reached)
                    passed.append(tuple(wps[reached]))   # ghi nhan diem da di qua (de lui nguoc)
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

                # Huong click: binh thuong ve phia waypoint hien tai; khi BI KET that su
                # (stuck_active) thi lui nguoc LAI duong cu (diem da di truoc do) de thoat kem.
                dseg = math.hypot(tx_seg - x, ty_seg - y)
                if stuck_active[0]:
                    # lui ve diem da di truoc gan nhat (tu passed), bat ke wp_idx
                    aim_x, aim_y = passed[-1] if len(passed) >= 1 else (x0, y0)
                    if len(passed) >= 2:
                        aim_x, aim_y = passed[-2]
                else:
                    # diem dich phia truoc tren duong thang toi waypoint, cach AHEAD
                    ahead_now = START_AHEAD if step_no[0] == 0 else AHEAD
                    if dseg <= ahead_now:
                        aim_x, aim_y = tx_seg, ty_seg
                    else:
                        k = ahead_now / dseg
                        aim_x = x + (tx_seg - x) * k
                        aim_y = y + (ty_seg - y) * k

                # pixel delta tu tam den aim QUA MA TRAN (chinh xac nhu ban da chay tot)
                dx_px = inv[0][0] * (aim_x - x) + inv[0][1] * (aim_y - y)
                dy_px = inv[1][0] * (aim_x - x) + inv[1][1] * (aim_y - y)
                if stuck_active[0]:
                    # BI KET that su: dung khoang cach click da tang (x2..x6) tu tam,
                    # huong nguoc lai duong cu de ep thoat vat can.
                    pw = math.hypot(dx_px, dy_px)
                    if pw > 1e-6:
                        nx, ny = dx_px / pw, dy_px / pw
                        cd = min(click_dist, max_dist)
                        dx_px, dy_px = nx * cd, ny * cd
                click_x = max(L + 10, min(L + W - 10, cx_screen + dx_px))
                click_y = max(T + 10, min(T + H - 10, cy_screen + dy_px))

                # neu dich (waypoint) gan nhan vat qua muc -> bo qua click, cho chuyen WP
                if dseg < MIN_AIM:
                    time.sleep(POLL)
                    continue

                moved_since = math.hypot(x - last_click_pos[0], y - last_click_pos[1])
                stuck = stuck_active[0] or (now - last_move_t > STUCK_T)
                if (now - last_click_t >= CLICK_INTERVAL or moved_since >= MOV_AHEAD
                        or stuck) and now - last_click_t >= MIN_GAP:
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

    def calculate():
        """Tinh truoc duong di (khong click, khong di): in tat ca cac buoc,
        sau do lan luot sang tung diem (den -> xanh) va cuon log theo dong sang."""
        if running[0]:
            return
        try:
            m, tx, ty = get_target()
        except ValueError:
            set_status("Chon 1 train spot hoac dam bao nhan vat dang o map."); return
        running[0] = True
        set_status("Tinh toan duong di (dry-run)...")
        try:
            x0, y0 = rd_pos(pm)
        except Exception:
            x0, y0 = None, None
        if x0 is None:
            # Khong doc duoc vi tri that -> gio lap tam de van xem duoc duong di
            x0, y0 = mu_path.tile_to_coord(*mu_path.coord_to_tile(tx, ty))
            log_add("  (Khong doc duoc vi tri nhan vat -> chi xem duong di den dich)")
        s0 = mu_path.coord_to_tile(x0, y0)
        g0 = mu_path.coord_to_tile(tx, ty)
        try:
            walk, _ = mu_path.load_grid(m, keep_points=[s0, g0])
        except Exception as e:
            set_status(f"Loi load map {m}: {e}")
            log_err(f"[calculate] Loi load map {m}: {e}")
            running[0] = False; return
        sx, sy = mu_path.nearest_walkable(walk, *s0) or s0
        gx, gy = mu_path.nearest_walkable(walk, *g0) or g0
        if (gx, gy) != g0:
            log_add(f"  Dich ({tx:.0f},{ty:.0f}) la tuong -> snap ({gx},{gy})")
        path = mu_path.astar(walk, (sx, sy), (gx, gy))
        if not path or len(path) < 2:
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
                log_err(f"[calculate] Map {m}: khong tim duoc duong den ({tx:.0f},{ty:.0f})")
                running[0] = False; return
        wps = [mu_path.tile_to_coord(*p) for p in path]
        n_wp = len(wps)
        log_add(f"  Bat dau: ({x0:.0f},{y0:.0f})  ->  Dich: ({tx:.0f},{ty:.0f})  | {n_wp} diem")
        log_add(f"  Tile: ({s0[0]},{s0[1]}) -> ({g0[0]},{g0[1]})")
        # In tat ca cac buoc, dau tien mau xam (chua di toi)
        line_idx = []
        for i, (wx, wy) in enumerate(wps):
            tag = " (DICH CUOI)" if i == n_wp - 1 else ""
            idx = logbox.size()
            logbox.insert(tk.END, f"  [{i+1:>3}/{n_wp}] ({wx:.0f},{wy:.0f}){tag}")
            logbox.itemconfig(idx, fg="#888")
            line_idx.append(idx)
        logbox.see(tk.END)
        set_status(f"Da tinh {n_wp} diem. Dang chay anh sang...")
        # Lan luot sang tung diem: den -> xanh, va cuon theo dong sang
        delay = max(20, min(400, int(8000 / n_wp)))   # ms / diem, gioi han 20-400ms
        def light(i):
            if not running[0] or i >= n_wp:
                if running[0]:
                    set_status(f"Xong: da chay het {n_wp} diem (dry-run).")
                running[0] = False
                return
            idx = line_idx[i]
            if 0 <= idx < logbox.size():
                logbox.itemconfig(idx, fg="green")
                logbox.see(idx)
            root.after(delay, lambda: light(i + 1))
        root.after(delay, lambda: light(0))

    root.mainloop()


if __name__ == "__main__":
    main()

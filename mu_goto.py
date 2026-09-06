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
import sys, os, time, math, json, re, ctypes, ctypes.wintypes as wt, threading
import tkinter as tk
from tkinter import font as tkfont
import tkinter.ttk as ttk
import pymem, pymem.process
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mu_path
try:
    import customtkinter as ctk
except Exception:
    ctk = None  # fallback neu chua cai CustomTkinter


def _is_descendant(w, ancestor):
    """True neu w chinh la ancestor hoac la con chau cua ancestor (con giu de
    tuong thich neu phan khac con tham chieu)."""
    while w:
        if w == ancestor:
            return True
        try:
            w = w.master
        except Exception:
            return False
    return False


class DropList:
    """Selector macOS-style: goi CTkOptionMenu neu co, fallback ttk.Combobox.
    API giu nguyen (set_items / set_sel / on_select / .head / .extra) de khong
    pha code save_spot / pick_spot ben duoi. .head la frame chua dropdown +
    frame .extra (ben phai) de gan nut + / x nho."""
    def __init__(self, parent, title, max_rows=5, width=16, compact=False, btn_px=90):
        self.title = title
        self.max_rows = max_rows
        self.width = width
        self.compact = compact   # True: header chi hien noi dung, bo prefix "Title: "
        self.items = []
        self.sel = -1
        self.on_select = None
        self._use_ctk = ctk is not None
        self.head = (ctk.CTkFrame(parent, fg_color="transparent")
                     if self._use_ctk else tk.Frame(parent))
        if self._use_ctk:
            self.var = tk.StringVar(value=f"{title}: ?")
            self.btn = ctk.CTkOptionMenu(self.head, variable=self.var,
                                         values=[""], width=btn_px,
                                         command=self._on_pick,
                                         font=("Segoe UI", 13),
                                         dropdown_font=("Segoe UI", 12))
            self.btn.pack(side="left", fill="x", expand=True, padx=(0, 6))
            self.extra = ctk.CTkFrame(self.head, fg_color="transparent", height=30)
            self.extra.pack(side="right")
        else:
            self.var = tk.StringVar(value=f"{title}: ?")
            self.btn = ttk.Combobox(self.head, textvariable=self.var,
                                    state="readonly", width=width)
            self.btn.pack(side="left", fill="x", expand=True, padx=(0, 6))
            self.btn.bind("<<ComboboxSelected>>", self._on_pick_combo)
            self.extra = tk.Frame(self.head)
            self.extra.pack(side="right")

    def _on_pick(self, value):
        try:
            i = self.items.index(value)
        except ValueError:
            return
        self.sel = i
        if self.on_select:
            self.on_select(i)

    def _on_pick_combo(self, _evt=None):
        text = self.var.get()
        try:
            i = self.items.index(text)
        except ValueError:
            return
        self.sel = i
        if self.on_select:
            self.on_select(i)

    def set_items(self, items, sel=None):
        self.items = list(items)
        if sel is not None and 0 <= sel < len(self.items):
            self.sel = sel
        elif self.sel >= len(self.items):
            self.sel = -1
        if not self.items:
            self.var.set("?" if self.compact else f"{self.title}: ?")
            if self._use_ctk:
                self.btn.configure(values=[""])
            return
        cur = self.items[self.sel] if 0 <= self.sel < len(self.items) else self.items[0]
        head = cur if self.compact else f"{self.title}: {cur}"
        self.var.set(head)
        if self._use_ctk:
            self.btn.configure(values=self.items)
            self.btn.set(head)

    def set_sel(self, i):
        if 0 <= i < len(self.items):
            self.sel = i
            cur = self.items[i]
            head = cur if self.compact else f"{self.title}: {cur}"
            self.var.set(head)
            if self._use_ctk:
                self.btn.set(head)


class MapDropList:
    """Dropdown map tu ve: header nut + popup tk.Text, moi dong 'Ten (n)' voi
    so n MAU DO (so toa do da luu). CTkOptionMenu khong to duoc 2 mau/item nen
    dung Text. API: set_items(names, counts, sel), set_sel(i), on_select(i),
    .head, .extra."""
    def __init__(self, parent, title, width=20, compact=False, btn_px=90):
        self.title = title
        self.width = width
        self.compact = compact   # True: header bo prefix "Title: "
        self.names = []
        self.counts = []
        self.sel = -1
        self.on_select = None
        self.popup = None
        self._txt = None
        self._ob = None
        self._root = parent.winfo_toplevel()
        self._use_ctk = ctk is not None
        if self._use_ctk:
            self.head = ctk.CTkFrame(parent, fg_color="transparent")
            self.btn = ctk.CTkButton(self.head, text=f"{title}: ?", width=btn_px,
                                     command=self.toggle, font=("Segoe UI", 13))
            self.btn.pack(side="left", fill="x", expand=True, padx=(0, 6))
            self.extra = ctk.CTkFrame(self.head, fg_color="transparent", height=30)
            self.extra.pack(side="right")
        else:
            self.head = tk.Frame(parent)
            self.btn = tk.Button(self.head, text=f"{title}: ?", command=self.toggle)
            self.btn.pack(side="left", fill="x", expand=True, padx=(0, 6))
            self.extra = tk.Frame(self.head)
            self.extra.pack(side="right")

    def _set_head(self, t):
        if self._use_ctk:
            self.btn.configure(text=t)
        else:
            self.btn.config(text=t)

    def _head_text(self):
        p = "" if self.compact else f"{self.title}: "
        if 0 <= self.sel < len(self.names):
            return f"{p}{self.names[self.sel]} ({self.counts[self.sel]})"
        return f"{p}?"

    def set_items(self, names, counts, sel=None):
        self.names = list(names)
        self.counts = list(counts)
        if sel is not None and 0 <= sel < len(self.names):
            self.sel = sel
        elif self.sel >= len(self.names):
            self.sel = -1
        self._set_head(self._head_text())
        if self.popup:
            self._fill_popup()

    def set_sel(self, i):
        if 0 <= i < len(self.names):
            self.sel = i
            self._set_head(self._head_text())

    def toggle(self):
        if self.popup:
            self.close()
        else:
            self.open()

    def open(self):
        if not self.names or self.popup:
            return
        pop = tk.Toplevel(self._root)
        pop.wm_overrideredirect(True)
        pop.lift()
        self.popup = pop
        txt = tk.Text(pop, width=self.width, height=min(8, len(self.names)),
                      relief="solid", borderwidth=1, highlightthickness=0,
                      bg="#FFFFFF", fg="#1C1C1E", font=("Segoe UI", 12),
                      padx=8, pady=4, wrap="none", cursor="hand2")
        txt.pack(fill="both", expand=True)
        txt.tag_configure("cnt", foreground="#FF3B30")
        txt.tag_configure("sel", background="#E5F1FF")
        self._txt = txt
        self._fill_popup()
        txt.bind("<Button-1>", self._on_click)
        txt.bind("<MouseWheel>", lambda e: txt.yview_scroll(
            -1 if e.delta > 0 else 1, "units"))
        pop.bind("<Escape>", lambda e: self.close())
        self._ob = self._root.bind("<Button-1>", self._outside, add="+")
        pop.update_idletasks()
        x = self.head.winfo_rootx()
        y = self.head.winfo_rooty() + self.head.winfo_height()
        w = max(self.head.winfo_width(), txt.winfo_reqwidth())
        pop.geometry(f"{w}x{txt.winfo_reqheight()}+{x}+{y}")

    def _fill_popup(self):
        txt = self._txt
        txt.delete("1.0", tk.END)
        for i, nm in enumerate(self.names):
            c = self.counts[i] if i < len(self.counts) else 0
            txt.insert(tk.END, f"{nm} ")
            txt.insert(tk.END, f"({c})", "cnt")
            txt.insert(tk.END, "\n", "sel" if i == self.sel else None)

    def _on_click(self, ev):
        line = int(self._txt.index(f"@{ev.x},{ev.y}").split(".")[0])
        i = line - 1
        if 0 <= i < len(self.names):
            self.sel = i
            self._set_head(self._head_text())
            if self.on_select:
                self.on_select(i)
        self.close()

    def _outside(self, ev):
        if not self.popup:
            return
        tgt = ev.widget
        if _is_descendant(tgt, self.popup) or _is_descendant(tgt, self.head):
            return
        self.close()

    def close(self):
        if self.popup:
            try:
                self.popup.destroy()
            except Exception:
                pass
            self.popup = None
            self._txt = None
        if self._ob:
            try:
                self._root.unbind("<Button-1>", self._ob)
            except Exception:
                pass
            self._ob = None


PROCESS_NAME = "main.exe"
CUR_X = 0xB80AF60
CUR_Y = 0xB80AF64
CALIB_FILE = "mu_goto_calib.json"
ERR_LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mu_goto_errors.log")
SPOTS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mu_goto_spots.json")
CFG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mu_goto_cfg.json")


# Diem cong khi Reset (sua bang chuot PHAI vao nut Reset).
RESET_POINTS = {"str": 500, "agi": 500, "vit": 500, "ene": 500, "cmd": 500}


def load_cfg():
    """Doc cai dat: {"rows": [[mv_sel, sp_sel, min, max], ...],
    "reset_points": {...}}. Dong thoi nap reset_points vao RESET_POINTS toan cuc."""
    try:
        d = json.load(open(CFG_FILE, encoding="utf-8"))
        if isinstance(d, list):          # dinh dang cu: chi co rows
            d = {"rows": d}
        pts = d.get("reset_points") or {}
        for k in RESET_POINTS:
            try:
                RESET_POINTS[k] = int(pts.get(k, RESET_POINTS[k]))
            except (TypeError, ValueError):
                pass
        return d.get("rows", [])
    except Exception:
        return []


def save_cfg(rows):
    try:
        json.dump({"rows": rows, "reset_points": RESET_POINTS},
                  open(CFG_FILE, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
    except Exception:
        pass


def load_spots():
    """Doc train spot da luu tu lan truoc: {token: [[token,name,x,y], ...]}."""
    if not os.path.exists(SPOTS_FILE):
        return {}
    try:
        d = json.load(open(SPOTS_FILE, encoding="utf-8"))
        out = {}
        for key, lst in d.items():
            # key = token /move (string). Tuple cu: (tok, name, x, y).
            out[str(key)] = [(str(key), n, int(x), int(y)) for (_, n, x, y) in lst]
        return out
    except Exception:
        return {}


def save_spots_all(spots):
    """Ghi toan bo train spot ra file de tai su dung lan sau."""
    try:
        json.dump({tok: [[tok, n, x, y] for (tok, n, x, y) in lst]
                   for tok, lst in spots.items()},
                  open(SPOTS_FILE, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
    except Exception:
        pass


def log_err(msg):
    """Ghi log loi ra file (de debug cac map khong dung duoc)."""
    try:
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(ERR_LOG, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {msg}\n")
    except Exception:
        pass

# HWND cua cua so game (set trong main()). Dung de click truc tiep vao game
# bang PostMessage ma khong can foreground.
GHWND = None

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

# Danh sach lenh /move hoat dong tren server (user xac nhan). Thu tu DUNG nhu
# user liet ke. Moi phan tu: (token /move, MapID 0-based tuong ung de load grid).
# Khi den map khac voi map hien tai, gui /move tuong ung, cho load xong moi tinh duong.
# Cac phien ban "2/3/.." la cung 1 ban do (chung MapID) nen dung chung grid.
MOVE_COMMANDS = [
    ("Lorencia", 0), ("Noria", 3), ("Devias", 2), ("Devias2", 2), ("Devias3", 2),
    ("Devias4", 2), ("Dungeon", 1), ("Dungeon2", 1), ("Dungeon3", 1),
    ("Losttower", 4), ("Losttower2", 4), ("Losttower3", 4), ("Losttower4", 4),
    ("Losttower5", 4), ("Losttower6", 4), ("Losttower7", 4),
    ("Arena", 6), ("Atlans", 7), ("Atlans2", 7), ("Atlans3", 7),
    ("Tarkan", 8), ("Tarkan2", 8), ("Icarus", 10), ("Aida2", 33), ("Karutan2", 81),
    ("Crywolf", 34), ("Elbeland", 51), ("Elbeland2", 51), ("Elbeland3", 51),
    ("Raklion", 57), ("Ferea", 112),
]
# token -> MapID (chi nhung co MapID biet de load grid; None = chi de warp).
_TOKEN_TO_MID = {t: m for (t, m) in MOVE_COMMANDS if m is not None}
# MapID -> token (de warp tu mot MapID da biet).
_MID_TO_TOKEN = {m: t for (t, m) in MOVE_COMMANDS if m is not None}

def move_token_for(mid):
    """Tra ve token /move tuong ung voi MapID, hoac None neu khong co."""
    return _MID_TO_TOKEN.get(mid)

# 5 map phai chon bang menu M (nguoi dung se huong dan sau). Tam thoi de trong.
MENU_WARP_MAPS = []


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

# Trang thai nhan vat doc tu title cua so game.
# Format EpicMU: "[EPICMU] [Char: Coca012] [Level: 400 + 703] [RR: 345 / GR: 0] - ServerTime: ..."
LIVE_NAME = [None]
LIVE_LEVEL = [None]
_TITLE_NAME = re.compile(r"\[Char:\s*([^\]]+?)\s*\]")
_TITLE_LV = re.compile(r"\[Level:\s*(\d+)")

def read_title(hwnd):
    """Doc title cua so game, parse (ten, level). Tra ve (None, None) neu hong."""
    try:
        n = user32.GetWindowTextLengthW(hwnd)
        if not n:
            return None, None
        buf = ctypes.create_unicode_buffer(n + 1)
        user32.GetWindowTextW(hwnd, buf, n + 1)
        mn = _TITLE_NAME.search(buf.value)
        ml = _TITLE_LV.search(buf.value)
        if mn and ml:
            return mn.group(1), int(ml.group(1))
    except Exception:
        pass
    return None, None

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
user32.SetProcessDPIAware()
# Khai bao argtypes de GetWindowThreadProcessId tra ve thread id dung.
user32.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]
user32.GetWindowThreadProcessId.restype = wt.DWORD
user32.AttachThreadInput.argtypes = [wt.DWORD, wt.DWORD, wt.BOOL]
user32.AttachThreadInput.restype = wt.BOOL
user32.VkKeyScanW.argtypes = [wt.WCHAR]
user32.VkKeyScanW.restype = ctypes.c_short
user32.MapVirtualKeyW.argtypes = [wt.UINT, wt.UINT]
user32.MapVirtualKeyW.restype = wt.UINT
user32.PostMessageW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
user32.PostMessageW.restype = wt.BOOL
user32.ScreenToClient.argtypes = [wt.HWND, ctypes.POINTER(wt.POINT)]
user32.ScreenToClient.restype = wt.BOOL
user32.ClientToScreen.argtypes = [wt.HWND, ctypes.POINTER(wt.POINT)]
user32.ClientToScreen.restype = wt.BOOL
user32.GetClientRect.argtypes = [wt.HWND, ctypes.POINTER(wt.RECT)]
user32.GetClientRect.restype = wt.BOOL
user32.GetWindowTextLengthW.argtypes = [wt.HWND]
user32.GetWindowTextLengthW.restype = ctypes.c_int
user32.GetWindowTextW.argtypes = [wt.HWND, ctypes.POINTER(ctypes.c_wchar), ctypes.c_int]
user32.GetWindowTextW.restype = ctypes.c_int

# Nguong: den gan dich hon muc nay thi coi nhu den noi (don vi world)
ARRIVE = 1.5
# Sai so cho phep khi kiem tra nhan vat co dang o dung toa do train (don vi world).
POS_TOL = 5.0
# Vi tri CO DINH cua nhan vat trong client area game (do dac, khong can tinh tam).
ANCHOR_X, ANCHOR_Y = 400, 300
# Level tu dong chay chuoi Reset stat khi train toi.
AUTO_RESET_LV = 400


def at_spot(cx, cy, tx, ty, tol=POS_TOL):
    """True neu (cx,cy) nam trong hop vuong [tx-tol, tx+tol] x [ty-tol, ty+tol]."""
    return cx is not None and abs(cx - tx) <= tol and abs(cy - ty) <= tol


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


def find_window_hwnd():
    """Tra ve (client_rect_screen, hwnd) cua cua so game.
    client_rect = vung render THAT (bo title bar + vien), quy doi sang toa do
    man hinh qua ClientToScreen. Tam client rect = vi tri nhan vat (MU giu
    nhan vat o giua client area). Tra ve None neu khong tim thay."""
    targets = set()
    for p in pymem.process.list_processes():
        try:
            name = p.szExeFile.decode("utf-8", "ignore")
        except Exception:
            continue
        if name.lower() == PROCESS_NAME.lower():
            targets.add(p.th32ProcessID)
    GW = [None, None]
    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def cb(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        pid = wt.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value in targets:
            cr = wt.RECT()
            user32.GetClientRect(hwnd, ctypes.byref(cr))
            tl = wt.POINT(0, 0)
            user32.ClientToScreen(hwnd, ctypes.byref(tl))
            GW[0] = (tl.x, tl.y, cr.right, cr.bottom)
            GW[1] = hwnd
        return True
    user32.EnumWindows(cb, 0)
    if GW[0] is None:
        return None
    return GW[0], GW[1]


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
    mouse_event la input TOAN CUC: click roi vao cua so nam duoi con tro,
    khong can game o foreground. Day la co che goc da duoc chung minh chay
    dung voi client MU (khong dung SendInput/PostMessage - bi loc/sai coord).
    Tool GIU TOAN QUYEN chuot trong suot qua trinh di chuyen (khong tra ve
    vi tri cu)."""
    sx, sy = int(sx), int(sy)
    user32.SetCursorPos(sx, sy)
    time.sleep(0.02)
    down = 0x0008 if right else 0x0002   # RIGHTDOWN / LEFTDOWN
    up = 0x0010 if right else 0x0004     # RIGHTUP / LEFTUP
    user32.mouse_event(down, 0, 0, 0, 0)
    time.sleep(0.04)
    user32.mouse_event(up, 0, 0, 0, 0)


def focus_game():
    """Dem cua so game len foreground de cac phim/chuot gui toi dung game
    (khong phai cua so Tkinter cua tool).

    Windows chi cho SetForegroundWindow neu tien trinh dang co foreground, nen
    SetForegroundWindow don thuong thuong that bai. Trick chuan:
      - AttachThreadInput voi thread foreground hien tai
      - Gui Alt (VK_MENU) xuong + len de 'unlock' foreground cua tien trinh khac
      - SetForegroundWindow + ShowWindow(SW_RESTORE)
      - Detach thread.
    Tra ve HWND cua cua so game, hoac None neu khong tim thay."""
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
    hwnd = GW[0]
    if not hwnd:
        return None
    try:
        fg = user32.GetForegroundWindow()
        cur_thread = kernel32.GetCurrentThreadId()
        _tp = wt.DWORD()
        user32.GetWindowThreadProcessId(fg, ctypes.byref(_tp))
        fg_thread = _tp.value
        if fg_thread:
            user32.AttachThreadInput(cur_thread, fg_thread, True)
        # Alt trick: nhan + tha Menu de tien trinh khac nhuong foreground
        user32.keybd_event(0x12, 0, 0, 0)   # VK_MENU down
        time.sleep(0.05)
        user32.keybd_event(0x12, 0, 0x0002, 0)  # VK_MENU up
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        user32.SetForegroundWindow(hwnd)
        time.sleep(0.10)
        if fg_thread:
            user32.AttachThreadInput(cur_thread, fg_thread, False)
    except Exception:
        pass
    return hwnd


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
    global GHWND
    enable_debug()
    pm = pymem.Pymem(PROCESS_NAME)
    rect = find_window_hwnd()
    if not rect:
        raise RuntimeError("Khong tim thay cua so main.exe")
    (L, T, W, H), GHWND = rect
    cx_screen, cy_screen = L + ANCHOR_X, T + ANCHOR_Y
    A, inv = load_matrix()
    print(f"[calib] A={A}")
    print(f"[calib] inv={inv}")
    print(f"[window] {W}x{H} tai ({L},{T}); tam nhan vat=({cx_screen},{cy_screen})")

    # Focus cua so game
    if GHWND:
        user32.SetForegroundWindow(GHWND)

    running = [False]

    def stop():
        running[0] = False
        set_status("Da dung.")

    # ===== THIET KE LAI UI: sidebar + main, phong cach macOS =====
    USE_CTK = ctk is not None
    if USE_CTK:
        ctk.set_appearance_mode("Light")
        ctk.set_default_color_theme("blue")
        root = ctk.CTk()
    else:
        root = tk.Tk()
    root.title("MU GOTO")
    root.geometry("640x680")
    root.minsize(600, 620)

    # --- Theme macOS ---
    ACCENT = "#007AFF"
    ACCENT_HOVER = "#0A84FF"
    SUCCESS = "#34C759"
    DANGER = "#FF3B30"
    MUTED = "#8E8E93"
    BG = "#F5F5F7"
    CARD = "#FFFFFF"
    BORDER = "#E5E5EA"
    TEXT = "#1C1C1E"
    if USE_CTK:
        root.configure(fg_color=BG)
        f_title = ctk.CTkFont(family="Segoe UI", size=18, weight="bold")
        f_sub = ctk.CTkFont(family="Segoe UI", size=12)
        f_body = ctk.CTkFont(family="Segoe UI", size=13)
        f_btn = ctk.CTkFont(family="Segoe UI", size=14, weight="bold")
        f_small = ctk.CTkFont(family="Segoe UI", size=11)
        f_bar = ctk.CTkFont(family="Segoe UI", size=14, weight="bold")
    else:
        f_title = tkfont.Font(family="Segoe UI", size=18, weight="bold")
        f_sub = tkfont.Font(family="Segoe UI", size=12)
        f_body = tkfont.Font(family="Segoe UI", size=13)
        f_btn = tkfont.Font(family="Segoe UI", size=14, weight="bold")
        f_small = tkfont.Font(family="Segoe UI", size=11)
        f_bar = tkfont.Font(family="Segoe UI", size=14, weight="bold")
        try:
            ttk.Style().theme_use("clam")
        except Exception:
            pass

    PAD = 14

    def card(parent, **kw):
        """Khung trang bo goc 12px, vam mo (macOS card)."""
        if USE_CTK:
            return ctk.CTkFrame(parent, corner_radius=12, fg_color=CARD,
                                border_width=1, border_color=BORDER, **kw)
        f = tk.Frame(parent, bg=CARD, highlightbackground=BORDER,
                     highlightthickness=1)
        return f

    def label(parent, text, font, **kw):
        if USE_CTK:
            kw.setdefault("text_color", TEXT)
            return ctk.CTkLabel(parent, text=text, font=font, **kw)
        kw.setdefault("fg", TEXT)
        kw.setdefault("bg", CARD)
        return tk.Label(parent, text=text, font=font, **kw)

    def btn_primary(parent, text, cmd=None, **kw):
        kw.setdefault("command", cmd)
        if USE_CTK:
            return ctk.CTkButton(parent, text=text,
                                 font=f_btn, height=44, corner_radius=10,
                                 fg_color=ACCENT, hover_color=ACCENT_HOVER,
                                 text_color="#FFFFFF", **kw)
        return tk.Button(parent, text=text, font=f_btn,
                         bg=ACCENT, fg="#FFFFFF", activebackground=ACCENT_HOVER,
                         activeforeground="#FFFFFF", relief="flat", bd=0, **kw)

    def btn_secondary(parent, text, cmd=None, **kw):
        kw.setdefault("command", cmd)
        if USE_CTK:
            return ctk.CTkButton(parent, text=text,
                                 font=f_body, height=40, corner_radius=10,
                                 fg_color="#F2F2F7", hover_color="#E5E5EA",
                                 text_color=TEXT, **kw)
        return tk.Button(parent, text=text, font=f_body,
                         bg="#F2F2F7", fg=TEXT, activebackground="#E5E5EA",
                         relief="flat", bd=0, **kw)

    def btn_danger(parent, text, cmd=None, **kw):
        kw.setdefault("command", cmd)
        if USE_CTK:
            return ctk.CTkButton(parent, text=text,
                                 font=f_btn, height=44, corner_radius=10,
                                 fg_color=DANGER, hover_color="#FF453A",
                                 text_color="#FFFFFF", **kw)
        return tk.Button(parent, text=text, font=f_btn,
                         bg=DANGER, fg="#FFFFFF", activebackground="#FF453A",
                         relief="flat", bd=0, **kw)

    # ===== Layout: sidebar 180px (trai) + main =====
    if USE_CTK:
        root.grid_columnconfigure(0, weight=0, minsize=200)
        root.grid_columnconfigure(1, weight=1)
        root.grid_rowconfigure(0, weight=1)
    else:
        root.configure(bg=BG)
        root.columnconfigure(0, weight=0, minsize=200)
        root.columnconfigure(1, weight=1)
        root.rowconfigure(0, weight=1)

    # luu tru: token /move -> [(token, name, x, y), ...]
    SPOTS = load_spots()
    SELECTED_SPOT = [None]   # (token, x, y) duoc chon lam dich

    def set_status(m):
        log_add(f"[*] {m}")

    # ---------- SIDEBAR (trai) ----------
    if USE_CTK:
        sidebar = ctk.CTkFrame(root, corner_radius=0, fg_color="#FFFFFF",
                               border_width=0)
    else:
        sidebar = tk.Frame(root, bg="#FFFFFF")
    sidebar.grid(row=0, column=0, sticky="nsew", padx=(0, 0))
    if USE_CTK:
        # vien phai ngan cach
        sep = ctk.CTkFrame(root, width=1, fg_color=BORDER)
        sep.grid(row=0, column=0, sticky="nse", padx=(199, 0))
    # Logo + tieu de
    if USE_CTK:
        ctk.CTkLabel(sidebar, text="MU GOTO", font=f_title,
                     text_color=TEXT).pack(anchor="w", padx=PAD, pady=(PAD, 0))
        ctk.CTkLabel(sidebar, text="Auto Move", font=f_sub,
                     text_color=MUTED).pack(anchor="w", padx=PAD, pady=(0, PAD))
    else:
        tk.Label(sidebar, text="MU GOTO", font=f_title, fg=TEXT,
                 bg="#FFFFFF").pack(anchor="w", padx=PAD, pady=(PAD, 0))
        tk.Label(sidebar, text="Auto Move", font=f_sub, fg=MUTED,
                 bg="#FFFFFF").pack(anchor="w", padx=PAD, pady=(0, PAD))
    btn_train = btn_primary(sidebar, "▶  Train",
                            command=lambda: toggle_train())
    btn_train.pack(fill="x", padx=PAD, pady=(0, 4))
    btn_reset = btn_secondary(sidebar, "↺  Reset",
                              command=lambda: toggle_reset())
    btn_reset.pack(fill="x", padx=PAD, pady=(0, 8))
    if USE_CTK:
        ctk.CTkLabel(sidebar, text="Reset: chờ Lv 400 mới chạy.\nBấm lần 2 để hủy · Chuột phải: sửa điểm",
                     font=f_small, text_color=MUTED).pack(anchor="w", padx=PAD, pady=(0, 8))
    else:
        tk.Label(sidebar, text="Reset: chờ Lv 400 mới chạy.\nBấm lần 2 để hủy · Chuột phải: sửa điểm",
                 font=f_small, fg=MUTED, bg="#FFFFFF", justify="left"
                 ).pack(anchor="w", padx=PAD, pady=(0, 8))

    def toggle_train():
        """Lan dau: bat dau chain. Lan tiep (dang chay): dung chain."""
        if TRAIN_ACTIVE[0]:
            STOP_REQUESTED[0] = True
            running[0] = False
        else:
            threading.Thread(target=train_chain, daemon=True).start()

    def open_reset_dialog(_evt=None):
        """Chuot phai nut Reset: mo bang nhap 5 diem cong (str/agi/vit/ene/cmd)."""
        dlg = tk.Toplevel(root)
        dlg.title("Điểm cộng khi Reset")
        dlg.transient(root)
        dlg.grab_set()
        dlg.configure(bg=CARD)
        vars_ = {}
        keys = [("str", "Strength (/addstr)"), ("agi", "Agility (/addagi)"),
                ("vit", "Vitality (/addvit)"), ("ene", "Energy (/addene)"),
                ("cmd", "Command (/addcmd)")]
        for i, (k, lab) in enumerate(keys):
            tk.Label(dlg, text=lab, font=f_body, fg=TEXT, bg=CARD
                     ).grid(row=i, column=0, sticky="w", padx=12, pady=4)
            v = tk.StringVar(value=str(RESET_POINTS[k]))
            vars_[k] = v
            tk.Entry(dlg, textvariable=v, width=8, font=f_body, justify="center",
                     relief="solid", bd=1).grid(row=i, column=1, padx=12, pady=4)
        def save():
            for k, v in vars_.items():
                try:
                    RESET_POINTS[k] = max(0, int(v.get()))
                except ValueError:
                    pass
            persist_rows()   # ghi ca reset_points vao CFG_FILE
            set_status(f"Đã lưu điểm Reset: {RESET_POINTS}")
            dlg.destroy()
        tk.Button(dlg, text="Lưu", command=save, font=f_btn,
                  bg=ACCENT, fg="#FFFFFF", activebackground=ACCENT_HOVER,
                  relief="flat", bd=0).grid(row=len(keys), column=0, columnspan=2,
                                            sticky="ew", padx=12, pady=(8, 12))
    btn_reset.bind("<Button-3>", open_reset_dialog)

    def set_train_active(active):
        """Xanh duong khi nghi, xanh la khi Train dang chay."""
        def _do():
            if USE_CTK:
                btn_train.configure(
                    fg_color=SUCCESS if active else ACCENT,
                    hover_color="#2FB84F" if active else ACCENT_HOVER)
            else:
                btn_train.configure(
                    bg=SUCCESS if active else ACCENT,
                    activebackground="#2FB84F" if active else ACCENT_HOVER)
        try:
            root.after(0, _do)
        except Exception:
            pass
    if USE_CTK:
        ctk.CTkLabel(sidebar, text="Nhấn Space để dừng", font=f_small,
                     text_color=MUTED).pack(anchor="w", padx=PAD, pady=(0, 16))
    else:
        tk.Label(sidebar, text="Nhấn Space để dừng", font=f_small, fg=MUTED,
                 bg="#FFFFFF").pack(anchor="w", padx=PAD, pady=(0, 16))

    # Tick: Helper (Home) + Giam tai (Ctrl+F)
    if USE_CTK:
        ctk.CTkLabel(sidebar, text="Khi đến nơi", font=f_small,
                     text_color=MUTED).pack(anchor="w", padx=PAD, pady=(8, 4))
    else:
        tk.Label(sidebar, text="Khi đến nơi", font=f_small, fg=MUTED,
                 bg="#FFFFFF").pack(anchor="w", padx=PAD, pady=(8, 4))
    do_ctrl_f = tk.BooleanVar(value=False)
    if USE_CTK:
        ctk.CTkCheckBox(sidebar, text="Giảm tải (Ctrl+F)", variable=do_ctrl_f,
                        font=f_body, text_color=TEXT,
                        fg_color=ACCENT, hover_color=ACCENT_HOVER,
                        border_color=BORDER).pack(anchor="w", padx=PAD, pady=2)
    else:
        tk.Checkbutton(sidebar, text="Giảm tải (Ctrl+F)", variable=do_ctrl_f,
                       font=f_body, fg=TEXT, bg="#FFFFFF",
                       activebackground="#FFFFFF", selectcolor="#FFFFFF",
                       anchor="w").pack(anchor="w", padx=PAD, pady=2, fill="x")

    # stretch
    if USE_CTK:
        ctk.CTkFrame(sidebar, fg_color="transparent").pack(fill="both", expand=True)
        ctk.CTkLabel(sidebar, text="v1.0  ·  macOS-style",
                     font=f_small, text_color=MUTED).pack(anchor="w", padx=PAD, pady=PAD)
    else:
        tk.Frame(sidebar, bg="#FFFFFF").pack(fill="both", expand=True)
        tk.Label(sidebar, text="v1.0  ·  macOS-style", font=f_small,
                 fg=MUTED, bg="#FFFFFF").pack(anchor="w", padx=PAD, pady=PAD)

    # ---------- MAIN (phai) ----------
    if USE_CTK:
        main_col = ctk.CTkFrame(root, corner_radius=0, fg_color=BG)
    else:
        main_col = tk.Frame(root, bg=BG)
    main_col.grid(row=0, column=1, sticky="nsew", padx=0)
    if USE_CTK:
        main_col.grid_columnconfigure(0, weight=1)
        main_col.grid_rowconfigure(2, weight=1)
    else:
        main_col.columnconfigure(0, weight=1)
        main_col.rowconfigure(2, weight=1)

    # -- Card 1: thanh tien trinh xanh la (ten + Lv + vi tri, % theo Lv 1..400) --
    head = card(main_col)
    head.grid(row=0, column=0, sticky="ew", padx=PAD, pady=(PAD, 8))
    head.grid_columnconfigure(0, weight=1)
    # Ten/Lv/toa do ve TRUC TIEP len canvas cua thanh tien trinh -> nam BEN
    # TRONG bar; tag_raise de luon o tren lop fill xanh (khong bao bi che).
    if USE_CTK:
        bar = ctk.CTkProgressBar(head, height=34, corner_radius=8,
                                 fg_color="#B7E4C0", progress_color=SUCCESS)
        bar.grid(row=0, column=0, sticky="ew", padx=14, pady=(10, 10))
        bar.set(0.0)
        _cv = bar._canvas
        _cv.create_text(10, 17, anchor="w", text="? · Lv ? — ? (?, ?)",
                        font=f_bar, fill=TEXT, tags=("txt",))
        _cv.tag_raise("txt")
        cur = _cv
    else:
        bar = tk.Canvas(head, height=34, highlightthickness=0, bg="#B7E4C0")
        bar.grid(row=0, column=0, sticky="ew", padx=14, pady=(10, 10))
        bar._fill = bar.create_rectangle(0, 0, 0, 40, fill=SUCCESS, width=0)
        bar.create_text(10, 17, anchor="w", text="? · Lv ? — ? (?, ?)",
                        font=f_bar, fill=TEXT, tags=("txt",))
        bar.tag_raise("txt")
        cur = bar

    def set_bar_pct(lv):
        try:
            p = 0.0 if lv is None else max(0.0, min(1.0, (lv - 1) / (AUTO_RESET_LV - 1)))
        except Exception:
            p = 0.0
        if USE_CTK:
            bar.set(p)
            bar._canvas.tag_raise("txt")   # set() ve lai fill -> keo text len tren
        else:
            w = bar.winfo_width()
            bar.coords(bar._fill, 0, 0, int(w * p), 40)
            bar.tag_raise("txt")

    # -- Card 2: 5 dong [Map + | Spot x | Lv Min | Lv Max] --
    N_ROWS = 5
    pick = card(main_col)
    pick.grid(row=1, column=0, sticky="ew", padx=PAD, pady=8)
    pick.grid_columnconfigure(0, weight=1)
    pick.grid_columnconfigure(2, weight=2)
    label(pick, "Lệnh /move", f_sub, text_color=MUTED).grid(
        row=0, column=0, sticky="ew", padx=6, pady=(12, 4))
    label(pick, "Tọa độ đã lưu", f_sub, text_color=MUTED).grid(
        row=0, column=1, sticky="ew", padx=6, pady=(12, 4))
    label(pick, "Lv Min", f_sub, text_color=MUTED).grid(
        row=0, column=2, sticky="ew", padx=6, pady=(12, 4))
    label(pick, "Lv Max", f_sub, text_color=MUTED).grid(
        row=0, column=3, sticky="ew", padx=6, pady=(12, 4))

    mv_sel = [0] * N_ROWS     # chi muc /move dang chon cua tung dong
    sp_sel = [None] * N_ROWS  # chi muc spot dang chon cua tung dong
    mv_drops = []
    sp_drops = []
    min_vars = []             # tk.StringVar level min tung dong
    max_vars = []             # tk.StringVar level max tung dong

    def refresh_map_row(r):
        names = [t for (t, _) in MOVE_COMMANDS]
        counts = [len(SPOTS.get(t, [])) for t in names]
        mv_drops[r].set_items(names, counts, mv_sel[r])

    def refresh_spot_row(r):
        tok = MOVE_COMMANDS[mv_sel[r]][0]
        lst = SPOTS.get(tok, [])
        items = [f"{x}, {y}" for (_, nm, x, y) in lst]
        if sp_sel[r] is not None and sp_sel[r] >= len(lst):
            sp_sel[r] = None
        # Tu dong chon toa do DAU TIEN khi chua chon (hien thi = trang thai that).
        if sp_sel[r] is None and lst:
            sp_sel[r] = 0
        sp_drops[r].set_items(items, -1 if sp_sel[r] is None else sp_sel[r])

    def refresh_all():
        for r in range(N_ROWS):
            refresh_map_row(r); refresh_spot_row(r)

    def persist_rows():
        """Luu toan bo trang thai 5 dong ra file config."""
        save_cfg([[mv_sel[r], sp_sel[r], min_vars[r].get(), max_vars[r].get()]
                  for r in range(N_ROWS)])

    def pick_move(r, i):
        mv_sel[r] = i
        mv_drops[r].set_sel(i)
        sp_sel[r] = None
        refresh_spot_row(r)
        persist_rows()

    def pick_spot(r, i):
        lst = SPOTS.get(MOVE_COMMANDS[mv_sel[r]][0], [])
        if 0 <= i < len(lst):
            sp_sel[r] = i
            sp_drops[r].set_sel(i)
            _tok, nm, x, y = lst[i]
            set_status(f"Dòng {r+1}: chọn đích {nm} ({x}, {y})")
            persist_rows()

    def save_spot(r):
        """Luu toa do hien tai vao map dang chon o dong r."""
        if LIVE_POS[0] is None:
            set_status("Chưa đọc được vị trí nhân vật")
            return
        tok = MOVE_COMMANDS[mv_sel[r]][0]
        x, y = int(LIVE_POS[0]), int(LIVE_POS[1])
        nm = live_map_name()
        SPOTS.setdefault(tok, []).append((tok, nm, x, y))
        sp_sel[r] = len(SPOTS[tok]) - 1
        refresh_all()
        save_spots_all(SPOTS)
        persist_rows()
        log_add(f"  Đã lưu {tok}: {nm} ({x}, {y})")

    TRAIN_ACTIVE = [False]

    def train_chain():
        """Chuỗi train theo level: duyet tung dong hop le (co spot + Min/Max).
        - Lv < Min   : cho (nhan vat train o map cu).
        - Lv trong [Min, Max] : di toi spot cua dong do, xong cho train toi Max.
        - Lv > Max   : bo qua dong, sang map ke tiep.
        Space = dung toan bo."""
        if TRAIN_ACTIVE[0] or running[0]:
            return
        rows = []
        for r in range(N_ROWS):
            i = sp_sel[r]
            tok = MOVE_COMMANDS[mv_sel[r]][0]
            lst = SPOTS.get(tok, [])
            if i is None or not (0 <= i < len(lst)):
                continue
            try:
                vmin = int(min_vars[r].get())
                vmax = int(max_vars[r].get())
            except ValueError:
                continue
            if vmin > vmax:
                vmin, vmax = vmax, vmin
            _t, nm, x, y = lst[i]
            rows.append((tok, x, y, vmin, vmax))
        if not rows:
            set_status("Chưa có dòng hợp lệ (cần chọn spot + nhập Lv Min/Max)")
            return
        TRAIN_ACTIVE[0] = True
        set_train_active(True)
        reset_stop()
        log_add(f"  === Train chain: {len(rows)} map ===")
        try:
            # Sau Reset, nhan vat ve Lv 1 -> chay lai tu dau chuoi (while True).
            while True:
                outcome = run_pass(rows)   # "done" | "stopped" | "reset"
                if outcome != "reset":
                    break
                log_add("  === Reset xong → Train bắt đầu lại từ dòng 1 ===")
            if outcome == "stopped":
                set_status("Train chain: ĐÃ DỪNG (Space).")
            else:
                set_status("Train chain: hoàn tất tất cả các map.")
                log_add("  === Train chain xong ===")
        finally:
            TRAIN_ACTIVE[0] = False
            set_train_active(False)
            running[0] = False

    def run_pass(rows):
        """1 luot duyet toan bo dong. Tra 'reset' neu auto-reset xay ra (can chay
        lai tu dau), 'stopped' neu Space, nguoc lai 'done'."""
        for (tok, x, y, vmin, vmax) in rows:
            # --- Cho toi Lv Min (hoac bo qua neu da vuot Lv Max) ---
            skip = False
            while not STOP_REQUESTED[0] and not check_stop_key():
                lv = LIVE_LEVEL[0]
                if lv is None:
                    set_status("Chưa đọc được level từ title cửa sổ...")
                    time.sleep(2); continue
                if lv > vmax:
                    set_status(f"Lv {lv} > {vmax}: bỏ qua {tok}")
                    skip = True; break
                if lv >= vmin:
                    break
                set_status(f"Lv {lv} < {vmin}: chờ train trước khi tới {tok}")
                time.sleep(3)
            if STOP_REQUESTED[0] or check_stop_key():
                STOP_REQUESTED[0] = True; return "stopped"
            if skip:
                continue
            # --- Di toi spot cua dong ---
            SELECTED_SPOT[0] = (tok, x, y)
            log_add(f"  Train {tok} ({x},{y}) · Lv {vmin}-{vmax}")
            goto(_from_train=True)
            if STOP_REQUESTED[0]:
                return "stopped"
            # --- Cho train den khi vuot Lv Max ---
            while not STOP_REQUESTED[0] and not check_stop_key():
                lv = LIVE_LEVEL[0]
                if lv is not None and lv > vmax:
                    log_add(f"  Đủ Lv {lv} > {vmax} → sang map kế tiếp")
                    break
                # Tu dong Reset stat khi dat Lv 400 -> ve Lv 1, chay lai tu dau.
                if lv is not None and lv >= AUTO_RESET_LV:
                    log_add(f"  Đạt Lv {lv} >= {AUTO_RESET_LV} → tự động Reset stat")
                    reset_stats()
                    if STOP_REQUESTED[0]:
                        return "stopped"
                    return "reset"
                # Kiem tra bi day lech khoi spot (check ±POS_TOL unit) -> di lai.
                if not at_spot(LIVE_POS[0], LIVE_POS[1], x, y):
                    log_add(f"  Lệch khỏi spot ({LIVE_POS[0]:.0f},{LIVE_POS[1]:.0f}) "
                            f"so với ({x},{y}) > {POS_TOL:.0f} → di chuyển lại")
                    SELECTED_SPOT[0] = (tok, x, y)
                    goto(_from_train=True)
                    if STOP_REQUESTED[0]:
                        return "stopped"
                time.sleep(5)
            if STOP_REQUESTED[0] or check_stop_key():
                STOP_REQUESTED[0] = True; return "stopped"
        return "done"

    # 4 cot deu nhau (Map | Spot | Min | Max), can giua, le trai/phai bang nhau.
    for c in range(4):
        pick.grid_columnconfigure(c, weight=1, uniform="cols")
    CELL_PADX = (6, 6)   # le deu 2 ben moi o
    ROW_PADY = (0, 4)

    # Khoi phuc cai dat lan truoc (neu co).
    cfg = load_cfg()
    for r in range(N_ROWS):
        if r < len(cfg):
            try:
                mv_sel[r] = max(0, min(len(MOVE_COMMANDS) - 1, int(cfg[r][0])))
                s = cfg[r][1]
                sp_sel[r] = None if s is None else int(s)
                min_vars.append(tk.StringVar(value=str(cfg[r][2] if len(cfg[r]) > 2 else "")))
                max_vars.append(tk.StringVar(value=str(cfg[r][3] if len(cfg[r]) > 3 else "")))
                continue
            except Exception:
                pass
        min_vars.append(tk.StringVar(value=""))
        max_vars.append(tk.StringVar(value=""))

    for r in range(N_ROWS):
        mvd = MapDropList(pick, "Map", width=14, compact=True, btn_px=110)
        mv_drops.append(mvd)
        mvd.on_select = lambda i, r=r: pick_move(r, i)
        mvd.head.grid(row=1 + r, column=0, sticky="ew", padx=CELL_PADX, pady=ROW_PADY)
        if USE_CTK:
            ctk.CTkButton(mvd.extra, text="+", width=28, height=28,
                          corner_radius=8, font=f_btn,
                          fg_color=ACCENT, hover_color=ACCENT_HOVER,
                          text_color="#FFFFFF",
                          command=lambda r=r: save_spot(r)).pack()
        else:
            tk.Button(mvd.extra, text="+", font=f_btn, width=2,
                      bg=ACCENT, fg="#FFFFFF", activebackground=ACCENT_HOVER,
                      activeforeground="#FFFFFF", relief="flat", bd=0,
                      command=lambda r=r: save_spot(r)).pack()
        spd = DropList(pick, "Spot", max_rows=5, width=10, compact=True, btn_px=90)
        sp_drops.append(spd)
        spd.on_select = lambda i, r=r: pick_spot(r, i)
        spd.head.grid(row=1 + r, column=1, sticky="ew", padx=CELL_PADX, pady=ROW_PADY)
        # 2 entry Level Min / Max cho dong nay
        vmin, vmax = min_vars[r], max_vars[r]
        if USE_CTK:
            e_min = ctk.CTkEntry(pick, textvariable=vmin, width=44, height=28,
                                 font=f_body, border_color=BORDER, fg_color="#FAFAFA",
                                 justify="center")
            e_max = ctk.CTkEntry(pick, textvariable=vmax, width=44, height=28,
                                 font=f_body, border_color=BORDER, fg_color="#FAFAFA",
                                 justify="center")
        else:
            e_min = tk.Entry(pick, textvariable=vmin, width=5, font=f_body,
                             relief="solid", bd=1, bg="#FAFAFA", justify="center")
            e_max = tk.Entry(pick, textvariable=vmax, width=5, font=f_body,
                             relief="solid", bd=1, bg="#FAFAFA", justify="center")
        e_min.grid(row=1 + r, column=2, sticky="ew", padx=CELL_PADX, pady=ROW_PADY)
        e_max.grid(row=1 + r, column=3, sticky="ew", padx=CELL_PADX, pady=ROW_PADY)
        # Luu moi khi sua Min/Max.
        vmin.trace_add("write", lambda *a: persist_rows())
        vmax.trace_add("write", lambda *a: persist_rows())

    refresh_all()

    # -- Card 3: log duong di --
    log_card = card(main_col)
    log_card.grid(row=2, column=0, sticky="nsew", padx=PAD, pady=(8, PAD))
    log_card.grid_columnconfigure(0, weight=1)
    log_card.grid_rowconfigure(1, weight=1)
    label(log_card, "Đường đi  ·  đến = xanh, cuối = đỏ",
          f_sub, text_color=MUTED).grid(
        row=0, column=0, sticky="w", padx=14, pady=(12, 4))
    if USE_CTK:
        lf = ctk.CTkFrame(log_card, fg_color="transparent")
    else:
        lf = tk.Frame(log_card, bg=CARD)
    lf.grid(row=1, column=0, sticky="nsew", padx=14, pady=(0, 14))
    lf.grid_columnconfigure(0, weight=1)
    lf.grid_rowconfigure(0, weight=1)
    logbox = tk.Listbox(
        lf, height=10, relief="flat", highlightthickness=1,
        borderwidth=1, highlightbackground=BORDER, highlightcolor=BORDER,
        bg="#FAFAFA", fg=TEXT,
        selectbackground=ACCENT, selectforeground="#FFFFFF",
        font=f_body, activestyle="none")
    logbox.grid(row=0, column=0, sticky="nsew")
    scroll = ttk.Scrollbar(lf, orient="vertical", command=logbox.yview)
    scroll.grid(row=0, column=1, sticky="ns")
    logbox.config(yscrollcommand=scroll.set)

    # --- Cap nhat toa do + ten/level hien tai (1s/lan) ---
    LIVE_POS = [None, None]
    _last_pos_text = [None]
    def set_pos_text(x, y):
        """Ghi len label vi tri: ten+Lv CO DINH, chi toa do thay doi.
        Chi configure khi text thuc su khac -> het nhap nhay.
        Dong thoi cap nhat % thanh tien trinh theo Lv (1..400)."""
        lv = LIVE_LEVEL[0]
        set_bar_pct(lv)
        who = f"{LIVE_NAME[0] or '?'} · Lv {lv if lv is not None else '?'}"
        t = f"{who}  —  {fmt_live(x, y)}"
        if t != _last_pos_text[0]:
            _last_pos_text[0] = t
            cur.itemconfig("txt", text=t)
    def poll_live():
        try:
            x, y = rd_pos(pm)
            if x is not None:
                LIVE_POS[0], LIVE_POS[1] = x, y
                LIVE_MAP[0] = rd_map(pm)
                nm, lv = read_title(GHWND)
                if nm:
                    LIVE_NAME[0] = nm
                if lv is not None:
                    LIVE_LEVEL[0] = lv
                set_pos_text(x, y)
        except Exception:
            pass
        root.after(1000, poll_live)
    root.after(1000, poll_live)

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
        """Tra ve (mid, tok, tx, ty) tu spot duoc chon, hoac vi tri live hien tai."""
        if SELECTED_SPOT[0]:
            tok, x, y = SELECTED_SPOT[0]
            mid = _TOKEN_TO_MID.get(tok)
            if mid is None:
                raise ValueError(f"Token {tok} khong biet MapID de load grid")
            return (mid, tok, x, y)
        if LIVE_MAP[0] is not None and LIVE_POS[0] is not None:
            mid = LIVE_MAP[0]
            return (mid, move_token_for(mid), int(LIVE_POS[0]), int(LIVE_POS[1]))
        raise ValueError("Chua chon spot va chua doc duoc vi tri")

    def send_chat_command(cmd):
        """Gui 1 lenh chat vao game: Enter mo chat, go tung ky tu, Enter gui.
        Dung VkKeyScanW + keybd_event (da chung minh go duoc vao game)."""
        focus_game()
        time.sleep(0.20)
        _tap_key(0x0D); time.sleep(0.20)          # Enter mo khung chat
        for ch in cmd:
            _tap_char(ch); time.sleep(0.04)
        time.sleep(0.15)
        _tap_key(0x0D); time.sleep(0.15)          # Enter gui

    def type_move_command(tok):
        send_chat_command(f"/move {tok}")

    def build_reset_commands():
        """Chuoi lenh reset dung diem cong tu RESET_POINTS (sua bang chuot phai)."""
        p = RESET_POINTS
        return [
            "/reset",
            f"/addstr {p['str']}",
            f"/addagi {p['agi']}",
            f"/addvit {p['vit']}",
            f"/addene {p['ene']}",
            f"/addcmd {p['cmd']}",
            "/addstr auto 32000",
            "/addagi auto 32000",
            "/addene auto 32000",
            "/addvit auto 32000",
            "/addcmd auto 32000",
        ]

    RESET_ACTIVE = [False]

    def set_reset_active(active):
        """Xanh duong khi nghi, DO khi Reset dang chay."""
        def _do():
            if USE_CTK:
                btn_reset.configure(
                    fg_color=DANGER if active else "#F2F2F7",
                    hover_color="#FF453A" if active else "#E5E5EA",
                    text_color="#FFFFFF" if active else TEXT)
            else:
                btn_reset.configure(
                    bg=DANGER if active else "#F2F2F7",
                    fg="#FFFFFF" if active else TEXT,
                    activebackground="#FF453A" if active else "#E5E5EA")
        try:
            root.after(0, _do)
        except Exception:
            pass

    RESET_STOP = [False]

    def _run_reset_chain():
        """Thuc hien chuoi lenh: /reset -> cho 5s -> /add... cach 1s.
        Diem cong lay tu RESET_POINTS (sua bang chuot phai). Tra True neu xong."""
        cmds = build_reset_commands()
        log_add("  === Reset stats ===")
        for idx, cmd in enumerate(cmds):
            if RESET_STOP[0] or STOP_REQUESTED[0] or check_stop_key():
                log_add("  Reset bị dừng.")
                return False
            set_status(f"Reset {idx+1}/{len(cmds)}: {cmd}")
            send_chat_command(cmd)
            log_add(f"  >> {cmd}")
            # Sau /reset cho 5s de game reset xong; cac lenh sau cach 1s.
            wait = 5.0 if idx == 0 else 1.0
            t0 = time.time()
            while time.time() - t0 < wait:
                if RESET_STOP[0] or STOP_REQUESTED[0] or check_stop_key():
                    log_add("  Reset bị dừng.")
                    return False
                time.sleep(0.2)
        set_status("Reset xong toan bo stat.")
        log_add("  === Reset hoan tat ===")
        return True

    def reset_stats():
        """Chay NGAY (Train goi khi nhan vat dat Lv 400)."""
        if RESET_ACTIVE[0]:
            return
        RESET_ACTIVE[0] = True
        RESET_STOP[0] = False
        set_reset_active(True)
        try:
            _run_reset_chain()
        finally:
            RESET_ACTIVE[0] = False
            set_reset_active(False)
            RESET_STOP[0] = False

    def reset_button_task():
        """Nut Reset: KHONG chay ngay - cho toi khi Lv = 400 moi thuc hien."""
        RESET_ACTIVE[0] = True
        RESET_STOP[0] = False
        set_reset_active(True)
        try:
            while not RESET_STOP[0]:
                lv = LIVE_LEVEL[0]
                if lv is not None and lv >= AUTO_RESET_LV:
                    break
                time.sleep(1.0)
            if RESET_STOP[0]:
                log_add("  Reset đã hủy (bấm nút lần 2).")
                set_status("Reset đã hủy.")
                return
            _run_reset_chain()
        finally:
            RESET_ACTIVE[0] = False
            set_reset_active(False)
            RESET_STOP[0] = False

    def toggle_reset():
        """Bam 1 lan: hen Reset (cho Lv 400). Bam lan 2: dung/huy."""
        if RESET_ACTIVE[0]:
            RESET_STOP[0] = True
            set_status("Reset: đã bấm dừng, đang kết thúc...")
        else:
            threading.Thread(target=reset_button_task, daemon=True).start()

    def _tap_key(vk):
        user32.keybd_event(vk, 0, 0, 0); time.sleep(0.03)
        user32.keybd_event(vk, 0, 0x0002, 0); time.sleep(0.03)

    def _tap_char(ch):
        """Go 1 ky tu vao cua so active bang VK lay tu VkKeyScanW.
        bit 9 cua VkKeyScanW = 1 nghia la can giu Shift."""
        res = user32.VkKeyScanW(ch)
        vk = res & 0xFF
        need_shift = (res & 0x0100) != 0
        if need_shift:
            user32.keybd_event(0x10, 0, 0, 0)   # Shift down
            time.sleep(0.02)
        user32.keybd_event(vk, 0, 0, 0); time.sleep(0.03)
        user32.keybd_event(vk, 0, 0x0002, 0); time.sleep(0.03)
        if need_shift:
            user32.keybd_event(0x10, 0, 0x0002, 0)  # Shift up
            time.sleep(0.02)

    def pos_stable(pm, timeout=2.0, tol=0.5):
        """Doc rd_pos toi khi 2 lan lien tiep gan nhu khong doi (memory da
        cap nhat sau warp/click). Tra (x, y) gan nhat hoac (None, None)."""
        last = None
        t0 = time.time()
        while time.time() - t0 < timeout:
            x, y = rd_pos(pm)
            if x is not None:
                if last is not None and math.hypot(x - last[0], y - last[1]) < tol:
                    return x, y
                last = (x, y)
            time.sleep(0.15)
        return last if last else (None, None)

    def do_warp(m, tok):
        """Luon gui /move <tok> de ve toa do goc cua map do (khong kiem tra
        cung/khac map). Thanh cong = dung map M **va** vi tri THAT SU doi sau
        warp (neu spot o cung map dang dung, mid==m ngay lap tuc -> phai doi
        toa do thay doi, neu khong se doc vi tri cu va bao 'den noi' gia).
        Tra ve True neu da warp thanh cong, False neu khong co token /move."""
        if not tok:
            set_status(f"Map {m} khong co lenh /move trong danh sach.")
            log_add(f"  (map {m}: khong co token /move)")
            return False
        bx, by = rd_pos(pm)   # vi tri TRUOC warp de phat hien dich chuyen
        log_add(f"  Warp: /move {tok}")
        for attempt in range(1, 4):
            set_status(f"Warp toi {tok} (/move) ... lan {attempt}")
            type_move_command(tok)
            # Sau lenh /move: cho 3s de game warp xong moi lam tiep.
            t_wait = time.time()
            while time.time() - t_wait < 3.0:
                if not running[0]:
                    return False
                time.sleep(0.2)
            changed = False
            t0 = time.time()
            clicked = False
            while time.time() - t0 < 6.0:
                time.sleep(0.2)
                try:
                    mid = rd_map(pm)
                except Exception:
                    mid = None
                if mid != m:
                    if not running[0]:
                        return False
                    continue
                # Dung map: click 400,300 EP game cap nhat toa do memory
                # (offset chi refresh khi co thao tac), roi doc on dinh.
                if not clicked:
                    clicked = True
                    click_at(cx_screen, cy_screen, right=False, hwnd=GHWND)
                x, y = pos_stable(pm)
                if x is None:
                    continue
                if bx is None or math.hypot(x - bx, y - by) > 2.0:
                    changed = True   # warp that: vi tri doi
                    break
                # Vi tri khong doi so voi truoc warp: nhan vat da o dung diem
                # warp -> chap nhan sau khi doc on dinh (pos_stable da dam bao).
                if time.time() - t0 > 1.5:
                    changed = True
                    break
                if not running[0]:
                    return False
            if changed:
                time.sleep(1.0)
                log_add(f"  Da warp sang {tok} (map {mid}).")
                return True
            log_add(f"  Lan {attempt}: chua warp xong toi {tok} (hien tai map {mid}).")
        set_status(f"Warp {tok} THAT BAI sau 3 lan. Kiem tra focus/typing hoac token /move.")
        log_add(f"  Warp {tok} that bai hoan toan.")
        return False

    def goto(_from_train=False):
        if running[0]:
            return
        try:
            m, tok, tx, ty = get_target()
        except ValueError:
            set_status("Chon 1 train spot hoac dam bao nhan vat dang o map."); return
        # Tham so da chon sau khi test: 0.1s / 6 unit
        click_interval = 0.1
        mov_ahead = 6.0
        running[0] = True
        # Dam bao game o foreground truoc khi click (gui phim/warp can focus).
        focus_game()
        time.sleep(0.1)
        # Buoc 1: luon warp ve map goc cua spot (/move <tok>), ke ca khi dang
        # o dung map do (de ve toa do goc truoc khi tinh duong). Khong kiem tra
        # cung/khac map.
        if not do_warp(m, tok):
            # Khong co token /move -> dung lai.
            set_status(f"Map {m} khong co lenh /move; dung lai.")
            log_add("  (da dung: khong co token /move)")
            running[0] = False
            return
        set_status("Click 400,300 de cap nhat toa do...")
        # Click vao tam nhan vat (400,300) de EP game ghi lai toa do memory
        # (offset chi refresh khi co thao tac), roi doc toi khi ONH DINH.
        click_at(cx_screen, cy_screen, right=False, hwnd=GHWND)
        x0, y0 = pos_stable(pm)
        if x0 is None:
            set_status("Mat ket noi game. Admin + game mo."); running[0] = False; return
        log_add(f"  Vi tri sau warp/click: ({x0:.0f},{y0:.0f})")
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

        # --- Tham so thuat toan ---
        AHEAD = 5.0        # MOI click chi aim toi da 5 unit tu nhan vat (chong click nham)
        CLICK_INTERVAL = click_interval   # Thoi gian giua 2 lan click (s) - tu UI
        MOV_AHEAD = mov_ahead             # Khoang cach di duoc moi click lai (unit) - tu UI
        MIN_GAP = 0.10
        REACH_WP = 2.5     # den gan waypoint nay thi chuyen waypoint ke tiep
        MIN_AIM = 1.0      # neu aim cach nhan vat < 1 unit -> bo qua click
        POLL = 0.03
        WP_TIMEOUT = 5.0   # qua 5s chua toi waypoint ke tiep -> dung, tinh lai duong
        home_near_sent = [False]   # da gui Home lan "cach dich 10 unit" chua
        wp_deadline = [time.time()]  # moc thoi diem tinh 5s cho waypoint hien tai
        last_click_pos = (x0, y0)
        last_click_t = -10.0
        step_no = [0]
        last_rect_t = -10.0
        # Bien local, cap nhat moi khi user di chuyen/resize cua so game.
        _L, _T, _W, _H = L, T, W, H
        _cx, _cy = cx_screen, cy_screen
        reset_stop()  # xoa co STOP tu lan chay truoc
        try:
            while running[0] and not STOP_REQUESTED[0]:
                if check_stop_key():
                    STOP_REQUESTED[0] = True
                    break
                x, y = rd_pos(pm)
                if x is None:
                    set_status("Mat ket noi game."); break
                root.after(0, lambda v=(x, y): set_pos_text(v[0], v[1]))
                now = time.time()
                # Refresh rect cua so game moi 0.4s (neu user di chuyen/resize).
                if now - last_rect_t > 0.4:
                    last_rect_t = now
                    rect2 = find_window_hwnd()
                    if rect2:
                        (nL, nT, nW, nH), _ = rect2
                        if (nL, nT, nW, nH) != (_L, _T, _W, _H):
                            _L, _T, _W, _H = nL, nT, nW, nH
                            _cx, _cy = nL + ANCHOR_X, nT + ANCHOR_Y
                            log_add(f"  Window da doi: {_W}x{_H} tai ({_L},{_T})")

                # --- Chuyen sang waypoint ke tiep neu da den gan ---
                advanced = False
                while (wp_idx[0] < len(wps) - 1 and
                       math.hypot(wps[wp_idx[0]][0] - x, wps[wp_idx[0]][1] - y) < REACH_WP):
                    reached = wp_idx[0]
                    wp_idx[0] += 1
                    advanced = True
                    # To xanh diem vua den, roi hien diem ke tiep (den / do neu la diem cuoi)
                    mark_done(reached)
                    nxt = wp_idx[0]
                    reveal_wp(nxt, "red" if nxt == n_wp - 1 else None)
                if advanced:
                    wp_deadline[0] = now   # reset dong ho 5s cho waypoint moi

                # --- Qua 5s chua toi waypoint hien tai -> dung, tinh lai duong ---
                if now - wp_deadline[0] > WP_TIMEOUT:
                    wp_deadline[0] = now
                    log_add(f"  >{WP_TIMEOUT:.0f}s chua toi diem {wp_idx[0]+1}/{n_wp} "
                            f"-> dung, tinh lai duong tu ({x:.0f},{y:.0f})")
                    set_status("Quá 5s chưa tới điểm → tính lại đường đi...")
                    s_t = mu_path.coord_to_tile(x, y)
                    g_t = mu_path.coord_to_tile(tx, ty)
                    new_path = mu_path.astar(walk, s_t, g_t)
                    if not new_path or len(new_path) < 2:
                        try:
                            walk0, _ = mu_path.load_grid(m, safe_margin=0,
                                                         keep_points=[s_t, g_t])
                            sx0, sy0 = mu_path.nearest_walkable(walk0, *s_t) or s_t
                            gx0, gy0 = mu_path.nearest_walkable(walk0, *g_t) or g_t
                            new_path = mu_path.astar(walk0, (sx0, sy0), (gx0, gy0))
                            if new_path and len(new_path) >= 2:
                                walk = walk0
                        except Exception:
                            new_path = None
                    if new_path and len(new_path) >= 2:
                        wps[:] = [mu_path.tile_to_coord(*p) for p in new_path]
                        n_wp = len(wps); wp_idx[0] = 0
                        logbox.delete(0, tk.END); wp_lines.clear(); reveal_wp(0, None)
                        log_add(f"  Duong moi: {n_wp} diem")
                    else:
                        log_add("  Khong tim duoc duong moi; tiep tuc di theo duong cu.")

                tx_seg, ty_seg = wps[wp_idx[0]]
                dist_goal = math.hypot(tx - x, ty - y)
                # Home som theo DIEM DUONG: con <=10 waypoint thi bat
                # (vd duong 50 diem -> tai 40/50; 150 diem -> tai 140/150).
                if not home_near_sent[0] and wp_idx[0] + 1 >= n_wp - 10:
                    home_near_sent[0] = True
                    send_home()
                    log_add(f"  Con {n_wp - wp_idx[0]} diem ({wp_idx[0]+1}/{n_wp}): da gui Home (lan 1)")
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
                    # Toi noi: cho 1s -> Home (tat Helper) -> cho 3s -> Home
                    # (kich hoat lai tai vi tri moi); Ctrl+F neu duoc tick.
                    try:
                        time.sleep(1.0)
                        send_home()
                        log_add("  Den noi: Home lan tat (sau 1s)")
                        time.sleep(3.0)
                        send_home()
                        log_add("  Den noi: Home lan kich hoat (sau 3s)")
                        if do_ctrl_f.get():
                            time.sleep(1.0)
                            send_ctrl_f()
                            log_add("  Da gui Ctrl+F (Giam tai)")
                    except Exception as e:
                        log_add(f"  Loi gui phim: {e}")
                    break
                # den waypoint cuoi -> dich chinh la tx,ty
                if wp_idx[0] >= len(wps) - 1:
                    tx_seg, ty_seg = tx, ty

                # MOI click chi aim toi da AHEAD (5) unit TU NHAN VAT theo huong
                # waypoint hien tai -> khong bao gio click qua xa tam (chong nham).
                dseg = math.hypot(tx_seg - x, ty_seg - y)
                if step_no[0] == 0:
                    aim_x, aim_y = x, y          # lan dau: click tai tam nhan vat
                elif dseg <= AHEAD:
                    aim_x, aim_y = tx_seg, ty_seg
                else:
                    k = AHEAD / dseg
                    aim_x = x + (tx_seg - x) * k
                    aim_y = y + (ty_seg - y) * k

                # pixel delta tu tam den aim QUA MA TRAN isometric
                dx_px = inv[0][0] * (aim_x - x) + inv[0][1] * (aim_y - y)
                dy_px = inv[1][0] * (aim_x - x) + inv[1][1] * (aim_y - y)
                click_x = max(_L + 10, min(_L + _W - 10, _cx + dx_px))
                click_y = max(_T + 10, min(_T + _H - 10, _cy + dy_px))

                # neu waypoint gan nhan vat qua muc -> bo qua click, cho chuyen WP
                if dseg < MIN_AIM:
                    time.sleep(POLL)
                    continue

                moved_since = math.hypot(x - last_click_pos[0], y - last_click_pos[1])
                if (now - last_click_t >= CLICK_INTERVAL
                        or moved_since >= MOV_AHEAD) and now - last_click_t >= MIN_GAP:
                    step_no[0] += 1
                    click_at(click_x, click_y, right=False, hwnd=GHWND)
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
            m, tok, tx, ty = get_target()
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

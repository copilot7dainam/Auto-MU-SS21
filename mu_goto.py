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
from datetime import datetime
import tkinter as tk
from tkinter import font as tkfont, filedialog, messagebox
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
                                         font=("Segoe UI", 15),
                                         dropdown_font=("Segoe UI", 14))
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
                                     command=self.toggle, font=("Segoe UI", 14),
                                     height=30)
            self.btn.pack(side="left", fill="x", expand=True)
            # .extra chi de tuong thich API; rong 1px (CTkFrame mac dinh 200px
            # se lam lech cot grid khi trong rong).
            self.extra = ctk.CTkFrame(self.head, fg_color="transparent",
                                      width=1, height=30)
            self.extra.pack(side="right")
        else:
            self.head = tk.Frame(parent)
            self.btn = tk.Button(self.head, text=f"{title}: ?", command=self.toggle)
            self.btn.pack(side="left", fill="x", expand=True)
            self.extra = tk.Frame(self.head, width=1)
            self.extra.pack(side="right")

    def _set_head(self, t):
        if self._use_ctk:
            self.btn.configure(text=t)
        else:
            self.btn.config(text=t)

    def _head_text(self):
        p = "" if self.compact else f"{self.title}: "
        if 0 <= self.sel < len(self.names):
            nm = self.names[self.sel]
            if self.counts is not None and self.sel < len(self.counts):
                return f"{p}{nm} ({self.counts[self.sel]})"
            return f"{p}{nm}"
        return f"{p}?"

    def set_items(self, names, counts=None, sel=None):
        self.names = list(names)
        self.counts = list(counts) if counts is not None else None
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
                      bg="#FFFFFF", fg="#1C1C1E", font=("Segoe UI", 14),
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
            txt.insert(tk.END, nm)
            if self.counts is not None:
                c = self.counts[i] if i < len(self.counts) else 0
                txt.insert(tk.END, f" ({c})", "cnt")
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
# Thu muc chua FILE THUC (exe dong goi PyInstaller → __file__ chi vao tam
# _MEIxxx, ghi config o do se MAT → dung thu muc cua .exe).
APP_DIR = (os.path.dirname(os.path.abspath(sys.argv[0]))
           if getattr(sys, "frozen", False)
           else os.path.dirname(os.path.abspath(__file__)))
CALIB_FILE = os.path.join(APP_DIR, "mu_goto_calib.json")
ERR_LOG = os.path.join(APP_DIR, "mu_goto_errors.log")
SPOTS_FILE = os.path.join(APP_DIR, "mu_goto_spots.json")
CFG_FILE = os.path.join(APP_DIR, "mu_goto_cfg.json")


def _seed_bundled_files():
    """Ban exe: anh template + calib + spots duoc dong goi trong bundle
    (_MEIPASS). Lan chay dau, copy nhung file CHUA TON TAI sang canh exe de
    nguoi dung khong phai chup lai. File da co (ho chinh sua) -> giu nguyen."""
    base = getattr(sys, "_MEIPASS", None)
    if not base:
        return
    for fn in ("mu_goto_calib.json", "mu_goto_spots.json", "mu_goto_helper.png",
               "mu_goto_lt.png"):
        src = os.path.join(base, fn)
        dst = os.path.join(APP_DIR, fn)
        try:
            if os.path.exists(src) and not os.path.exists(dst):
                import shutil
                shutil.copy2(src, dst)
        except Exception:
            pass


_seed_bundled_files()


# Diem cong khi Reset (sua bang chuot PHAI vao nut Reset).
RESET_POINTS = {"str": 500, "agi": 500, "vit": 500, "ene": 500, "cmd": 500}

def _cfg_dict():
    """Toan bo dict config (giu nguyen cac key khac khi ghi)."""
    try:
        d = json.load(open(CFG_FILE, encoding="utf-8"))
        if isinstance(d, list):          # dinh dang cu: chi co rows
            d = {"rows": d}
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def load_cfg():
    """Doc cai dat: {"rows": [...], "rows_by_acc": {...}, "reset_points": {...}}.
    Tra ve rows (bo dung chung). Dong thoi nap reset_points vao RESET_POINTS."""
    d = _cfg_dict()
    pts = d.get("reset_points") or {}
    for k in RESET_POINTS:
        try:
            RESET_POINTS[k] = int(pts.get(k, RESET_POINTS[k]))
        except (TypeError, ValueError):
            pass
    return d.get("rows", [])


def save_cfg(rows):
    """Ghi rows + reset_points, GIU NGUYEN rows_by_acc va cac key khac."""
    try:
        d = _cfg_dict()
        d["rows"] = rows
        d["reset_points"] = RESET_POINTS
        d.pop("simple_b", None)
        json.dump(d, open(CFG_FILE, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
    except Exception:
        pass


def load_rows_map():
    """{acc_key: rows5} — rows rieng theo account (LI). "" / "(Chung)" = bo
    dung; neu chua co rieng thi fallback ve rows chung."""
    d = _cfg_dict()
    m = d.get("rows_by_acc")
    return dict(m) if isinstance(m, dict) else {}


def save_rows_map(m):
    try:
        d = _cfg_dict()
        d["rows_by_acc"] = m
        json.dump(d, open(CFG_FILE, "w", encoding="utf-8"),
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
# Cua so game dang duoc tool dieu khien (hwnd). Dong bo voi GHWND.
ACTIVE_HWND = [None]

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
user32.WindowFromPoint.argtypes = [wt.POINT]
user32.WindowFromPoint.restype = wt.HWND
user32.GetAncestor.argtypes = [wt.HWND, wt.UINT]
user32.GetAncestor.restype = wt.HWND
user32.BringWindowToTop.argtypes = [wt.HWND]
user32.BringWindowToTop.restype = wt.BOOL
user32.SetWindowPos.argtypes = [wt.HWND, wt.HWND, ctypes.c_int, ctypes.c_int,
                                ctypes.c_int, ctypes.c_int, wt.UINT]
user32.SetWindowPos.restype = wt.BOOL

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


def find_window_hwnd(hwnd=None):
    """Tra ve (client_rect_screen, hwnd) cua cua so game.
    hwnd=None -> cua so game dau tien tim thay; hwnd cho truoc -> tra rect cua
    dung cua so do. client_rect = vung render THAT (bo title bar + vien), quy
    doi sang toa do man hinh qua ClientToScreen. Tra ve None neu khong co."""
    if hwnd:
        if not user32.IsWindow(hwnd):
            return None
        cr = wt.RECT()
        user32.GetClientRect(hwnd, ctypes.byref(cr))
        tl = wt.POINT(0, 0)
        user32.ClientToScreen(hwnd, ctypes.byref(tl))
        return (tl.x, tl.y, cr.right, cr.bottom), hwnd
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


def _window_at(x, y):
    """HWND cua cua so TOP-LEVEL nam duoi diem man hinh (x, y)."""
    try:
        hw = user32.WindowFromPoint(wt.POINT(int(x), int(y)))
        if not hw:
            return None
        root = user32.GetAncestor(hw, 3)        # GA_ROOTOWNER
        return root or hw
    except Exception:
        return None


def _fg_is_ok(hwnd):
    """True neu foreground LA hwnd hoac cua so cung PROCESS cua no.
    (Khi mo o chat, MU/Windows IME tao cua so con cung pid game →
    GetForegroundWindow() != hwnd_game Nhung phim VAN toi dung game. So sanh
    strict == truoc day bao 'mat focus' GIA → lenh bi HOAN, paste khong chay.)"""
    fg = user32.GetForegroundWindow()
    if not fg:
        return False
    if fg == hwnd:
        return True
    try:
        p1 = wt.DWORD(); p2 = wt.DWORD()
        user32.GetWindowThreadProcessId(fg, ctypes.byref(p1))
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(p2))
        return p1.value != 0 and p1.value == p2.value
    except Exception:
        return False

def guard_foreground(hwnd, what=""):
    """TRUOC moi thao tac phim/chuot: neu cua so hwnd KHONG con la
    foreground → lap tuc SetForegroundWindow/BringWindowToTop lai (focus_game)
    va kiem tra lan 2. Khong lay lai duoc → False (goi TU CHOI thao tac,
    tranh phim/chuot roi vao cua so khac = di lech huong)."""
    if not hwnd or not user32.IsWindow(hwnd):
        return False
    for _ in range(3):
        if _fg_is_ok(hwnd):
            return True
        focus_game(hwnd)
        time.sleep(0.10)
    log_arrive(f"  {what}: mat focus cua so {hwnd:#x}, KHONG lay lai duoc — "
               f"bo qua thao tac")
    return False


def click_at(sx, sy, right=False, hwnd=None):
    """Click vao vi tri man hinh (sx,sy) bang SetCursorPos + mouse_event.
    mouse_event la input TOAN CUC: click roi vao cua so NAM DUOI con tro.
    → Voi nhieu cua so game CHONG NHAU, phai kiem tra cua so duoi con tro
    DUNG LA hwnd (cua so dang lam viec) truoc khi bam; bi che -> keo no len
    dinh (focus_game) roi kiem tra lai, toi da 3 lan. Neu van bi che thi
    VAN bam (khong the lam khac) + log canh bao."""
    sx, sy = int(sx), int(sy)
    if hwnd:
        for _ in range(3):
            user32.SetCursorPos(sx, sy)
            time.sleep(0.03)
            if _window_at(sx, sy) == hwnd:
                break
            focus_game(hwnd)                    # keo dung cua so len dinh
            time.sleep(0.12)
        else:
            log_arrive(f"  click: cua so {hwnd:#x} van bi che tai ({sx},{sy})"
                       f" — click co the roi vao cua so khac!")
    else:
        user32.SetCursorPos(sx, sy)
        time.sleep(0.02)
    down = 0x0008 if right else 0x0002   # RIGHTDOWN / LEFTDOWN
    up = 0x0010 if right else 0x0004     # RIGHTUP / LEFTUP
    user32.mouse_event(down, 0, 0, 0, 0)
    time.sleep(0.04)
    user32.mouse_event(up, 0, 0, 0, 0)


# --- Chan thao tac chuot VAT LY cua nguoi dung khi App dang su dung ---
# WH_MOUSE_LL loc theo co LLMHF_INJECTED: su kien sinh boi mouse_event/SetCursorPos
# (App) co flag -> cho qua; su kien chuot that -> return 1 (nuot). Ban phim
# KHONG bi chan -> PgUp van dung duoc tool. Hook phai cai o main thread
# (tkinter mainloop pump message cho no).
MOUSE_BLOCK = [False]
class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("pt", wt.POINT), ("mouseData", wt.DWORD), ("flags", wt.DWORD),
                ("time", wt.DWORD), ("dwExtraInfo", ctypes.c_void_p)]
_LLHOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_int, wt.WPARAM, wt.LPARAM)
_hook_ref = [None]
_hook_handle = [None]

def _mouse_proc(nCode, wParam, lParam):
    if MOUSE_BLOCK[0] and nCode == 0:   # HC_ACTION
        info = ctypes.cast(lParam, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
        if not (info.flags & 0x1):      # LLMHF_INJECTED = 0 -> chuot vat ly
            return 1                     # chan
    return user32.CallNextHookEx(_hook_handle[0], nCode, wParam, lParam)

def install_mouse_hook():
    """Cai hook 1 lan o main thread. Thanh cong = MOUSE_BLOCK quyet dinh chan/cho."""
    if _hook_handle[0]:
        return
    try:
        user32.SetWindowsHookExW.restype = wt.HHOOK
        user32.SetWindowsHookExW.argtypes = [ctypes.c_int, _LLHOOKPROC,
                                             wt.HINSTANCE, wt.DWORD]
        user32.CallNextHookEx.restype = ctypes.c_long
        user32.CallNextHookEx.argtypes = [wt.HHOOK, ctypes.c_int, wt.WPARAM, wt.LPARAM]
        _hook_ref[0] = _LLHOOKPROC(_mouse_proc)   # giu reference (khong de GC)
        _hook_handle[0] = user32.SetWindowsHookExW(
            14, _hook_ref[0], kernel32.GetModuleHandleW(None), 0)  # WH_MOUSE_LL
    except Exception:
        _hook_handle[0] = None


def focus_game(hwnd=None):
    """Dem cua so game len foreground de phim/chuot gui toi dung game.
    hwnd=None -> ACTIVE_HWND[0] (cua so dang lam viec), khong co thi lay cua so
    game dau tien. Trick AttachThreadInput + Alt de SetForegroundWindow khong
    bi Windows chan. Tra ve HWND da focus."""
    if not hwnd:
        hwnd = ACTIVE_HWND[0]
    if not hwnd:
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
        user32.BringWindowToTop(hwnd)   # cho du SetForegroundWindow bi chan
        user32.SetForegroundWindow(hwnd)
        time.sleep(0.10)
        if fg_thread:
            user32.AttachThreadInput(cur_thread, fg_thread, False)
    except Exception:
        pass
    return hwnd


def _ensure_foreground(hwnd, tries=3):
    """Chac chan cua so hwnd THUC SU la foreground truoc khi gui phim
    (SetForegroundWindow doi khi that bai im lang -> phim roi vao cua so khac).
    hwnd thieu -> cua so ACTIVE (mac dinh theo ACTIVE_HWND, KHONG phai 'ai
    dang foreground thi gui cho ay'). Tra True khi da la foreground."""
    hwnd = hwnd or ACTIVE_HWND[0]
    if not hwnd:
        return True
    for _ in range(tries):
        if user32.GetForegroundWindow() == hwnd:
            return True
        focus_game(hwnd)
        time.sleep(0.15)
    ok = user32.GetForegroundWindow() == hwnd
    if not ok:
        log_arrive(f"  phim: KHONG focus duoc cua so {hwnd:#x} — phim co the roi vao noi khac!")
    return ok


def _tap_vk(vk, ext=False):
    """Nhan 1 phim co scan code that (MapVirtualKeyW) — game doc scan code qua
    DirectInput, keybd_event scan=0 co the bi bo qua (nguyen nhan Ctrl+F
    khong toi duoc cua so game)."""
    scan = user32.MapVirtualKeyW(vk, 0)
    flag = 0x0001 if ext else 0x0000           # KEYEVENTF_EXTENDEDKEY
    user32.keybd_event(vk, scan, flag, 0)
    time.sleep(0.05)
    user32.keybd_event(vk, scan, flag | 0x0002, 0)
    time.sleep(0.05)


def _hold_vk(vk, ext=False):
    scan = user32.MapVirtualKeyW(vk, 0)
    user32.keybd_event(vk, scan, 0x0001 if ext else 0, 0)


def _release_vk(vk, ext=False):
    scan = user32.MapVirtualKeyW(vk, 0)
    user32.keybd_event(vk, scan, (0x0001 if ext else 0) | 0x0002, 0)


def send_home(hwnd=None):
    """Gui phim Home (Helper). Chi gui khi giu duoc focus cua so that."""
    hwnd = hwnd or ACTIVE_HWND[0]
    if not guard_foreground(hwnd, "Home"):
        return
    time.sleep(0.10)
    _tap_vk(0x24)                               # VK_HOME


HELPER_IMG = os.path.join(APP_DIR, "mu_goto_helper.png")
LT_IMG = os.path.join(APP_DIR, "mu_goto_lt.png")
CHAT_IMG = os.path.join(APP_DIR, "mu_goto_chat.png")
# Danh sach icon can nhan dien (ten hien thi, duong dan file template).
# Them muc moi vao day -> tu dong xuat hien trong modal "Chup anh".
ICON_ITEMS = [("Helper", HELPER_IMG), ("Giảm tải", LT_IMG)]


def grab_client(hwnd=None):
    """Chup vung client cua game -> PIL.Image (RGB). None neu hong.
    QUAN TRONG: ImageGrab chay theo toa do man hinh — cua so KHAC de len tren
    thi anh chup duoc la cua so de! → keo dung cua so hwnd len dinh truoc
    khi chup (BringWindowToTop + SetForegroundWindow)."""
    try:
        from PIL import ImageGrab
        hwnd = hwnd or ACTIVE_HWND[0]
        r = find_window_hwnd(hwnd)
        if not r:
            return None
        (L, T, W, H), wh = r
        if W < 8 or H < 8:
            return None
        if wh:
            try:
                if user32.GetForegroundWindow() != wh:
                    user32.BringWindowToTop(wh)
                    user32.SetForegroundWindow(wh)
                    time.sleep(0.12)   # cho ve lai xong moi chup
            except Exception:
                pass
        return ImageGrab.grab(bbox=(L, T, L + W, T + H))
    except Exception:
        return None


def icon_present(img_path, thresh=0.90, hwnd=None):
    """True/False: template co/khong hien tren vung CLIENT cua cua so game
    (cv2 matchTemplate, khong log, khong luu file).
    None: chua co template hoac loi -> khong kiem tra duoc (bo qua verify)."""
    try:
        import cv2, numpy as np
        tpl = cv2.imread(img_path)
        if tpl is None:
            return None
        shot = grab_client(hwnd)
        if shot is None:
            return None
        img = cv2.cvtColor(np.asarray(shot), cv2.COLOR_RGB2BGR)
        if tpl.shape[0] > img.shape[0] or tpl.shape[1] > img.shape[1]:
            return None
        res = cv2.matchTemplate(img, tpl, cv2.TM_CCOEFF_NORMED)
        return float(res.max()) >= thresh
    except Exception:
        return None


# ================== AUTO-LOGIN (tab LI) — primitives ==================
# Dung lai grab_client/icon_present/click_at/copy_to_clipboard/paste_clipboard/
# read_clipboard/_tap_vk/goi _ensure_foreground cua train. Them: tim nut theo
# ANH (tra toa do TUONG DOI trong cua so), window theo title regex, minimize.
LI_TPL_DIR = os.path.join(APP_DIR, "li_templates")
LI_COORDS_FILE = os.path.join(APP_DIR, "mu_goto_li.json")
LI_IMG_TIMEOUT = 90.0         # max moi buoc anh (truoc day 300 → 1 buoc ket
                              # hang van cho 5' trong khi ca luong chi co 5')
LI_TOTAL_TIMEOUT = 300.0      # 5 phut TOAN LUONG login 1 account; het gio →
                              # dong cua so game, lam lai tu dau (li_run_all)
LI_STEP_PAUSE = 3.0


def li_tpl(key):
    return os.path.join(LI_TPL_DIR, f"{key}.png")


def li_find_button(img_path, hwnd):
    """Tim template tren anh client cua hwnd. Tra (x, y, score) TUONG DOI
    trong WINDOW RECT (khop khong gian li_click_rel — ANH CHUP la client
    region, thieu title bar nen phai tru/cong offset client→window, neu
    khong moi click lech ~30px xuong duoi). None neu khong thay."""
    try:
        import cv2, numpy as np
        tpl = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
        if tpl is None:
            return None
        shot = grab_client(hwnd)
        if shot is None:
            return None
        g = cv2.cvtColor(np.asarray(shot), cv2.COLOR_RGB2GRAY)
        if tpl.shape[0] >= g.shape[0] or tpl.shape[1] >= g.shape[1]:
            return None
        res = cv2.matchTemplate(g, tpl, cv2.TM_CCOEFF_NORMED)
        _, score, _, top_left = cv2.minMaxLoc(res)
        score = float(score)
        if score < 0.90:
            return None
        th, tw = tpl.shape[:2]
        cx = top_left[0] + tw // 2          # toa do TRONG ANH CLIENT
        cy = top_left[1] + th // 2
        r = wt.RECT()                        # quy ve window-relative
        user32.GetWindowRect(hwnd, ctypes.byref(r))
        r2 = find_window_hwnd(hwnd)
        if r2:
            (cl, ct, _cw, _ch), _h2 = r2
            cx += cl - r.left
            cy += ct - r.top
        return (cx, cy, score)
    except Exception:
        return None


def _li_title_regex(pattern):
    return re.compile(pattern, re.I)


def li_find_windows(pattern):
    """[hwnd] co title khop regex. minimize (IsIconic) VAN duoc tra ve —
    launcher LI bi chinh tool minimize sau khi Play; loai no di se dan toi
    khoi dong exe lan 2, chong launcher. Off-screen thuong thi van bo qua."""
    rx = _li_title_regex(pattern)
    out = []
    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def cb(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        if not user32.IsIconic(hwnd):
            r = wt.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(r))
            if r.left <= -10000 or (r.right - r.left) < 40:
                return True      # off-screen -> bo qua
        n = user32.GetWindowTextLengthW(hwnd)
        if n:
            buf = ctypes.create_unicode_buffer(n + 1)
            user32.GetWindowTextW(hwnd, buf, n + 1)
            if buf.value and rx.search(buf.value):
                out.append(hwnd)
        return True
    user32.EnumWindows(cb, 0)
    return out


def _rect_area(hwnd):
    # MINIMIZE: GetWindowRect tra ve gia tri sentinel (-32000...) → dien tich
    # "khong lo" 16000x16000. Tinh no = 0 de li_pick_window KHONG ba o chon
    # cua so minimize khi co cua so khac dang hien (van duoc chon khi TOAN BO
    # danh sach deu minimize — B1 can tim launcher minimize de restore).
    if user32.IsIconic(hwnd):
        return 0
    r = wt.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    return (r.right - r.left) * (r.bottom - r.top)


def li_pick_window(hits):
    """Chon cua so lon nhat trong hits (None neu rong)."""
    if not hits:
        return None
    return max(hits, key=_rect_area)


def li_restore_launcher(hwnd):
    """Khui cua so launcher: MINIMIZE -> RESTORE -> MAXIMIZE -> foreground.
    (Chi ShowWindow(9) doi khi khong du — MU launcher o che do minimize/maximize
    cua Windows, phai ep 3 lan moi chac len toi dinh.)"""
    try:
        SW_MINIMIZE_, SW_RESTORE_, SW_MAXIMIZE_ = 6, 9, 3
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, SW_RESTORE_)
            time.sleep(0.3)
        user32.ShowWindow(hwnd, SW_MAXIMIZE_)
        time.sleep(0.3)
        _ensure_foreground(hwnd)
    except Exception:
        pass


def li_launcher_windows(cfg):
    """Cua so launcher: tim theo TITLE regex; NEU KHONG thay → tim theo PID cua
    process launcher (chac — nhieu variant launcher co title khong khop
    'MU.*Launcher', cu tim theo title → khong thấy → mo exe lan 2, MU chan).
    Chi tra launcher cua process dang chay; rong = chua co, duoc phep mo moi."""
    hits = li_find_windows(cfg.get("launcher_title", "MU.*Launcher"))
    if hits:
        return hits
    exe = cfg.get("launcher_path", "") or ""
    pname = os.path.splitext(os.path.basename(exe))[0].lower()
    if not pname:
        return []
    pids = set()
    for p in pymem.process.list_processes():
        try:
            nm = p.szExeFile.decode("utf-8", "ignore").lower()
        except Exception:
            continue
        if nm.split(".")[0] == pname:
            pids.add(p.th32ProcessID)
    if not pids:
        return []
    out = []
    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def cb(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        pid = wt.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value in pids and _rect_area(hwnd) >= 40 * 40:
            out.append(hwnd)
        return True
    user32.EnumWindows(cb, 0)
    return out


def li_minimize(hwnd):
    try:
        user32.ShowWindow(hwnd, 6)     # SW_MINIMIZE
    except Exception:
        pass


def li_grab_hwnd(hwnd):
    """Chup toan bo vung cua so hwnd (ke ca khong phai main.exe) -> PIL.Image
    RGB. Dung cho launcher (Play now). None neu hong.
    Restore NEU MINIMIZE: GetWindowRect cua an = (-32000,-32000)+16000 →
    grab bbox ngoai man hinh → anh DEN/loi (nguyen nhan hong nut 📷/◎)."""
    try:
        from PIL import ImageGrab
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, 9)         # SW_RESTORE
            time.sleep(0.4)
        r = wt.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(r))
        W, H = r.right - r.left, r.bottom - r.top
        if W < 8 or H < 8 or r.left <= -30000:
            return None
        try:
            if user32.GetForegroundWindow() != hwnd:
                user32.BringWindowToTop(hwnd)
                user32.SetForegroundWindow(hwnd)
                time.sleep(0.12)
        except Exception:
            pass
        return ImageGrab.grab(bbox=(r.left, r.top, r.left + W, r.top + H))
    except Exception:
        return None


def li_click_rel(hwnd, x, y):
    """Bam toa do TUONG DOI trong cua so hwnd (quy doi sang man hinh).
    GUAN TRONGLIEN: (1) active cua so truoc khi bam; (2) poll toi ~8s cho
    den khi cua so THAT SU nam duoi con tro — giua man hinh login/game load
    <1s khong kip, click roi vao void = 'bam khong duoc' (P2/P4)."""
    _ensure_foreground(hwnd)
    r = wt.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    sx, sy = r.left + int(x), r.top + int(y)
    end = time.time() + 8.0
    ok = False
    while time.time() < end:
        user32.SetCursorPos(sx, sy)
        time.sleep(0.05)
        if _window_at(sx, sy) == hwnd and \
                user32.GetForegroundWindow() in (hwnd, user32.GetAncestor(hwnd, 2)):
            ok = True
            break
        _ensure_foreground(hwnd)
        user32.GetWindowRect(hwnd, ctypes.byref(r))   # rect co the doi (restore)
        sx, sy = r.left + int(x), r.top + int(y)
        time.sleep(0.3)
    if not ok:
        log_arrive(f"  [LI] click ({x},{y}): cua so khong nam duoi tro sau 8s — van bam")
    down = 0x0002
    user32.mouse_event(down, 0, 0, 0, 0)
    time.sleep(0.05)
    user32.mouse_event(0x0004, 0, 0, 0, 0)


def li_wait_img_click(hwnd, key, timeout=LI_IMG_TIMEOUT):
    """Cho anh template xuat hien on dinh (2 lan lien tiep) trong cua so roi
    bam vao no. Tra True neu bam, False neu het gio/bi dung."""
    path = li_tpl(key)
    if not os.path.exists(path):
        return False
    end, last, stable = time.time() + timeout, None, 0
    while time.time() < end:
        if STOP_REQUESTED[0] or check_stop_key():
            return False
        _ensure_foreground(hwnd)
        hit = li_find_button(path, hwnd)
        if hit:
            if last and abs(hit[0] - last[0]) <= 2 and abs(hit[1] - last[1]) <= 2:
                stable += 1
            else:
                stable = 0
            last = hit
            if stable >= 1:
                li_click_rel(hwnd, hit[0], hit[1])
                time.sleep(LI_STEP_PAUSE)
                return True
        else:
            last, stable = None, 0
        time.sleep(0.8)
    return False


def li_wait_img_present(hwnd, key, timeout=LI_IMG_TIMEOUT):
    """Chi cho anh xuat hien (khong bam) — dung cho Credit (tin hieu load xong)."""
    path = li_tpl(key)
    if not os.path.exists(path):
        return True        # khong co template -> coi như xong (khong chan)
    end, last, stable = time.time() + timeout, None, 0
    while time.time() < end:
        if STOP_REQUESTED[0] or check_stop_key():
            return False
        _ensure_foreground(hwnd)
        hit = li_find_button(path, hwnd)
        if hit:
            if last and abs(hit[0] - last[0]) <= 2 and abs(hit[1] - last[1]) <= 2:
                return True
            last = hit
        else:
            last = None
        time.sleep(0.8)
    return False


def li_type_credentials(user, pwd):
    """user → Tab → pass → Enter. GO TUNG PHIM THAT (vk+scan, nhu ban tay go)
    — KHONG dung clipboard: lan dau paste mat khau vao o pass, client MU LUU
    CHUOI DO VINH VIEN va moi Ctrl+V sau (o chat) dan ra gia tri CU nay, bat
    chap clipboard hien tai. Khong copy gi ca → khong con gi de no cache."""
    _ensure_foreground(ACTIVE_HWND[0])
    time.sleep(0.3)
    type_keys(user)
    time.sleep(0.6)
    _tap_vk(0x09)                   # VK_TAB (scan code that)
    time.sleep(0.6)
    type_keys(pwd)
    time.sleep(0.6)
    _tap_vk(0x0D)                   # VK_RETURN gui dang nhap


def load_li_cfg():
    """Doc cai dat LI: accounts, launcher_path, titles, coords, confidence.
    Lan dau chay _li_migrate_legacy de KHONG phai cai lai (giu config cu)."""
    try:
        d = json.load(open(LI_COORDS_FILE, encoding="utf-8"))
        d = d if isinstance(d, dict) else {}
    except Exception:
        d = {}
    d = _li_migrate_legacy(d)
    return d


def save_li_cfg(d):
    try:
        os.makedirs(LI_TPL_DIR, exist_ok=True)
        json.dump(d, open(LI_COORDS_FILE, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
    except Exception:
        pass


def li_default_account():
    return {"user": "", "password": "", "server_index": 0,
            "char_name": "", "enabled": True}


def _li_migrate_legacy(cfg):
    """GIU NGUYEN config da luu truoc do: neu LI chua co gia tri cho key nao,
    lay tu config.json cua tool MU-Login cu (co the nam canh app hoac o
    ~/mu_login). Khong bao gio ghi de key da ton tai."""
    for cand in (os.path.join(APP_DIR, "mu_login", "config.json"),
                 os.path.join(os.path.expanduser("~"), "mu_login", "config.json")):
        try:
            d = json.load(open(cand, encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(d, dict):
            continue
        for key in ("launcher_path", "launcher_title", "game_title", "confidence"):
            alt = "window_title" if key == "launcher_title" else key
            if key not in cfg and d.get(alt):
                cfg[key] = d[alt]
        if "coords" not in cfg and isinstance(d.get("coords"), dict) and d["coords"]:
            cfg["coords"] = d["coords"]
        if "accounts" not in cfg and d.get("user"):
            acc = {"user": d.get("user", ""), "password": d.get("password", ""),
                   "server_index": int(d.get("server_index", 0) or 0),
                   "char_name": d.get("char_name", ""), "enabled": True}
            src = d.get("accounts")
            cfg["accounts"] = src if isinstance(src, list) and src else [acc]
        break
    return cfg


def li_load_accounts(cfg=None):
    cfg = cfg if cfg is not None else load_li_cfg()
    accs = cfg.get("accounts")
    if isinstance(accs, list) and accs:
        out = []
        for a in accs:
            d = li_default_account()
            d.update({k: a[k] for k in d if k in a})
            out.append(d)
        return out
    # migrate tu ban mu_login cu (user/password/server_index o goc)
    if cfg.get("user"):
        return [{"user": cfg["user"], "password": cfg.get("password", ""),
                 "server_index": int(cfg.get("server_index", 0)),
                 "char_name": cfg.get("char_name", ""), "enabled": True}]
    return []


def li_save_accounts(cfg, accs):
    cfg = dict(cfg)
    cfg["accounts"] = accs
    save_li_cfg(cfg)


def send_home_verified(hwnd=None):
    """Toi duoc dich: 1s sau -> co che Home nhu cu: nhan Home -> 1s -> kiem
    tra anh Helper -> chua co -> nhan lai -> ... LAP VO HAN toi khi thay
    (PgUp thoat). (Che do don gian KHONG o day — chay ngay sau thoat Giam
    tai trong send_ctrl_f_off, trung o day la thua.)"""
    time.sleep(1.0)
    i = 0
    while True:
        if STOP_REQUESTED[0] or check_stop_key():
            return False
        p = icon_present(HELPER_IMG, hwnd=hwnd)
        if p is None:
            # Khong verify duoc bang anh → bam Home 1 lan (best effort) va
            # di tiep; KHONG im lang bo qua nhu truoc day.
            log_arrive("  Helper: khong verify duoc anh → bam Home 1 lan.")
            send_home(hwnd)
            time.sleep(1.0)
            return True
        if p:
            log_arrive("  Helper: da thay bieu tuong -> cho 1s roi di tiep.")
            time.sleep(1.0)
            return True
        i += 1
        log_arrive(f"  Helper: chua thay -> nhan Home lan {i}, 1s sau kiem tra")
        send_home(hwnd)
        time.sleep(1.0)


def send_ctrl_f(hwnd=None):
    """Gui phim Ctrl+F (Giam tai) DUNG vao cua so hwnd: giu Ctrl + nhan F co
    scan code that. KHONG gui Esc — Esc gay loi toan bo qua trinh.
    Dam bao foreground: hwnd thieu -> dung cua so ACTIVE; khong focus duoc
    -> log canh bao (phim se roi vao cua so khac)."""
    hwnd = hwnd or ACTIVE_HWND[0]
    if not guard_foreground(hwnd, "Ctrl+F"):
        log_arrive(f"  Ctrl+F: khong giu duoc focus {hwnd} — "
                   f"bo qua de tranh phim roi vao cua so khac!")
        return
    time.sleep(0.10)
    scan_ctrl = user32.MapVirtualKeyW(0x11, 0)  # VK_CONTROL
    scan_f = user32.MapVirtualKeyW(0x46, 0)     # VK_F
    user32.keybd_event(0x11, scan_ctrl, 0, 0)   # Ctrl down
    time.sleep(0.06)
    user32.keybd_event(0x46, scan_f, 0, 0)      # F down
    time.sleep(0.06)
    user32.keybd_event(0x46, scan_f, 0x0002, 0) # F up
    time.sleep(0.06)
    user32.keybd_event(0x11, scan_ctrl, 0x0002, 0)  # Ctrl up


# Trang thai Giam tai theo cua so (tool TU NHHO): hwnd -> True/False/None.
LT_ON = {}


def send_ctrl_f_on(hwnd=None):
    """Vao Giam tai theo dung spec:
    tim hinh → KHONG thay → gui Ctrl+F → 1s sau kiem tra → THAY → dung.
    (Chua thay → bam lai...) lap lai cho toi khi THAY icon.
    Moi lan bam deu dam bao Ctrl+F roi DUNG cua so hwnd (focus + ACTIVE_HWND).
    TOI DA 10 LAN de khong ket khi phim khong toi; ghi nho ON/OFF theo t."""
    hwnd = hwnd or ACTIVE_HWND[0]
    i = 0
    while True:
        if STOP_REQUESTED[0] or check_stop_key():
            return False
        p = icon_present(LT_IMG, hwnd=hwnd)
        if p is None:
            LT_ON[hwnd] = None
            log_arrive("  Giam tai ON: khong verify duoc anh (chup lai template 📷"
                       " / loi chup man hinh) → chua bat, vong sau thu lai.")
            return False
        if p:
            LT_ON[hwnd] = True
            log_arrive("  Giam tai ON: da thay bieu tuong -> cho 1s roi di tiep.")
            time.sleep(1.0)
            return True
        if i >= 10:
            LT_ON[hwnd] = None
            log_arrive("  Giam tai ON: 10 LAN van khong thay icon → bo qua, "
                       "chay tiep (kiem tra template LT / focus cua so).")
            return False
        i += 1
        log_arrive(f"  Giam tai ON: chua thay -> nhan Ctrl+F lan {i}"
                   f" (vao cua so {hwnd:#x}), 1s sau kiem tra")
        send_ctrl_f(hwnd)
        time.sleep(1.0)


def send_ctrl_f_off(hwnd=None):
    """Thoat Giam tai theo dung spec:
    tim hinh → THAY → gui Ctrl+F → 1s sau kiem tra → KHONG thay → dung.
    (Van thay → bam lai...) lap lai cho toi khi KHONG con thay icon.
    Moi lan bam deu dam bao Ctrl+F roi DUNG cua so hwnd.
    TOI DA 10 LAN de khong ket khi phim khong toi.
    Tra True khi icon da mat / khong co template; False khi 10 lan khong xong.
    CHE DO DON GIAN khong o day — run_visit goi RIENG sau khi off thanh cong."""
    hwnd = hwnd or ACTIVE_HWND[0]
    i = 0
    while True:
        if STOP_REQUESTED[0] or check_stop_key():
            return False
        p = icon_present(LT_IMG, hwnd=hwnd)
        if p is None:
            LT_ON[hwnd] = None                   # KHONG verify duoc → khong gia dinh gi ca
            log_arrive("  Giam tai OFF: khong verify duoc anh (chup lai template 📷"
                       " / loi chup man hinh) → CHUA thoat, thu lai sau.")
            return False
        if not p:
            LT_ON[hwnd] = False
            log_arrive("  Giam tai OFF: icon da mat -> cho 1s roi di tiep.")
            time.sleep(1.0)
            return True
        if i >= 10:
            LT_ON[hwnd] = None
            log_arrive("  Giam tai OFF: 10 LAN van con thay icon → bo qua, "
                       "chay tiep (kiem tra template LT / focus cua so).")
            return False
        i += 1
        log_arrive(f"  Giam tai OFF: con thay -> nhan Ctrl+F lan {i}"
                   f" (vao cua so {hwnd:#x}), 1s sau kiem tra")
        send_ctrl_f(hwnd)
        time.sleep(1.0)


# log_arrive duoc goi tu cac ham CAP MODULE (send_home_verified,
# send_ctrl_f_on/off...) — ma `root` / `_log_add` chi ton tai BEN TRONG main().
# main() nap 2 gia tri nay vao day khi UI san sang.
ROOT = [None]
LOG_HOOK = [None]


def log_arrive(msg):
    """Ghi log an toan tu thread nen — CHI vao logbox trong ung dung
    (khong file, khong console). _log_add(text, done, color): du 3 tham so."""
    try:
        r, fn = ROOT[0], LOG_HOOK[0]
        if r is not None and fn is not None:
            r.after(0, lambda: fn(msg, False, None))
    except Exception:
        pass


# --- Clipboard: copy/dan lenh chat (nhanh & chinh xac hon go tung ky tu) ---
_cf = ctypes.windll.user32
kernel32.GlobalAlloc.restype = ctypes.c_void_p
kernel32.GlobalAlloc.argtypes = [wt.UINT, ctypes.c_size_t]
kernel32.GlobalLock.restype = ctypes.c_void_p
kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
kernel32.GlobalUnlock.restype = wt.BOOL
kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
kernel32.GlobalSize.restype = ctypes.c_size_t
kernel32.GlobalSize.argtypes = [ctypes.c_void_p]
kernel32.GlobalFree.restype = ctypes.c_void_p
kernel32.GlobalFree.argtypes = [ctypes.c_void_p]
_cf.OpenClipboard.restype = wt.BOOL
_cf.OpenClipboard.argtypes = [wt.HWND]
_cf.SetClipboardData.restype = ctypes.c_void_p
_cf.SetClipboardData.argtypes = [wt.UINT, ctypes.c_void_p]
_cf.GetClipboardData.restype = ctypes.c_void_p
_cf.GetClipboardData.argtypes = [wt.UINT]
_cf.IsClipboardFormatAvailable.restype = wt.BOOL
_cf.IsClipboardFormatAvailable.argtypes = [wt.UINT]
_cf.GetClipboardSequenceNumber.restype = wt.DWORD
CF_UNICODETEXT = 13

# --- Go ky tu bang PHIM THAT (vk + scan code) — duong duy nhat MU khong chan ---
user32.VkKeyScanW.restype = ctypes.c_short
user32.VkKeyScanW.argtypes = [wt.WCHAR]

def _tap_char(ch):
    """Bam 1 ky tu nhu nguoi dung: VkKeyScanW → vk + modifier (Shift cho
    hoa/ky tu dac biet), scan code that qua keybd_event. False neu layout
    khong map duoc ky tu."""
    u = user32.VkKeyScanW(ch)
    if u == -1 or (u & 0x100):           # -1: khong map; bit Ctrl: lo
        return False
    vk = u & 0xFF
    mods = []
    if u & 0x200: mods.append(0x10)      # VK_SHIFT
    if u & 0x400: mods.append(0x12)      # VK_MENU (AltGr)
    for m in mods:
        user32.keybd_event(m, user32.MapVirtualKeyW(m, 0), 0, 0)
    _tap_vk(vk)
    for m in reversed(mods):
        user32.keybd_event(m, user32.MapVirtualKeyW(m, 0), 0x0002, 0)
    return True

def type_keys(text):
    """Ca chuoi = tung _tap_char; ky tu layout kh map → SendInput unicode
    (hi hi: chu VN). Tra True neu toan bo duoc go."""
    for ch in text:
        if not _tap_char(ch):
            if not type_unicode(ch):
                return False
        time.sleep(0.03)
    return True


def copy_to_clipboard(text):
    """Dat text vao clipboard (CF_UNICODETEXT). Retry OpenClipboard toi da
    10 lan (clipboard co the bi app khac giu tam thoi). Tra True/False."""
    for _ in range(10):
        if _cf.OpenClipboard(None):
            break
        time.sleep(0.05)
    else:
        return False
    try:
        _cf.EmptyClipboard()
        data = text.encode("utf-16-le") + b"\x00\x00"
        hmem = kernel32.GlobalAlloc(0x0042, len(data))   # GMEM_MOVEABLE|ZEROINIT
        if not hmem:
            return False
        ptr = kernel32.GlobalLock(hmem)
        if not ptr:
            kernel32.GlobalFree(hmem)
            return False
        ctypes.memmove(ptr, data, len(data))
        kernel32.GlobalUnlock(hmem)
        ok = _cf.SetClipboardData(CF_UNICODETEXT, hmem)
        return bool(ok)
    except Exception:
        return False
    finally:
        _cf.CloseClipboard()


def read_clipboard():
    """Doc NOI DUNG that dang nam trong clipboard (CF_UNICODETEXT).
    Tra str, hoac None neu khong doc duoc. Dung de XAC MINH lenh da copy
    dung truoc khi dan — tranh dan nham noi dung cu con sot trong bo nho."""
    if not _cf.IsClipboardFormatAvailable(CF_UNICODETEXT):
        return None
    for _ in range(10):
        if _cf.OpenClipboard(None):
            break
        time.sleep(0.05)
    else:
        return None
    try:
        hmem = _cf.GetClipboardData(CF_UNICODETEXT)
        if not hmem:
            return None
        ptr = kernel32.GlobalLock(hmem)
        if not ptr:
            return None
        try:
            n = kernel32.GlobalSize(hmem)
            raw = ctypes.string_at(ptr, n)
        finally:
            kernel32.GlobalUnlock(hmem)
        # cat tai ky tu NUL ket thuc (clipboard khong dem them byte rac)
        return raw.decode("utf-16-le", "ignore").split("\x00", 1)[0]
    except Exception:
        return None
    finally:
        _cf.CloseClipboard()


def paste_clipboard():
    """Gui Ctrl+V bang SCAN CODE THAT (MapVirtualKeyW).

    Ban cu dung keybd_event(vk, scan=0) — chinh codebase nay da ghi nhan
    (ham _tap_vk): game doc ban phim qua DirectInput/raw input BO QUA phim
    co scan=0, nen Ctrl+V/Enter co the KHONG toi duoc cua so game va lenh
    roi vao cua so khac. O day gui scan chat cho ca Ctrl luot V."""
    VK_CONTROL = 0x11
    VK_V = 0x56
    _hold_vk(VK_CONTROL)
    time.sleep(0.04)
    _tap_vk(VK_V)
    time.sleep(0.04)
    _release_vk(VK_CONTROL)
    time.sleep(0.04)

# --- G_ui text: MAC DINH SendInput unicode, KHONG dung clipboard ---
#clipboard bi "ket" (dan ra noi dung cu du da copy khac): trinh quan ly
#clipboard / Windows 11 history (Win+V) / app dong bo clipboard (TeamViewer,
#Logitech Options, Dropbox...) giat WM_CLIPBOARDUPDATE va RENDERFORMAT tre —
#no cache gia tri DAU TIEN va ghi de moi lan ta Set → Ctrl+V trong game luon
#ra NOI DUNG CU. type_unicode (KEYEVENTF_UNICODE) khong cham clipboard →
#kh the bi trung choan (mo rong BMP ky tu an toan).


# --- SendInput unicode: go dung tung ky tu, khong phu thuoc layout ban phim ---
class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wt.WORD), ("wScan", wt.WORD), ("dwFlags", wt.DWORD),
                ("time", wt.DWORD), ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]


class _INPUTU(ctypes.Union):
    _fields_ = [("ki", _KEYBDINPUT)]


class _INPUT(ctypes.Structure):
    _fields_ = [("type", wt.DWORD), ("u", _INPUTU)]


_cf.SendInput.restype = ctypes.c_uint
_cf.SendInput.argtypes = [ctypes.c_uint, ctypes.POINTER(_INPUT), ctypes.c_int]
KEYEVENTF_UNICODE, KEYEVENTF_KEYUP = 0x0004, 0x0002


def type_unicode(text):
    """Gui tung ky tu bang SendInput KEYEVENTF_UNICODE — ma hoa truc tiep,
    KHONG qua VkKeyScanW/layout nen kh the sai ky tu (khac _tap_char:
    VkKeyScanW tra -1 voi ky tu khong co tren layout -> bam nham phim).
    Chi dung khi clipboard hong; duong dan chinh van la Ctrl+V."""
    for ch in text:
        code = ord(ch)
        if code > 0xFFFF:
            continue                      # ngoai BMP: bo qua, khong doan sai
        for flags in (KEYEVENTF_UNICODE, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP):
            ev = _INPUT()
            ev.type = 1                   # INPUT_KEYBOARD
            ev.u.ki = _KEYBDINPUT(0, code, flags, 0, None)
            if _cf.SendInput(1, ctypes.byref(ev), ctypes.sizeof(_INPUT)) != 1:
                return False
            time.sleep(0.02)
    return True


# --- Dung tool bang phim PgUp (polling toan cuc) ---
STOP_REQUESTED = [False]
VK_PGUP = 0x21


def check_stop_key():
    """Tra ve True neu phim PgUp dang duoc nhan (GetAsyncKeyState toan cuc).
    Goi trong vong lap di chuyen de phat hien PgUp -> dung + tra quyen chuot."""
    # bit cao nhat (0x8000) = phim dang duoc giu
    return bool(user32.GetAsyncKeyState(VK_PGUP) & 0x8000)


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


LI_BUSY = [False]           # login dang chay — train tu choi de tranh tranh
LI_BINDINGS = {}            # user -> hwnd dang gan (do LI dang hoac title map)
LI_NEEDS_RELOGIN = []       # queue: user can relogin lai
LI_RELOGIN_FAILS = {}       # user -> so lan fail lien tiep (>=3 thi nghi 60s)
LI_RELOGIN_WAIT = {}        # user -> epoch duoc phep thu lai


def li_game_windows(pattern):
    return [h for h in li_find_windows(pattern)]


def li_parse_pt(v):
    try:
        return (int(v[0]), int(v[1]))
    except (TypeError, ValueError, IndexError):
        return None


def li_close_hwnd(hwnd):
    """Gui WM_CLOSE de dong cua so (luong login hong → don deo, lan sau mo moi)."""
    if not hwnd:
        return
    try:
        if user32.IsWindow(hwnd):
            user32.PostMessageW(hwnd, 0x0010, 0, 0)   # WM_CLOSE
    except Exception:
        pass


def li_run_account(acc, cfg, log, deadline=None):
    """1 luong dang nhap cho 1 account. cfg: keys launcher_path, launcher_title,
    game_title, coords{login,s0..s4,post1..4}. Tra (True, hwnd) neu thanh cong
    (kem cua so game MOI) hoac (False, None). deadline = epoch TOAN LUONG
    (mac dinh 5 phut): het gio → dong cua so game, tra that bai de li_run_all
    lam lai TU DAU. Moi thao tac chuat/phim deu active cua so truoc (guard
    trong li_click_rel / _ensure_foreground)."""
    coords = cfg.get("coords", {}) or {}
    ltitle = cfg.get("launcher_title", "MU.*Launcher")
    gtitle = cfg.get("game_title", "Season21")
    login_pt = li_parse_pt(coords.get("login"))
    srv_pt = li_parse_pt(coords.get(f"s{int(acc['server_index'])}"))
    if login_pt is None or srv_pt is None:
        log(f"[loi] {acc['user']}: thieu toa do Dang nhap/Server")
        return (False, None)
    if deadline is None:
        deadline = time.time() + LI_TOTAL_TIMEOUT

    def stopped():
        return STOP_REQUESTED[0] or check_stop_key()

    def late(g=None):
        """Het gio toan luong → dong cua so game, that bai (run_all lam lai)."""
        if time.time() >= deadline or stopped():
            if g:
                li_close_hwnd(g)
                log(f"  [LI] {acc['user']}: qua gio/PgUp → dong cua so game, lam lai tu dau")
            return True
        return False

    def rem():
        return max(5.0, deadline - time.time())

    # B1 launcher: TON TAI SAN (title HOAC process dang chay, ke ca minimize)
    # → maximize + active cua CU, KHONG mo exe lan 2 (MU chan launcher thu 2).
    h = li_pick_window(li_launcher_windows(cfg))
    if h:
        li_restore_launcher(h)
    else:
        exe = cfg.get("launcher_path", "")
        if not exe or not os.path.isfile(exe):
            log("[loi] launcher_path khong ton tai (cau hinh LI)"); return (False, None)
        log("[LI] khong thay launcher → mo exe moi")
        try:
            import subprocess
            subprocess.Popen([exe], cwd=os.path.dirname(exe))
        except Exception:
            log("[loi] khong mo duoc launcher"); return (False, None)
        end = min(time.time() + 60, deadline)
        while time.time() < end and not h:
            h = li_pick_window(li_launcher_windows(cfg))
            if not h:
                time.sleep(0.5)
        if not h:
            log("[loi] khong thay cua so launcher"); return (False, None)

    # B2 Play now (anh) -> bam -> minimize launcher
    before = set(li_game_windows(gtitle))
    if stopped() or not li_wait_img_click(h, "play", timeout=rem()):
        return (False, None)
    li_minimize(h)
    if late():
        return (False, None)

    # B3 cua so game MOI
    g = None
    while time.time() < deadline and not stopped():
        fresh = [x for x in li_game_windows(gtitle) if x not in before]
        if fresh:
            g = li_pick_window(fresh); break
        time.sleep(0.5)
    if g is None and not before:
        g = li_pick_window(li_game_windows(gtitle))
    if g is None:
        if late():
            return (False, None)
        log("  [loi] khong co cua so game moi"); return (False, None)
    _ensure_foreground(g)
    ACTIVE_HWND[0] = g
    time.sleep(LI_STEP_PAUSE)
    if late(g):
        return (False, None)

    # B4 Credit = tin hieu load xong
    if not li_wait_img_present(g, "credit", timeout=rem()):
        li_close_hwnd(g)
        return (False, None)
    time.sleep(LI_STEP_PAUSE)
    if late(g):
        return (False, None)

    # B5/B6 Dang nhap -> Server (li_click_rel tu active + verify duoi tro)
    li_click_rel(g, login_pt[0], login_pt[1]); time.sleep(LI_STEP_PAUSE)
    li_click_rel(g, srv_pt[0], srv_pt[1]); time.sleep(LI_STEP_PAUSE)
    if late(g):
        return (False, None)

    # B7 clipboard dang nhap
    _ensure_foreground(g); li_type_credentials(acc["user"], acc["password"])
    time.sleep(LI_STEP_PAUSE)

    # B8 Connect -> bam (hong → DONG cua so game: de mo lan sau thay cua so cu
    # o man hinh connect, B3 se khong tim duoc cua so moi va ket tang)
    if not li_wait_img_click(g, "connect", timeout=rem()):
        li_close_hwnd(g)
        return (False, None)
    time.sleep(LI_STEP_PAUSE)
    if late(g):
        return (False, None)

    # B9 4 diem sau Connect (co dinh trong config; thieu -> bo qua)
    for j in range(1, 5):
        if late(g):
            return (False, None)
        pt = li_parse_pt(coords.get(f"post{j}"))
        if pt:
            li_click_rel(g, pt[0], pt[1]); time.sleep(LI_STEP_PAUSE)

    # B10a: doi NHAN VATVao WORLD that su (title doi thành [Char:..][Level:..]).
    # Ctrl+F bam luc CON o man hinh chon nhan vat / loading = VO NGHIA
    # (icon Giam tai chi ton tai trong world) → day la ly do "login xong ma
    # khong vao Giam tai, log khong thay".
    end_w = min(time.time() + 120, deadline + 120)
    while time.time() < end_w and not stopped():
        nm_w, lv_w = read_title(g)
        if nm_w:
            log(f"  [LI] {acc['user']}: da vo world ({nm_w} Lv {lv_w})")
            break
        time.sleep(1.0)
    else:
        log(f"  [LI] {acc['user']}: chua thay title nhan vat — van thu bat Giam tai")

    # B10b: BAT HELPER truoc (Home) — verify bang anh Helper, nhan lai toi khi
    # thay (cung co che train chain dung). CHUA Helper → KHONG bat Giam tai.
    _ensure_foreground(g)
    if send_home_verified(g):
        log(f"  [LI] {acc['user']}: Helper BAT (icon thay) → tiep Giam tai")
    else:
        log(f"  [LI] {acc['user']}: Helper CHUA bat duoc (PgUp?) → bo buoc Giam tai")
        return (True, g)

    # B10c: → BAT GIAM TAI cho cua so nay (verify hinh, toi da 10 lan)
    _ensure_foreground(g)
    if send_ctrl_f_on(g):
        log(f"  [LI] {acc['user']}: ✔ DA VAT Giam tai (icon xuat hien)")
    else:
        log(f"  [LI] {acc['user']}: Giam tai CHUA bat duoc — train se thu lai")
    return (True, g)


def li_run_all(cfg, accounts, log, on_done=None):
    """Chay lan luot moi account (worker thread). Tranh train qua LI_BUSY."""
    LI_BUSY[0] = True
    STOP_REQUESTED[0] = False
    ok_n = 0
    try:
        enabled = [a for a in accounts if a.get("user") and a.get("enabled", True)]
        for i, acc in enumerate(enabled, 1):
            u = acc["user"]
            # DA DANG NHAP (bind cua so con song, o tren the gioi) → BO QUA,
            # KHONG mo cua so login nua. Watchdog van canh neu cua so chet.
            hwnd_b = LI_BINDINGS.get(u)
            if hwnd_b and user32.IsWindow(hwnd_b):
                nm_b, _lv = read_title(hwnd_b)
                if nm_b:                      # co [Char:] = da in-game that
                    log(f"===== LI {i}/{len(enabled)}: {u} — Bỏ qua "
                        f"(dang trong world: {nm_b}) =====")
                    ok_n += 1
                    continue
            log(f"===== LI {i}/{len(enabled)}: {acc['user']} (S{int(acc['server_index'])+1}) =====")
            attempt = 0
            # MOI LAN THU co deadline 5 phut (LI_TOTAL_TIMEOUT) trong
            # li_run_account; het gio → cua so game bi dong → LAP LAI TU DAU,
            # khong gioi han 3 lan nua — chi dung khi thanh cong hoac PgUp.
            while True:
                if STOP_REQUESTED[0] or check_stop_key():
                    log(">> LI dung."); return
                attempt += 1
                ok, g = li_run_account(
                    acc, cfg, log, deadline=time.time() + LI_TOTAL_TIMEOUT)
                if ok:
                    ok_n += 1
                    if g:
                        LI_BINDINGS[acc["user"]] = g
                    LI_RELOGIN_FAILS.pop(acc["user"], None)
                    LI_RELOGIN_WAIT.pop(acc["user"], None)
                    log(f"  ✔ {acc['user']} xong" + (f" hwnd={g}" if g else ""))
                    break
                log(f"  {acc['user']}: lan {attempt} that bai/qua gio — "
                    f"lam lai tu dau")
                time.sleep(LI_STEP_PAUSE)
        log(f"===== LI xong: {ok_n}/{len(enabled)} =====")
    except Exception as e:
        log(f"[loi LI] {type(e).__name__}: {e}")
    finally:
        LI_BUSY[0] = False
        if on_done:
            on_done()


def main():
    global GHWND
    enable_debug()
    A, inv = load_matrix()
    print(f"[calib] A={A}")
    print(f"[calib] inv={inv}")

    # --- Da cua so: moi cua so game (pid) co Pymem rieng ---
    PMS = {}                      # pid -> pymem.Pymem
    ARECT = [None]                # client rect cua cua so dang ACTIVE
    ACX = [0]
    ACY = [0]

    def get_pm_for(hwnd):
        """Pymem gan voi pid cua hwnd (mo lazy, tu choi khi hong)."""
        pid = wt.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        pid = pid.value
        if pid not in PMS:
            try:
                PMS[pid] = pymem.Pymem(pid)
            except Exception:
                return None
        return PMS[pid]

    def set_active(hwnd):
        """Chuyen cua so lam viec: cap nhat GHWND/ACTIVE_HWND/rect/anchor."""
        global GHWND
        ACTIVE_HWND[0] = hwnd
        GHWND = hwnd
        r = find_window_hwnd(hwnd)
        if r:
            (nL, nT, nW, nH), _ = r
            ARECT[0] = (nL, nT, nW, nH)
            ACX[0], ACY[0] = nL + ANCHOR_X, nT + ANCHOR_Y
            print(f"[active] {nW}x{nH} tai ({nL},{nT}); tam=({ACX[0]},{ACY[0]})")

    # Mo cua so game dau tien lam active — KHONG raise neu chua mo game:
    # UI van phai hien len duoc; sync_bars/train_chain se tu bat kip cua so
    # game mo sau nay.
    _w0 = find_window_hwnd()
    if _w0:
        (L, T, W, H), _hwnd0 = _w0
        set_active(_hwnd0)
        if GHWND:
            user32.SetForegroundWindow(GHWND)
    else:
        print("[window] Chua mo game — UI van chay; mo main.exe roi thao tac.")

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
    root.geometry("280x520")
    root.resizable(False, False)   # kich thuoc CO DINH -> layout on dinh

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
    # Segoe UI = font Windows ho tro dau tieng Viet day du nhat. (80% kich thuoc cu)
    if USE_CTK:
        root.configure(fg_color=BG)
        f_title = ctk.CTkFont(family="Segoe UI", size=15, weight="bold")
        f_sub = ctk.CTkFont(family="Segoe UI", size=12)
        f_body = ctk.CTkFont(family="Segoe UI", size=13)
        f_btn = ctk.CTkFont(family="Segoe UI", size=14, weight="bold")
        f_small = ctk.CTkFont(family="Segoe UI", size=11)
        f_bar = ctk.CTkFont(family="Segoe UI", size=11, weight="bold")
    else:
        f_title = tkfont.Font(family="Segoe UI", size=15, weight="bold")
        f_sub = tkfont.Font(family="Segoe UI", size=12)
        f_body = tkfont.Font(family="Segoe UI", size=13)
        f_btn = tkfont.Font(family="Segoe UI", size=14, weight="bold")
        f_small = tkfont.Font(family="Segoe UI", size=11)
        f_bar = tkfont.Font(family="Segoe UI", size=11, weight="bold")
        try:
            ttk.Style().theme_use("clam")
        except Exception:
            pass

    PAD = 12

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
        kw.setdefault("font", f_btn)
        if USE_CTK:
            kw.setdefault("height", 36)          # px (tk.Button: height = SO DONG!)
            kw.setdefault("anchor", "center")
            return ctk.CTkButton(parent, text=text, corner_radius=10,
                                 fg_color=ACCENT, hover_color=ACCENT_HOVER,
                                 text_color="#FFFFFF", **kw)
        kw.pop("height", None)
        kw.pop("anchor", None)
        return tk.Button(parent, text=text,
                         bg=ACCENT, fg="#FFFFFF", activebackground=ACCENT_HOVER,
                         activeforeground="#FFFFFF", relief="flat", bd=0, **kw)

    def btn_secondary(parent, text, cmd=None, **kw):
        kw.setdefault("command", cmd)
        if USE_CTK:
            return ctk.CTkButton(parent, text=text,
                                 font=f_body, height=34, corner_radius=10,
                                 fg_color="#F2F2F7", hover_color="#E5E5EA",
                                 text_color=TEXT, **kw)
        return tk.Button(parent, text=text, font=f_body,
                         bg="#F2F2F7", fg=TEXT, activebackground="#E5E5EA",
                         relief="flat", bd=0, **kw)

    def btn_danger(parent, text, cmd=None, **kw):
        kw.setdefault("command", cmd)
        if USE_CTK:
            return ctk.CTkButton(parent, text=text,
                                 font=f_btn, height=36, corner_radius=10,
                                 fg_color=DANGER, hover_color="#FF453A",
                                 text_color="#FFFFFF", **kw)
        return tk.Button(parent, text=text, font=f_btn,
                         bg=DANGER, fg="#FFFFFF", activebackground="#FF453A",
                         relief="flat", bd=0, **kw)

    # ===== Layout: hang tren = Train + 3 tab; duoi = noi dung tab =====
    if USE_CTK:
        root.grid_columnconfigure(0, weight=1)
        root.grid_rowconfigure(1, weight=1)
    else:
        root.configure(bg=BG)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(1, weight=1)

    top_bar = (ctk.CTkFrame(root, fg_color="transparent") if USE_CTK
               else tk.Frame(root, bg=BG))
    top_bar.grid(row=0, column=0, sticky="ew", padx=PAD, pady=(PAD, 6))

    # --- Nut Train: CHAN ICON. CTkButton can lech glyph trai — them
    # anchor/padx trong btn_primary de ▶ nam dung giua. ---
    btn_train = btn_primary(top_bar, "▶", width=26, height=26, font=f_body,
                            command=lambda: toggle_train())
    btn_train.pack(side="left", padx=(0, 8))

    content = (ctk.CTkFrame(root, fg_color="transparent") if USE_CTK
               else tk.Frame(root, bg=BG))
    content.grid(row=1, column=0, sticky="nsew", padx=PAD, pady=(0, PAD))
    content.grid_columnconfigure(0, weight=1)
    content.grid_rowconfigure(0, weight=1)

    TABS = {}
    tab_btns = {}

    def show_tab(name):
        for k, f in TABS.items():
            f.grid_forget()
        TABS[name].grid(row=0, column=0, sticky="nsew")
        for k, b in tab_btns.items():
            sel = (k == name)
            if USE_CTK:
                b.configure(fg_color=ACCENT if sel else CARD,
                            text_color="#FFFFFF" if sel else TEXT,
                            hover_color=ACCENT_HOVER if sel else "#E5E5EA")
            else:
                b.configure(bg=ACCENT if sel else CARD,
                            fg="#FFFFFF" if sel else TEXT)

    for key, txt in (("ctrl", "RR"), ("cfg", "Spot"),
                     ("log", "Log"), ("li", "LI")):
        if USE_CTK:
            b = ctk.CTkButton(top_bar, text=txt, font=f_body, height=26,
                              width=52, corner_radius=6,
                              command=lambda k=key: show_tab(k))
        else:
            b = tk.Button(top_bar, text=txt, font=f_body, relief="flat", bd=0,
                          command=lambda k=key: show_tab(k))
        b.pack(side="left", padx=(0, 4))
        tab_btns[key] = b

    # luu tru: token /move -> [(token, name, x, y), ...]
    SPOTS = load_spots()
    SELECTED_SPOT = [None]   # (token, x, y) duoc chon lam dich

    def set_status(m):
        log_add(f"[*] {m}")

    def capture_icon(save_path, label, grab_fn=None):
        """Chup anh client game -> VE LEN overlay (den 100%) -> keo chuot
        quanh bieu tuong TRUC TIEP TREN ANH (ty le 1:1, khong qua toa do man
        hinh → hong khi game off-screen/DPI scaling) -> luu template PNG.
        grab_fn=None -> grab_client (game); truyen ham khac de chup cua so
        launcher cho tab LI."""
        shot = (grab_fn or grab_client)()
        if shot is None:
            set_status("Khong chup duoc man hinh (mo cua so nguon truoc).")
            return False
        from PIL import Image, ImageTk
        prev_grab = root.grab_current()   # modal dang mo (LI Config) — overlay
                                          # phai gianh grab thi moi keo duoc
        ov = tk.Toplevel(root)
        ov.attributes("-fullscreen", True)
        ov.attributes("-topmost", True)
        ov.configure(bg="black", cursor="crosshair")
        ov.grab_set()
        ov.lift()
        cv = tk.Canvas(ov, bg="black", highlightthickness=0)
        cv.pack(fill="both", expand=True)
        SW, SH = ov.winfo_screenwidth(), ov.winfo_screenheight()
        # Phong to (nguyen) neu client nho, de keo vung chinh xac hon
        scale = 1
        if shot.width < SW // 2 and shot.height < SH // 2:
            scale = min(2, SW // shot.width, SH // shot.height)
        im = shot if scale == 1 else shot.resize(
            (shot.width * scale, shot.height * scale), Image.LANCZOS)
        tk_img = ImageTk.PhotoImage(im)
        ox = (SW - im.width) // 2
        oy = (SH - im.height) // 2
        cv.create_image(ox, oy, anchor="nw", image=tk_img)
        cv._img_ref = tk_img
        cv.create_text(SW // 2, 24, fill="#FFD60A",
                       font=("Segoe UI", 17, "bold"),
                       text=f"Keo vung QUANH bieu tuong {label} tren anh  "
                            f"(x{scale}, Esc de huy)")
        box = {"x0": 0, "y0": 0, "id": None}

        def press(e):
            box["x0"], box["y0"] = e.x, e.y
            box["id"] = cv.create_rectangle(e.x, e.y, e.x, e.y,
                                            outline="#00FF00", width=2)

        def drag(e):
            if box["id"]:
                cv.coords(box["id"], box["x0"], box["y0"], e.x, e.y)

        def release(e):
            x1, y1 = min(box["x0"], e.x) - ox, min(box["y0"], e.y) - oy
            x2, y2 = max(box["x0"], e.x) - ox, max(box["y0"], e.y) - oy
            ov.destroy()
            x1, y1 = max(0, x1 // scale), max(0, y1 // scale)
            x2, y2 = min(shot.width, x2 // scale), min(shot.height, y2 // scale)
            if x2 - x1 < 4 or y2 - y1 < 4:
                set_status(f"Vung chon {x2-x1}x{y2-y1} qua nho (<4px), chua luu.")
                return
            shot.crop((x1, y1, x2, y2)).save(save_path)
            set_status(f"Da luu template {label}: {save_path}")

        def esc(_e):
            ov.destroy()

        cv.bind("<ButtonPress-1>", press)
        cv.bind("<B1-Motion>", drag)
        cv.bind("<ButtonRelease-1>", release)
        ov.bind("<Escape>", esc)
        # dong overlay → tra grab ve modal cu (neu co) de tiep tuc dung
        ov.bind("<Destroy>", lambda _e: prev_grab and prev_grab.grab_set())
        return True

    def center_on_root(dlg, w=None, h=None):
        """Dat dlg vao GIUA cua so tool (tinh sau khi ep layout xong)."""
        dlg.update_idletasks()
        dw = w or dlg.winfo_reqwidth()
        dh = h or dlg.winfo_reqheight()
        rx = root.winfo_rootx() + (root.winfo_width() - dw) // 2
        ry = root.winfo_rooty() + (root.winfo_height() - dh) // 2
        dlg.geometry(f"+{max(rx, 0)}+{max(ry, 0)}")

    def open_capture_dialog():
        """Modal chon loai anh can chup (Helper / Giam tai / ...), hien xem
        truoc anh dang luu. Danh sach lay tu ICON_ITEMS."""
        dlg = tk.Toplevel(root)
        dlg.title("Chọn ảnh cần chụp")
        dlg.transient(root)
        dlg.grab_set()
        dlg.configure(bg=CARD)
        tk.Label(dlg, text="Chọn icon để chụp từ màn hình game:",
                 font=f_body, fg=TEXT, bg=CARD).pack(padx=14, pady=(12, 6))
        for name, path in ICON_ITEMS:
            row = tk.Frame(dlg, bg=CARD)
            row.pack(fill="x", padx=14, pady=3)
            exists = os.path.exists(path)
            b = tk.Button(row, text=f"📷  {name}" + ("  ✓" if exists else "  (chưa chụp)"),
                          font=f_body, fg=TEXT, bg="#F2F2F7",
                          activebackground="#E5E5EA", relief="flat", bd=0, anchor="w",
                          command=lambda n=name, p=path: (dlg.destroy(),
                                                          capture_icon(p, n)))
            b.pack(side="left", fill="x", expand=True, ipady=6)
            # Anh xem truoc (phong to 3x de de nhin)
            if exists:
                try:
                    from PIL import Image, ImageTk
                    im = Image.open(path)
                    im = im.resize((max(1, im.width * 3), max(1, im.height * 3)),
                                   Image.NEAREST)
                    tk_img = ImageTk.PhotoImage(im)
                    lbl = tk.Label(row, image=tk_img, bg=CARD, bd=1,
                                   relief="solid")
                    lbl.image = tk_img   # giu reference
                    lbl.pack(side="right", padx=(8, 0))
                except Exception:
                    pass
        tk.Button(dlg, text="Đóng", command=dlg.destroy, font=f_body,
                  fg=MUTED, bg=CARD, relief="flat", bd=0
                  ).pack(padx=14, pady=(6, 12), anchor="e")
        center_on_root(dlg)

    # ---------- TAB 1: RR — HET NHU TAB LI: pill #F2F2F7, cham dau XUONG ----------
    # (xanh = cua so con song; DO = cua so dang duyet. Trong pill: bar tien
    # trinh (fill xanh/da) + chu DEN "Ten · Lv". Grid/kich thuoc/cach le =
    # cong thuc giong LI: slot expand deu, pill cap = grid/5.)
    rr_card = card(content)
    TABS["ctrl"] = rr_card
    rr_card.grid_columnconfigure(0, weight=1)
    rr_card.grid_rowconfigure(0, weight=1)
    bars_frame = tk.Frame(rr_card, bg=CARD)
    bars_frame.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
    MAX_SLOTS = 10
    BAR_H = 22
    BAR_R = 10
    PILL = "#F2F2F7"
    DOT_RED = "#FF3B30"
    DOT_GREEN = "#34C759"

    class Bar:
        """Canvas bar trong pill: track tron #E9E9EE + fill theo Lv + chu DEN."""
        def __init__(self, parent):
            self.r = BAR_R
            self._full_h = BAR_H
            self.c = tk.Canvas(parent, width=100, height=self._full_h,
                               highlightthickness=0, bg=PILL)
            self.c.pack(side="left", fill="both", expand=True)
            self._w = 100
            self._pct = 0.0
            self._color = SUCCESS
            self._text = ""
            self.c.bind("<Configure>", self._resize)
            self._draw()

        def _rrect(self, x1, y1, x2, y2, r, color):
            pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r,
                   x2, y2, x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r,
                   x1, y1 + r, x1, y1]
            return self.c.create_polygon(*pts, smooth=True, fill=color,
                                         outline="")

        def _resize(self, evt):
            self._w = evt.width
            self._draw()

        def _draw(self):
            self.c.delete("all")
            w, h = self._w, self._full_h
            r = min(self.r, h // 2)
            self._rrect(0, 0, w, h, r, "#E9E9EE")
            fw = int(w * self._pct)
            if fw > 2 * r:
                self._rrect(0, 0, fw, h, r, self._color)
            elif fw > 0:
                self.c.create_rectangle(0, 0, fw, h, fill=self._color,
                                        outline="")
            if self._text:
                self.c.create_text(8, h / 2.0, anchor="w", text=self._text,
                                   font=f_bar, fill=TEXT)

        def set(self, p, color, text=None, active=None):
            self._pct = max(0.0, min(1.0, p))
            self._color = color
            if text is not None:
                self._text = text
            self._draw()

        def set_h(self, h):
            h = max(BAR_H, int(h))
            if h != self._full_h:
                self._full_h = h
                self.c.configure(height=h)
                self._draw()

        def clear(self):
            self.set(0.0, SUCCESS, "")

    # Holder = slot deu (expand); trong holder: spacer tren/duoi weight →
    # PILL nam giua, khoang cach gia cac pill DAU NHAU — y het LI.
    SLOTS = []
    for _i in range(MAX_SLOTS):
        holder = tk.Frame(bars_frame, bg=CARD)
        holder.pack(fill="both", expand=True)
        tk.Frame(holder, bg=CARD).pack(fill="both", expand=True)
        box = tk.Frame(holder, bg=PILL)
        box.pack(fill="x", padx=2)
        dot = tk.Label(box, text="", font=f_bar, fg=DOT_GREEN, bg=PILL,
                       width=2)
        dot.pack(side="left")
        b = Bar(box)
        tk.Frame(holder, bg=CARD).pack(fill="both", expand=True)
        SLOTS.append({"frame": holder, "box": box, "bar": b, "dot": dot,
                      "hwnd": None})

    def _slot_release(sl):
        sl["hwnd"] = None
        sl["bar"].clear()

    def _slot_assign(hwnd):
        for sl in SLOTS:
            if sl["hwnd"] is None:
                sl["hwnd"] = hwnd
                return sl
        return None

    BARS = {}          # hwnd -> Bar (bar dang gao cho cua so nay)
    bar = None         # bar cua cua so dang dieu khien (GHWND)
    cur = None

    def bar_pct_color(lv):
        p = 0.0 if lv is None else max(0.0, min(1.0, (lv - 1) / (AUTO_RESET_LV - 1)))
        return p, (DANGER if (lv is not None and lv >= AUTO_RESET_LV) else SUCCESS)

    def set_bar_pct(lv):
        if bar is not None:
            p, col = bar_pct_color(lv)
            bar.set(p, col)

    def list_game_windows():
        """{hwnd: pid} cua moi cua so game main.exe dang hien."""
        targets = set()
        for p in pymem.process.list_processes():
            try:
                name = p.szExeFile.decode("utf-8", "ignore")
            except Exception:
                continue
            if name.lower() == PROCESS_NAME.lower():
                targets.add(p.th32ProcessID)
        out = {}
        @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
        def cb(hwnd, _):
            if not user32.IsWindowVisible(hwnd):
                return True
            pid = wt.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value in targets:
                cr = wt.RECT()
                user32.GetClientRect(hwnd, ctypes.byref(cr))
                if cr.right > 200 and cr.bottom > 200:
                    out[hwnd] = pid.value
            return True
        user32.EnumWindows(cb, 0)
        return out

    def sync_bars():
        """Gan cua so vao SLOT CO DINH; thu cho trong; vien xanh cho cua so
        dang thao tac; an cac hang trong o CUOI (khong bao gio dot giua)."""
        nonlocal bar, cur
        wins = list_game_windows()
        # thu cho cua so da dong — giu nguyen vi tri cac hang khac
        for sl in SLOTS:
            if sl["hwnd"] is not None and sl["hwnd"] not in wins:
                _slot_release(sl)
        # gan cua so moi vao cho trong dau tien
        have = {sl["hwnd"] for sl in SLOTS if sl["hwnd"] is not None}
        for hwnd in wins:
            if hwnd not in have:
                _slot_assign(hwnd)
        BARS.clear()
        bar = cur = None
        n_vis = sum(1 for sl in SLOTS if sl["hwnd"] is not None)
        fh = bars_frame.winfo_height()
        # bar = min(slot - khe 10px, grid/5): khe GIA card LUON con ≥10px khi
        # ≤5 cua so; >5 cua so → bar ep min 22px (khe tu hep).
        if n_vis and fh > 60:
            slot_h = fh // n_vis
            bar_h = max(BAR_H, min(slot_h - 10, fh // 5))
            for sl in SLOTS:
                if sl["hwnd"] is not None:
                    sl["bar"].set_h(bar_h)
        for sl in SLOTS:
            hwnd = sl["hwnd"]
            active = (hwnd == ACTIVE_HWND[0]) and hwnd is not None
            # cham dau PILL: DO = dang duyet, XANH = cua so song chua duyet
            # (giong cham xanh o tab LI; an khi pill trong)
            if hwnd is None:
                sl["dot"].configure(text="")
                continue
            sl["dot"].configure(text="●",
                                fg=DOT_RED if active else DOT_GREEN)
            BARS[hwnd] = sl["bar"]
            nm, lv = read_title(hwnd)
            p, col = bar_pct_color(lv)
            txt = f"{nm or '?'} · Lv {lv if lv is not None else '?'}"
            if active:
                bar, cur = sl["bar"], sl["bar"].c
            sl["bar"].set(p, col, txt)
        # an hang trong o CUOI; slot o giua giu nguyen cho trong (khong dot).
        last_used = -1
        for i, sl in enumerate(SLOTS):
            if sl["hwnd"] is not None:
                last_used = i
        for i in reversed(range(MAX_SLOTS)):
            sl = SLOTS[i]
            if i <= last_used:
                sl["frame"].pack(fill="both", expand=True)
            else:
                sl["frame"].pack_forget()
        li_idle_watch(wins)   # khong Train: quet BIND + tu dong relogin cua so mat
        li_refresh_bind_colors()   # nen xanh = user dang gan cua so song
        root.after(2000, sync_bars)

    def li_idle_watch(wins):
        """Ngoai Train (sync_bars goi 2s/lan — DONG THOI la luong QUET BIND
        LUC MO TOOL): cua so game trung ten nhan vat voi username/char_name
        → TU DAT ket noi (bind) user do → nen xanh o tab LI + watchdog bat
        dau canh. Account da bind ma cua so mat → spawn worker relogin
        (thread rieng, khong lam dong bang tk). Co cheque LI_BUSY/TRAIN_ACTIVE
        de khong bao gio cham ban phim cung luc voi Train hay login thu cong."""
        if LI_BUSY[0] or TRAIN_ACTIVE[0]:
            return
        now = time.time()
        alive = set(wins.keys())
        # 1) QUET BIND: cua so chua bind nao, title [Char:] khop user/char_name
        for hwnd in alive:
            nm, _lv = read_title(hwnd)
            if not nm:
                continue
            bound_hwnds = set(LI_BINDINGS.values())
            if hwnd in bound_hwnds:
                continue
            for a in li_snapshot_accounts():
                cn = (a.get("char_name") or "").strip()
                u = a.get("user") or ""
                if not u or u in LI_BINDINGS:
                    continue
                if not a.get("enabled", True):
                    continue
                if cn.lower() == nm.strip().lower() or u.lower() == nm.strip().lower():
                    LI_BINDINGS[u] = hwnd
                    log_add(f"  🔗 {u}: gan cua so game '{nm}' — watchdog bat dau")
                    break
        # 2) account da tung bind ma cua so bien mat → relogin (KHONG pop o
        # day — guLI_BINDINGS cho toi khi worker relogin xong hoac het buoc;
        # nen xanh tu tat vi IsWindow=False trong li_refresh_bind_colors)
        for u, hwnd in list(LI_BINDINGS.items()):
            if hwnd in alive:
                continue
            if now < LI_RELOGIN_WAIT.get(u, 0):
                continue
            try:
                acc = next(a for a in li_snapshot_accounts() if a["user"] == u)
            except StopIteration:
                LI_BINDINGS.pop(u, None)
                continue
            LI_BUSY[0] = True
            log_add(f"  ⚠ {u}: cua so mat → tu dong relogin (khong Train)")

            def _worker(a=acc, key=u):
                ok = False
                try:
                    for _attempt in range(1, 4):
                        if STOP_REQUESTED[0] or check_stop_key():
                            return
                        ok, g = li_run_account(a, load_li_cfg(), log_add)
                        if ok:
                            if g:
                                LI_BINDINGS[key] = g
                            LI_RELOGIN_WAIT.pop(key, None)
                            log_add(f"  ✔ {key}: relogin thanh cong")
                            return
                    LI_RELOGIN_WAIT[key] = time.time() + 60.0
                    log_add(f"  {key}: 3 lan hong — thu lai sau 60s")
                finally:
                    LI_BUSY[0] = False
            threading.Thread(target=_worker, daemon=True).start()
            break                      # mot lan chi mot relogin

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
        center_on_root(dlg)

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
    # ===== TAB CONFIG — luu 5 GRID doc; moi grid: Map/Spot hang tren,
    # Min/Max hang duoi; chieu rong grid = chieu rong card (50% cu). =====
    TABS["cfg"] = None   # dat o duoi, sau khi co grid_card (bo wrapper main_col
                         # — card nam truc tiep trong content nhu tab khac)

    GAP = 6
    CELL_W = 112          # = 1/2 chieu rong card tru le → 2 cot/xen Map|Spot, Min|Max
    HALF = (GAP // 2, GAP // 2)
    ROW_PADY = (0, 6)
    N_ROWS = 5

    mv_sel = [0] * N_ROWS     # chi muc /move dang chon cua tung dong
    sp_sel = [None] * N_ROWS  # chi muc spot dang chon cua tung dong
    mv_drops = []
    sp_drops = []
    min_vars = []             # tk.StringVar level min tung dong
    max_vars = []             # tk.StringVar level max tung dong

    # ---- spot per-account: ROWS_MAP {key: rows5}; "(Chung)" = du lieu cu ----
    ROWS_MAP = load_rows_map()
    if "(Chung)" not in ROWS_MAP:
        ROWS_MAP["(Chung)"] = load_cfg()
    SPOT_ACC_KEY = ["(Chung)"]

    # Khoi phuc bo dong "(Chung)" (TRUOC khi tao card — card doc min_vars[r]).
    cfg = ROWS_MAP["(Chung)"]
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

    # ---- 1 GRID CHINH choán TOAN tab (bang RR/Log); dong dau = dropdown
    # Account NAM BENCHAU grid; moi dong: [Map|Spot] tren, [Min|Max] duoi. ----
    SPOT_SEL = tk.StringVar(value="(Chung)")

    def _spot_hdr_row():
        nonlocal spot_combo
        hb = tk.Frame(grid_card, bg=CARD)
        hb.grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 0))
        hb.grid_columnconfigure(0, weight=1)
        # khong con text "Account" — dropdown CHIEM HET chieu ngang, cao
        # bang nut Map (font body + ipady), NOI DUNG CAN GIUA (justify) nhu
        # nut Map cua CTkButton.
        spot_combo = ttk.Combobox(hb, textvariable=SPOT_SEL, state="readonly",
                                  font=f_body, justify="center",
                                  values=["(Chung)"])
        spot_combo.grid(row=0, column=0, sticky="ew", padx=HALF, pady=(0, 2),
                        ipady=3)
        return hb

    grid_card = card(content)
    TABS["cfg"] = grid_card
    grid_card.grid_columnconfigure(0, weight=1)
    spot_combo = None
    hdr_box = _spot_hdr_row()
    for r in range(N_ROWS):
        row_box = tk.Frame(grid_card, bg=CARD)
        row_box.grid(row=r + 1, column=0, sticky="ew", padx=10,
                     pady=(6, 0))
        for c in range(2):
            row_box.grid_columnconfigure(c, weight=1, uniform=f"g{r}")
        # ke ngang mem phan chia cac dong (ke ca voi dong dau)
        tk.Frame(row_box, bg=BORDER, height=1).grid(
            row=0, column=0, columnspan=2, sticky="ew", pady=(0, 4))
        mvd = MapDropList(row_box, "Map", width=10, compact=True, btn_px=CELL_W)
        mv_drops.append(mvd)
        mvd.on_select = lambda i, r=r: pick_move(r, i)
        mvd.head.grid(row=1, column=0, sticky="ew", padx=HALF, pady=(2, 4))
        spd = MapDropList(row_box, "Spot", width=10, compact=True, btn_px=CELL_W)
        sp_drops.append(spd)
        spd.on_select = lambda i, r=r: pick_spot(r, i)
        spd.head.grid(row=1, column=1, sticky="ew", padx=HALF, pady=(2, 4))
        vmin, vmax = min_vars[r], max_vars[r]
        if USE_CTK:
            e_min = ctk.CTkEntry(row_box, textvariable=vmin, height=26,
                                 font=f_body, border_color=BORDER,
                                 fg_color="#FAFAFA", justify="center")
            e_max = ctk.CTkEntry(row_box, textvariable=vmax, height=26,
                                 font=f_body, border_color=BORDER,
                                 fg_color="#FAFAFA", justify="center")
        else:
            e_min = tk.Entry(row_box, textvariable=vmin, font=f_body,
                             relief="solid", bd=1, bg="#FAFAFA", justify="center")
            e_max = tk.Entry(row_box, textvariable=vmax, font=f_body,
                             relief="solid", bd=1, bg="#FAFAFA", justify="center")
        e_min.grid(row=2, column=0, sticky="ew", padx=HALF, pady=(0, 2))
        e_max.grid(row=2, column=1, sticky="ew", padx=HALF, pady=(0, 2))
        # Luu moi khi sua Min/Max (nut "+" da bo — grid tu luu).
        vmin.trace_add("write", lambda *a: persist_rows())
        vmax.trace_add("write", lambda *a: persist_rows())
    grid_card.grid_rowconfigure(N_ROWS + 1, weight=1)

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
        sp_drops[r].set_items(items, None, -1 if sp_sel[r] is None else sp_sel[r])

    def refresh_all():
        for r in range(N_ROWS):
            refresh_map_row(r); refresh_spot_row(r)

    ROWS_LOADING = [False]

    def persist_rows():
        """Luu 5 dong hien tai theo KEY dang chon (per-account). "(Chung)"
        dong thoi ghi ve dinh dang cu (save_cfg) de tuong thich ngoc."""
        if ROWS_LOADING[0]:
            return
        key = SPOT_SEL.get() or "(Chung)"
        SPOT_ACC_KEY[0] = key
        ROWS_MAP[key] = [[mv_sel[r], sp_sel[r], min_vars[r].get(), max_vars[r].get()]
                         for r in range(N_ROWS)]
        save_rows_map(ROWS_MAP)
        if key == "(Chung)":
            save_cfg(ROWS_MAP[key])

    def apply_rows(cfg5):
        """Nap 5 dong (list rows) vao widget dang hien thi."""
        ROWS_LOADING[0] = True
        try:
            for r in range(N_ROWS):
                mv_sel[r] = 0
                sp_sel[r] = None
                min_vars[r].set("")
                max_vars[r].set("")
                if r < len(cfg5):
                    try:
                        mv_sel[r] = max(0, min(len(MOVE_COMMANDS) - 1, int(cfg5[r][0])))
                        s = cfg5[r][1]
                        sp_sel[r] = None if s is None else int(s)
                        min_vars[r].set(str(cfg5[r][2] if len(cfg5[r]) > 2 else ""))
                        max_vars[r].set(str(cfg5[r][3] if len(cfg5[r]) > 3 else ""))
                    except Exception:
                        pass
            refresh_all()
        finally:
            ROWS_LOADING[0] = False

    def build_rows(cfg5):
        """Chuyen list rows trong config -> [(tok,x,y,vmin,vmax)] hop le."""
        out = []
        for row in cfg5 or []:
            try:
                mv = int(row[0]); s = row[1]
                if s is None:
                    continue
                i = int(s)
                tok = MOVE_COMMANDS[mv][0]
                lst = SPOTS.get(tok, [])
                if not (0 <= i < len(lst)):
                    continue
                vmin = int(row[2]); vmax = int(row[3])
            except (ValueError, IndexError, TypeError):
                continue
            if vmin > vmax:
                vmin, vmax = vmax, vmin
            _t, _nm, x, y = lst[i]
            out.append((tok, x, y, vmin, vmax))
        return out

    def spot_acc_choices():
        ch = ["(Chung)"]
        try:
            for a in li_snapshot_accounts():
                if a["user"] and a["user"] not in ch:
                    ch.append(a["user"])
        except Exception:
            pass
        return ch

    def refresh_spot_choices():
        vals = spot_acc_choices()
        try:
            spot_combo.configure(values=vals)
            if SPOT_SEL.get() not in vals:
                SPOT_SEL.set("(Chung)")
        except Exception:
            pass

    def on_spot_acc_change(*_a):
        key = SPOT_SEL.get() or "(Chung)"
        SPOT_ACC_KEY[0] = key
        apply_rows(ROWS_MAP.get(key) or [])

    SPOT_SEL.trace_add("write", on_spot_acc_change)

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
    def acc_key_for_name(nm):
        """(char_name/username -> account key) cho dropdown Spot + bind.
        Khong co thi '(Chung)'."""
        if not nm:
            return "(Chung)"
        try:
            for a in li_snapshot_accounts():
                cn = (a.get("char_name") or "").strip()
                us = (a.get("user") or "").strip()
                if (cn and cn.lower() == nm.strip().lower()) or \
                        (us and us.lower() == nm.strip().lower()):
                    return a["user"] or "(Chung)"
        except Exception:
            pass
        return "(Chung)"

    def rows_cfg_for(hwnd):
        """5 dong config ap dung cho cua so (theo nhan vat trong title)."""
        nm, _lv = read_title(hwnd)
        key = acc_key_for_name(nm)
        return ROWS_MAP.get(key) or ROWS_MAP.get("(Chung)") or load_cfg()

    def check_relogin(wins):
        """Watchdog chay TRONG train thread (cung thread → khong bao gio
        tranh ban phim):
          - cua so game xuat hien va title khop char_name 1 account → BIND.
          - cua so da BIND cua account nao bien mat → relogin inline ngay
            tai do (train dung tam), toi da 3 lan, hong ca 3 thi nghi 60s.
        Chi xu ly account tung duoc bind — ban tay dong thi KHONG bi lap."""
        now = time.time()
        try:
            accounts = [a for a in li_snapshot_accounts()
                        if a["user"] and a["enabled"]]
        except Exception:
            return
        alive = set(wins.keys())
        # 1) bind cua so hien dien theo char_name
        for hwnd in alive:
            nm, _lv = read_title(hwnd)
            key = acc_key_for_name(nm)
            if key != "(Chung)":
                LI_BINDINGS[key] = hwnd
                LI_RELOGIN_FAILS.pop(key, None)
        # 2) account da tung bind ma cua so mat → relogin
        for a in accounts:
            u = a["user"]
            prev = LI_BINDINGS.get(u)
            if prev is None or user32.IsWindow(prev):
                continue
            wait_until = LI_RELOGIN_WAIT.get(u, 0)
            if now < wait_until:
                continue
            log_add(f"  ⚠ {u}: cua so mat ket noi → tu dong relogin")
            ok = False
            for attempt in range(1, 4):
                if STOP_REQUESTED[0] or check_stop_key():
                    return
                ok, _g = li_run_account(a, load_li_cfg(), log_add)
                if ok:
                    break
                log_add(f"  {u}: relogin lan {attempt}/3 that bai")
                time.sleep(LI_STEP_PAUSE)
            if ok:
                LI_RELOGIN_FAILS[u] = 0
                LI_RELOGIN_WAIT.pop(u, None)
                log_add(f"  ✔ {u}: relogin thanh cong — train tiep tuc")
            else:
                LI_RELOGIN_FAILS[u] = LI_RELOGIN_FAILS.get(u, 0) + 1
                LI_RELOGIN_WAIT[u] = time.time() + 60.0
                log_add(f"  {u}: 3 lan hong — nghi 60s roi thu lai "
                        f"(tong lan fail: {LI_RELOGIN_FAILS[u]})")
        # 3) dong cua so da dong han (khong con game nao cua no) → don binding
        for u in list(LI_BINDINGS):
            if not any(x["user"] == u for x in accounts):
                del LI_BINDINGS[u]

    def train_chain():
        """Duyet LAN LUOT tung cua so game. Moi vong: tham 1 cua so — dam bao
        nhan vat o dung spot theo Lv cua no (spot theo account, fallback
        '(Chung)'), Helper + Giam tai dang BAT — roi RUI cho tu train.
        Lv dat nguong -> Reset -> spot dong 1. PgUp = dung tat ca."""
        if TRAIN_ACTIVE[0] or running[0]:
            return
        # Can it least one usable bo dong — QUET MỌI key: "(Chung)" va cua
        # account rieng (user dien trong dropdown Spot → luu vao ROWS_MAP[user],
        # "(Chung)" van trong → truoc day bao LO "chưa có dòng").
        any_rows = []
        for key in ROWS_MAP:
            any_rows = build_rows(ROWS_MAP[key])
            if any_rows:
                break
        if not any_rows:
            set_status("Chưa có dòng hợp lệ (cần chọn spot + nhập Lv Min/Max)")
            return
        TRAIN_ACTIVE[0] = True
        set_train_active(True)
        reset_stop()
        log_add("  === Train chain: duyet tung cua so (spot theo account) ===")
        try:
          try:
            while True:
                wins = dict(list_game_windows())
                check_relogin(wins)          # inline — relogin xong moi train
                wins = dict(list_game_windows())
                log_add(f"  Vong train: {len(wins)} cua so game")
                if not wins:
                    set_status("Khong con cua so game nao.")
                    break
                pending = []
                stopped = False
                for hwnd, pid in wins.items():
                    if STOP_REQUESTED[0] or check_stop_key():
                        log_add("  Dung: STOP_REQUESTED/PgUp duoc phat hien.")
                        stopped = True
                        break
                    set_active(hwnd)
                    time.sleep(2.0)              # moi cua so cach nhau 2s
                    rows = build_rows(rows_cfg_for(hwnd))
                    if not rows:
                        log_add("  (cua so nay chua co dong spot — bo qua)")
                        continue
                    outcome = run_visit(rows)
                    if outcome == "stopped":
                        stopped = True
                        break
                    if outcome == "visit":
                        pending.append(hwnd)
                if stopped:
                    set_status("Train chain: ĐÃ DỪNG (PgUp).")
                    send_ctrl_f_off()   # dung giua chung: tat Giam tai cho chac
                    break
                if not pending:
                    set_status("Train chain: hoàn tất tất cả các cửa sổ.")
                    log_add("  === Train chain xong ===")
                    break
                set_status(f"Train: {len(pending)} cua so — qua lien tuc, cach nhau 2s")
          except Exception as e:
            import traceback
            tb = traceback.format_exc()
            log_add(f"  LOI Train chain: {e}")
            log_err(f"[train_chain] {tb}")
        finally:
            TRAIN_ACTIVE[0] = False
            set_train_active(False)
            running[0] = False

    def run_visit(rows):
        """1 lan tham cua so ACTIVE: dam bao o dung spot theo Lv, Helper +
        Giam tai BAT. Tra 'done' (Lv vuot het moi dong) / 'visit' / 'stopped'."""
        hwnd = ACTIVE_HWND[0]
        nm, lv = read_title(hwnd)
        if lv is None:
            log_add("  (chua doc duoc Lv tu title — bo qua lan nay)")
            return "visit"
        if lv >= AUTO_RESET_LV:
            log_add(f"  {nm}: dat Lv {lv} >= {AUTO_RESET_LV} → tat Giam tai, Reset stat")
            # THAT BAI khi thoat Giam tai (nhap sai / phim khong toi / khop
            # nham) → KHONG reset, KHONG di tiep; quay lai cua so nay o vong
            # duyet sau (lan thu hai cua Ctrl+F nhieu khi cung do focus).
            if not send_ctrl_f_off(hwnd):
                log_add("  Chua thoat duoc Giam tai → HOAN lai cua so nay, "
                        "thu lai vong sau.")
                return "visit"
            if reset_stats():
                note_reset_success(nm)
            if STOP_REQUESTED[0]:
                return "stopped"
            lv = 1
        # Dong dau tien ma Lv hien tai van con nam trong (lv <= vmax)
        target = None
        for (tok, x, y, vmin, vmax) in rows:
            if lv <= vmax:
                target = (tok, x, y, vmin, vmax)
                break
        if target is None:
            log_add(f"  {nm}: Lv {lv} vuot moi dong → hoan tat chuoi")
            send_ctrl_f_off(hwnd)
            return "done"
        tok, x, y, vmin, vmax = target
        # DOC TOA DO KHONG CAN THAO TAC CHUOT truoc: neu Giam tai dang BAT va
        # van o dung spot -> THAM LAN nay chi xem Lv, KHONG click gi ca
        # (tranh moi vong duyet bam (400,300) lien tuc khi khong can).
        px, py = a_pos()
        if LT_ON.get(hwnd) and px is not None and at_spot(px, py, x, y):
            log_add(f"  {nm}: Lv {lv} — o dung spot, Giam tai dang BAT → "
                    f"bo qua Home/Helper, cho tu train")
            return "visit"
        # Offset memory chi refresh khi co thao tac trong client -> click
        # (400,300) ep cap nhat ROI MOI so sanh vi tri (tranh doc toa do cu
        # -> tuong "dung spot" -> khong di chuyen lai). Chi click khi THUC SU
        # can quyet dinh di/cham soc cua so nay.
        r = find_window_hwnd(hwnd)
        if r:
            (nL, nT, nW, nH), _ = r
            click_at(nL + ANCHOR_X, nT + ANCHOR_Y, right=False, hwnd=hwnd)
        time.sleep(0.5)
        px, py = a_pos()
        if px is None or not at_spot(px, py, x, y):
            log_add(f"  {nm}: Lv {lv} → di toi {tok} ({x},{y}) [Lv {vmin}-{vmax}]")
            SELECTED_SPOT[0] = (tok, x, y)
            goto(_from_train=True)
            if STOP_REQUESTED[0]:
                return "stopped"
        else:
            log_add(f"  {nm}: Lv {lv} — dang o dung {tok} ({x},{y})")
        # Helper + Giam tai phai BAT de nhan vat tu train khi tool sang cua so khac
        send_home_verified(hwnd)
        send_ctrl_f_on(hwnd)
        return "visit"

    refresh_all()

    # Nut Reset + Chup anh DA BO theo yeu cau: Reset TU chay khi dat Lv trong
    # vong train; template Helper/Giam tai nam tren file (muon doi thi thay
    # file PNG tuong ung — ham capture_icon van giu lai trong code).

    # ---------- TAB LOG: nut; nua tren = reset; nua duoi = log tien trinh ----
    log_card = card(content)
    TABS["log"] = log_card
    log_card.grid_columnconfigure(0, weight=1)
    log_card.grid_rowconfigure(1, weight=1, uniform="logsplit")
    log_card.grid_rowconfigure(2, weight=1, uniform="logsplit")

    btn_row = (ctk.CTkFrame(log_card, fg_color="transparent") if USE_CTK
               else tk.Frame(log_card, bg=CARD))
    btn_row.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 0))
    btn_row.grid_columnconfigure((0, 1), weight=1, uniform="btnrow")

    # Nut "Add Point": mo modal nhap so diem cong cho /addstr /addagi ... (KHONG
    # phai toa do). Dung lai open_reset_dialog (nhap 5 diem, luu vao config).
    btn_addp = btn_secondary(btn_row, "➕ Add Point", command=open_reset_dialog)
    btn_addp.grid(row=0, column=0, sticky="ew", padx=(0, 4))
    btn_cam = btn_secondary(btn_row, "📷 Camera", command=open_capture_dialog)
    btn_cam.grid(row=0, column=1, sticky="ew", padx=(4, 0))

    def _mk_listbox(row, pady):
        lb = tk.Listbox(
            log_card, relief="flat", highlightthickness=0,
            borderwidth=0, bg=CARD, fg=TEXT,
            selectbackground=ACCENT, selectforeground="#FFFFFF",
            font=f_small, activestyle="none")
        lb.grid(row=row, column=0, sticky="nsew", padx=8, pady=pady)
        def _wheel(ev):
            lb.yview_scroll(-1 if ev.delta > 0 else 1, "units")
            return "break"
        lb.bind("<MouseWheel>", _wheel)
        return lb

    logbox = _mk_listbox(1, (6, 1))        # tren: lich su reset
    proc_box = _mk_listbox(2, (1, 8))      # duoi: log tien trinh

    # ---------- TAB LI: auto-login (config gear + +account + danh sach 2x5) ----
    li_card = card(content)
    TABS["li"] = li_card
    li_card.grid_columnconfigure(0, weight=1)
    li_card.grid_rowconfigure(2, weight=1)

    li_hdr = (ctk.CTkFrame(li_card, fg_color="transparent") if USE_CTK
              else tk.Frame(li_card, bg=CARD))
    li_hdr.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 0))
    li_hdr.grid_columnconfigure((0, 1), weight=1, uniform="lihdr")
    btn_li_cfg = btn_secondary(li_hdr, "⚙ Config", command=lambda: li_open_config())
    btn_li_cfg.grid(row=0, column=0, sticky="ew", padx=(0, 4))
    btn_li_add = btn_secondary(li_hdr, "➕ Account", command=lambda: li_edit_account())
    btn_li_add.grid(row=0, column=1, sticky="ew", padx=(4, 0))

    btn_li_run = btn_primary(li_card, "▶  Chay login", width=0, height=30,
                             command=lambda: li_run_clicked())
    btn_li_run.grid(row=1, column=0, sticky="ew", padx=8, pady=(6, 0))

    # Danh sach account: CHI hien Username (bam vao de sua). Bo thanh truot —
    # modal now giu thong tin, danh sach ngan gon khong can cuon.
    li_list_parent = tk.Frame(li_card, bg=CARD)
    li_list_parent.grid(row=2, column=0, sticky="nsew", padx=8, pady=8)
    li_list_parent.grid_columnconfigure(0, weight=1)

    li_accounts = []      # nguon du lieu duy nhat: list dict account

    def li_snapshot_accounts():
        return [dict(a) for a in li_accounts]

    def li_persist():
        try:
            li_save_accounts(load_li_cfg(), li_accounts)
            refresh_spot_choices()
        except Exception:
            pass

    def li_edit_account(idx=None):
        """Modal nhap thong tin 1 account (them moi neu idx=None, sua neu co).
        Size + vi tri = dung GUI chinh (overlay len tool)."""
        acc = dict(li_accounts[idx]) if idx is not None else li_default_account()
        dlg = tk.Toplevel(root)
        dlg.title("Sua account" if idx is not None else "Them account")
        dlg.transient(root); dlg.grab_set(); dlg.configure(bg=CARD)
        dlg.resizable(False, False)
        # trung kich thuoc + vi tri GUI chinh
        dlg.geometry(f"{root.winfo_width()}x{root.winfo_height()}"
                     f"+{root.winfo_rootx()}+{root.winfo_rooty()}")

        def field(labeltext, key, default=""):
            tk.Label(dlg, text=labeltext, font=f_small, fg=MUTED, bg=CARD
                     ).pack(anchor="w", padx=14, pady=(10, 0))
            v = tk.StringVar(value=str(acc.get(key, default)))
            e = tk.Entry(dlg, textvariable=v, font=f_body, relief="solid", bd=1)
            e.pack(fill="x", padx=14)
            return v, e

        u_v, u_e = field("Username:", "user")
        p_v, p_e = field("Mật khẩu:", "password")
        p_e.configure(show="*")
        c_v, _ = field("Tên nhân vật:", "char_name")
        tk.Label(dlg, text="Server:", font=f_small, fg=MUTED, bg=CARD
                 ).pack(anchor="w", padx=14, pady=(10, 0))
        s_v = tk.StringVar(value=f"Server {int(acc.get('server_index', 0)) + 1}")
        ttk.Combobox(dlg, textvariable=s_v, state="readonly", font=f_body,
                     values=[f"Server {i + 1}" for i in range(5)]
                     ).pack(fill="x", padx=14)
        en_v = tk.BooleanVar(value=bool(acc.get("enabled", True)))
        tk.Checkbutton(dlg, text="Kích hoạt (login + watchdog relogin)",
                       variable=en_v, font=f_small, bg=CARD,
                       activebackground=CARD).pack(anchor="w", padx=12, pady=(10, 0))

        def _save():
            user = u_v.get().strip()
            if not user:
                set_status("Username trong — khong luu.")
                return
            # trung user (khong tinh chinh no khi sua) → chan
            for i, a in enumerate(li_accounts):
                if a["user"] == user and i != idx:
                    set_status(f"Username '{user}' da ton tai.")
                    return
            new = {"user": user, "password": p_v.get(),
                   "server_index": int(s_v.get().split()[-1]) - 1,
                   "char_name": c_v.get().strip(), "enabled": bool(en_v.get())}
            if idx is None:
                li_accounts.append(new)
            else:
                li_accounts[idx] = new
            li_persist()
            li_render_accounts()
            dlg.destroy()

        btnfr = tk.Frame(dlg, bg=CARD); btnfr.pack(fill="x", padx=14, pady=14)
        tk.Button(btnfr, text="Lưu", command=_save, font=f_body, relief="flat",
                  bd=0, bg=ACCENT, fg="#FFFFFF"
                  ).pack(side="left", expand=True, fill="x", ipady=4, padx=(0, 4))
        tk.Button(btnfr, text="Hủy", command=dlg.destroy, font=f_body,
                  relief="flat", bd=0, bg="#F2F2F7", fg=TEXT
                  ).pack(side="left", expand=True, fill="x", ipady=4, padx=(4, 0))
        if idx is not None:
            tk.Button(btnfr, text="🗑", command=lambda: (li_del_account(idx),
                      dlg.destroy()), font=f_body, relief="flat", bd=0,
                      bg="#F2F2F7", fg=DOT_RED).pack(side="left", padx=(8, 0), ipadx=6, ipady=2)
        dlg.bind("<Return>", lambda _e: _save())
        dlg.bind("<Escape>", lambda _e: dlg.destroy())
        u_e.focus_set()

    def li_del_account(idx):
        if 0 <= idx < len(li_accounts):
            li_accounts.pop(idx)
            li_persist()
            li_render_accounts()

    LI_ROW_WIDGETS = {}    # user -> (box, lbl) de doi mau khi bind song
    LI_ROW_H = [-1]        # extra pady hien tai cua hang account (-1 = chua lay)
    LI_HOLDERS = []        # (holder, spacer_top, box, spacer_bot) theo thu tu

    def li_render_accounts():
        for w in li_list_parent.winfo_children():
            w.destroy()
        LI_ROW_WIDGETS.clear()
        LI_HOLDERS.clear()
        LI_ROW_H[0] = -1     # hang moi render → buoc layout ap chieu cao lai
        for i, a in enumerate(li_accounts):
            # holder CHIEM SLOT DEU (expand), box LE co chen 2 spacer → box
            # duoc = min(slot, grid/5) nam GIUA slot: it account → khoang
            # trong chia deu tren/duoi, nhieu → ken kin (o tab RR cung cach).
            holder = tk.Frame(li_list_parent, bg="#F2F2F7")
            holder.pack(fill="both", expand=True)
            top = tk.Frame(holder, bg=CARD); top.pack(fill="both", expand=True)
            box = tk.Frame(holder, bg="#F2F2F7")
            box.pack(fill="x", expand=False, padx=2, pady=1)
            bot = tk.Frame(holder, bg=CARD); bot.pack(fill="both", expand=True)
            dot = "●" if a.get("enabled", True) else "○"
            col = "#34C759" if a.get("enabled", True) else MUTED
            dl = tk.Label(box, text=dot, font=f_small, fg=col, bg="#F2F2F7")
            dl.pack(side="left", padx=(6, 0))
            lbl = tk.Label(box, text=a.get("user") or "(trống)", font=f_body,
                           fg=TEXT, bg="#F2F2F7", anchor="w")
            lbl.pack(side="left", fill="x", expand=True, padx=6,
                     pady=(3 + max(0, (li_row_height() - 26) // 2),
                           3 + max(0, (li_row_height() - 26) // 2)))
            for wdg in (box, lbl):
                wdg.bind("<Button-1>", lambda _e, k=i: li_edit_account(k))
                wdg.configure(cursor="hand2")
            LI_ROW_WIDGETS[a.get("user")] = (box, lbl)
            LI_HOLDERS.append((holder, top, box, bot))
        li_refresh_bind_colors()
        root.after(50, li_layout_rows)   # sau khi card ep layout xong

    def li_row_height():
        """Cao pill tai khoan = min(slot, card/5) — it tai khoan → pill CAO
        dan toi DAU card/5 (spacer 2 dau chia het phan con), nhieu → pill
        tu co lai. slot = card / so_hang."""
        try:
            h = li_list_parent.winfo_height()
        except Exception:
            h = 0
        n = max(1, len(LI_HOLDERS))
        slot = h // n if h > 50 else 26
        return max(26, min(slot, h // 5 if h > 50 else 26))

    def li_layout_rows():
        """Ap chieu cao moi (pady lbl → pill duoc nang) khi card/so hang doi.
        Chi re-pack khi gia tri THAY DOI — khong chop 2s/lan."""
        extra = max(0, (li_row_height() - 26) // 2)
        if extra == LI_ROW_H[0]:
            return
        LI_ROW_H[0] = extra
        for _holder, _top, box, _bot in LI_HOLDERS:
            labels = [w for w in box.winfo_children()
                      if isinstance(w, tk.Label)]
            for lbl in labels[1:]:          # [0] = cot dot, giu nguyen
                try:
                    lbl.pack_forget()
                    lbl.pack(side="left", fill="x", expand=True, padx=6,
                             pady=(3 + extra, 3 + extra))
                except Exception:
                    pass

    def li_refresh_bind_colors():
        """Nen XANH LA = user dang gan (bind) voi cua so game con song."""
        for u, (box, lbl) in LI_ROW_WIDGETS.items():
            bound = (u in LI_BINDINGS and user32.IsWindow(LI_BINDINGS[u]))
            bg = "#D1F2DB" if bound else "#F2F2F7"
            try:
                for c in (box, lbl) + tuple(box.winfo_children()):
                    c.configure(bg=bg)
            except Exception:
                pass
        li_layout_rows()   # so hang / chieu cao card co the doi — gian lai

    def li_open_config():
        dlg = tk.Toplevel(root)
        dlg.title("LI Config")
        dlg.transient(root); dlg.grab_set(); dlg.configure(bg=CARD)
        # trung kich thuoc + vi tri GUI chinh (overlay len tool)
        dlg.resizable(False, False)
        dlg.geometry(f"{root.winfo_width()}x{root.winfo_height()}"
                     f"+{root.winfo_rootx()}+{root.winfo_rooty()}")
        cfg = load_li_cfg()
        rows = []
        def add_row(labeltext, key, default=""):
            tk.Label(dlg, text=labeltext, font=f_small, fg=TEXT, bg=CARD
                     ).pack(anchor="w", padx=10, pady=(6, 0))
            v = tk.StringVar(value=str(cfg.get(key, default)))
            fr = tk.Frame(dlg, bg=CARD); fr.pack(fill="x", padx=10)
            tk.Entry(fr, textvariable=v, font=f_small, relief="solid", bd=1
                     ).pack(side="left", fill="x", expand=True)
            rows.append((key, v))
            return fr
        # launcher path + Chon
        tk.Label(dlg, text="Launcher:", font=f_small, fg=TEXT, bg=CARD
                 ).pack(anchor="w", padx=10, pady=(6, 0))
        fr = tk.Frame(dlg, bg=CARD); fr.pack(fill="x", padx=10)
        ex = tk.StringVar(value=str(cfg.get("launcher_path", "")))
        tk.Entry(fr, textvariable=ex, font=f_small, relief="solid", bd=1
                 ).pack(side="left", fill="x", expand=True)
        def _pick():
            pth = filedialog.askopenfilename(
                filetypes=[("Exe", "*.exe"), ("All", "*.*")])
            if pth:
                ex.set(pth.replace("\\", "/"))
        tk.Button(fr, text="Chon", command=_pick, font=f_small, relief="flat", bd=0,
                  bg="#F2F2F7").pack(side="left", padx=(4, 0))
        rows.append(("launcher_path", ex))
        add_row("Title launcher (regex):", "launcher_title", "MU.*Launcher")
        add_row("Title game (regex):", "game_title", "Season21")
        coords = dict(cfg.get("coords", {}) or {})
        camfr = tk.Frame(dlg, bg=CARD); camfr.pack(fill="x", padx=10)
        # Play = cua so launcher; Credit/Connect = cua so game (grab_client)
        for kind, lbl, gf in (("play", "Play", li_grab_launcher_shot),
                              ("credit", "Credit", None),
                              ("connect", "Connect", None)):
            tk.Button(camfr, text=f"📷 {lbl}",
                      command=lambda kk=kind, ll=lbl, g=gf: capture_icon(
                          li_tpl(kk), ll, grab_fn=g),
                      font=f_small, relief="flat", bd=0, bg="#F2F2F7"
                      ).pack(side="left", padx=2, pady=2)
        coordfr = tk.Frame(dlg, bg=CARD); coordfr.pack(fill="x", padx=10)
        _cb = {"n": 0}
        def _coord_btn(key, labeltext):
            def go():
                pt = li_capture_coord_via_cursor()
                if pt:
                    coords[key] = list(pt)
                    set_status(f"{labeltext} = {pt}")
            i = _cb["n"]; _cb["n"] += 1
            tk.Button(coordfr, text=f"◎ {labeltext}", command=go, font=f_small,
                      relief="flat", bd=0, bg="#F2F2F7"
                      ).grid(row=i // 5, column=i % 5, sticky="ew",
                             padx=2, pady=2)
        for c in range(5):
            coordfr.grid_columnconfigure(c, weight=1)
        _coord_btn("login", "Login")
        for i in range(5):
            _coord_btn(f"s{i}", f"S{i+1}")
        for i in range(1, 5):
            _coord_btn(f"post{i}", f"P{i}")
        def _save():
            new = load_li_cfg()
            for key, v in rows:
                new[key] = v.get()
            new["coords"] = coords
            save_li_cfg(new)
            set_status("LI config da luu.")
            dlg.destroy()
        tk.Button(dlg, text="Luu", command=_save, font=f_body, relief="flat", bd=0,
                  bg=ACCENT, fg="#FFFFFF").pack(pady=10)

    # shot cua launcher cho capture template Play (khong phai main.exe)
    def li_grab_launcher_shot():
        cfg = load_li_cfg()
        hits = li_find_windows(cfg.get("launcher_title", "MU.*Launcher"))
        h = li_pick_window(hits)
        return li_grab_hwnd(h) if h else None

    def li_capture_coord_via_cursor():
        """Chup anh cua so game -> overlay fullscreen hien anh -> BAM 1 DIEM
        tren anh -> tra (x,y) TUONG DOI cua so game. (Cu dung root.withdraw +
        sleep 3s block mainloop va bi modal grab_set chan Chuot → khong dung
        duoc; bay gio theo co che overlay nhu capture_icon.)"""
        cfg = load_li_cfg()
        g = li_pick_window(li_find_windows(cfg.get("game_title", "Season21")))
        if not g:
            g = ACTIVE_HWND[0] if ACTIVE_HWND[0] and user32.IsWindow(ACTIVE_HWND[0]) else None
        if not g:
            # title game da doi (da vo world) → cua so cua process game
            r2 = find_window_hwnd()
            if r2:
                g = r2[1]
        if not g:
            set_status("Tim khong thay cua so game (mo game truoc)")
            return None
        shot = li_grab_hwnd(g)
        if shot is None:
            set_status("Khong chup duoc cua so game.")
            return None
        from PIL import Image, ImageTk
        prev_grab = root.grab_current()
        box = {"pt": None}
        ov = tk.Toplevel(root)
        ov.attributes("-fullscreen", True)
        ov.attributes("-topmost", True)
        ov.configure(bg="black", cursor="crosshair")
        ov.grab_set()
        ov.lift()
        cv = tk.Canvas(ov, bg="black", highlightthickness=0)
        cv.pack(fill="both", expand=True)
        SW, SH = ov.winfo_screenwidth(), ov.winfo_screenheight()
        scale = min(2, max(1, SW // shot.width, SH // shot.height))
        im = shot if scale == 1 else shot.resize(
            (shot.width * scale, shot.height * scale), Image.LANCZOS)
        tk_img = ImageTk.PhotoImage(im)
        ox, oy = (SW - im.width) // 2, (SH - im.height) // 2
        cv.create_image(ox, oy, anchor="nw", image=tk_img)
        cv._img_ref = tk_img
        cv.create_text(SW // 2, 24, fill="#FFD60A", font=("Segoe UI", 17, "bold"),
                       text=f"BAM 1 DIEM vao vi tri can lay toa do  "
                            f"(x{scale}, Esc de huy)")

        def _click(e):
            box["pt"] = ((e.x - ox) // scale, (e.y - oy) // scale)
            ov.destroy()

        cv.bind("<ButtonRelease-1>", _click)
        ov.bind("<Escape>", lambda _e: ov.destroy())
        ov.bind("<Destroy>", lambda _e: prev_grab and prev_grab.grab_set())
        ov.wait_window()   # block TREN OVERLAY, mainloop van chay -> khong dong bang
        r = wt.RECT()
        user32.GetWindowRect(g, ctypes.byref(r))
        x, y = box["pt"] if box["pt"] else (0, 0)
        if box["pt"] and not (0 <= x < (r.right - r.left) and 0 <= y < (r.bottom - r.top)):
            set_status("Diem ngoai cua so game")
            return None
        return box["pt"]

    def li_run_clicked():
        if LI_BUSY[0]:
            set_status("Login dang chay."); return
        if TRAIN_ACTIVE[0]:
            set_status("Train dang chay — dung Train truoc."); return
        cfg = load_li_cfg()
        accs = li_snapshot_accounts()
        li_save_accounts(cfg, accs)
        if not [a for a in accs if a["user"] and a["enabled"]]:
            set_status("Chua co account nao."); return
        threading.Thread(target=li_run_all,
                         args=(cfg, accs, lambda s: set_status(s)),
                         daemon=True).start()

    li_accounts.extend(li_load_accounts(load_li_cfg()))
    li_render_accounts()
    refresh_spot_choices()   # account san co (config cu / migrate) → dropdown
                             # Spot phai co ngay luc mo tool, khong phai khi nao
                             # modal luu moi refresh

    # --- Cap nhat toa do + ten/level hien tai (1s/lan) ---
    LIVE_POS = [None, None]
    _last_pos_text = [None]
    def set_pos_text(x, y):
        """Bar cua so dang dieu khien: chi ten + Lv (bo toa do — ngan cho).
        Chi ve lai khi text thuc su khac -> het nhap nhay."""
        lv = LIVE_LEVEL[0]
        t = f"{LIVE_NAME[0] or '?'} · Lv {lv if lv is not None else '?'}"
        if t != _last_pos_text[0]:
            _last_pos_text[0] = t
            if bar is not None:
                p, col = bar_pct_color(lv)
                bar.set(p, col, t, active=True)
    def poll_live():
        try:
            x, y = a_pos()
            if x is not None:
                LIVE_POS[0], LIVE_POS[1] = x, y
                LIVE_MAP[0] = a_map()
                nm, lv = read_title(ACTIVE_HWND[0])
                if nm:
                    LIVE_NAME[0] = nm
                if lv is not None:
                    LIVE_LEVEL[0] = lv
                set_pos_text(x, y)
        except Exception:
            pass
        root.after(1000, poll_live)
    root.after(1000, poll_live)
    root.after(500, sync_bars)   # dong bo bar theo cua so game mo/dong

    def log_add(text, done=False, color=None):
        root.after(0, lambda: _log_add(text, done, color))
    def _log_add(text, done, color):
        # Tab Log 2 phan: tren = lich su reset (chi note_reset_success ghi);
        # duoi = log tien trinh/cac buoc de tra soat loi.
        idx = proc_box.size()
        proc_box.insert(tk.END, text)
        if color:
            proc_box.itemconfig(idx, fg=color)
        elif done:
            proc_box.itemconfig(idx, fg=SUCCESS)
        proc_box.see(tk.END)
        try:
            root.title("MU GOTO — " + text.strip()[:80])
        except Exception:
            pass

    # ---- Lich su reset: tab Log chi ghi ngan "Ten reset ( avg min / so lan )" ----
    # avg = thoi gian TRUNG BINH giua cac lan reset cung nhan vat ke tu luc
    # tool chay; so lan = tong lan reset thanh cong cua nhan vat do.
    RESET_TIMES = {}               # name -> [epoch, epoch, ...] (lan luot)
    def note_reset_success(name):
        now = time.time()
        key = name or "?"
        hist = RESET_TIMES.setdefault(key, [])
        hist.append(now)
        n = len(hist)
        if n >= 2:
            avg_min = (hist[-1] - hist[0]) / 60.0 / (n - 1)
            avg_txt = f"{avg_min:.0f} min" if avg_min >= 1 else f"{avg_min*60:.0f} s"
        else:
            avg_txt = "—"
        line = f"{key} reset ( {avg_txt} / {n} )"
        def _w():
            logbox.insert(tk.END, line)
            logbox.itemconfig(logbox.size() - 1, fg=SUCCESS)
            logbox.see(tk.END)
        root.after(0, _w)
    # Nap hook cho log_arrive (ham CAP MODULE, khong nhin thay root/_log_add
    # cua main() → truoc day moi log kiem tra anh bi mat im lang).
    ROOT[0] = root
    LOG_HOOK[0] = _log_add

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
        """Gui 1 lenh chat: Enter mo chat → COPY lenh vao clipboard → doc lai
        xac minh DUNG → Ctrl+V → Enter gui (toi da 3 lan copy→verify→dan).

        Clipboard NAY SACH mat khau: login da chuyen sang go tung phim (khong
        copy user/pass) → client MU khong con gia tri cache de 'mieu' Ctrl+V.
        Moi lenh tu copy lai tu dau, verify clipboard THAT SU mang dung lenh
        truoc khi dan."""
        wh = ACTIVE_HWND[0] or focus_game()
        if not wh or not user32.IsWindow(wh):
            log_add("  lenh: chua co cua so game dang mo — HOAN gui lenh "
                    "(mo game roi thao tac).")
            return False
        if not guard_foreground(wh, "lenh"):
            log_add("  lenh: khong focus duoc cua so game — HOAN gui lenh.")
            return False
        time.sleep(0.10)
        _tap_vk(0x0D); time.sleep(0.30)             # Enter mo khung chat
        if not guard_foreground(wh, "lenh/sau-enter"):
            log_add("  lenh: mat focus khi mo chat — HOAN gui lenh.")
            return False

        def _paste(text):
            for k in range(3):
                _ensure_foreground(wh)
                if not copy_to_clipboard(text):
                    log_add(f"  lenh: copy THAT BAI lan {k+1} (clipboard bi chan)")
                    time.sleep(0.15)
                    continue
                time.sleep(0.05)
                if read_clipboard() != text:        # app khac ghi de → copy lai
                    log_add(f"  lenh: clipboard bi GHI DE lan {k+1} → copy lai")
                    time.sleep(0.15)
                    continue
                if not guard_foreground(wh, "lenh/truoc-dan"):
                    time.sleep(0.15)
                    continue
                paste_clipboard()
                return True
            return False

        if not _paste(cmd):
            log_add(f"  lenh: clipboard kh xac minh duoc 3 lan — KHONG gui {cmd!r}.")
            return False
        time.sleep(0.15)
        if guard_foreground(wh, "lenh/Enter-gui"):
            _tap_vk(0x0D); time.sleep(0.15)         # Enter gui
        else:
            log_add("  lenh: mat focus luc Enter — lenh co the chua duoc gui.")
        return True

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
            "/addagi auto 32000",
            "/addstr auto 32000",
            "/addene auto 32000",
            "/addvit auto 32000",
            "/addcmd auto 32000",
        ]

    RESET_ACTIVE = [False]

    def set_reset_active(active):
        """Nut Reset da bo — chi log trang thai (train tu reset khi Lv >= max)."""
        log_add(f"  Reset {'dang chay' if active else 'ket thuc'}.")

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
        """Chay NGAY (Train goi khi nhan vat dat Lv 400). Tra True neu chain
        thanh cong (khong bi dung) — de ghi vao lich su reset."""
        if RESET_ACTIVE[0]:
            return False
        RESET_ACTIVE[0] = True
        RESET_STOP[0] = False
        set_reset_active(True)
        try:
            return _run_reset_chain()
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

    def a_pos():
        """Toa do nhan vat cua cua so dang ACTIVE."""
        pm = get_pm_for(ACTIVE_HWND[0]) if ACTIVE_HWND[0] else None
        return rd_pos(pm) if pm else (None, None)

    def a_map():
        """World ID map cua cua so dang ACTIVE."""
        pm = get_pm_for(ACTIVE_HWND[0]) if ACTIVE_HWND[0] else None
        return rd_map(pm) if pm else None

    def pos_stable(timeout=2.0, tol=0.5):
        """Doc rd_pos cua cua so ACTIVE toi khi 2 lan lien tiep gan nhu khong
        doi (memory da cap nhat sau warp/click). Tra (x, y) hoac (None, None)."""
        last = None
        t0 = time.time()
        while time.time() - t0 < timeout:
            x, y = a_pos()
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
        bx, by = a_pos()   # vi tri TRUOC warp de phat hien dich chuyen
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
                    mid = a_map()
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
                    click_at(ACX[0], ACY[0], right=False, hwnd=GHWND)
                x, y = pos_stable()
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
        """Di toi spot: warp -> tim duong -> di. Neu sau 60s chua toi -> warp
        lai va bat dau lai tu dau."""
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
        MOUSE_BLOCK[0] = True   # App toan quyen chuot: chan click vat ly cua user
        try:
            while running[0] and not STOP_REQUESTED[0]:
                arrived = _goto_once(m, tok, tx, ty, click_interval, mov_ahead,
                                     _from_train)
                if arrived or STOP_REQUESTED[0] or not running[0]:
                    return
                log_add("  Chua toi dich (60s / stuck >5 / 30s) -> /move lai tu dau.")
                set_status("Move lại từ đầu...")
        finally:
            running[0] = False
            MOUSE_BLOCK[0] = False   # tra chuot cho nguoi dung

    def _goto_once(m, tok, tx, ty, click_interval, mov_ahead, from_train=False):
        """1 lan di: warp + A* + di chuyen. Tra True neu DEN NOI, False neu
        qua 60s / stuck >5 lan / 30s chua toi diem (goto se warp lai).
        from_train=True: KHONG kiem tra Helper khi DEN NOI — run_visit se
        lam theo thu tu chuan (tat Giam tai -> Home -> bat Giam tai)."""
        # Dam bao game o foreground truoc khi click (gui phim/warp can focus).
        focus_game()
        time.sleep(0.1)
        # TRUOC /move: neu NUT GIAM TAI CON HIEN tren man hinh -> tat truoc
        # (send_ctrl_f_off tu kiem tra: icon mat san thi khong nhan).
        # CHUA THOAT duoc → KHONG warp, KHONG di tiep: tra False de vong
        # ngoài goto() nghi 3s roi thu lai tu dau.
        if not send_ctrl_f_off():
            log_add("  Chua thoat duoc Giam tai → chua the /move, thu lai.")
            time.sleep(3.0)
            return False
        # Buoc 1: luon warp ve map goc cua spot (/move <tok>), ke ca khi dang
        # o dung map do (de ve toa do goc truoc khi tinh duong). Khong kiem tra
        # cung/khac map.
        if not do_warp(m, tok):
            # Khong co token /move -> dung lai.
            set_status(f"Map {m} khong co lenh /move; dung lai.")
            log_add("  (da dung: khong co token /move)")
            return True   # khong the warp -> dung vong lap, bao loi
        set_status("Click 400,300 de cap nhat toa do...")
        # Click vao tam nhan vat (400,300) de EP game ghi lai toa do memory
        # (offset chi refresh khi co thao tac), roi doc toi khi ONH DINH.
        click_at(ACX[0], ACY[0], right=False, hwnd=GHWND)
        x0, y0 = pos_stable()
        if x0 is None:
            set_status("Mat ket noi game. Admin + game mo."); return True
        log_add(f"  Vi tri sau warp/click: ({x0:.0f},{y0:.0f})")
        # Tinh tile start/goal truoc de giu nguyen walkable (khong bi margin loai)
        s0 = mu_path.coord_to_tile(x0, y0)
        g0 = mu_path.coord_to_tile(tx, ty)
        try:
            walk, is_ext = mu_path.load_grid(m, keep_points=[s0, g0])
        except Exception as e:
            set_status(f"Loi load map {m}: {e}")
            log_err(f"[goto] Loi load map {m}: {e}")
            return True
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
                return True
            walk = walk0  # su dung grid goc de di (khong dam bao cach tuong)
        # chuyen waypoint tile -> toa do world (tam tile)
        wps = [mu_path.tile_to_coord(*p) for p in path]
        n_wp = len(wps)

        wp_idx = [0]

        # --- Tham so thuat toan ---
        AHEAD = 5.0        # MOI click chi aim toi da 5 unit tu nhan vat (chong click nham)
        CLICK_INTERVAL = click_interval   # Thoi gian giua 2 lan click (s) - tu UI
        MOV_AHEAD = mov_ahead             # Khoang cach di duoc moi click lai (unit) - tu UI
        MIN_GAP = 0.10
        REACH_WP = 2.5     # den gan waypoint nay thi chuyen waypoint ke tiep
        MIN_AIM = 1.0      # neu aim cach nhan vat < 1 unit -> bo qua click
        POLL = 0.03
        STUCK_T = 3.0      # 3s khong doi toa do = stuck -> giu chuot phai 1s
        STUCK_MAX = 5      # stuck tong >5 lan -> nghi 3s, warp lai tu dau
        WP_TIMEOUT = 30.0  # 30s chua toi diem ke tiep -> nghi 3s, warp lai
        GO_TIMEOUT = 60.0  # 60s tu lenh /move chua toi dich -> warp lai
        t_move = time.time()
        wp_deadline = [time.time()]  # moc 30s cho waypoint hien tai
        stuck_total = [0]            # tong so lan stuck cua lan di nay
        last_move_t = t_move
        last_pos = (x0, y0)
        stuck_stage = [0]  # 0=binh thuong, 1/2=da giu phai, 3=replan
        last_click_pos = (x0, y0)
        last_click_t = -10.0
        step_no = [0]
        last_rect_t = -10.0
        # Bien local, cap nhat moi khi user di chuyen/resize cua so game.
        _L, _T, _W, _H = ARECT[0]
        _cx, _cy = ACX[0], ACY[0]

        def right_hold_1s():
            """Giu nut chuot PHAI 1s tai tam nhan vat (lenh 'dung tan cong'
            cua MU) roi tha ra."""
            user32.SetCursorPos(int(_cx), int(_cy))
            time.sleep(0.02)
            user32.mouse_event(0x0008, 0, 0, 0, 0)   # RIGHTDOWN
            time.sleep(1.0)
            user32.mouse_event(0x0010, 0, 0, 0, 0)   # RIGHTUP

        def replan_here(x, y):
            """Tinh lai duong A* tu vi tri hien tai ve dich."""
            nonlocal walk, n_wp
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
                wp_deadline[0] = time.time()   # duong moi -> reset dong ho 30s
                log_add(f"  Duong moi: {n_wp} diem")
                return True
            log_add("  Khong tim duoc duong moi; tiep tuc di theo duong cu.")
            return False

        reset_stop()  # xoa co STOP tu lan chay truoc
        try:
            while running[0] and not STOP_REQUESTED[0]:
                if check_stop_key():
                    STOP_REQUESTED[0] = True
                    break
                x, y = a_pos()
                if x is None:
                    set_status("Mat ket noi game."); break
                root.after(0, lambda v=(x, y): set_pos_text(v[0], v[1]))
                now = time.time()
                # --- 60s tu /move chua toi dich -> thoat, goto se warp lai ---
                if now - t_move > GO_TIMEOUT:
                    log_add(f"  >{GO_TIMEOUT:.0f}s chua toi dich -> warp lai.")
                    return False
                # Refresh rect cua so game moi 0.4s (neu user di chuyen/resize).
                if now - last_rect_t > 0.4:
                    last_rect_t = now
                    rect2 = find_window_hwnd(ACTIVE_HWND[0])
                    if rect2:
                        (nL, nT, nW, nH), _ = rect2
                        if (nL, nT, nW, nH) != (_L, _T, _W, _H):
                            _L, _T, _W, _H = nL, nT, nW, nH
                            _cx, _cy = nL + ANCHOR_X, nT + ANCHOR_Y
                            log_add(f"  Window da doi: {_W}x{_H} tai ({_L},{_T})")

                # --- Theo doi STUCK: 3s khong doi toa do -> giu phai 1s;
                #     6s -> giu phai lan 2; 9s -> tinh lai duong. Tong stuck
                #     >5 lan -> nghi 3s roi warp lai tu dau. ---
                if math.hypot(x - last_pos[0], y - last_pos[1]) > 0.1:
                    last_move_t = now
                    last_pos = (x, y)
                    if stuck_stage[0]:
                        stuck_stage[0] = 0
                        log_add("  Da thoat stuck, tiep tuc di.")
                if now - last_move_t >= STUCK_T * (stuck_stage[0] + 1):
                    stuck_stage[0] += 1
                    stuck_total[0] += 1
                    if stuck_total[0] > STUCK_MAX:
                        log_add(f"  Stuck tong {stuck_total[0]} lan > {STUCK_MAX} "
                                "-> nghi 3s, /move lai tu dau.")
                        set_status("Stuck nhiều → nghỉ 3s, move lại...")
                        time.sleep(3.0)
                        return False
                    if stuck_stage[0] <= 2:
                        log_add(f"  Stuck {STUCK_T*stuck_stage[0]:.0f}s: giu chuot phai 1s.")
                        set_status("Stuck → giữ chuột phải 1s...")
                        right_hold_1s()
                        last_move_t = time.time()   # tinh lai dong ho 3s
                    else:
                        log_add(f"  Stuck {STUCK_T*3:.0f}s: tinh lai duong tu ({x:.0f},{y:.0f}).")
                        set_status("Stuck → tính lại đường đi...")
                        replan_here(x, y)
                        stuck_stage[0] = 0
                        last_move_t = time.time()

                # --- Chuyen sang waypoint ke tiep neu da den gan ---
                advanced = False
                while (wp_idx[0] < len(wps) - 1 and
                       math.hypot(wps[wp_idx[0]][0] - x, wps[wp_idx[0]][1] - y) < REACH_WP):
                    wp_idx[0] += 1
                    advanced = True
                if advanced:
                    wp_deadline[0] = now   # reset dong ho 30s cho waypoint moi

                # --- 30s chua toi diem ke tiep -> nghi 3s, /move lai tu dau ---
                if now - wp_deadline[0] > WP_TIMEOUT:
                    log_add(f"  >{WP_TIMEOUT:.0f}s chua toi diem {wp_idx[0]+1}/{n_wp} "
                            "-> nghi 3s, /move lai tu dau.")
                    set_status("30s chưa tới điểm → nghỉ 3s, move lại...")
                    time.sleep(3.0)
                    return False

                tx_seg, ty_seg = wps[wp_idx[0]]
                dist_goal = math.hypot(tx - x, ty - y)
                if dist_goal < ARRIVE:
                    log_add(f"  DEN NOI ({x:.1f},{y:.1f})", done=True)
                    set_status(f"DEN NOI ({x:.1f},{y:.1f})")
                    # Toi dung toa do: Home 1 lan (kiem tra icon Helper) —
                    # CH khi di THU CONG. Tu Train chain (from_train): bo qua
                    # o day, de run_visit thu Home theo dung thu tu
                    # (tat Giam tai -> Home -> bat Giam tai), tranh Home bi
                    # kiem tra 2 lan lien tiep.
                    if not from_train:
                        try:
                            send_home_verified()
                            log_add("  Den noi: da gui Home (da kiem tra icon)")
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
                # Nhan PgUp -> dung va tra quyen dieu khien chuot
                running[0] = False
                set_status("DA DUNG (PgUp) - da tra quyen chuot.")
                log_add("  Stopped by PgUp: da ngung chiem chuot.")
            elif running[0]:
                set_status("Da dung.")
        except Exception as e:
            set_status(f"Loi: {e}")
        return True   # ket thuc binh thuong (den noi / dung / loi) -> goto dung vong

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
        x0, y0 = a_pos()
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

    show_tab("ctrl")       # mo dau o tab Dieu khien
    install_mouse_hook()   # chan chuot vat ly khi MOUSE_BLOCK (App dang dung)
    root.mainloop()


if __name__ == "__main__":
    main()

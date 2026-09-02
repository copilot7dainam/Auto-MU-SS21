"""
MU Coord Monitor - UNG DUNG DUY NHAT, chay QUYEN ADMIN.
  - Tu dong phat hien chi cac cua so game (process main.exe).
  - Hien thi tung cua so mot dong: PID, tieu de, X, Y, Z.
  - Cap nhat tieu de khi no thay doi (vi du: sau khi dang nhap thanh cong).
  - Cap nhat toa do lien tuc.

Vi sao chay Admin: process Admin (High IL) doc duoc tieu de moi cua so (UIPI
chi chan IL thap doc IL cao, khong chan nguoc lai) va mo duoc handle game de
ReadProcessMemory. Chay binh thuong se khong doc duoc memory.

Chay: (PowerShell chuot phai -> Run as administrator)  python mu_gui.py
"""
import time
import struct
import ctypes
import ctypes.wintypes as wt
import tkinter as tk
from tkinter import ttk
import pymem
import pymem.process

PROCESS_NAME = "main.exe"
X_OFFSET = 0xB40AF60
Y_OFFSET = 0xB40AF64
Z_OFFSET = 0xB40AF68
REFRESH_GAMES = 1.5     # quet lai danh sach cua so + tieu de (giay)
READ_EVERY     = 0.25    # cap nhat toa do (giay)

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
adv = ctypes.windll.advapi32

user32.EnumWindows.restype = wt.BOOL
user32.GetWindowTextW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
user32.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]

class LUID(ctypes.Structure):
    _fields_ = [("LowPart", ctypes.c_ulong), ("HighPart", ctypes.c_long)]


adv.OpenProcessToken.argtypes = [wt.HANDLE, wt.DWORD, ctypes.POINTER(wt.HANDLE)]
adv.OpenProcessToken.restype = wt.BOOL
adv.LookupPrivilegeValueW.argtypes = [wt.LPCWSTR, wt.LPCWSTR, ctypes.POINTER(LUID)]
adv.LookupPrivilegeValueW.restype = wt.BOOL
adv.AdjustTokenPrivileges.argtypes = [wt.HANDLE, wt.BOOL, ctypes.c_void_p, wt.DWORD, ctypes.c_void_p, ctypes.c_void_p]
adv.AdjustTokenPrivileges.restype = wt.BOOL


def enable_debug_privilege():
    h = wt.HANDLE()
    if not adv.OpenProcessToken(kernel32.GetCurrentProcess(), 0x20 | 0x8, ctypes.byref(h)):
        return
    luid = LUID()
    if not adv.LookupPrivilegeValueW(None, "SeDebugPrivilege", ctypes.byref(luid)):
        return
    class LAA(ctypes.Structure):
        _fields_ = [("Luid", LUID), ("Attributes", ctypes.c_ulong)]
    class TP(ctypes.Structure):
        _fields_ = [("PrivilegeCount", ctypes.c_ulong), ("Privileges", LAA * 1)]
    tp = TP()
    tp.PrivilegeCount = 1
    tp.Privileges[0].Luid = luid
    tp.Privileges[0].Attributes = 0x2
    adv.AdjustTokenPrivileges(h, False, ctypes.byref(tp), 0, None, None)


def enum_window_titles():
    """Tra ve {pid: tieu de dai nhat} cho moi cua so hien thi."""
    result = {}

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def cb(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        pid = wt.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        buf = ctypes.create_unicode_buffer(512)
        user32.GetWindowTextW(hwnd, buf, 512)
        t = buf.value.strip()
        if pid.value:
            cur = result.get(pid.value, "")
            if len(t) > len(cur):
                result[pid.value] = t
        return True

    user32.EnumWindows(cb, 0)
    return result


def list_games():
    """Chi lay cac cua so hien thi thuoc process main.exe.
    Tieu de cua so (EnumWindows) lam tham quyen: khi cua so dong, PID khong con
    trong tap cua so visible nua -> loai bo ngay (khong bi treo vi handle minh giu)."""
    wins = enum_window_titles()          # pid -> title (chi cua so visible)
    visible_pids = set(wins.keys())
    out, seen = [], set()
    try:
        procs = pymem.process.list_processes()
    except Exception:
        procs = []
    for p in procs:
        try:
            name = p.szExeFile.decode("utf-8", "ignore")
        except Exception:
            name = str(p.szExeFile)
        if name.lower() != PROCESS_NAME.lower():
            continue
        pid = p.th32ProcessID
        if pid in seen:
            continue
        if pid not in visible_pids:
            continue  # khong co cua so visible -> bo qua (da dong hoac an)
        seen.add(pid)
        out.append((pid, wins.get(pid) or f"(PID {pid})"))
    return out


def rd_float(pm, off):
    try:
        return struct.unpack("<f", pm.read_bytes(0x400000 + off, 4))[0]
    except Exception:
        return None


class Monitor(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("MU Coord Monitor")
        self.geometry("700x380")
        self.resizable(True, True)

        cols = ("pid", "window", "X", "Y", "Z")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=16)
        self.tree.heading("pid", text="PID")
        self.tree.heading("window", text="Cua so (ten nhan vat)")
        self.tree.heading("X", text="X")
        self.tree.heading("Y", text="Y")
        self.tree.heading("Z", text="Z")
        self.tree.column("pid", width=70)
        self.tree.column("window", width=360)
        self.tree.column("X", width=80, anchor="e")
        self.tree.column("Y", width=80, anchor="e")
        self.tree.column("Z", width=80, anchor="e")
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)

        self.status = tk.Label(self, text="Dang tim cua so MU...", anchor="w")
        self.status.pack(fill="x", padx=8, pady=(0, 8))

        self.pm_by_pid = {}        # pid -> Pymem
        self.title_by_pid = {}     # pid -> tieu de da hien thi
        self.tree_items = set()
        self.last_scan = 0
        self.after(100, self.tick)

    def get_pm(self, pid):
        pm = self.pm_by_pid.get(pid)
        if pm is None:
            try:
                pm = pymem.Pymem(pid)
                self.pm_by_pid[pid] = pm
            except Exception:
                return None
        return pm

    def tick(self):
        now = time.time()
        if now - self.last_scan >= REFRESH_GAMES:
            self.last_scan = now
            self.refresh_games()

        for pid, pm in list(self.pm_by_pid.items()):
            r = None
            try:
                x = rd_float(pm, X_OFFSET)
                y = rd_float(pm, Y_OFFSET)
                z = rd_float(pm, Z_OFFSET)
                if None not in (x, y, z):
                    r = (x, y, z)
            except Exception:
                r = None
            iid = str(pid)
            if iid in self.tree_items and self.tree.exists(iid):
                if r is not None:
                    self.tree.set(iid, "X", f"{r[0]:.1f}")
                    self.tree.set(iid, "Y", f"{r[1]:.1f}")
                    self.tree.set(iid, "Z", f"{r[2]:.1f}")
                else:
                    for c in ("X", "Y", "Z"):
                        self.tree.set(iid, c, "?")

        self.after(int(READ_EVERY * 1000), self.tick)

    def refresh_games(self):
        games = list_games()
        current = {pid for pid, _ in games}
        for pid, title in games:
            iid = str(pid)
            if iid not in self.tree_items:
                self.tree.insert("", "end", iid=iid,
                                 values=(pid, title, "?", "?", "?"))
                self.tree_items.add(iid)
                self.get_pm(pid)
            else:
                # Cap nhat tieu de neu no thay doi (vd: sau khi dang nhap)
                if self.title_by_pid.get(pid) != title:
                    self.tree.set(iid, "window", title)
                    self.title_by_pid[pid] = title
        for iid in list(self.tree_items):
            pid = int(iid)
            if pid not in current:
                if self.tree.exists(iid):
                    self.tree.delete(iid)
                self.tree_items.discard(iid)
                self.title_by_pid.pop(pid, None)
                pm = self.pm_by_pid.pop(pid, None)
                if pm:
                    try:
                        pm.close_process()
                    except Exception:
                        pass

        n = len(games)
        if n:
            self.status.config(text=f"Dang theo doi {n} cua so MU")
        else:
            self.status.config(text="Chua co cua so MU nao. Mo game roi cho 1.5s...")

    def destroy(self):
        for pm in self.pm_by_pid.values():
            try:
                pm.close_process()
            except Exception:
                pass
        super().destroy()


if __name__ == "__main__":
    enable_debug_privilege()
    Monitor().mainloop()

"""
DEBUG: kiem tra click co toi duoc game khong.
Chay: python mu_debug_click.py  (Admin)
- Doc current pos
- Focus cua so game, click TRAI vao GIUA man hinh (vi tri nhan vat)
- Doi 2s, doc lai pos
- In ket qua de biet click co hieu luc
"""
import time, ctypes, ctypes.wintypes as wt, struct
import pymem, pymem.process

PROCESS_NAME = "main.exe"
CUR_X = 0xB80AF60
CUR_Y = 0xB80AF64
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

def find_window():
    targets = set()
    for p in pymem.process.list_processes():
        try:
            n = p.szExeFile.decode("utf-8", "ignore")
        except Exception:
            continue
        if n.lower() == PROCESS_NAME.lower():
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
        raise RuntimeError("Khong tim thay main.exe")
    return list(found.values())[0]

def rd_pos(pm):
    try:
        x = struct.unpack("<f", pm.read_bytes(CUR_X, 4))[0]
        y = struct.unpack("<f", pm.read_bytes(CUR_Y, 4))[0]
        return x, y
    except Exception:
        return None, None

def main():
    pm = pymem.Pymem(PROCESS_NAME)
    L, T, W, H = find_window()
    cx, cy = L + W // 2, T + H // 2
    print(f"Cua so: left={L} top={T} size={W}x{H}")
    print(f"Giua man hinh (vi tri nv): ({cx},{cy})")

    x0, y0 = rd_pos(pm)
    print(f"POS TRUOC: ({x0:.1f},{y0:.1f})")

    # Focus cua so game
    procs = pymem.process.list_processes()
    target_pids = {p.th32ProcessID for p in procs
                   if p.szExeFile.decode('utf-8', 'ignore').lower() == PROCESS_NAME.lower()}
    GW = None
    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def finder(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        pid = wt.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value in target_pids:
            global GW
            GW = hwnd
        return True
    user32.EnumWindows(finder, 0)
    if GW:
        user32.SetForegroundWindow(GW)
        print("Da SetForegroundWindow")
    time.sleep(0.5)

    # Click trai tai 1 diem LECH (cach giua 150px ben phai) de test nhan vat co di
    click_x, click_y = cx + 150, cy
    user32.SetCursorPos(click_x, click_y)
    time.sleep(0.1)
    user32.mouse_event(0x0002, 0, 0, 0, 0)  # LEFT DOWN
    time.sleep(0.05)
    user32.mouse_event(0x0004, 0, 0, 0, 0)  # LEFT UP
    print(f"Da click TRAI tai ({click_x},{click_y}) [cach giua 150px ben phai]")

    time.sleep(2.5)
    x1, y1 = rd_pos(pm)
    print(f"POS SAU:   ({x1:.1f},{y1:.1f})")
    if x0 is not None and x1 is not None:
        d = ((x1-x0)**2 + (y1-y0)**2)**0.5
        print(f"=> Thay doi: {d:.2f}  {'NHAN VAT DI DUOC' if d > 0.5 else 'KHONG DI (click vo hieu luc)'}")
    input("Enter de thoat...")

if __name__ == "__main__":
    main()

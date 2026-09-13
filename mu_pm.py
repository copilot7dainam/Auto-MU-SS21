"""
mu_pm — input qua PostMessage (PM) cho cua so game MU, chay NEN (background):
khong can foreground, khong chem chuot/ban phim that cua nguoi dung.

Da chung minh tren client MU song (implementation tham chieu:
C:\\Users\\Admin\\HookProbe\\hook_probe_gui.py — constants + lParam conventions
duoc sao y nguyen ven, da field-tested):
  * CHUOT PM (WM_MOUSEMOVE / WM_LBUTTONDOWN / ...) HOAT DONG khi cua so game
    nam o SAU — client doc vi tri tu lParam cua message.
  * GO O CHAT qua PM HOAT DONG — o chat cua MU doc message queue
    (WM_KEYDOWN + WM_CHAR), nen pm_tap / pm_text / pm_chat dung duoc o day.
  * PHIM NONG (hotkey) qua PM KHONG HOAT DONG: game poll truc tiep
    DirectInput / GetAsyncKeyState, bo hoan toan WM_KEYDOWN. Dayla gioi han
    cua PM — muon bam skill qua PM thi phai dung cach khac (hook/inject).

GIU CHUOT (kieu "stuck recovery" — giu phai chuot de mo lai o khi bi am):
lam duoc bang PM: pm_move(hwnd, x, y) → PostMessage WM_RBUTTONDOWN →
time.sleep(...) → PostMessage WM_RBUTTONUP (khong gui BUTTONUP trong luc giu).
pm_hold_key / pm_release_key la GIU PHIM (keydown/keyup tach), khong phai chuot.

Toan bo toa do cua cac ham pm_* la toa do CLIENT — dung screen_to_client(hwnd,
sx, sy) de doi tu toa do man hinh (vi du cursor_pos()) sang client.

Ham cong cong: cho qua cua so da chet / hwnd None — PostMessage duoc try/except,
tra ve False/None, KHONG BAO BAO gioi (never raise). Chi ctypes + stdlib.
"""
import time
import ctypes
import ctypes.wintypes as wt

u32 = ctypes.windll.user32

# --- kieu 64-bit phai khai bao ro: PostMessageW thieu argtypes → LPARAM la
# c_long signed 32b, gia tri 0xC0470001 bi OverflowError; VkKeyScanW thieu
# restype c_short → bit rac phia cao lam sai phep kiem tra -1.
u32.PostMessageW.restype = wt.BOOL
u32.PostMessageW.argtypes = [wt.HWND, ctypes.c_uint, wt.WPARAM, wt.LPARAM]
u32.MapVirtualKeyW.restype = wt.UINT
u32.MapVirtualKeyW.argtypes = [wt.UINT, wt.UINT]
u32.VkKeyScanW.restype = ctypes.c_short
u32.VkKeyScanW.argtypes = [wt.WCHAR]
u32.IsWindow.restype = wt.BOOL
u32.IsWindow.argtypes = [wt.HWND]
u32.ScreenToClient.restype = wt.BOOL
u32.ScreenToClient.argtypes = [wt.HWND, ctypes.POINTER(wt.POINT)]
u32.GetCursorPos.restype = wt.BOOL
u32.GetCursorPos.argtypes = [ctypes.POINTER(wt.POINT)]

WM_KEYDOWN, WM_KEYUP, WM_CHAR = 0x0100, 0x0101, 0x0102
WM_MOUSEMOVE, WM_LBUTTONDOWN, WM_LBUTTONUP = 0x0200, 0x0201, 0x0202
WM_RBUTTONDOWN, WM_RBUTTONUP = 0x0204, 0x0205
MK_LBUTTON, MK_RBUTTON = 0x0001, 0x0002

# Danh sach phim co bit 24 (0x01000000) — nguyen ven tu ban field-tested
# (PgUp/PgDn/End/Home/4 mui ten/Ins/Del + 0x0F; them RCtrl/RAlt). Enter (13)
# CO Y giu khong ext: duong chat da duoc do dung voi lp_down=1|(0x1C<<16).
_EXT = (0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x2D, 0x2E, 0x0F,
        0xA3, 0xA5)


def _lp(x, y):
    """lParam toa do: loword=X, hiword=Y (client coords, co the am — cat 16b)."""
    return (y << 16) | (x & 0xFFFF)


def is_alive(hwnd):
    """True neu hwnd van con song (IsWindow). hwnd = None/0/chet → False."""
    try:
        return bool(u32.IsWindow(hwnd))
    except Exception:
        return False


def key_params(vk):
    """(lParam_down, lParam_up) voi scan code THAT cua vk (MapVirtualKeyW).
    Bit 24 = extended flag (KHONG phai bit 16 — do la scan). Up = them
    previous(30)+transition(31). Vi du Home(36): (0x01470001, 0xC1470001)."""
    sc = u32.MapVirtualKeyW(vk, 0)
    ext = 0x01000000 if vk in _EXT else 0
    lp_down = 1 | (sc << 16) | ext
    return lp_down, lp_down | 0x40000000 | 0xC0000000


def _post(hwnd, msg, wp, lp):
    """PostMessageW chong crash: hwnd chet/None → False, khong bao raise."""
    try:
        if not is_alive(hwnd):
            return False
        return bool(u32.PostMessageW(hwnd, msg, wp, lp))
    except Exception:
        return False


def pm_move(hwnd, cx, cy):
    """Di chuot (WM_MOUSEMOVE, wparam=0) toi toa do CLIENT (cx, cy)."""
    return _post(hwnd, WM_MOUSEMOVE, 0, _lp(cx, cy))


def pm_keydown(hwnd, vk):
    return _post(hwnd, WM_KEYDOWN, vk, key_params(vk)[0])


def pm_keyup(hwnd, vk):
    return _post(hwnd, WM_KEYUP, vk, key_params(vk)[1])


# GIU PHIM (khac giu CHUOT — giu chuot: pm_move + WM_*BUTTONDOWN khong UP).
pm_hold_key = pm_keydown
pm_release_key = pm_keyup


def pm_tap(hwnd, vk, hold=0.05):
    """Bam + tha 1 phim (WM_KEYDOWN → sleep(hold) → WM_KEYUP)."""
    if not pm_keydown(hwnd, vk):
        return False
    time.sleep(hold)
    return pm_keyup(hwnd, vk)


def pm_click(hwnd, cx, cy, right=False):
    """Click trai/phai tai CLIENT (cx, cy): MOVE(mk) → 50ms → DOWN(mk) →
    60ms → UP(0) — thu tu/wparam nguyen ven ban field-tested.
   (hwnd None/chet → False.)"""
    down = WM_RBUTTONDOWN if right else WM_LBUTTONDOWN
    up = WM_RBUTTONUP if right else WM_LBUTTONUP
    mk = MK_RBUTTON if right else MK_LBUTTON
    lp = _lp(cx, cy)
    if not _post(hwnd, WM_MOUSEMOVE, mk, lp):   # MOVE mang mk nhu ban goc
        return False
    time.sleep(0.05)
    if not _post(hwnd, down, mk, lp):
        return False
    time.sleep(0.06)
    return _post(hwnd, up, 0, lp)


def pm_mouse_hold(hwnd, cx, cy, seconds, right=True):
    """Giu nut chuot (phai) `seconds` tai CLIENT (cx,cy) roi tha — bang
    PM: MOVE → DOWN → sleep → UP. Dung cho stuck-recovery cua goto()
    khong can cua so foreground."""
    mk = MK_RBUTTON if right else MK_LBUTTON
    lp = _lp(cx, cy)
    if not _post(hwnd, WM_MOUSEMOVE, mk, lp):
        return False
    time.sleep(0.03)
    if not _post(hwnd, WM_RBUTTONDOWN if right else WM_LBUTTONDOWN, mk, lp):
        return False
    time.sleep(seconds)
    return _post(hwnd, WM_RBUTTONUP if right else WM_LBUTTONUP, 0, lp)


def pm_text(hwnd, text, gap=0.02):
    """Go chuoi: ky tu thuong (VkKeyScanW state==0) → pm_tap VK; con lai
    (hoa, dau /, ky tu dac biet) → WM_CHAR truc tiep. O chat MU doc ca 2."""
    ok = True
    for ch in text:
        try:
            vk = u32.VkKeyScanW(ch)
        except Exception:
            vk = -1
        state = (vk >> 8) & 7 if vk != -1 else 7
        if vk != -1 and state == 0:
            ok = pm_tap(hwnd, vk & 0xFF, hold=gap) and ok
        else:
            ok = _post(hwnd, WM_CHAR, ord(ch), _lp(0, 0) | 1) and ok
        time.sleep(gap)
    return ok


def pm_chat(hwnd, cmd, open_delay=0.35, send_delay=0.15):
    """Gui 1 lenh chat background: Enter (mo o) → pm_text(cmd) → Enter (gui).
    KHONG co Esc — MU tu dong dong o sau Enter. False neu cua chet giu chung."""
    if not is_alive(hwnd):
        return False
    if not pm_tap(hwnd, 13):
        return False
    time.sleep(open_delay)
    ok = pm_text(hwnd, cmd)
    time.sleep(send_delay)
    return ok and pm_tap(hwnd, 13)


def screen_to_client(hwnd, sx, sy):
    """Toa do MAN HINH → CLIENT cua hwnd. None neu hwnd chet/convert fail."""
    try:
        pt = wt.POINT(int(sx), int(sy))
        return (pt.x, pt.y) if u32.ScreenToClient(hwnd, ctypes.byref(pt)) else None
    except Exception:
        return None


def cursor_pos():
    """(x, y) toa do man hinh cua chuot THAT (GetCursorPos), None khi fail."""
    try:
        p = wt.POINT()
        return (p.x, p.y) if u32.GetCursorPos(ctypes.byref(p)) else None
    except Exception:
        return None


if __name__ == "__main__":
    # 1. Home: scan that 0x47 + ext bit24 + transition bits — tinh tu cong
    #    thuc, doi chieu gia tri hang so da do duoc tren client.
    sc = u32.MapVirtualKeyW(36, 0)
    assert sc == 0x47, hex(sc)
    lp1 = 1 | (sc << 16) | 0x01000000
    assert key_params(36) == (lp1, lp1 | 0x40000000 | 0xC0000000)
    assert key_params(36) == (0x1470001, 0xC1470001 | 0x40000000)
    # 2. A khong phai phim mo rong
    assert key_params(65)[0] & 0x01000000 == 0
    # 3-5. cua so chet/None: tra None/False, khong crash, khong post that
    assert screen_to_client(0, 0, 0) is None
    assert pm_click(0, 10, 10) is False
    assert pm_chat(0, "/test") is False
    assert is_alive(0) is False
    print("mu_pm selftest OK")

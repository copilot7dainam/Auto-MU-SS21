# -*- coding: utf-8 -*-
"""Đọc trạng thái toggle của game (Helper / GiamTai / MobileMod) trực tiếp từ
bộ nhớ tiến trình game qua pymem, theo PID — không cần screenshot, chạy được
khi cửa sổ game bị minimize hoặc bị che.

Cờ là các byte-flag tìm bằng differential heap scan (mu_goto_flags.json,
mỗi cờ nhiều địa chỉ). Đọc majority-vote trên toàn bộ địa chỉ của cờ:
nhiều nửa khác 0 => ON; đúng nửa hoặc ít hơn => OFF (an toàn, thà báo OFF);
đọc không được hết => None. Lớp này cố tình "ngu": giá trị rác sau khi game
restart không phát hiện ở đây — cha tự watchdog bằng none_rate().
"""
import os
import sys
import json
import threading
from collections import deque

try:
    import pymem
except ImportError:  # pymem là dependency của project; thiếu thì báo rõ
    pymem = None

APP_DIR = (os.path.dirname(os.path.abspath(sys.argv[0]))
           if getattr(sys, "frozen", False)
           else os.path.dirname(os.path.abspath(__file__)))
FLAGS_FILE = os.path.join(APP_DIR, "mu_goto_flags.json")


def load_flags(path=FLAGS_FILE):
    """{ten_cờ: [int_addr, ...]} — {} nếu thiếu file / hỏng."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        return {k: [int(x, 16) for x in v] for k, v in raw.items()}
    except Exception:
        return {}


def vote(vals):
    """vals: list int|None (None = đọc không được). Trả True/False theo
    majority nghiêm (đúng nửa => False), None nếu không đọc được byte nào."""
    ok = [v for v in vals if v is not None]
    if not ok:
        return None
    return sum(1 for v in ok if v) * 2 > len(ok)


class FlagReader:
    """Đọc cờ game theo PID, lazy-connect, thread-safe (dùng từ train thread).
    Cờ: Helper / GiamTai / MobileMod (xem mu_goto_flags.json)."""

    def __init__(self, pid):
        self.pid = pid
        self.flags = load_flags()
        self._pm = None
        self._lock = threading.Lock()
        self._hist = deque(maxlen=50)  # True/False/None của các lần đọc gần nhất

    def _connect(self):
        if pymem is None:
            return None
        try:
            self._pm = pymem.Pymem(self.pid)
        except Exception:
            self._pm = None
        return self._pm

    def _byte(self, addr):
        try:
            return self._pm.read_bytes(addr, 1)[0]
        except Exception:
            return None

    def read(self, name):
        """bool | None — majority vote trên mọi địa chỉ của cờ `name`.
        Ten khop mem: hoa thuong + bo khoang/tr_gach (user co the luu
        'Giam Tai' hoac 'GiamTai')."""
        addrs = self.flags.get(name)
        if not addrs:
            want = name.lower().replace(" ", "").replace("_", "")
            for k, v in self.flags.items():
                if k.lower().replace(" ", "").replace("_", "") == want:
                    addrs = v
                    break
        if not addrs:
            return None
        with self._lock:
            if self._pm is None and self._connect() is None:
                self._hist.append(None)
                return None
            vals = [self._byte(a) for a in addrs]
            if any(v is None for v in vals):
                # handle có thể stale -> mở lại đúng 1 lần rồi đọc tiếp
                self._close_locked()
                if self._connect() is not None:
                    vals = [self._byte(a) for a in addrs]
            if all(v is None for v in vals):
                self._close_locked()  # pid chết / quyền truy cập mất
        res = vote(vals)
        self._hist.append(res)
        return res

    def none_rate(self):
        """Tỉ lệ lần đọc trả None trong ~50 lần gần nhất (watchdog cho cha)."""
        if not self._hist:
            return 0.0
        return sum(1 for r in self._hist if r is None) / len(self._hist)

    def _close_locked(self):
        if self._pm is not None:
            try:
                self._pm.close_process()
            except Exception:
                pass
            self._pm = None

    def close(self):
        with self._lock:
            self._close_locked()


if __name__ == "__main__":
    assert vote([1, 1, 0]) is True
    assert vote([1, 0]) is False
    assert vote([1, 1, 0, 0]) is False   # đúng nửa => OFF cho an toàn
    assert vote([None, None]) is None
    assert vote([]) is None
    assert vote([1]) is True

    fl = load_flags()
    assert set(fl) >= {"Helper", "GiamTai", "MobileMod"}, fl.keys()
    assert all(isinstance(v, list) and v and all(isinstance(x, int) for x in v)
               for v in fl.values())
    assert len(fl["Helper"]) == 7 and len(fl["GiamTai"]) == 20

    if pymem is None:
        print("pymem KHONG co — bo qua selftest doc memory")
    else:
        r = FlagReader(999999)           # pid khong ton tai, khong duoc crash
        assert r.read("Helper") is None
        assert r.none_rate() >= 0.0
        r.close()
    print("mu_state selftest OK -", len(fl), "flags:", ", ".join(sorted(fl)))

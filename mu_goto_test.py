"""
MU GOTO - TEST TAT CA MAP

Mo phong: voi moi map co san (att_samples/_grid_cache/WorldN.json), chay 100 lan:
  - chon toa do hien tai & toa do den NGAU NHIEN trong map (0..255)
  - tinh duong di A* giong mu_goto.py (snap walkable + safe margin, thu lai grid goc neu bi kem)
  - thanh cong neu tim duoc duong (>=2 diem), nguoc lai la that bai.

Cua so hien thi tien trinh: map hien tai, lan thu /100, % tong the, so lan thanh cong/that bai.
Chay: python mu_goto_test.py
"""
import os, sys, json, random, threading, tkinter as tk
from tkinter import ttk, scrolledtext

import mu_path

HERE = os.path.dirname(os.path.abspath(__file__))
ATT = os.path.join(HERE, "att_samples")
CACHE = os.path.join(ATT, "_grid_cache")
N = 256
RUNS_PER_MAP = 100


def list_maps():
    out = []
    if not os.path.isdir(CACHE):
        return out
    for f in sorted(os.listdir(CACHE)):
        if f.startswith("World") and f.endswith(".json"):
            try:
                out.append(int(f[5:-5]))
            except ValueError:
                pass
    return out


def run_all(app, maps):
    total = len(maps) * RUNS_PER_MAP
    done = 0
    for mi, m in enumerate(maps):
        if app.stop:
            break
        # preload grid 1 lan/map (safe margin 1 + raw margin 0) de test nhanh
        try:
            safe, _ = mu_path.load_grid(m)            # margin 1
            raw, _ = mu_path.load_grid(m, safe_margin=0)
        except Exception as e:
            app.log(f"[Map {m}] LOI LOAD: {e}")
            app.set_map(m, mi + 1, len(maps))
            # dem ca 100 lan nay la that bai vi khong load duoc
            for _ in range(RUNS_PER_MAP):
                if app.stop:
                    break
                app.record(False)
                done += 1
                app.set_progress(done, total)
            continue

        ok = 0
        fail = 0
        for r in range(RUNS_PER_MAP):
            if app.stop:
                break
            # toa do ngau nhien trong map
            x0, y0 = random.randint(0, N - 1), random.randint(0, N - 1)
            tx, ty = random.randint(0, N - 1), random.randint(0, N - 1)
            s0 = mu_path.coord_to_tile(x0, y0)
            g0 = mu_path.coord_to_tile(tx, ty)
            # chon grid + snap giong mu_goto.calculate
            sx, sy = mu_path.nearest_walkable(safe, *s0) or s0
            gx, gy = mu_path.nearest_walkable(safe, *g0) or g0
            path = mu_path.astar(safe, (sx, sy), (gx, gy))
            if not path or len(path) < 2:
                # thu lai tren grid goc (bo margin) nhu mu_goto
                sx0, sy0 = mu_path.nearest_walkable(raw, *s0) or s0
                gx0, gy0 = mu_path.nearest_walkable(raw, *g0) or g0
                path = mu_path.astar(raw, (sx0, sy0), (gx0, gy0))
            success = bool(path and len(path) >= 2)
            if success:
                ok += 1
            else:
                fail += 1
            done += 1
            app.record(success)
            app.set_progress(done, total)
        app.log(f"[Map {m}] xong: thanh cong {ok}, that bai {fail}")
        app.set_map(m, mi + 1, len(maps))
    app.finish()


class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("MU GOTO - Test tat ca map")
        self.root.geometry("480x360")
        self.stop = False

        f = ttk.Frame(self.root, padding=10)
        f.pack(fill="both", expand=True)

        self.lbl_map = ttk.Label(f, text="Dang chuan bi...")
        self.lbl_map.pack(anchor="w", pady=(0, 4))
        self.lbl_run = ttk.Label(f, text="")
        self.lbl_run.pack(anchor="w", pady=(0, 4))
        self.lbl_total = ttk.Label(f, text="Tien trinh: 0%")
        self.lbl_total.pack(anchor="w", pady=(0, 4))

        self.bar = ttk.Progressbar(f, mode="determinate", maximum=100)
        self.bar.pack(fill="x", pady=(0, 8))

        self.lbl_ok = ttk.Label(f, text="Thanh cong: 0")
        self.lbl_ok.pack(anchor="w")
        self.lbl_fail = ttk.Label(f, text="That bai: 0")
        self.lbl_fail.pack(anchor="w", pady=(0, 8))

        self.log = scrolledtext.ScrolledText(f, height=10, state="disabled")
        self.log.pack(fill="both", expand=True)

        bf = ttk.Frame(f)
        bf.pack(fill="x", pady=(6, 0))
        ttk.Button(bf, text="Dung", command=self.do_stop).pack(side="right")

        self.ok = 0
        self.fail = 0
        self._lock = threading.Lock()

    def do_stop(self):
        self.stop = True

    def record(self, success):
        with self._lock:
            if success:
                self.ok += 1
            else:
                self.fail += 1
            self.root.after(0, self._refresh_counts)

    def _refresh_counts(self):
        self.lbl_ok.config(text=f"Thanh cong: {self.ok}")
        self.lbl_fail.config(text=f"That bai: {self.fail}")

    def set_map(self, m, i, total_maps):
        self.root.after(0, lambda: self.lbl_map.config(
            text=f"Map {m}  ({i}/{total_maps})"))

    def set_run(self, r):
        self.root.after(0, lambda: self.lbl_run.config(
            text=f"Lan thu: {r}/{RUNS_PER_MAP}"))

    def set_progress(self, done, total):
        pct = int(done / total * 100) if total else 0
        self.root.after(0, lambda: self._set_bar(done, total, pct))

    def _set_bar(self, done, total, pct):
        self.bar["value"] = pct
        self.lbl_total.config(text=f"Tien trinh: {pct}%  ({done}/{total})")

    def log(self, msg):
        self.root.after(0, lambda: self._log(msg))

    def _log(self, msg):
        self.log.config(state="normal")
        self.log.insert("end", msg + "\n")
        self.log.see("end")
        self.log.config(state="disabled")

    def finish(self):
        self.root.after(0, lambda: self._finish())

    def _finish(self):
        self.lbl_map.config(text="HOAN THANH" if not self.stop else "DUNG BOI NGUOI DUNG")
        self.log("=== KET THUC ===")
        self.log(f"Tong thanh cong: {self.ok}")
        self.log(f"Tong that bai: {self.fail}")

    def start(self, maps):
        t = threading.Thread(target=run_all, args=(self, maps), daemon=True)
        t.start()
        self.root.mainloop()


if __name__ == "__main__":
    maps = list_maps()
    if not maps:
        print("Khong tim thay grid nao trong", CACHE)
        sys.exit(1)
    print(f"Tim thay {len(maps)} map. Bat dau test ({RUNS_PER_MAP} lan/map)...")
    app = App()
    # cap nhat label lan thu qua set_progress neu can; chay
    app.start(maps)

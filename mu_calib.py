"""
MU CALIB - Quet goc 360 do de fit ma tran world = A * screen_offset.

Co che (chi chinh xac theo yeu cau):
  BUOC 1: Ban TU CLICK vao TRUNG TAM nhan vat -> PUNG GOC (pixel).
  BUOC 2: Quet 360 do, moi goc (vd 24 huong, cach 15 do) tu pung goc, TANG DAN
          px (10,20,30...) den khi nhan vat BAT DAU DI (worldDelta >= 1 unit).
          Ghi lai (screen_offset_px, worldDelta) tai diem do.
  BUOC 3: Tu cac cap do duoc, fit ma tran A (2x2) bang least-squares:
            world = A * screen_offset.
  BUOC 4: Luu A va nghich dao de mu_goto.py tinh diem click.

Tai sao quet goc: MU isometric nen 1 huong man hinh co the ra world cheo. Quet
tron se cho du vector co so de fit A chinh xac (khong bi trung nhau nhu 8 huong).

Yeu cau: ADMIN, WINDOWED, nhan vat GIUA noi THOANG.
Su dung: python mu_calib.py [--rays 24] [--maxpx 250] [--gap 1.0]
"""
import sys, os, time, math, json, argparse
import tkinter as tk
import pymem
import mu_goto

CALIB_FILE = "mu_goto_calib.json"
POLL = 0.05
STOP_GAP = 0.5
MIN_MOVE = 0.03
MOVE_EPS = 1.0       # world delta >= 1.0 moi tinh la "da di den muc do"


def wait_for_user_click():
    result = {}
    def on_click(ev):
        result["pos"] = (ev.x_root, ev.y_root)
        root.destroy()
    root = tk.Tk()
    root.attributes("-fullscreen", True)
    root.attributes("-alpha", 0.25)
    root.configure(bg="black")
    root.bind("<Button-1>", on_click)
    tk.Label(root, text="CLICK CHUOT TRAI VAO TRUNG TAM NHAN VAT",
             fg="yellow", bg="black", font=("Arial", 28)).place(
        relx=0.5, rely=0.1, anchor="center")
    print(">> BUOC 1: CLICK chuot trai vao TRUNG TAM nhan vat (overlay da mo)...")
    root.mainloop()
    pos = result.get("pos")
    print(f"   Da bat duoc pung goc tai pixel man hinh: {pos}")
    return pos


def wait_arrival(pm, prev0, t_click, timeout):
    prev = prev0
    started = False
    t_start = t_click
    last_move = t_click
    while time.time() - t_click < timeout:
        time.sleep(POLL)
        nx, ny = mu_goto.rd_pos(pm)
        if nx is None:
            continue
        d = math.hypot(nx - prev[0], ny - prev[1])
        if d > MIN_MOVE:
            if not started:
                started = True
                t_start = time.time(); last_move = t_start
            else:
                last_move = time.time()
        prev = (nx, ny)
        if started and time.time() - last_move > STOP_GAP:
            break
    reaction = (t_start - t_click) if started else 0.0
    travel = (last_move - t_start) if started else 0.0
    return prev, travel, reaction, started


def probe(pm, cx, cy, L, T, W, H, angle, off, right, timeout):
    rad = math.radians(angle)
    ux, uy = math.cos(rad), math.sin(rad)
    click_x = max(L + 5, min(L + W - 5, int(round(cx + ux * off))))
    click_y = max(T + 5, min(T + H - 5, int(round(cy + uy * off))))
    x0, y0 = mu_goto.rd_pos(pm)
    if x0 is None:
        return None
    mu_goto.click_at(click_x, click_y, right=right)
    final, travel, react, started = wait_arrival(pm, (x0, y0), time.time(), timeout)
    if not started:
        return (0.0, 0.0, False)
    wdx = final[0] - x0
    wdy = final[1] - y0
    return (wdx, wdy, math.hypot(wdx, wdy) >= MOVE_EPS)


def solve_A(pairs):
    # pairs: list[(sx, sy, wx, wy)]  tim A sao cho [wx,wy] = A*[sx,sy]
    Sxx = Syy = Sxy = Sxw0 = Syw0 = Sxw1 = Syw1 = 0.0
    for sx, sy, wx, wy in pairs:
        Sxx += sx*sx; Syy += sy*sy; Sxy += sx*sy
        Sxw0 += sx*wx; Syw0 += sy*wx
        Sxw1 += sx*wy; Syw1 += sy*wy
    det = Sxx*Syy - Sxy*Sxy
    if abs(det) < 1e-9:
        return None
    a00 = (Syy*Sxw0 - Sxy*Syw0)/det
    a01 = (Sxx*Syw0 - Sxy*Sxw0)/det
    a10 = (Syy*Sxw1 - Sxy*Syw1)/det
    a11 = (Sxx*Syw1 - Sxy*Sxw1)/det
    return [[a00, a01], [a10, a11]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rays", type=int, default=24, help="so huong quet (360/rays do)")
    ap.add_argument("--maxpx", type=int, default=250)
    ap.add_argument("--step", type=int, default=10)
    ap.add_argument("--gap", type=float, default=1.0)
    ap.add_argument("--wait", type=float, default=2.0, help="cho sau khi nhan vat di")
    ap.add_argument("--timeout", type=float, default=12.0)
    ap.add_argument("--button", choices=["left", "right"], default="left")
    args = ap.parse_args()

    mu_goto.enable_debug()
    pm = pymem.Pymem(mu_goto.PROCESS_NAME)
    L, T, W, H = mu_goto.find_window()
    print(f"[info] Cua so: {W}x{H} tai ({L},{T})")
    cx, cy = wait_for_user_click()
    right = (args.button == "right")
    print(f"[info] Quet {args.rays} huong, buoc {args.step}px den {args.maxpx}px")
    print(f"[info] Moi huong bat dau TU GOC; sau khi nhan vat di cho {args.wait}s "
          f"roi chuyen huong khac (khong keo ve goc).\n")

    pairs = []
    for r in range(args.rays):
        ang = r * 360.0 / args.rays
        got = None
        for off in range(args.step, args.maxpx + 1, args.step):
            res = probe(pm, cx, cy, L, T, W, H, ang, off, right, args.timeout)
            if res is None:
                print(f"  [goc {ang:5.1f}] MAT KET NOI"); got = None; break
            wdx, wdy, moved = res
            if moved:
                got = (off * math.cos(math.radians(ang)),
                       off * math.sin(math.radians(ang)), wdx, wdy)
                print(f"  [goc {ang:5.1f}] +{off:3d}px -> world({wdx:+.2f},{wdy:+.2f})")
                # cho 2s de nhan vat dung yen, roi BAT DAU LAI TU GOC o huong khac
                time.sleep(args.wait)
                break
        if got is None:
            print(f"  [goc {ang:5.1f}] khong di duoc trong {args.maxpx}px (tuong?)")
        time.sleep(args.gap)

    if len(pairs) < 4:
        print(f"\nChi co {len(pairs)} mau. Dung o noi thoang hon.")
        return

    A = solve_A(pairs)
    if A is None:
        print("\nKhong giai duoc ma tran."); return
    a00, a01 = A[0]; a10, a11 = A[1]
    det = a00*a11 - a01*a10
    if abs(det) < 1e-9:
        print("\nMa tran suy bien."); return
    inv = [[a11/det, -a01/det], [-a10/det, a00/det]]

    resid = 0.0
    for sx, sy, wx, wy in pairs:
        ex = a00*sx + a01*sy
        ey = a10*sx + a11*sy
        resid += math.hypot(ex - wx, ey - wy)
    resid /= len(pairs)

    json.dump({
        "world_per_px": [a00, a01, a10, a11],
        "px_per_world": [inv[0][0], inv[0][1], inv[1][0], inv[1][1]],
        "resid": resid, "rays": args.rays,
    }, open(CALIB_FILE, "w"))

    print(f"\n[Sai so fit TB = {resid:.2f} px (nho <15 la sach)]")
    print(f"\n=== MA TRAN A: world = A * screen_offset ===")
    print(f"  worldX = {a00:+.4f}*sx + {a01:+.4f}*sy")
    print(f"  worldY = {a10:+.4f}*sx + {a11:+.4f}*sy")
    print(f"Inverse (de tinh click):")
    print(f"  dx_px = {inv[0][0]:+.4f}*wx + {inv[0][1]:+.4f}*wy")
    print(f"  dy_px = {inv[1][0]:+.4f}*wx + {inv[1][1]:+.4f}*wy")
    print(f"Da luu {CALIB_FILE}")
    ex, ey = 10.0, 0.0
    print(f"Vi du di world(+{ex:.0f},+{ey:.0f}): dx={inv[0][0]*ex+inv[0][1]*ey:+.1f}px "
          f"dy={inv[1][0]*ex+inv[1][1]*ey:+.1f}px")


if __name__ == "__main__":
    main()
